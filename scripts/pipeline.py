# -*- coding: utf-8 -*-
"""Fetch RSS/Atom feeds, cluster headlines into stories, and rank them.

Standard library only. The goal is a defensible draft: one item per outlet per
story, at least two outlets where possible, and an explicit record of failures.
"""
from __future__ import annotations

import concurrent.futures
import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from typing import Iterable

from .sources import FEEDS, GOOGLE_QUERIES, LEAN_BUCKET, Feed, lean_of_outlet

UA = "Mozilla/5.0 (compatible; DailyBriefBot/1.0; +https://github.com)"
WINDOW = timedelta(hours=48)
SIM_THRESHOLD = 0.37

STOP = set("""a an and are as at be been being but by can could did do does for from had has have
he her here him his how i if in into is it its just like may me might more most much my new no nor
not now of on one only or other our out over own said same she should so some such than that the their
them then there these they this those through to too under up us very was we were what when where which
while who why will with would you your""".split())

CATEGORY_PREFIX = {"政治": "P", "经济": "E", "F1": "F", "AI": "A"}

# Feed-level category filters. Tech and business feeds carry general news too;
# these terms keep the four sections on-topic without an LLM.
CATEGORY_TERMS = {
    "AI": ["artificial intelligence", "openai", "anthropic", "nvidia", "chatgpt", "gemini",
           "claude", "machine learning", "neural", "robot", "semiconductor", "chip",
           "data center", "datacenter", "llm", "ai model", "ai "],
    "F1": ["formula 1", "f1", "grand prix", "gp", "antonelli", "verstappen", "hamilton",
           "leclerc", "norris", "russell", "mercedes", "ferrari", "red bull", "mclaren",
           "pirelli", "las vegas", "qatar", "abu dhabi", "driver"],
    "经济": ["stock", "market", "economy", "inflation", "fed", "rate", "oil", "trade",
           "tariff", "gdp", "jobs", "earnings", "bond", "dollar", "yuan", "bank", "price"],
}


def _allowed(category: str, title: str, summary: str) -> bool:
    terms = CATEGORY_TERMS.get(category)
    if not terms:
        return True
    text = f"{title} {summary}".lower()
    for term in terms:
        if term == "ai":
            if re.search(r"\bai\b", text):
                return True
        elif term in text:
            return True
    return False


@dataclass
class Item:
    outlet: str
    lean: str
    category: str
    title: str
    summary: str
    url: str
    published: datetime | None = None
    via_google: bool = False
    source_key: str = ""


@dataclass
class Cluster:
    items: list[Item] = field(default_factory=list)

    @property
    def category(self) -> str:
        return self.items[0].category

    @property
    def outlets(self) -> set[str]:
        return {i.outlet for i in self.items}

    @property
    def buckets(self) -> set[str]:
        return {LEAN_BUCKET.get(i.lean, "other") for i in self.items}

    @property
    def newest(self) -> datetime | None:
        dates = [i.published for i in self.items if i.published]
        return max(dates) if dates else None

    def score(self) -> float:
        outlets = len(self.outlets)
        buckets = len(self.buckets - {"other"})
        center = 1 if "center" in self.buckets else 0
        recency = 0.0
        if self.newest:
            hours = max(0.0, (datetime.now(timezone.utc) - self.newest).total_seconds() / 3600)
            recency = max(0.0, 8.0 - hours / 6.0)
        return 10.0 * min(outlets, 4) + 6.0 * buckets + 4.0 * center + recency

    @property
    def title(self) -> str:
        # Prefer a title from a center outlet; otherwise the first.
        for item in self.items:
            if LEAN_BUCKET.get(item.lean) == "center":
                return item.title
        return self.items[0].title


def _clean_text(value: str, limit: int = 520) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _parse_date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _child_text(node: ET.Element, names: Iterable[str]) -> str:
    wanted = set(names)
    for child in node:
        if _local(child.tag) in wanted:
            if _local(child.tag) == "link" and child.attrib.get("href"):
                return child.attrib["href"]
            return "".join(child.itertext())
    return ""


def parse_feed(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8", errors="ignore")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return _parse_regex(text)
    items = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        title = _clean_text(_child_text(node, ("title",)), 240)
        link = _child_text(node, ("link", "guid", "id")).strip()
        summary = _clean_text(_child_text(node, ("description", "summary", "content")), 520)
        date_raw = _child_text(node, ("pubdate", "published", "updated", "date"))
        source = _clean_text(_child_text(node, ("source",)), 80)
        if title and link:
            items.append({"title": title, "link": link, "summary": summary,
                          "published": _parse_date(date_raw), "source": source})
    return items


def _parse_regex(text: str) -> list[dict]:
    items = []
    for block in re.findall(r"<item\b[^>]*>(.*?)</item>", text, re.S | re.I):
        def tag(name: str) -> str:
            m = re.search(rf"<{name}\b[^>]*>(.*?)</{name}>", block, re.S | re.I)
            if not m:
                return ""
            return re.sub(r"^<!\[CDATA\[(.*?)\]\]>$", r"\1", m.group(1).strip(), flags=re.S)
        title = _clean_text(tag("title"), 240)
        link = tag("link").strip()
        summary = _clean_text(tag("description"), 520)
        date_raw = tag("pubDate")
        source = _clean_text(tag("source"), 80)
        if title and link:
            items.append({"title": title, "link": link, "summary": summary,
                          "published": _parse_date(date_raw), "source": source})
    return items


def fetch_url(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(2_000_000)


def _strip_source_suffix(title: str, source: str) -> str:
    title = title.strip()
    if source and title.lower().endswith(" - " + source.lower()):
        return title[: -(len(source) + 3)].strip()
    return title


def _fetch_feed(feed: Feed) -> tuple[Feed, list[Item], str | None]:
    try:
        raw = fetch_url(feed.url)
        parsed = parse_feed(raw)
        now = datetime.now(timezone.utc)
        items = []
        for p in parsed[:60]:
            published = p.get("published")
            if published and now - published > WINDOW:
                continue
            title = _strip_source_suffix(p["title"], feed.outlet)
            if len(title) < 12 or not _allowed(feed.category, title, p.get("summary", "")):
                continue
            items.append(Item(feed.outlet, feed.lean, feed.category, title,
                              p.get("summary", ""), p["link"], published,
                              False, feed.key))
        return feed, items, None
    except Exception as exc:
        return feed, [], f"{type(exc).__name__}: {str(exc)[:140]}"


def _fetch_google(category: str, query: str) -> tuple[str, list[Item], str | None]:
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": f"when:2d {query}", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    try:
        raw = fetch_url(url, timeout=14)
        parsed = parse_feed(raw)
        now = datetime.now(timezone.utc)
        items = []
        for p in parsed[:20]:
            published = p.get("published")
            if published and now - published > WINDOW:
                continue
            # Google News exposes the publisher per item in <source>.
            source = p.get("source", "") or ""
            title = _strip_source_suffix(p["title"], source)
            if len(title) < 12 or not _allowed(category, title, p.get("summary", "")):
                continue
            items.append(Item(source or "Google News", lean_of_outlet(source), category,
                              title, p.get("summary", ""), p["link"], published, True, f"g:{query}"))
        return query, items, None
    except Exception as exc:
        return query, [], f"{type(exc).__name__}: {str(exc)[:140]}"


def fetch_direct(feeds: list[Feed], workers: int = 12) -> tuple[list[Item], list[dict], dict]:
    items: list[Item] = []
    errors: list[dict] = []
    ok = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_fetch_feed, f) for f in feeds]
        for fut in concurrent.futures.as_completed(futures):
            feed, got, err = fut.result()
            if err:
                errors.append({"source": feed.outlet, "feed": feed.key, "error": err})
                print(f"[feed:fail] {feed.key}: {err}", flush=True)
            else:
                ok += 1
                items.extend(got)
                print(f"[feed:ok] {feed.key}: {len(got)}", flush=True)
    return items, errors, {"feeds_ok": ok, "feeds_failed": len(errors)}


def fetch_google(categories: list[str]) -> tuple[list[Item], list[dict]]:
    items, errors = [], []
    jobs = [(cat, q) for cat in categories for q in GOOGLE_QUERIES.get(cat, [])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_fetch_google, cat, q) for cat, q in jobs]
        for fut in concurrent.futures.as_completed(futures):
            query, got, err = fut.result()
            if err:
                errors.append({"source": "Google News", "feed": query, "error": err})
                print(f"[google:fail] {query}: {err}", flush=True)
            else:
                items.extend(got)
                print(f"[google:ok] {query}: {len(got)}", flush=True)
    return items, errors


def _norm_tokens(text: str) -> tuple[set[str], str]:
    text = html.unescape(text or "").lower()
    text = re.sub(r"['’]s\b", "s", text)
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff ]+", " ", text)
    tokens = {w for w in text.split() if len(w) > 2 and w not in STOP}
    return tokens, " ".join(sorted(tokens))


GENERIC_ENTITIES = {
    "The", "This", "That", "With", "From", "After", "Before", "What", "Why", "How",
    "New", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December", "President", "Prime", "Minister",
    "Government", "Officials", "Report", "World", "Week", "Year", "Today", "Live",
}


LEADING_WORDS = {"The", "This", "That", "How", "Why", "What", "When", "Where", "Who",
                 "After", "Before", "With", "From", "New", "Live", "Exclusive", "Analysis",
                 "Opinion", "Watch", "Explained"}


def _entities(text: str) -> set[str]:
    words = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text or "")
    out = set()
    for w in words:
        if w in LEADING_WORDS or w in GENERIC_ENTITIES:
            continue
        low = w.lower()
        if low in ("gp", "grand", "prix", "grandprix"):
            out.add("grandprix")
        else:
            out.add(low)
    return out


def _entity_jaccard(a: str, b: str) -> float:
    ea, eb = _entities(a), _entities(b)
    if not ea or not eb:
        return 0.0
    return len(ea & eb) / len(ea | eb)


def similarity(a: Item, b: Item) -> float:
    ta, sa = _norm_tokens(a.title)
    tb, sb = _norm_tokens(b.title)
    shared = ta & tb
    if len(shared) < 2:
        return 0.0
    jac = len(shared) / max(1, len(ta | tb))
    seq = SequenceMatcher(None, sa, sb).ratio()
    ea, eb = _entities(a.title), _entities(b.title)
    ent = len(ea & eb) / max(1, min(len(ea), len(eb))) if (ea and eb) else 0.0
    return 0.45 * jac + 0.35 * seq + 0.20 * ent


def cluster(items: list[Item]) -> list[Cluster]:
    # Deduplicate by title before clustering; keep the earliest/cleanest copy.
    seen = set()
    unique = []
    for item in sorted(items, key=lambda x: (x.published or datetime.min.replace(tzinfo=timezone.utc)), reverse=True):
        key = re.sub(r"[^a-z0-9]+", "", item.title.lower())[:90]
        if key and key in seen:
            continue
        seen.add(key)
        unique.append(item)

    clusters: list[Cluster] = []
    for item in unique:
        best, best_score = None, 0.0
        for c in clusters:
            if item.outlet in c.outlets:
                continue
            s = max((similarity(item, other) for other in c.items), default=0.0)
            if s > best_score:
                best, best_score = c, s
        if best is not None and best_score >= SIM_THRESHOLD and len(best.items) < 5:
            best.items.append(item)
        else:
            clusters.append(Cluster([item]))
    return merge_related(clusters)


def merge_related(clusters: list[Cluster]) -> list[Cluster]:
    """Second pass: merge clusters that are clearly the same event.

    Headlines about one event are often written from different angles ("Musk
    petitions Nvidia" vs "Asian governments react"). Title similarity alone
    misses them; a strong proper-noun overlap catches them without merging
    unrelated stories that merely share a politician's name.
    """
    merged = True
    while merged:
        merged = False
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                a, b = clusters[i], clusters[j]
                if a.category != b.category:
                    continue
                if len(a.outlets | b.outlets) > 6:
                    continue
                if _entity_jaccard(a.title, b.title) >= 0.5:
                    seen = {x.outlet for x in a.items}
                    a.items.extend(x for x in b.items if x.outlet not in seen)
                    clusters.pop(j)
                    merged = True
                    break
            if merged:
                break
    return clusters


def _pick_sources(c: Cluster, limit: int = 4) -> list[Item]:
    # One per outlet, one per lean bucket first, then fill by recency.
    ordered = sorted(c.items, key=lambda x: (x.published or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    picked, buckets, outlets = [], set(), set()
    for item in ordered:
        if item.outlet in outlets:
            continue
        b = LEAN_BUCKET.get(item.lean, "other")
        if b not in buckets:
            picked.append(item)
            buckets.add(b)
            outlets.add(item.outlet)
        if len(picked) >= limit:
            return picked
    for item in ordered:
        if item.outlet in outlets:
            continue
        picked.append(item)
        outlets.add(item.outlet)
        if len(picked) >= limit:
            break
    return picked


def select_stories(clusters: list[Cluster], per_category: int = 4) -> list[dict]:
    stories = []
    for cat, prefix in CATEGORY_PREFIX.items():
        pool = sorted([c for c in clusters if c.category == cat], key=lambda c: c.score(), reverse=True)
        chosen: list[Cluster] = []
        for require_multi in (True, False):
            for c in pool:
                if len(chosen) >= per_category:
                    break
                if c in chosen:
                    continue
                if require_multi and len(c.outlets) < 2:
                    continue
                # Avoid near-duplicate story lines.
                if any(SequenceMatcher(None, c.title.lower(), o.title.lower()).ratio() > 0.72 for o in chosen):
                    continue
                if any(_entity_jaccard(c.title, o.title) >= 0.5 for o in chosen):
                    continue
                chosen.append(c)
        for idx, c in enumerate(chosen[:per_category], 1):
            sources = _pick_sources(c)
            representative = next((s for s in sources if s.title == c.title), sources[0])
            stories.append({
                "id": f"{prefix}{idx}",
                "category": cat,
                "title": c.title,
                "facts": [representative.summary or c.title],
                "sources": [{"name": s.outlet, "lean": s.lean, "angle": "", "url": s.url} for s in sources],
                "framing": f"{len(c.outlets)} 家来源 · " + " / ".join(sorted({s.lean for s in sources})),
                "items": [{"outlet": s.outlet, "lean": s.lean, "title": s.title,
                           "summary": s.summary, "url": s.url} for s in sources],
                "_score": round(c.score(), 2),
            })
    return stories


def build_dataset(date_str: str, use_google: bool = True, per_category: int = 4,
                  offline_items: list[Item] | None = None) -> dict:
    started = datetime.now(timezone.utc)
    items: list[Item] = []
    errors: list[dict] = []
    stats: dict = {}

    if offline_items is not None:
        items = offline_items
        stats = {"feeds_ok": 0, "feeds_failed": 0, "offline": True}
    else:
        direct, errors, stats = fetch_direct(FEEDS)
        items.extend(direct)
        # Google News fallback: only for categories with thin direct coverage.
        thin = [cat for cat in CATEGORY_PREFIX
                if len([i for i in items if i.category == cat]) < 12]
        if use_google and thin:
            google_items, google_errors = fetch_google(thin)
            items.extend(google_items)
            errors.extend(google_errors)

    clusters = cluster(items)
    stories = select_stories(clusters, per_category=per_category)
    stats["items"] = len(items)
    stats["clusters"] = len(clusters)
    stats["stories"] = len(stories)
    stats["feeds_total"] = len(FEEDS)
    stats["errors"] = len(errors)
    stats["elapsed_sec"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)

    warnings = []
    for cat in CATEGORY_PREFIX:
        got = [s for s in stories if s["category"] == cat]
        if len(got) < per_category:
            warnings.append(f"{cat} 仅聚合到 {len(got)} 条（目标 {per_category} 条）")
        thin_sources = [s["id"] for s in got if len(s["sources"]) < 2]
        if thin_sources:
            warnings.append(f"{cat} 单一来源条目：{', '.join(thin_sources)}")

    return {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stories": stories,
        "stats": stats,
        "errors": errors[:30],
        "warnings": warnings,
        "llm_used": False,
        "llm_provider": "",
    }

# -*- coding: utf-8 -*-
"""Last-resort machine translation for headlines and facts.

Uses the public Google Translate endpoint (no key). It is intentionally a
fallback: an LLM rewrite is better, but a translated page beats an English one
when no model key is configured. If the endpoint is unavailable, the original
text is returned unchanged.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://translate.googleapis.com/translate_a/single"
UA = "Mozilla/5.0 (compatible; DailyBriefBot/1.0)"
MAX_CHARS = 3800


def _has_cjk(text: str) -> bool:
    if not text:
        return False
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    return cjk / max(1, len(text)) > 0.2


def _request(text: str) -> str:
    params = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": text})
    req = urllib.request.Request(ENDPOINT + "?" + params, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read().decode("utf-8", "ignore")
    data = json.loads(raw)
    segments = data[0] or []
    return "".join(seg[0] for seg in segments if seg and seg[0])


def translate_lines(lines: list[str]) -> list[str]:
    if not lines:
        return []
    cleaned = [(" ".join((x or "").split())) for x in lines]
    out: list[str] = []
    chunk: list[str] = []
    size = 0
    for line in cleaned:
        if chunk and size + len(line) + 1 > MAX_CHARS:
            out.extend(_translate_chunk(chunk))
            chunk, size = [], 0
        chunk.append(line)
        size += len(line) + 1
    if chunk:
        out.extend(_translate_chunk(chunk))
    if len(out) != len(lines):
        return lines
    return out


def _translate_chunk(lines: list[str]) -> list[str]:
    text = "\n".join(lines)
    for attempt in range(2):
        try:
            translated = _request(text)
            parts = [p.strip() for p in translated.split("\n")]
            if len(parts) == len(lines):
                return parts
        except Exception:
            pass
        time.sleep(1)
    return lines


def translate_dataset(data: dict) -> dict:
    stories = data.get("stories", [])
    if not stories or all(_has_cjk(s.get("title", "")) for s in stories):
        return data
    try:
        titles = translate_lines([s.get("title", "") for s in stories])
        for story, title in zip(stories, titles):
            if title:
                story["title"] = title

        fact_lines, spans = [], []
        for story in stories:
            facts = story.get("facts", [])
            spans.append(len(facts))
            fact_lines.extend(facts)
        translated_facts = translate_lines(fact_lines)
        pos = 0
        for story, count in zip(stories, spans):
            if count:
                story["facts"] = translated_facts[pos:pos + count]
                pos += count

        angle_refs, angle_lines = [], []
        for story in stories:
            for src in story.get("sources", []):
                if src.get("angle") and not _has_cjk(src["angle"]):
                    angle_refs.append(src)
                    angle_lines.append(src["angle"])
        translated_angles = translate_lines(angle_lines)
        for src, angle in zip(angle_refs, translated_angles):
            if angle:
                src["angle"] = angle

        data["translation_used"] = True
        if not data.get("llm_provider"):
            data["llm_provider"] = "机器翻译"
        data.pop("translation_error", None)
    except Exception as exc:  # noqa: BLE001
        data["translation_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    return data

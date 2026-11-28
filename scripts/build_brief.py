# -*- coding: utf-8 -*-
"""Build one daily briefing.

Usage:
    python scripts/build_brief.py
    python scripts/build_brief.py --date 2026-11-15 --no-llm --no-email
    python scripts/build_brief.py --sample --out docs-sample

Environment:
    GITHUB_TOKEN / DEEPSEEK_API_KEY / LLM_*  optional Chinese rewriting
    MAIL_TO, SMTP_* or RESEND_API_KEY        optional email delivery
    PAGES_URL                                link placed in the email
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import llm, mailer, render, translate  # noqa: E402
from scripts.pipeline import build_dataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", default="", help="YYYY-MM-DD; defaults to today in Asia/Shanghai")
    p.add_argument("--out", default="docs", help="output directory (default: docs)")
    p.add_argument("--no-google", action="store_true", help="skip Google News fallback")
    p.add_argument("--no-llm", action="store_true", help="skip Chinese rewriting")
    p.add_argument("--no-translate", action="store_true", help="skip the machine-translation fallback")
    p.add_argument("--no-email", action="store_true", help="skip email delivery")
    p.add_argument("--email-dry-run", action="store_true", help="write .eml preview instead of sending")
    p.add_argument("--sample", action="store_true", help="use sample/sample.json (offline smoke test)")
    p.add_argument("--dataset", default="", help="render an existing dataset JSON instead of fetching (curated override)")
    p.add_argument("--pages-url", default=os.getenv("PAGES_URL", ""), help="public URL for the email button")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    tz = ZoneInfo("Asia/Shanghai")
    now = datetime.now(tz)
    date_str = args.date or now.strftime("%Y-%m-%d")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"invalid --date: {date_str}", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.dataset:
        dataset_path = Path(args.dataset)
        if not dataset_path.is_absolute():
            dataset_path = ROOT / dataset_path
        if not dataset_path.exists():
            print(f"dataset not found: {dataset_path}", file=sys.stderr)
            return 2
        data = json.loads(dataset_path.read_text(encoding="utf-8"))
        data["date"] = date_str
        data.setdefault("stats", {})["curated"] = True
        print(f"[build] curated dataset: {dataset_path} stories={len(data.get('stories', []))}", flush=True)
    elif args.sample:
        sample_path = ROOT / "sample" / "sample.json"
        data = json.loads(sample_path.read_text(encoding="utf-8"))
        data["date"] = date_str
        data.setdefault("stats", {})["sample"] = True
        print(f"[build] sample mode: {sample_path}", flush=True)
    else:
        print(f"[build] {date_str} fetching feeds...", flush=True)
        data = build_dataset(date_str, use_google=not args.no_google)
        print(f"[build] stories={len(data['stories'])} sources={len(render.all_sources(data))} "
              f"feeds_ok={data['stats'].get('feeds_ok')} failed={data['stats'].get('feeds_failed')}", flush=True)

    data["date"] = date_str
    data["generated_at"] = now.astimezone(timezone.utc).isoformat(timespec="seconds")

    if not args.no_llm and not args.sample and not args.dataset:
        print("[llm] summarizing...", flush=True)
        data = llm.summarize(data)
        if data.get("llm_used"):
            print(f"[llm] ok provider={data.get('llm_provider')}", flush=True)
        else:
            print(f"[llm] fallback: {data.get('llm_error')}", flush=True)

    if not data.get("llm_used") and not args.no_translate and not args.dataset:
        print("[translate] model unavailable; translating headlines/facts...", flush=True)
        data = translate.translate_dataset(data)
        if data.get("translation_used"):
            print("[translate] ok", flush=True)
        else:
            print(f"[translate] skipped/failed: {data.get('translation_error', 'no change')}", flush=True)

    data = render.fallback_fields(data)

    css = (ROOT / "templates" / "style.css").read_text(encoding="utf-8")
    html = render.render_html(data, css)
    md = render.render_markdown(data)
    html_path = out_dir / f"{date_str}.html"
    md_path = out_dir / f"{date_str}.md"
    xlsx_path = out_dir / f"{date_str}.xlsx"
    html_path.write_text(html, encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    render.write_xlsx(data, str(xlsx_path))

    # Latest page + archive + machine-readable data.
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "archive.html").write_text(render.render_archive(str(out_dir), css), encoding="utf-8")
    data_dir = out_dir / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / f"{date_str}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Email (optional). Failure is logged, not fatal: the site is already built.
    email_result = {"status": "skipped", "reason": "--no-email"}
    if not args.no_email:
        to_addr = os.getenv("MAIL_TO", "").strip()
        subject = f"全球要闻简报 · {date_str}"
        email_html = render.render_email_html(data, pages_url=args.pages_url)
        attachment = (f"{date_str}.xlsx", xlsx_path.read_bytes())
        print(f"[email] to={to_addr or '(MAIL_TO empty)'} dry_run={args.email_dry_run}", flush=True)
        email_result = mailer.send_email(
            email_html, subject, to_addr, [attachment],
            dry_run=args.email_dry_run,
            preview_path=str(out_dir / "email-preview.eml") if args.email_dry_run else None,
        )
        print(f"[email] {json.dumps(email_result, ensure_ascii=False)}", flush=True)
    data["email"] = email_result
    (out_dir / "email-status.json").write_text(
        json.dumps(email_result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "date": date_str,
        "html": str(html_path),
        "xlsx": str(xlsx_path),
        "stories": len(data["stories"]),
        "sources": len(render.all_sources(data)),
        "llm": data.get("llm_provider") or "none",
        "email": email_result.get("status"),
        "warnings": data.get("warnings", []),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

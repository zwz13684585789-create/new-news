# -*- coding: utf-8 -*-
"""Resend an already-built briefing by email.

Usage:
    python scripts/send_email.py --date 2026-11-15
    python scripts/send_email.py --date 2026-11-15 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import mailer, render  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--to", default=os.getenv("MAIL_TO", ""))
    p.add_argument("--out", default="docs")
    p.add_argument("--pages-url", default=os.getenv("PAGES_URL", ""))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    data_path = out / "data" / f"{args.date}.json"
    xlsx_path = out / f"{args.date}.xlsx"
    if not data_path.exists() or not xlsx_path.exists():
        print(f"missing build for {args.date} in {out}", file=sys.stderr)
        return 2
    data = json.loads(data_path.read_text(encoding="utf-8"))
    html = render.render_email_html(data, pages_url=args.pages_url)
    result = mailer.send_email(
        html,
        f"全球要闻简报 · {args.date}",
        args.to,
        [(f"{args.date}.xlsx", xlsx_path.read_bytes())],
        dry_run=args.dry_run,
        preview_path=str(out / "email-preview.eml") if args.dry_run else None,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") in ("sent", "dry-run", "skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())

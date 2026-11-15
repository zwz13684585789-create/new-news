# -*- coding: utf-8 -*-
"""Send the briefing by email.

Two providers are supported:
1. Resend HTTP API (recommended; reliable from GitHub Actions).
2. SMTP, including 163.com (smtp.163.com:465, login with an app password).

No credentials are stored in the repository. Configure them as GitHub Actions
secrets; without them the build still publishes to Pages and skips email.
"""
from __future__ import annotations

import base64
import json
import os
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage
from email.utils import formatdate, make_msgid


def email_configured() -> bool:
    if os.getenv("RESEND_API_KEY"):
        return True
    return bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))


def _build_message(html: str, subject: str, to_addr: str,
                   attachments: list[tuple[str, bytes]]) -> EmailMessage:
    smtp_user = os.getenv("SMTP_USER", "")
    from_addr = os.getenv("MAIL_FROM") or smtp_user or "daily-brief@localhost"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="daily-brief.local")
    msg.set_content("这份简报包含 HTML 表格，请使用支持 HTML 的邮件客户端查看。")
    msg.add_alternative(html, subtype="html")
    for filename, payload in attachments:
        msg.add_attachment(
            payload,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if filename.endswith(".xlsx") else "octet-stream",
            filename=filename,
        )
    return msg


def _send_resend(html: str, subject: str, to_addr: str,
                 attachments: list[tuple[str, bytes]]) -> dict:
    api_key = os.environ["RESEND_API_KEY"]
    from_addr = os.getenv("MAIL_FROM", "onboarding@resend.dev")
    body = {
        "from": from_addr,
        "to": [to_addr],
        "subject": subject,
        "html": html,
        "attachments": [
            {"filename": name, "content": base64.b64encode(payload).decode("ascii")}
            for name, payload in attachments
        ],
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", "ignore")
    return {"status": "sent", "provider": "resend", "response": raw[:200]}


def _send_smtp(html: str, subject: str, to_addr: str,
               attachments: list[tuple[str, bytes]]) -> dict:
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    host = os.getenv("SMTP_HOST") or ("smtp.163.com" if user.endswith("@163.com") else "")
    if not host:
        raise RuntimeError("SMTP_HOST is required when SMTP_USER is not a 163.com address")
    port = int(os.getenv("SMTP_PORT") or "465")
    msg = _build_message(html, subject, to_addr, attachments)

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.send_message(msg)
    return {"status": "sent", "provider": "smtp", "host": host, "port": port}


def send_email(html: str, subject: str, to_addr: str,
               attachments: list[tuple[str, bytes]] | None = None,
               dry_run: bool = False, preview_path: str | None = None) -> dict:
    attachments = attachments or []
    if dry_run:
        msg = _build_message(html, subject, to_addr, attachments)
        if preview_path:
            os.makedirs(os.path.dirname(preview_path) or ".", exist_ok=True)
            with open(preview_path, "wb") as fh:
                fh.write(msg.as_bytes())
        return {"status": "dry-run", "provider": "preview", "path": preview_path}

    if not email_configured():
        return {"status": "skipped", "provider": "", "reason": "no RESEND_API_KEY or SMTP_USER/SMTP_PASS"}
    if not to_addr:
        return {"status": "skipped", "provider": "", "reason": "MAIL_TO is empty"}

    last_error = ""
    for attempt in range(2):
        try:
            if os.getenv("RESEND_API_KEY"):
                return _send_resend(html, subject, to_addr, attachments)
            return _send_smtp(html, subject, to_addr, attachments)
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {str(exc)[:240]}"
            if attempt == 0:
                continue
    return {"status": "failed", "provider": "resend" if os.getenv("RESEND_API_KEY") else "smtp",
            "error": last_error}

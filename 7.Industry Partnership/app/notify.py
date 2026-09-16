"""Partner notification email - same dry-run pattern as 5.ULB Dispatch's
email_adapter.py and 6.Track B Innovation's notify.py."""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.config import settings


def _build_email(*, partner_name: str, proposal_title: str, proposal_summary: str, match_type: str, decide_url: str) -> tuple[str, str, str]:
    subject = f"[SAHYOG Industry Partnership] {match_type.title()} opportunity: {proposal_title}"
    text_body = (
        f"A Track B R&D proposal is looking for a {match_type} partner.\n\n"
        f"Title: {proposal_title}\nSummary: {proposal_summary}\n\n"
        f"Accept or decline: {decide_url}\n\n"
        f"This is an automated message from the SAHYOG Industry Partnership pipeline."
    )
    html_body = f"""
    <html><body>
      <p>A Track B R&amp;D proposal is looking for a {match_type} partner.</p>
      <p><b>Title:</b> {proposal_title}</p>
      <p><b>Summary:</b> {proposal_summary}</p>
      <p><a href="{decide_url}"
            style="display:inline-block;padding:10px 16px;background:#1a73e8;color:#fff;
                   text-decoration:none;border-radius:4px;">
            Accept or decline
         </a></p>
      <p style="color:#666;font-size:12px;">This is an automated message from the SAHYOG Industry Partnership pipeline.</p>
    </body></html>
    """
    return subject, text_body, html_body


def send_partner_notification(*, to_email: str, partner_name: str, proposal_title: str, proposal_summary: str, match_type: str, decide_url: str) -> dict[str, Any]:
    subject, text_body, html_body = _build_email(
        partner_name=partner_name, proposal_title=proposal_title, proposal_summary=proposal_summary,
        match_type=match_type, decide_url=decide_url,
    )

    if settings.EMAIL_DRY_RUN:
        return {
            "success": True,
            "dry_run": True,
            "rendered_email": {"to": to_email, "subject": subject, "text_body": text_body, "html_body": html_body},
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_ADDRESS
        msg["To"] = to_email
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_ADDRESS, [to_email], msg.as_string())

        return {"success": True, "dry_run": False, "to": to_email, "subject": subject}
    except Exception as exc:  # noqa: BLE001 - notification failure must never crash the matcher
        return {"success": False, "error": str(exc)}

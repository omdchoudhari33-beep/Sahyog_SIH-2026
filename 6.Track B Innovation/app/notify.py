"""HEI notification email - same dry-run pattern as 5.ULB Dispatch's
email_adapter.py: builds the full email regardless of EMAIL_DRY_RUN, only
the actual smtplib call is skipped in dry-run mode."""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.config import settings


def _build_email(*, hei_name: str, ticket_problem_statement: str, similarity_score: float | None, decide_url: str) -> tuple[str, str, str]:
    subject = f"[SAHYOG Track B] New R&D opportunity for {hei_name}"
    score_line = f"Match confidence: {similarity_score:.0%}\n" if similarity_score is not None else ""
    text_body = (
        f"A civic issue has been matched to your institution as a potential R&D opportunity.\n\n"
        f"Problem: {ticket_problem_statement}\n"
        f"{score_line}\n"
        f"Accept or decline: {decide_url}\n\n"
        f"This is an automated message from the SAHYOG Track B Innovation pipeline."
    )
    html_body = f"""
    <html><body>
      <p>A civic issue has been matched to your institution as a potential R&amp;D opportunity.</p>
      <p><b>Problem:</b> {ticket_problem_statement}</p>
      {f'<p><b>Match confidence:</b> {similarity_score:.0%}</p>' if similarity_score is not None else ''}
      <p><a href="{decide_url}"
            style="display:inline-block;padding:10px 16px;background:#1a73e8;color:#fff;
                   text-decoration:none;border-radius:4px;">
            Accept or decline
         </a></p>
      <p style="color:#666;font-size:12px;">This is an automated message from the SAHYOG Track B Innovation pipeline.</p>
    </body></html>
    """
    return subject, text_body, html_body


def send_hei_notification(*, to_email: str, hei_name: str, ticket_problem_statement: str, similarity_score: float | None, decide_url: str) -> dict[str, Any]:
    subject, text_body, html_body = _build_email(
        hei_name=hei_name, ticket_problem_statement=ticket_problem_statement,
        similarity_score=similarity_score, decide_url=decide_url,
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

"""SMTP email adapter with a dry-run mode for hackathon/demo setup.

Fixed template strings live in EMAIL_TEMPLATES so a regional-language
template can be added later without touching send logic.

# TODO(human): add ULB-facing translations if a state requires officer
# communication in the regional language. The standardized_problem_statement
# itself is already English-normalized text produced upstream by
# "1.Language normalizer" / "2.Evidence Extractor" - this adapter does not
# attempt any translation of it in this MVP.
"""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.adapters.base import DispatchAdapter
from app.config import settings
from app.db import DispatchEvent

EMAIL_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "subject": "[{correlation_code}] New civic issue reported: {domain}",
        "greeting": "A new civic issue has been reported and assigned to your department.",
        "location_label": "Location",
        "map_label": "View on Google Maps",
        "status_button_label": "Open status link (acknowledge / update / mark resolved)",
        "footer": "This is an automated message from the SAHYOG civic issue dispatch system.",
    },
}


def _template(lang: str) -> dict[str, str]:
    return EMAIL_TEMPLATES.get(lang, EMAIL_TEMPLATES["en"])


def _build_email(*, contact, ticket, correlation_code: str, status_link_url: str) -> tuple[str, str, str]:
    tpl = _template(settings.DISPATCH_EMAIL_LANGUAGE)
    subject = tpl["subject"].format(correlation_code=correlation_code, domain=ticket.domain or "Uncategorized")

    lat, lon = _extract_lat_lon(ticket)
    maps_url = f"https://www.google.com/maps?q={lat},{lon}" if lat is not None and lon is not None else ""

    text_body = (
        f"{tpl['greeting']}\n\n"
        f"Problem: {ticket.standardized_problem_statement}\n"
        f"{tpl['location_label']}: {lat}, {lon}\n"
        f"{tpl['map_label']}: {maps_url}\n\n"
        f"{tpl['status_button_label']}: {status_link_url}\n\n"
        f"{tpl['footer']}"
    )
    html_body = f"""
    <html><body>
      <p>{tpl['greeting']}</p>
      <p><b>Problem:</b> {ticket.standardized_problem_statement}</p>
      <p><b>{tpl['location_label']}:</b> {lat}, {lon}
         {f'(<a href="{maps_url}">{tpl["map_label"]}</a>)' if maps_url else ''}</p>
      <p><a href="{status_link_url}"
            style="display:inline-block;padding:10px 16px;background:#1a73e8;color:#fff;
                   text-decoration:none;border-radius:4px;">
            {tpl['status_button_label']}
         </a></p>
      <p style="color:#666;font-size:12px;">{tpl['footer']}</p>
    </body></html>
    """
    return subject, text_body, html_body


def _extract_lat_lon(ticket) -> tuple[float | None, float | None]:
    # geom comes back as WKB/EWKB text via the raw-SQL path in router.py's
    # callers; ticket objects handed to adapters carry plain lat/lon instead
    # (see dispatch.py where this is assembled) to keep this adapter simple.
    return getattr(ticket, "lat", None), getattr(ticket, "lon", None)


class EmailAdapter(DispatchAdapter):
    def send(self, *, contact, ticket, correlation_code: str, status_link_url: str) -> dict[str, Any]:
        if not contact.email:
            return {"success": False, "raw_response": None, "error": "contact has no email configured"}

        subject, text_body, html_body = _build_email(
            contact=contact, ticket=ticket, correlation_code=correlation_code, status_link_url=status_link_url
        )

        if settings.EMAIL_DRY_RUN:
            # Still build the full email exactly as a real send would, but
            # record it instead of calling smtplib. The caller (dispatch.py)
            # is responsible for persisting this into dispatch_events per
            # the base.py contract - we just return the rendered content.
            return {
                "success": True,
                "raw_response": {
                    "dry_run": True,
                    "rendered_email": {
                        "to": contact.email,
                        "subject": subject,
                        "text_body": text_body,
                        "html_body": html_body,
                    },
                },
                "error": None,
            }

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_FROM_ADDRESS
            msg["To"] = contact.email
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                server.starttls()
                if settings.SMTP_USER:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_ADDRESS, [contact.email], msg.as_string())

            return {"success": True, "raw_response": {"to": contact.email, "subject": subject}, "error": None}
        except Exception as exc:  # noqa: BLE001 - adapter contract: never raise
            return {"success": False, "raw_response": None, "error": str(exc)}

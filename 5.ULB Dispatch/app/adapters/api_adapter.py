"""Generic REST-intake adapter for ULBs that have an API endpoint configured.

No real ULB API schema is known at build time, so this sends a clearly
documented generic payload shape.

# TODO(human): each real ULB API will need its own payload adapter subclass -
# this generic one is a placeholder for ULBs with a genuinely generic REST
# intake. Do not assume any real ULB's API matches this shape without
# checking their integration docs first.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from app.adapters.base import DispatchAdapter


class ApiAdapter(DispatchAdapter):
    def send(self, *, contact, ticket, correlation_code: str, status_link_url: str) -> dict[str, Any]:
        if not contact.api_endpoint:
            return {"success": False, "raw_response": None, "error": "contact has no api_endpoint configured"}

        api_key = os.getenv(contact.api_key_ref) if contact.api_key_ref else None
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        payload = {
            "correlation_code": correlation_code,
            "ticket_id": ticket.id,
            "domain": ticket.domain,
            "problem_statement": ticket.standardized_problem_statement,
            "severity": ticket.severity,
            "population_impact": ticket.population_impact,
            "status_link_url": status_link_url,
        }

        try:
            response = httpx.post(contact.api_endpoint, json=payload, headers=headers, timeout=15.0)
            response.raise_for_status()
            return {"success": True, "raw_response": _safe_body(response), "error": None}
        except Exception as exc:  # noqa: BLE001 - adapter contract: never raise
            return {"success": False, "raw_response": None, "error": str(exc)}


def _safe_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:  # noqa: BLE001
        return response.text[:2000]

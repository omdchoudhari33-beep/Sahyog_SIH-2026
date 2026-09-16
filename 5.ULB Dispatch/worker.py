"""Standalone background loop process for sla.py + inbox_poller.py +
dispatch.py's reconcile logic.

Run alongside `uvicorn app.main:app --port 8004` ONLY when
RUN_BACKGROUND_LOOP_IN_PROCESS=false (the default, RUN_BACKGROUND_LOOP_IN_PROCESS=true,
already runs this same logic inside the FastAPI app - running both at once
just means the sweeps happen twice, which is harmless but wasteful).

    python worker.py
"""
from __future__ import annotations

import logging
import time

from app.config import settings
from app.db import SessionLocal
from app.dispatch import reconcile
from app.inbox_poller import poll_inbox
from app.sla import scan_overdue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ulb_dispatch.worker")


def run_once() -> None:
    db = SessionLocal()
    try:
        escalated = scan_overdue(db)
        if escalated:
            logger.info("scan_overdue: escalated %s dispatch(es)", escalated)
    except Exception:  # noqa: BLE001
        logger.exception("scan_overdue pass failed")
    finally:
        db.close()

    db = SessionLocal()
    try:
        result = reconcile(db)
        if result["dispatched"]:
            logger.info("reconcile: dispatched %s previously-missed ticket(s)", result["dispatched"])
    except Exception:  # noqa: BLE001
        logger.exception("reconcile pass failed")
    finally:
        db.close()

    db = SessionLocal()
    try:
        matched = poll_inbox(db)
        if matched:
            logger.info("poll_inbox: matched %s reply email(s)", matched)
    except Exception:  # noqa: BLE001
        logger.exception("poll_inbox pass failed")
    finally:
        db.close()


def main() -> None:
    if settings.RUN_BACKGROUND_LOOP_IN_PROCESS:
        logger.warning(
            "RUN_BACKGROUND_LOOP_IN_PROCESS=true - the FastAPI app is already running this "
            "same loop in-process. Running worker.py too is harmless but redundant."
        )
    logger.info(
        "worker.py started - SLA/reconcile every %ss, inbox poll every %ss",
        settings.SLA_POLL_INTERVAL_SECONDS, settings.INBOX_POLL_INTERVAL_SECONDS,
    )
    while True:
        run_once()
        time.sleep(settings.SLA_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.audit import log_event
from app.citizen_status import get_unified_status
from app.config import settings
from app.dashboard import full_dashboard
from app.db import get_db
from app.schemas import AuditLogEntry, AuditLogOut

logger = logging.getLogger("transparency_layer")

app = FastAPI(title="Sahyog Transparency Layer", version="0.1.0")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}


def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    if not settings.INTERNAL_SERVICE_TOKEN or x_internal_token != settings.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="missing or invalid X-Internal-Token")


@app.post("/audit/log", response_model=AuditLogOut, dependencies=[Depends(require_internal_token)])
def audit_log_ingest(entry: AuditLogEntry, db: Session = Depends(get_db)):
    """Internal-only ingestion - see README on what "immutable" means here:
    this app never exposes an UPDATE/DELETE route for audit_log, but that's
    an honesty guarantee, not a cryptographic one (TODO(human) in README)."""
    saved = log_event(db, entry.service_name, entry.entity_type, entry.entity_id, entry.event, entry.actor, entry.payload)
    return AuditLogOut.model_validate(saved)


# ---------------------------------------------------------------------------
# X1 Govt Analytics Dashboard - public read-only aggregate view.
# ---------------------------------------------------------------------------

@app.get("/transparency/dashboard.json")
def transparency_dashboard_json(db: Session = Depends(get_db)):
    return full_dashboard(db)


@app.get("/transparency/dashboard", response_class=HTMLResponse)
def transparency_dashboard(db: Session = Depends(get_db)):
    stats = full_dashboard(db)
    heatmap_rows = "".join(
        f"<tr><td>{r['district']}</td><td>{r['domain']}</td><td>{r['ticket_count']}</td></tr>"
        for r in stats["district_domain_heatmap"]
    )
    return HTMLResponse(f"""
    <!DOCTYPE html><html><head><title>SAHYOG Transparency Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body{{font-family:sans-serif;max-width:900px;margin:40px auto;padding:0 16px}}
    table{{border-collapse:collapse;width:100%;margin:12px 0}}
    td,th{{border:1px solid #ccc;padding:6px;text-align:left}}
    .stat{{display:inline-block;margin:8px 16px 8px 0}}</style></head>
    <body>
      <h2>SAHYOG Transparency Dashboard</h2>

      <h3>HEI Participation</h3>
      <div class="stat">Active HEIs: <b>{stats['hei_participation']['active_heis']}</b></div>
      <div class="stat">Pending matches: <b>{stats['hei_participation']['pending_matches']}</b></div>
      <div class="stat">Declined matches: <b>{stats['hei_participation']['declined_matches']}</b></div>

      <h3>Industry Engagement</h3>
      <div class="stat">Active partners: <b>{stats['industry_engagement']['active_partners']}</b></div>
      <div class="stat">Pending matches: <b>{stats['industry_engagement']['pending_matches']}</b></div>
      <div class="stat">Total committed (INR): <b>{stats['industry_engagement']['total_committed_amount']}</b></div>

      <h3>Completion Rate</h3>
      <div class="stat">Pilots passed: <b>{stats['completion_rate']['pilots_passed']}</b></div>
      <div class="stat">Pilots failed: <b>{stats['completion_rate']['pilots_failed']}</b></div>
      <div class="stat">Pending review: <b>{stats['completion_rate']['pilots_pending']}</b></div>

      <h3>Outcomes</h3>
      <div class="stat">Handovers: <b>{stats['outcomes']['handovers']}</b></div>
      <div class="stat">Spin-outs: <b>{stats['outcomes']['spinouts']}</b></div>
      <div class="stat">Track A resolved: <b>{stats['outcomes']['track_a_resolved']}</b></div>

      <h3>District x Domain Heatmap</h3>
      <table><tr><th>District</th><th>Domain</th><th>Ticket count</th></tr>{heatmap_rows}</table>

      <p><a href="/transparency/dashboard.json">Raw JSON</a></p>
    </body></html>
    """)


# ---------------------------------------------------------------------------
# X2 Citizen Status Portal - public, ticket ID is the lookup key.
# ---------------------------------------------------------------------------

@app.get("/status/{ticket_id}.json")
def citizen_status_json(ticket_id: int, db: Session = Depends(get_db)):
    # Registered before /status/{ticket_id} - {ticket_id} would otherwise
    # greedily match the literal segment "13.json" first (as a
    # to-be-rejected int) and shadow this route, same class of bug as
    # 5.ULB Dispatch's /dispatch/reconcile vs /dispatch/{ticket_id} lesson.
    status = get_unified_status(db, ticket_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"no ticket found with id {ticket_id}")
    return status


@app.get("/status/{ticket_id}", response_class=HTMLResponse)
def citizen_status_page(ticket_id: int, db: Session = Depends(get_db)):
    status = get_unified_status(db, ticket_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"no ticket found with id {ticket_id}")

    track_html = ""
    if status["track"] == "track_a" and status["track_a"]:
        d = status["track_a"]
        track_html = f"<p><b>Dispatch status:</b> {d['status']} ({d['correlation_code']})</p>"
    elif status["track"] == "track_b" and status["track_b"]:
        tb = status["track_b"]
        proposal = tb.get("proposal")
        milestones_html = "".join(f"<li>{m['title']}: {m['status']}</li>" for m in tb.get("milestones", []))
        track_html = f"""
        <p><b>R&amp;D match status:</b> {tb['match']['status'] if tb['match'] else 'pending'}</p>
        {f"<p><b>Proposal:</b> {proposal['title']} ({proposal['status']})</p>" if proposal else ''}
        {f"<ul>{milestones_html}</ul>" if milestones_html else ''}
        """

    return HTMLResponse(f"""
    <!DOCTYPE html><html><head><title>SAHYOG - Ticket #{ticket_id} Status</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body{{font-family:sans-serif;max-width:480px;margin:40px auto;padding:0 16px}}</style></head>
    <body>
      <h2>Ticket #{ticket_id}</h2>
      <p><b>Domain:</b> {status['domain']}</p>
      <p><b>Status:</b> {status['status']}</p>
      <p><b>Problem:</b> {status['problem_statement']}</p>
      {track_html}
    </body></html>
    """)

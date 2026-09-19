from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, File, Form, Header, HTTPException, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import InvalidCredentialsError, SessionExpiredError, login as auth_login, logout as auth_logout, resolve_session
from app.config import settings
from app.db import HeiBroadcastNotice, HeiMatch, HeiRegistry, Proposal, SessionLocal, Team, get_db
from app.geocoding import maps_link, reverse_geocode
from app.matcher import apply_decision, create_match, decide_match, reconcile as reconcile_matches, register_interest
from app.onboarding import list_heis, onboard_hei, reset_hei_password
from app.schemas import (
    BroadcastNoticeOut,
    HeiMatchOut,
    HeiMatchWithTicketOut,
    ProposalOut,
    ReconcileResult,
    TeamFormRequest,
    TrackBAck,
)
from app.storage import storage
from app.teams import form_team, nodal_decide, submit_proposal

logger = logging.getLogger("trackb_innovation")

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _page(title: str, brand_icon: str, tag: str, body: str, *, nav: str = "", max_width: int = 640) -> str:
    """Shared page shell for every Track B HTML page - same "SAHYOG design
    system" stylesheet 4.Orchestrator's operator dashboard and admin portal
    use (app/static/styles.css here is a copy of that same file), so the
    University Portal reads as part of the same product instead of a bare
    HTML fallback."""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' fill='%230b3d66'/%3E%3Ctext x='50' y='68' font-size='58' text-anchor='middle'%3E%F0%9F%8E%93%3C/text%3E%3C/svg%3E" />
    <link rel="stylesheet" href="/static/styles.css" />
    </head>
    <body>
    <header class="top">
      <div style="max-width: {max_width}px;">
        <div class="brand">
          <div class="brand-mark">{brand_icon}</div>
          <div>
            <h1>{title}</h1>
            <div class="tag">{tag}</div>
          </div>
        </div>
        {f"<nav>{nav}</nav>" if nav else ""}
      </div>
    </header>
    <div class="wrap" style="max-width: {max_width}px;">
      {body}
    </div>
    </body>
    </html>
    """


def _seed_demo_data_if_empty() -> None:
    db = SessionLocal()
    try:
        count = db.execute(text("SELECT COUNT(*) FROM hei_registry")).scalar_one()
        if count > 0:
            return
        from app.embedding import embed_text

        hei_id = db.execute(
            text(
                "INSERT INTO hei_registry (institution_name, state, contact_email, capacity_active_projects, active) "
                "VALUES (:name, 'TODO(human): set real state', :email, 3, true) RETURNING id"
            ),
            {"name": settings.DEMO_HEI_NAME, "email": settings.DEMO_HEI_CONTACT_EMAIL},
        ).scalar_one()
        description = "Civil and municipal engineering R&D: roads, drainage, water supply, structural assessment"
        db.execute(
            text(
                "INSERT INTO hei_capabilities (hei_id, domain, department_name, description, embedding, active) "
                "VALUES (:hei_id, 'ROADS_BRIDGES', 'Civil Engineering', :description, :embedding, true)"
            ),
            {"hei_id": hei_id, "description": description, "embedding": str(embed_text(description))},
        )
        db.commit()
        logger.info("[demo-seed] inserted demo HEI + capability (hei_id=%s) - set SEED_DEMO_DATA=false to disable", hei_id)
    finally:
        db.close()


app = FastAPI(title="Sahyog Track B Innovation", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup() -> None:
    if settings.SEED_DEMO_DATA:
        _seed_demo_data_if_empty()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok"}


def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    if not settings.INTERNAL_SERVICE_TOKEN or x_internal_token != settings.INTERNAL_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="missing or invalid X-Internal-Token")


@app.post("/trackb/reconcile", response_model=ReconcileResult, dependencies=[Depends(require_internal_token)])
def trackb_reconcile(db: Session = Depends(get_db)):
    # Registered before /trackb/{ticket_id} - same path-shadowing lesson as
    # 5.ULB Dispatch's /dispatch/reconcile.
    result = reconcile_matches(db)
    return ReconcileResult(**result)


@app.post("/trackb/{ticket_id}", response_model=TrackBAck, dependencies=[Depends(require_internal_token)])
def trackb_dispatch(ticket_id: int, db: Session = Depends(get_db)):
    try:
        result = create_match(db, ticket_id)
    except Exception as exc:  # noqa: BLE001 - the webhook caller must never see an unhandled 500
        logger.exception("trackb_dispatch failed for ticket_id=%s", ticket_id)
        return JSONResponse(status_code=500, content={"ticket_id": ticket_id, "created": False, "detail": str(exc)})

    match = result.get("match")
    return TrackBAck(
        ticket_id=ticket_id,
        match=HeiMatchOut.model_validate(match) if match is not None and match.id is not None else None,
        created=bool(result.get("created")),
        detail=result.get("detail"),
    )


@app.get("/trackb/{ticket_id}", response_model=HeiMatchOut, dependencies=[Depends(require_internal_token)])
def get_trackb_match(ticket_id: int, db: Session = Depends(get_db)):
    match = db.query(HeiMatch).filter(HeiMatch.ticket_id == ticket_id).order_by(HeiMatch.created_at.desc()).first()
    if match is None:
        raise HTTPException(status_code=404, detail=f"no match found for ticket {ticket_id}")
    return HeiMatchOut.model_validate(match)


@app.get(
    "/trackb/{ticket_id}/broadcast",
    response_model=list[BroadcastNoticeOut],
    dependencies=[Depends(require_internal_token)],
)
def get_trackb_broadcast(ticket_id: int, db: Session = Depends(get_db)):
    """The top-N HEIs this ticket's problem brief was broadcast to (see
    matcher.py's broadcast_to_top_n) - consumed by the Admin Portal's Track B
    panel and by 9.Transparency Layer's citizen status aggregator."""
    rows = db.execute(
        text(
            """
            SELECT n.id, n.ticket_id, n.hei_id, hr.institution_name, n.rank, n.similarity_score, n.sent_at,
                   hm.status AS match_status
            FROM hei_broadcast_notices n
            JOIN hei_registry hr ON hr.id = n.hei_id
            LEFT JOIN hei_matches hm ON hm.ticket_id = n.ticket_id AND hm.hei_id = n.hei_id
            WHERE n.ticket_id = :ticket_id
            ORDER BY n.rank
            """
        ),
        {"ticket_id": ticket_id},
    ).mappings().all()
    return [BroadcastNoticeOut.model_validate(dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# Admin Portal proxy targets (4.Orchestrator calls these server-side, on
# behalf of a human who already passed ITS OWN admin_portal_password gate -
# see that service's app/clients.py). Internal-auth, not HTTPBasic: this is
# a service-to-service call, the human already authenticated upstream.
# ---------------------------------------------------------------------------

class NodalDecisionRequest(BaseModel):
    decision: str
    nodal_officer_id: str
    notes: Optional[str] = None


@app.get("/trackb/proposals/pending", response_model=list[ProposalOut], dependencies=[Depends(require_internal_token)])
def list_pending_proposals(db: Session = Depends(get_db)):
    proposals = db.query(Proposal).filter(Proposal.status.in_(["submitted", "nodal_review"])).order_by(Proposal.submitted_at).all()

    doc_media_ids = {p.solution_document_media_id for p in proposals if p.solution_document_media_id}
    doc_urls: dict[int, str] = {}
    if doc_media_ids:
        rows = db.execute(
            text("SELECT id, bucket, object_key FROM media_objects WHERE id = ANY(:ids)"),
            {"ids": list(doc_media_ids)},
        ).mappings()
        doc_urls = {row["id"]: _media_download_url(row["bucket"], row["object_key"]) for row in rows}

    return [
        ProposalOut(
            **ProposalOut.model_validate(p).model_dump(exclude={"solution_document_url"}),
            solution_document_url=doc_urls.get(p.solution_document_media_id) if p.solution_document_media_id else None,
        )
        for p in proposals
    ]


class MatchDecisionRequest(BaseModel):
    decision: str
    reason: Optional[str] = None


@app.get("/trackb/matches/pending", response_model=list[HeiMatchWithTicketOut], dependencies=[Depends(require_internal_token)])
def list_pending_matches(db: Session = Depends(get_db)):
    """Registered before /trackb/{ticket_id} for the same path-shadowing
    reason as trackb_reconcile above - matches awaiting an HEI accept/decline
    or team-formation, across all institutions. Enriched with the ticket's
    own domain/description (one batched query, not N+1) so the institution
    portal's Match Inbox can show what the case is actually about."""
    matches = db.query(HeiMatch).filter(HeiMatch.status.in_(["proposed", "accepted"])).order_by(HeiMatch.created_at.desc()).all()

    ticket_ids = {m.ticket_id for m in matches}
    ticket_info: dict[int, dict] = {}
    if ticket_ids:
        rows = db.execute(
            text(
                "SELECT id, domain, standardized_problem_statement, "
                "ST_Y(geom) AS latitude, ST_X(geom) AS longitude "
                "FROM active_tickets WHERE id = ANY(:ids)"
            ),
            {"ids": list(ticket_ids)},
        ).mappings()
        ticket_info = {row["id"]: row for row in rows}

    hei_ids = {m.hei_id for m in matches}
    hei_names: dict[int, str] = {}
    if hei_ids:
        rows = db.execute(
            text("SELECT id, institution_name FROM hei_registry WHERE id = ANY(:ids)"),
            {"ids": list(hei_ids)},
        ).mappings()
        hei_names = {row["id"]: row["institution_name"] for row in rows}

    results = []
    for m in matches:
        ticket = ticket_info.get(m.ticket_id)
        results.append(
            HeiMatchWithTicketOut(
                **HeiMatchOut.model_validate(m).model_dump(),
                ticket_domain=ticket["domain"] if ticket else None,
                ticket_problem_statement=ticket["standardized_problem_statement"] if ticket else None,
                ticket_lat=ticket["latitude"] if ticket else None,
                ticket_lon=ticket["longitude"] if ticket else None,
                institution_name=hei_names.get(m.hei_id),
            )
        )
    return results


@app.post("/trackb/matches/{match_id}/decide", response_model=HeiMatchOut, dependencies=[Depends(require_internal_token)])
def match_decision_json(match_id: int, body: MatchDecisionRequest, db: Session = Depends(get_db)):
    """JSON-body internal-auth equivalent of POST /university/matches/{id}/decide -
    same apply_decision() call, so both entry points share one code path."""
    if body.decision not in ("accept", "decline"):
        raise HTTPException(status_code=400, detail="decision must be accept or decline")
    match = db.query(HeiMatch).filter(HeiMatch.id == match_id).one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="match not found")
    try:
        apply_decision(db, match, body.decision, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.refresh(match)
    return HeiMatchOut.model_validate(match)


@app.post("/trackb/matches/{match_id}/team", dependencies=[Depends(require_internal_token)])
def match_form_team_json(match_id: int, body: TeamFormRequest, db: Session = Depends(get_db)):
    """JSON-body internal-auth equivalent of POST /university/matches/{id}/team -
    same form_team() call, so an Admin Portal action and an institution's own
    dashboard action produce identical rows either way. Lets SAHYOG program
    staff form a team on an institution's behalf from the Admin Portal, same
    trust relationship the existing .../decide endpoint above already has."""
    try:
        team = form_team(db, match_id, body.team_name, body.faculty_mentor_name, body.faculty_mentor_email, body.student_names)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"team_id": team.id, "team_name": team.team_name}


@app.post("/trackb/matches/{match_id}/proposal", response_model=ProposalOut, dependencies=[Depends(require_internal_token)])
def match_submit_proposal_json(
    match_id: int, title: str = Form(...), summary: str = Form(...),
    requested_budget: Optional[float] = Form(default=None), timeline_weeks: Optional[int] = Form(default=None),
    solution_document: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
):
    """Internal-auth equivalent of POST /university/matches/{id}/proposal -
    same submit_proposal() + _upload_solution_document() calls (multipart,
    not JSON, since it carries the solution PDF - a Pydantic body can't hold
    an UploadFile), for the Admin Portal's case-detail view."""
    team = db.query(Team).filter(Team.match_id == match_id).order_by(Team.id.desc()).first()
    if team is None:
        raise HTTPException(status_code=409, detail="no team formed yet for this match")
    solution_document_media_id = _upload_solution_document(solution_document)
    proposal = submit_proposal(db, team.id, title, summary, requested_budget, timeline_weeks, solution_document_media_id)
    return ProposalOut.model_validate(proposal)


class CollaborateRequest(BaseModel):
    hei_id: int


@app.post("/trackb/{ticket_id}/collaborate", response_model=HeiMatchOut, dependencies=[Depends(require_internal_token)])
def collaborate_json(ticket_id: int, body: CollaborateRequest, db: Session = Depends(get_db)):
    """JSON-body internal-auth equivalent of POST /university/collaborate/{ticket_id} -
    same register_interest() call, for the Admin Portal to trigger a
    self-join on an institution's behalf if ever needed."""
    try:
        result = register_interest(db, ticket_id, body.hei_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return HeiMatchOut.model_validate(result["match"])


@app.post("/trackb/proposals/{proposal_id}/nodal-decision", response_model=ProposalOut, dependencies=[Depends(require_internal_token)])
def nodal_decision_json(proposal_id: int, body: NodalDecisionRequest, db: Session = Depends(get_db)):
    """JSON-body internal-auth equivalent of POST /admin/nodal-review/{id} -
    same nodal_decide() call, so both entry points share one code path and
    can never drift out of sync with each other."""
    try:
        proposal = nodal_decide(db, proposal_id, body.decision, body.nodal_officer_id, body.notes)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ProposalOut.model_validate(proposal)


# ---------------------------------------------------------------------------
# Public HEI accept/decline + team/proposal flow - token is the credential.
# ---------------------------------------------------------------------------

def _hei_page_html(token: str, match: HeiMatch, message: str = "") -> str:
    if match.status == "proposed":
        body = f"""
        <div class="card">
          <p><span class="badge track_b">Proposed match</span> attempt {match.attempt_no} &middot; similarity {match.similarity_score:.0%}</p>
          <form method="post" action="/hei/{token}/decide">
            <div class="field"><label>Reason (if declining)</label><input type="text" name="reason"></div>
            <div class="row">
              <button class="primary" name="decision" value="accept" type="submit">Accept</button>
              <button class="ghost" name="decision" value="decline" type="submit">Decline</button>
            </div>
          </form>
        </div>
        """
    elif match.status == "accepted":
        body = f"""
        <div class="card">
          <p><span class="badge routed">Match accepted</span> &mdash; form your team below.</p>
          <form method="post" action="/hei/{token}/team">
            <div class="field"><label>Team name</label><input type="text" name="team_name" required></div>
            <div class="field"><label>Faculty mentor name</label><input type="text" name="faculty_mentor_name" required></div>
            <div class="field"><label>Faculty mentor email</label><input type="text" name="faculty_mentor_email" required></div>
            <div class="field"><label>Student names (comma-separated)</label><input type="text" name="student_names"></div>
            <button class="primary" type="submit">Form team</button>
          </form>
        </div>
        """
    else:
        body = f'<div class="card"><p>This match was <b>{match.status}</b>.</p></div>'

    message_html = f'<div class="error-box" style="display:block;">{message}</div>' if message else ""
    return _page(
        "SAHYOG Track B", "🎓", "R&D opportunity match",
        message_html + body, max_width=480,
    )


@app.get("/hei/{token}", response_class=HTMLResponse)
def hei_page(token: str, db: Session = Depends(get_db)):
    match = db.query(HeiMatch).filter(HeiMatch.match_token == token).one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="match token not found")
    if match.status == "proposed":
        expires_at = match.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="match token has expired")
    return HTMLResponse(_hei_page_html(token, match))


@app.post("/hei/{token}/decide")
def hei_decide(token: str, decision: str = Form(...), reason: Optional[str] = Form(default=None), db: Session = Depends(get_db)):
    if decision not in ("accept", "decline"):
        raise HTTPException(status_code=400, detail="decision must be accept or decline")
    try:
        result = decide_match(db, token, decision, reason)
    except LookupError:
        raise HTTPException(status_code=404, detail="match token not found")
    except TimeoutError:
        raise HTTPException(status_code=410, detail="match token has expired")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"status": result["match"].status, "re_routed": result.get("re_routed", False)}


@app.post("/hei/{token}/team")
def hei_form_team(
    token: str, team_name: str = Form(...), faculty_mentor_name: str = Form(...),
    faculty_mentor_email: str = Form(...), student_names: str = Form(default=""),
    db: Session = Depends(get_db),
):
    match = db.query(HeiMatch).filter(HeiMatch.match_token == token).one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="match token not found")
    names = [n.strip() for n in student_names.split(",") if n.strip()]
    try:
        team = form_team(db, match.id, team_name, faculty_mentor_name, faculty_mentor_email, names)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"team_id": team.id, "team_name": team.team_name}


@app.post("/hei/{token}/proposal", response_model=ProposalOut)
def hei_submit_proposal(
    token: str, title: str = Form(...), summary: str = Form(...),
    requested_budget: Optional[float] = Form(default=None), timeline_weeks: Optional[int] = Form(default=None),
    db: Session = Depends(get_db),
):
    match = db.query(HeiMatch).filter(HeiMatch.match_token == token).one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="match token not found")
    team = db.query(Team).filter(Team.match_id == match.id).order_by(Team.id.desc()).first()
    if team is None:
        raise HTTPException(status_code=409, detail="no team formed yet for this match")
    proposal = submit_proposal(db, team.id, title, summary, requested_budget, timeline_weeks)
    return ProposalOut.model_validate(proposal)


# ---------------------------------------------------------------------------
# Admin: onboard HEIs, nodal review of proposals - HTTPBasic, separate trust
# boundary from INTERNAL_SERVICE_TOKEN.
# ---------------------------------------------------------------------------

_basic_auth = HTTPBasic(auto_error=False)


def require_admin_password(credentials: Optional[HTTPBasicCredentials] = Depends(_basic_auth)) -> None:
    if not settings.ADMIN_FORM_PASSWORD:
        raise HTTPException(status_code=503, detail="ADMIN_FORM_PASSWORD is not configured")
    if credentials is None or credentials.password != settings.ADMIN_FORM_PASSWORD:
        raise HTTPException(status_code=401, detail="invalid admin credentials", headers={"WWW-Authenticate": "Basic"})


@app.get("/admin/onboard-hei", response_class=HTMLResponse, dependencies=[Depends(require_admin_password)])
def onboard_hei_form():
    body = """
    <div class="card">
      <form method="post" action="/admin/onboard-hei">
        <div class="field"><label>Institution name</label><input type="text" name="institution_name" required></div>
        <div class="row">
          <div class="field"><label>State</label><input type="text" name="state" required value="Jharkhand"></div>
          <div class="field"><label>District</label><input type="text" name="district"></div>
        </div>
        <div class="row">
          <div class="field"><label>Contact email</label><input type="text" name="contact_email" required></div>
          <div class="field"><label>Contact phone</label><input type="text" name="contact_phone"></div>
        </div>
        <div class="row">
          <div class="field"><label>Incubator name</label><input type="text" name="incubator_name"></div>
          <div class="field"><label>Capacity (concurrent active projects)</label><input type="number" name="capacity_active_projects" value="3"></div>
        </div>
        <div class="field"><label>Domain (e.g. AGRICULTURAL_DISEASE, UNKNOWN_STRUCTURAL_FAILURE)</label><input type="text" name="domain" required></div>
        <div class="field"><label>Department name</label><input type="text" name="department_name" required></div>
        <div class="field"><label>Capability description</label><input type="text" name="description" required></div>
        <div class="field"><label>University Portal password (leave blank to auto-generate one)</label><input type="text" name="initial_password"></div>
        <button class="primary" type="submit">Add HEI</button>
      </form>
      <p class="hint" style="margin-top:14px;">The response after submitting shows the plaintext password
      once - relay it to the HEI. Login at <a href="/university/login">/university/login</a>.</p>
    </div>
    """
    return HTMLResponse(_page(
        "Onboard an HEI", "🎓", "Track B admin", body,
        nav='<a href="/admin/heis">Manage HEIs</a><a href="/admin/nodal-review">Nodal review</a>',
    ))


@app.post("/admin/onboard-hei", dependencies=[Depends(require_admin_password)])
def onboard_hei_submit(
    institution_name: str = Form(...), state: str = Form(...), district: Optional[str] = Form(default=None),
    contact_email: str = Form(...), contact_phone: Optional[str] = Form(default=None),
    incubator_name: Optional[str] = Form(default=None), capacity_active_projects: int = Form(default=3),
    domain: str = Form(...), department_name: str = Form(...), description: str = Form(...),
    initial_password: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    hei, capability, password = onboard_hei(
        db, institution_name, state, district, contact_email, contact_phone,
        incubator_name, capacity_active_projects, domain, department_name, description,
        initial_password,
    )
    # The plaintext password is returned exactly once, here, for the admin
    # to relay to the HEI - it is never stored or logged (see onboarding.py).
    return {"hei_id": hei.id, "capability_id": capability.id, "university_portal_login": {"email": contact_email, "password": password}}


@app.get("/admin/heis", response_class=HTMLResponse, dependencies=[Depends(require_admin_password)])
def heis_list(db: Session = Depends(get_db), reset_password: Optional[str] = None, reset_email: Optional[str] = None):
    """Lists every onboarded HEI (including seed_jharkhand_heis.py's real
    institutions, whose passwords were randomly generated and never
    surfaced anywhere) with a one-click password reset - the only way to
    get a real, usable University Portal login for one of them."""
    heis = list_heis(db)
    banner = ""
    if reset_password and reset_email:
        banner = (
            f'<div class="error-box" style="display:block;background:var(--green-soft);'
            f'color:var(--green);border-color:var(--green);">New password for {reset_email}: '
            f'<b>{reset_password}</b> - copy it now, it will not be shown again.</div>'
        )
    rows = "".join(
        f"<tr><td>{h.institution_name}</td><td>{h.district or '-'}</td><td>{h.contact_email}</td>"
        f"<td><form method='post' action='/admin/heis/{h.id}/reset-password' class='actions'>"
        f"<button class='b' type='submit'>Reset password</button></form></td></tr>"
        for h in heis
    )
    table = (
        f'<table class="admin"><tr><th>Institution</th><th>District</th><th>Contact email</th><th>Action</th></tr>{rows}</table>'
        if heis else '<div class="empty"><span class="empty-icon">🎓</span>No HEIs onboarded yet.</div>'
    )
    body = f"{banner}<div class=\"card\">{table}</div>"
    return HTMLResponse(_page(
        "Manage HEIs", "🎓", f"{len(heis)} onboarded institutions", body,
        nav='<a href="/admin/onboard-hei">Onboard HEI</a><a href="/admin/nodal-review">Nodal review</a>',
        max_width=900,
    ))


@app.post("/admin/heis/{hei_id}/reset-password", dependencies=[Depends(require_admin_password)])
def heis_reset_password(hei_id: int, db: Session = Depends(get_db)):
    try:
        hei, password = reset_hei_password(db, hei_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return RedirectResponse(
        url=f"/admin/heis?reset_password={password}&reset_email={hei.contact_email}", status_code=303
    )


@app.get("/admin/nodal-review", response_class=HTMLResponse, dependencies=[Depends(require_admin_password)])
def nodal_review_list(db: Session = Depends(get_db)):
    proposals = db.query(Proposal).filter(Proposal.status.in_(["submitted", "nodal_review"])).order_by(Proposal.submitted_at).all()

    doc_media_ids = {p.solution_document_media_id for p in proposals if p.solution_document_media_id}
    doc_urls: dict[int, str] = {}
    if doc_media_ids:
        doc_rows = db.execute(
            text("SELECT id, bucket, object_key FROM media_objects WHERE id = ANY(:ids)"),
            {"ids": list(doc_media_ids)},
        ).mappings()
        doc_urls = {row["id"]: _media_download_url(row["bucket"], row["object_key"]) for row in doc_rows}

    rows = "".join(
        f"<tr><td>{p.id}</td><td>{p.title}"
        + (f"<br><a href='{doc_urls[p.solution_document_media_id]}' target='_blank' rel='noopener'>📄 Solution PDF</a>" if p.solution_document_media_id in doc_urls else "")
        + f"</td><td class='stmt'>{p.summary[:80]}</td><td>{p.requested_budget or '-'}</td>"
        f"<td><form method='post' action='/admin/nodal-review/{p.id}' class='actions'>"
        f"<input name='notes' placeholder='notes'><input name='nodal_officer_id' placeholder='your id'>"
        f"<button class='a' name='decision' value='approved'>Approve</button>"
        f"<button class='reject' name='decision' value='rejected'>Reject</button>"
        f"<button class='b' name='decision' value='revision_requested'>Request revision</button>"
        f"</form></td></tr>"
        for p in proposals
    )
    table = (
        f'<table class="admin"><tr><th>ID</th><th>Title</th><th>Summary</th><th>Budget</th><th>Action</th></tr>{rows}</table>'
        if proposals else '<div class="empty"><span class="empty-icon">📭</span>No proposals pending review.</div>'
    )
    body = f'<div class="card">{table}</div>'
    return HTMLResponse(_page(
        "Nodal Review", "🧑‍⚖️", "Proposals pending nodal review", body,
        nav='<a href="/admin/onboard-hei">Onboard HEI</a><a href="/admin/heis">Manage HEIs</a>', max_width=900,
    ))


@app.post("/admin/nodal-review/{proposal_id}", response_model=ProposalOut, dependencies=[Depends(require_admin_password)])
def nodal_review_decide(
    proposal_id: int, decision: str = Form(...), nodal_officer_id: str = Form(default="unknown"),
    notes: Optional[str] = Form(default=None), db: Session = Depends(get_db),
):
    try:
        proposal = nodal_decide(db, proposal_id, decision, nodal_officer_id, notes)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ProposalOut.model_validate(proposal)


# ---------------------------------------------------------------------------
# University Portal - real per-HEI login (app/auth.py), a returning-user
# dashboard replacing the need to keep re-using one-off email links for
# every interaction. The token-based /hei/{token}/* routes above still work
# unchanged (existing email links keep working) - this is an additional
# entry point onto the SAME underlying data and the SAME state-transition
# functions (apply_decision, form_team, submit_proposal), not a fork of them.
# ---------------------------------------------------------------------------

SESSION_COOKIE_NAME = "hei_session"


def _current_hei(db: Session = Depends(get_db), hei_session: Optional[str] = Cookie(default=None)) -> HeiRegistry:
    if not hei_session:
        raise HTTPException(status_code=401, detail="not logged in")
    try:
        return resolve_session(db, hei_session)
    except SessionExpiredError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


def _login_page_html(message: str = "") -> str:
    message_html = f'<div class="error-box" style="display:block;">{message}</div>' if message else ""
    body = f"""
    {message_html}
    <div class="card">
      <form method="post" action="/university/login">
        <div class="field"><label>Registered email</label><input type="text" name="email" required></div>
        <div class="field"><label>Password</label><input type="password" name="password" required></div>
        <button class="primary" type="submit">Log in</button>
      </form>
    </div>
    """
    return _page("University Portal", "🎓", "SAHYOG Track B - HEI login", body, max_width=420)


@app.get("/university/login", response_class=HTMLResponse)
def university_login_form():
    return HTMLResponse(_login_page_html())


@app.post("/university/login")
def university_login_submit(response: Response, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    try:
        hei, session_token = auth_login(db, email, password)
    except InvalidCredentialsError:
        return HTMLResponse(_login_page_html("Invalid email or password."), status_code=401)

    redirect = RedirectResponse(url="/university/dashboard", status_code=303)
    redirect.set_cookie(SESSION_COOKIE_NAME, session_token, httponly=True, samesite="lax", max_age=30 * 24 * 3600)
    return redirect


@app.post("/university/logout")
def university_logout(response: Response, hei_session: Optional[str] = Cookie(default=None), db: Session = Depends(get_db)):
    if hei_session:
        auth_logout(db, hei_session)
    redirect = RedirectResponse(url="/university/login", status_code=303)
    redirect.delete_cookie(SESSION_COOKIE_NAME)
    return redirect


_MATCH_BADGE = {
    "proposed": "track_b", "accepted": "routed", "declined": "track_b_bad", "expired": "review_required",
}


def _location_cell(info: Optional[dict]) -> str:
    if info is None or info.get("latitude") is None or info.get("longitude") is None:
        return "<span style='color:var(--muted-2)'>Not available</span>"
    lat, lon = info["latitude"], info["longitude"]
    place = reverse_geocode(lat, lon)
    link = maps_link(lat, lon)
    label = place if place else f"{lat:.5f}, {lon:.5f}"
    return f"{label}<br><a href='{link}' target='_blank' rel='noopener'>View on map ↗</a>"


def _problem_cell(info: Optional[dict]) -> str:
    if info is None:
        return "<span style='color:var(--muted-2)'>—</span>"
    statement = (info.get("standardized_problem_statement") or "")[:160]
    photo_url = _media_download_url(info.get("photo_bucket"), info.get("photo_object_key"))
    photo_html = (
        f"<a href='{photo_url}' target='_blank' rel='noopener'>"
        f"<img src='{photo_url}' alt='Report photo' style='width:64px;height:64px;object-fit:cover;"
        f"border-radius:var(--radius-sm);border:1px solid var(--border);display:block;margin-top:6px;'></a>"
        if photo_url else ""
    )
    domain = (info.get("domain") or "").replace("_", " ").title()
    return f"<div style='max-width:220px;'><b>{domain}</b><div class='hint' style='margin-top:2px;'>{statement}</div>{photo_html}</div>"


def _proposal_dialog(m: HeiMatch) -> str:
    """A native <dialog> modal (no JS framework, ~1 line to open/close) -
    the full proposal form laid out as stacked full-width fields, with a
    file input for the solution PDF, instead of the old cramped inline
    <form> crammed into a table cell."""
    return f"""
    <dialog id="proposal-dialog-{m.id}">
      <form method="post" action="/university/matches/{m.id}/proposal" enctype="multipart/form-data">
        <h3 style="margin-top:0;">Submit your solution proposal</h3>
        <div class="field"><label>Proposal title</label><input type="text" name="title" required></div>
        <div class="field"><label>Summary</label><textarea name="summary" rows="4" required></textarea></div>
        <div class="row">
          <div class="field"><label>Requested budget (INR)</label><input type="number" name="requested_budget" step="0.01"></div>
          <div class="field"><label>Timeline (weeks)</label><input type="number" name="timeline_weeks"></div>
        </div>
        <div class="field">
          <label>Solution document (PDF)</label>
          <input type="file" name="solution_document" accept="application/pdf">
          <p class="hint">Upload your detailed solution write-up, design, or report as a PDF.</p>
        </div>
        <div class="row" style="margin-top:6px;">
          <button class="ghost" type="button" onclick="this.closest('dialog').close()">Cancel</button>
          <button class="primary" type="submit">Submit proposal</button>
        </div>
      </form>
    </dialog>
    <button class="b" type="button" onclick="document.getElementById('proposal-dialog-{m.id}').showModal()">Submit proposal</button>
    """


def _dashboard_html(
    hei: HeiRegistry, matches: list[HeiMatch], teams_by_match: dict, proposals_by_match: dict,
    broadcasts: list[dict], ticket_info: dict, doc_urls: dict,
) -> str:
    rows = ""
    for m in matches:
        team = teams_by_match.get(m.id)
        proposal = proposals_by_match.get(m.id)
        actions = ""
        if m.status == "proposed":
            actions = f"""
            <form method="post" action="/university/matches/{m.id}/decide" class="actions">
              <button class="a" name="decision" value="accept">Accept</button>
              <button class="reject" name="decision" value="decline">Decline</button>
            </form>"""
        elif m.status == "accepted" and team is None:
            actions = f"""
            <form method="post" action="/university/matches/{m.id}/team" class="actions" style="flex-direction:column;align-items:stretch;gap:8px;max-width:220px;">
              <input name="team_name" placeholder="Team name" required>
              <input name="faculty_mentor_name" placeholder="Faculty mentor" required>
              <input name="faculty_mentor_email" placeholder="Mentor email" required>
              <input name="student_names" placeholder="Students (comma-separated)">
              <button class="b" type="submit">Form team</button>
            </form>"""
        elif team is not None and proposal is None:
            actions = _proposal_dialog(m)
        elif proposal is not None:
            doc_url = doc_urls.get(proposal.solution_document_media_id) if proposal.solution_document_media_id else None
            actions = f"Proposal: {proposal.title} ({proposal.status})"
            if doc_url:
                actions += f"<br><a href='{doc_url}' target='_blank' rel='noopener'>View solution PDF ↗</a>"

        badge = _MATCH_BADGE.get(m.status, "review_required")
        info = ticket_info.get(m.ticket_id)
        rows += (
            f"<tr><td>{m.id}</td><td><span class='badge {badge}'>{m.status}</span></td>"
            f"<td>{m.similarity_score:.0%}</td><td>{_problem_cell(info)}</td>"
            f"<td>{_location_cell(info)}</td><td>{actions}</td></tr>"
        )
    matches_table = (
        f'<table class="admin"><tr><th>Match ID</th><th>Status</th><th>Confidence</th>'
        f'<th>Problem</th><th>Location</th><th>Action</th></tr>{rows}</table>'
        if matches else '<div class="empty"><span class="empty-icon">📭</span>No R&amp;D matches yet.</div>'
    )

    matched_ticket_ids = {m.ticket_id for m in matches}
    broadcast_rows = "".join(
        f"<tr><td>#{b['rank']}</td><td>Ticket #{b['ticket_id']}</td><td>{b['similarity_score']:.0%}</td>"
        f"<td>{b['sent_at'].strftime('%d %b %Y')}</td>"
        f"<td><button class='ghost' onclick=\"document.getElementById('brief-{b['id']}').classList.toggle('hidden')\">View brief</button>"
        + (
            f"<form method='post' action='/university/collaborate/{b['ticket_id']}' style='display:inline'>"
            f"<button class='b'>Register interest</button></form>"
            if b["ticket_id"] not in matched_ticket_ids else ""
        )
        + "</td></tr>"
        f"<tr id='brief-{b['id']}' class='hidden'><td colspan='5'>{b['brief_html']}</td></tr>"
        for b in broadcasts
    )
    broadcasts_section = (
        f'<table class="admin"><tr><th>Rank</th><th>Ticket</th><th>Confidence</th><th>Sent</th><th></th></tr>{broadcast_rows}</table>'
        if broadcasts else '<div class="empty"><span class="empty-icon">📨</span>No problem briefs received yet.</div>'
    )

    body = f"""
    <div class="card">
      <p>{hei.contact_email} &middot; <form method="post" action="/university/logout" style="display:inline"><button class="ghost" style="width:auto;padding:6px 12px;">Log out</button></form></p>
    </div>
    <div class="card">
      <h3>Your R&amp;D matches</h3>
      {matches_table}
    </div>
    <div class="card">
      <h3>Problem briefs you've received</h3>
      <p class="hint">Your institution was among the top matches for these opportunities.
      Register interest to join the collaboration directly, even on ones where another
      institution already holds the primary match - multiple institutions can work on the
      same ticket at once.</p>
      {broadcasts_section}
    </div>
    <style>.hidden {{ display: none; }}</style>
    """
    return _page(f"University Portal - {hei.institution_name}", "🎓", hei.institution_name, body, max_width=900)


def _media_download_url(bucket: Optional[str], object_key: Optional[str]) -> Optional[str]:
    if not bucket or not object_key:
        return None
    return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{bucket}/{object_key}"


@app.get("/university/dashboard", response_class=HTMLResponse)
def university_dashboard(hei: HeiRegistry = Depends(_current_hei), db: Session = Depends(get_db)):
    matches = db.query(HeiMatch).filter(HeiMatch.hei_id == hei.id).order_by(HeiMatch.created_at.desc()).all()
    match_ids = [m.id for m in matches]
    teams_by_match = {t.match_id: t for t in db.query(Team).filter(Team.match_id.in_(match_ids)).all()} if match_ids else {}
    team_ids = [t.id for t in teams_by_match.values()]
    proposals_by_team = {p.team_id: p for p in db.query(Proposal).filter(Proposal.team_id.in_(team_ids)).all()} if team_ids else {}
    proposals_by_match = {match_id: proposals_by_team.get(team.id) for match_id, team in teams_by_match.items() if team.id in proposals_by_team}

    # Batched (not N+1) - same "one extra query, not one per row" pattern
    # list_pending_matches() already uses for the Admin Portal, extended
    # with the report photo (media_objects join, same as app/brief.py) and
    # raw lat/lon (ST_Y/ST_X, same as app/brief.py) for the map link.
    ticket_ids = {m.ticket_id for m in matches}
    ticket_info: dict[int, dict] = {}
    if ticket_ids:
        rows = db.execute(
            text(
                """
                SELECT t.id, t.standardized_problem_statement, t.domain,
                       ST_Y(t.geom) AS latitude, ST_X(t.geom) AS longitude,
                       photo.bucket AS photo_bucket, photo.object_key AS photo_object_key
                FROM active_tickets t
                LEFT JOIN media_objects photo ON photo.id = t.report_photo_media_id
                WHERE t.id = ANY(:ids)
                """
            ),
            {"ids": list(ticket_ids)},
        ).mappings()
        ticket_info = {row["id"]: dict(row) for row in rows}

    # Solution document download links, batched the same way.
    doc_media_ids = {p.solution_document_media_id for p in proposals_by_team.values() if p.solution_document_media_id}
    doc_urls: dict[int, str] = {}
    if doc_media_ids:
        rows = db.execute(
            text("SELECT id, bucket, object_key FROM media_objects WHERE id = ANY(:ids)"),
            {"ids": list(doc_media_ids)},
        ).mappings()
        doc_urls = {row["id"]: _media_download_url(row["bucket"], row["object_key"]) for row in rows}

    broadcasts = [
        dict(row) for row in db.execute(
            text(
                "SELECT id, ticket_id, rank, similarity_score, brief_html, sent_at FROM hei_broadcast_notices "
                "WHERE hei_id = :hei_id ORDER BY sent_at DESC"
            ),
            {"hei_id": hei.id},
        ).mappings().all()
    ]
    return HTMLResponse(_dashboard_html(hei, matches, teams_by_match, proposals_by_match, broadcasts, ticket_info, doc_urls))


def _upload_solution_document(file: Optional[UploadFile]) -> Optional[int]:
    """Best-effort: a storage/upload failure must never block proposal
    submission itself, same "the real thing already happened, don't lose
    it over a registration hiccup" stance app/object_storage.py takes -
    here it's stronger still, since the proposal text is the primary
    content and the PDF is a supporting attachment."""
    if file is None or not file.filename:
        return None
    try:
        data = file.file.read()
        if not data:
            return None
        object_key = storage.build_object_key("proposal-solutions", file.filename, default_ext=".pdf")
        uploaded = storage.upload(
            data, media_type="document",
            content_type=file.content_type or "application/pdf",
            object_key=object_key, original_filename=file.filename,
        )
        return uploaded.media_id
    except Exception:
        logger.warning("solution document upload failed - proposal will still be saved without it", exc_info=True)
        return None


def _owned_match(db: Session, hei: HeiRegistry, match_id: int) -> HeiMatch:
    match = db.query(HeiMatch).filter(HeiMatch.id == match_id).one_or_none()
    if match is None or match.hei_id != hei.id:
        raise HTTPException(status_code=404, detail="match not found")
    return match


@app.post("/university/matches/{match_id}/decide")
def university_decide(match_id: int, decision: str = Form(...), reason: Optional[str] = Form(default=None), hei: HeiRegistry = Depends(_current_hei), db: Session = Depends(get_db)):
    if decision not in ("accept", "decline"):
        raise HTTPException(status_code=400, detail="decision must be accept or decline")
    match = _owned_match(db, hei, match_id)
    try:
        apply_decision(db, match, decision, reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return RedirectResponse(url="/university/dashboard", status_code=303)


@app.post("/university/matches/{match_id}/team")
def university_form_team(match_id: int, team_name: str = Form(...), faculty_mentor_name: str = Form(...), faculty_mentor_email: str = Form(...), student_names: str = Form(default=""), hei: HeiRegistry = Depends(_current_hei), db: Session = Depends(get_db)):
    _owned_match(db, hei, match_id)  # ownership check
    names = [n.strip() for n in student_names.split(",") if n.strip()]
    try:
        form_team(db, match_id, team_name, faculty_mentor_name, faculty_mentor_email, names)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return RedirectResponse(url="/university/dashboard", status_code=303)


@app.post("/university/matches/{match_id}/proposal")
def university_submit_proposal(
    match_id: int, title: str = Form(...), summary: str = Form(...),
    requested_budget: Optional[float] = Form(default=None), timeline_weeks: Optional[int] = Form(default=None),
    solution_document: Optional[UploadFile] = File(default=None),
    hei: HeiRegistry = Depends(_current_hei), db: Session = Depends(get_db),
):
    _owned_match(db, hei, match_id)  # ownership check
    team = db.query(Team).filter(Team.match_id == match_id).order_by(Team.id.desc()).first()
    if team is None:
        raise HTTPException(status_code=409, detail="no team formed yet for this match")
    solution_document_media_id = _upload_solution_document(solution_document)
    submit_proposal(db, team.id, title, summary, requested_budget, timeline_weeks, solution_document_media_id)
    return RedirectResponse(url="/university/dashboard", status_code=303)


@app.post("/university/collaborate/{ticket_id}")
def university_collaborate(ticket_id: int, hei: HeiRegistry = Depends(_current_hei), db: Session = Depends(get_db)):
    """Multi-institution simultaneous collaboration: a broadcasted HEI
    self-joins a ticket's collaboration directly from its "Problem briefs
    you've received" dashboard section (app/matcher.py::register_interest) -
    independent of whichever HEI holds the primary accepted match."""
    try:
        register_interest(db, ticket_id, hei.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return RedirectResponse(url="/university/dashboard", status_code=303)

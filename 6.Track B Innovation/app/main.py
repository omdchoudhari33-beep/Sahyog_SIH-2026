from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, Form, Header, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import InvalidCredentialsError, SessionExpiredError, login as auth_login, logout as auth_logout, resolve_session
from app.config import settings
from app.db import HeiMatch, HeiRegistry, Proposal, SessionLocal, Team, get_db
from app.matcher import apply_decision, create_match, decide_match, reconcile as reconcile_matches
from app.onboarding import onboard_hei
from app.schemas import (
    HeiMatchOut,
    ProposalOut,
    ReconcileResult,
    TrackBAck,
)
from app.teams import form_team, nodal_decide, submit_proposal

logger = logging.getLogger("trackb_innovation")


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
    return [ProposalOut.model_validate(p) for p in proposals]


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
        <p>You have a proposed R&amp;D match (attempt {match.attempt_no}, similarity {match.similarity_score:.0%}).</p>
        <form method="post" action="/hei/{token}/decide">
          <button name="decision" value="accept" type="submit">Accept</button>
          <button name="decision" value="decline" type="submit">Decline</button>
          <p>Reason (if declining): <input name="reason"></p>
        </form>
        """
    elif match.status == "accepted":
        body = f"""
        <p>Match accepted. Form your team below.</p>
        <form method="post" action="/hei/{token}/team">
          <label>Team name <input name="team_name" required></label>
          <label>Faculty mentor name <input name="faculty_mentor_name" required></label>
          <label>Faculty mentor email <input name="faculty_mentor_email" type="email" required></label>
          <label>Student names (comma-separated) <input name="student_names"></label>
          <button type="submit">Form team</button>
        </form>
        """
    else:
        body = f"<p>This match was {match.status}.</p>"

    return f"""
    <!DOCTYPE html>
    <html><head><title>SAHYOG Track B - HEI Match</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body {{ font-family: sans-serif; max-width: 480px; margin: 40px auto; padding: 0 16px; }}
    button {{ display:block; width:100%; padding:12px; margin:8px 0; font-size:16px; }}
    .msg {{ color:#a00; }}</style></head>
    <body><h2>SAHYOG Track B</h2>{f'<p class="msg">{message}</p>' if message else ''}{body}</body></html>
    """


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
    return HTMLResponse("""
    <!DOCTYPE html><html><head><title>Onboard HEI</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body{font-family:sans-serif;max-width:480px;margin:40px auto;padding:0 16px}
    label{display:block;margin-top:12px}input{width:100%;padding:8px}button{margin-top:16px;padding:10px 16px}</style>
    </head><body><h2>Onboard an HEI</h2>
    <form method="post" action="/admin/onboard-hei">
      <label>Institution name <input name="institution_name" required></label>
      <label>State <input name="state" required></label>
      <label>District <input name="district"></label>
      <label>Contact email <input name="contact_email" type="email" required></label>
      <label>Contact phone <input name="contact_phone"></label>
      <label>Incubator name <input name="incubator_name"></label>
      <label>Capacity (concurrent active projects) <input name="capacity_active_projects" type="number" value="3"></label>
      <label>Domain (e.g. ROADS_BRIDGES) <input name="domain" required></label>
      <label>Department name <input name="department_name" required></label>
      <label>Capability description <input name="description" required></label>
      <label>University Portal password (leave blank to auto-generate one)
        <input name="initial_password"></label>
      <button type="submit">Add HEI</button>
    </form>
    <p style="color:#666;font-size:13px">The response after submitting shows the
    plaintext password once - relay it to the HEI. Login at
    <a href="/university/login">/university/login</a>.</p>
    </body></html>
    """)


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


@app.get("/admin/nodal-review", response_class=HTMLResponse, dependencies=[Depends(require_admin_password)])
def nodal_review_list(db: Session = Depends(get_db)):
    proposals = db.query(Proposal).filter(Proposal.status.in_(["submitted", "nodal_review"])).order_by(Proposal.submitted_at).all()
    rows = "".join(
        f"<tr><td>{p.id}</td><td>{p.title}</td><td>{p.summary[:80]}</td><td>{p.requested_budget}</td>"
        f"<td><form method='post' action='/admin/nodal-review/{p.id}'>"
        f"<button name='decision' value='approved'>Approve</button>"
        f"<button name='decision' value='rejected'>Reject</button>"
        f"<button name='decision' value='revision_requested'>Request revision</button>"
        f"<input name='notes' placeholder='notes'><input name='nodal_officer_id' placeholder='your id'>"
        f"</form></td></tr>"
        for p in proposals
    )
    return HTMLResponse(f"""
    <!DOCTYPE html><html><head><title>Nodal Review</title>
    <meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body><h2>Proposals pending nodal review</h2>
    <table border="1" cellpadding="6"><tr><th>ID</th><th>Title</th><th>Summary</th><th>Budget</th><th>Action</th></tr>
    {rows}</table></body></html>
    """)


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
    return f"""
    <!DOCTYPE html><html><head><title>University Portal - Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body{{font-family:sans-serif;max-width:400px;margin:60px auto;padding:0 16px}}
    label{{display:block;margin-top:12px}}input{{width:100%;padding:8px}}
    button{{margin-top:16px;padding:10px 16px;width:100%}}.msg{{color:#a00}}</style></head>
    <body><h2>University Portal</h2>
    {f'<p class="msg">{message}</p>' if message else ''}
    <form method="post" action="/university/login">
      <label>Registered email <input name="email" type="email" required></label>
      <label>Password <input name="password" type="password" required></label>
      <button type="submit">Log in</button>
    </form></body></html>
    """


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


def _dashboard_html(hei: HeiRegistry, matches: list[HeiMatch], teams_by_match: dict, proposals_by_match: dict) -> str:
    rows = ""
    for m in matches:
        team = teams_by_match.get(m.id)
        proposal = proposals_by_match.get(m.id)
        actions = ""
        if m.status == "proposed":
            actions = f"""
            <form method="post" action="/university/matches/{m.id}/decide" style="display:inline">
              <button name="decision" value="accept">Accept</button>
              <button name="decision" value="decline">Decline</button>
            </form>"""
        elif m.status == "accepted" and team is None:
            actions = f"""
            <form method="post" action="/university/matches/{m.id}/team">
              <input name="team_name" placeholder="Team name" required>
              <input name="faculty_mentor_name" placeholder="Faculty mentor" required>
              <input name="faculty_mentor_email" placeholder="Mentor email" type="email" required>
              <input name="student_names" placeholder="Students (comma-separated)">
              <button type="submit">Form team</button>
            </form>"""
        elif team is not None and proposal is None:
            actions = f"""
            <form method="post" action="/university/matches/{m.id}/proposal">
              <input name="title" placeholder="Proposal title" required>
              <input name="summary" placeholder="Summary" required>
              <input name="requested_budget" placeholder="Budget" type="number" step="0.01">
              <input name="timeline_weeks" placeholder="Timeline (weeks)" type="number">
              <button type="submit">Submit proposal</button>
            </form>"""
        elif proposal is not None:
            actions = f"Proposal: {proposal.title} ({proposal.status})"

        rows += f"<tr><td>{m.id}</td><td>{m.status}</td><td>{m.similarity_score:.0%}</td><td>{actions}</td></tr>"

    return f"""
    <!DOCTYPE html><html><head><title>University Portal - {hei.institution_name}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body{{font-family:sans-serif;max-width:900px;margin:40px auto;padding:0 16px}}
    table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px}}
    form{{display:inline-block}} input{{width:auto;margin:2px}}</style></head>
    <body>
      <h2>{hei.institution_name}</h2>
      <p>{hei.contact_email} &middot; <form method="post" action="/university/logout" style="display:inline"><button>Log out</button></form></p>
      <h3>Your R&amp;D matches</h3>
      <table><tr><th>Match ID</th><th>Status</th><th>Confidence</th><th>Action</th></tr>{rows}</table>
    </body></html>
    """


@app.get("/university/dashboard", response_class=HTMLResponse)
def university_dashboard(hei: HeiRegistry = Depends(_current_hei), db: Session = Depends(get_db)):
    matches = db.query(HeiMatch).filter(HeiMatch.hei_id == hei.id).order_by(HeiMatch.created_at.desc()).all()
    match_ids = [m.id for m in matches]
    teams_by_match = {t.match_id: t for t in db.query(Team).filter(Team.match_id.in_(match_ids)).all()} if match_ids else {}
    team_ids = [t.id for t in teams_by_match.values()]
    proposals_by_team = {p.team_id: p for p in db.query(Proposal).filter(Proposal.team_id.in_(team_ids)).all()} if team_ids else {}
    proposals_by_match = {match_id: proposals_by_team.get(team.id) for match_id, team in teams_by_match.items() if team.id in proposals_by_team}
    return HTMLResponse(_dashboard_html(hei, matches, teams_by_match, proposals_by_match))


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
def university_submit_proposal(match_id: int, title: str = Form(...), summary: str = Form(...), requested_budget: Optional[float] = Form(default=None), timeline_weeks: Optional[int] = Form(default=None), hei: HeiRegistry = Depends(_current_hei), db: Session = Depends(get_db)):
    _owned_match(db, hei, match_id)  # ownership check
    team = db.query(Team).filter(Team.match_id == match_id).order_by(Team.id.desc()).first()
    if team is None:
        raise HTTPException(status_code=409, detail="no team formed yet for this match")
    submit_proposal(db, team.id, title, summary, requested_budget, timeline_weeks)
    return RedirectResponse(url="/university/dashboard", status_code=303)

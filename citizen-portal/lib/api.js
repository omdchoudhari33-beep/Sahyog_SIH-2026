// Thin fetch wrappers around the real backend contracts (verified by reading
// each service's source, not guessed from the spec doc). There is no mock
// fallback - a failed call throws, and the caller shows a real error/retry
// state (see components/LoadError.js) instead of substituting fake data.

import { getStaffToken } from "@/lib/auth";

const ORCHESTRATOR_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://127.0.0.1:8005";
const AGENT1_URL = process.env.NEXT_PUBLIC_AGENT1_URL || "http://127.0.0.1:8001";
const AGENT2_URL = process.env.NEXT_PUBLIC_AGENT2_URL || "http://127.0.0.1:8002";
const AGENT3_URL = process.env.NEXT_PUBLIC_AGENT3_URL || "http://127.0.0.1:8003";
const AGENT9_URL = process.env.NEXT_PUBLIC_AGENT9_URL || "http://127.0.0.1:8009";

// Attaches the signed-in staff member's Basic-auth token (see lib/auth.js)
// to a request going to one of the Orchestrator's admin-gated proxy routes.
function authHeaders(portal) {
  const token = getStaffToken(portal);
  return token ? { Authorization: token } : {};
}

const DEFAULT_TIMEOUT_MS = 8000;

async function request(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || DEFAULT_TIMEOUT_MS);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      // Every backend here is FastAPI - error bodies are {"detail": "..."}.
      // Surface that specific message (e.g. "Voice recording isn't
      // available in this language yet") instead of a raw status code, so
      // callers showing err.message directly give the citizen something
      // actionable rather than "422 Unprocessable Entity: ...".
      let detail = null;
      try {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
      } catch {
        // Not JSON (or no body) - fall through to the raw status line below.
      }
      const err = new Error(detail || `${res.status} ${res.statusText}: ${text.slice(0, 300)}`);
      err.status = res.status;
      throw err;
    }
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) return await res.json();
    return await res.text();
  } catch (err) {
    // A timed-out AbortController makes fetch() reject with a raw browser
    // DOMException ("signal is aborted without reason" in Chromium, "The
    // user aborted a request." in Firefox/Safari) - neither means anything
    // to a citizen, and every caller in this file does
    // `setError(err?.message || t("common.errorGeneric"))`, which shows
    // err.message verbatim whenever it's set. Tagging it here lets callers
    // tell "the backend told us something specific" (detail message above)
    // apart from "the browser gave up waiting" and show a real, translated
    // message for the latter instead of leaking the raw exception text.
    if (err.name === "AbortError") {
      const timeoutErr = new Error("Request timed out.");
      timeoutErr.isTimeout = true;
      throw timeoutErr;
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

function postJson(url, body, opts = {}) {
  return request(url, {
    method: "POST",
    ...opts,
    headers: { "Content-Type": "application/json", ...opts.headers },
    body: JSON.stringify(body),
  });
}

function postForm(url, formData, opts) {
  return request(url, { method: "POST", body: formData, ...opts });
}

// ---------------------------------------------------------------------------
// Agent 1 - Language Normalizer (audio -> local path + transcription)
// ---------------------------------------------------------------------------

// Uploads a recorded voice note. Returns { local_audio_path, transcription, ... }.
// The local_audio_path is what gets forwarded to the orchestrator's
// /conversation/{id}/describe form field of the same name.
export function uploadAudio(audioBlob, filename = "recording.webm") {
  const form = new FormData();
  form.append("file", audioBlob, filename);
  return postForm(`${AGENT1_URL}/api/v1/audio/upload`, form, { timeoutMs: 30000 });
}

// ---------------------------------------------------------------------------
// Orchestrator - owns conversation/session state and HMAC-signs downstream
// calls, so the submit wizard talks to it rather than Agent 2/3 directly.
// There is no separate "start session" call: /conversation/describe both
// creates the session AND handles turn 1, returning the new session_id.
// ---------------------------------------------------------------------------

// Turn 1. Exactly one of text / localAudioPath (from uploadAudio) / audioFile
// should be given. Returns { session_id, state, understood_statement,
// domain, severity, suggested_track, warning, message }.
//
// timeoutMs is generous (6 minutes) because audio input for Santali/Urdu
// routes through the self-hosted ASR/TTS models in santali-voice-service
// (see "1.Language normalizer/app/services/santali_local.py"), which can
// genuinely take much longer than Bhashini's hosted API, especially under
// concurrent load on that container's single GPU queue - a real citizen
// recording live-tested at 120.75s and got a 502 from Agent1's OWN ASR
// client timing out at (then) 120s even though the container was still
// genuinely working; that was raised to 300s, so this and the
// Orchestrator's own internal timeout (see 4.Orchestrator/app/config.py's
// request_timeout_seconds) both need to stay comfortably above the
// worst-case ASR-then-translate chain rather than below it.
export function describeProblem({ text, localAudioPath, audioFile, sourceLanguage }) {
  const form = new FormData();
  if (text) form.append("text", text);
  if (localAudioPath) form.append("local_audio_path", localAudioPath);
  if (audioFile) form.append("audio", audioFile);
  if (sourceLanguage) form.append("source_language", sourceLanguage);
  return postForm(`${ORCHESTRATOR_URL}/conversation/describe`, form, { timeoutMs: 360000 });
}

// Turn 2. Returns { session_id, state, understood_statement, message }.
export function confirmProblem(sessionId, { confirmed, correctedText }) {
  return postJson(`${ORCHESTRATOR_URL}/conversation/${sessionId}/confirm`, {
    confirmed,
    corrected_text: correctedText ?? null,
  });
}

// Turn 3. state comes back "ready" (EXIF/device geo was enough - skip the
// location step) or "awaiting_location" (show it). Returns { session_id,
// state, photo_matches, discrepancy_notes?, message }.
//
// timeoutMs matches describeProblem()'s reasoning above, not a shorter
// guess: this triggers Agent 2's C2 geo + C3 vision (Ollama/LLaVA) chain,
// and that vision call alone "can take minutes on a cold-loaded local
// model" (see "2.Evidence Extractor" and the Orchestrator's own
// request_timeout_seconds comment) - a 30s client timeout here previously
// aborted the request mid-processing on exactly that cold-start case,
// surfacing a raw "signal is aborted without reason" browser exception to
// the citizen instead of ever reaching a real success or error response.
export function attachPhoto(sessionId, imageFile, { deviceLat, deviceLon, deviceTimestamp, force = false } = {}) {
  const form = new FormData();
  form.append("image", imageFile);
  if (deviceLat != null) form.append("device_lat", String(deviceLat));
  if (deviceLon != null) form.append("device_lon", String(deviceLon));
  if (deviceTimestamp) form.append("device_timestamp", deviceTimestamp);
  if (force) form.append("force", "true");
  return postForm(`${ORCHESTRATOR_URL}/conversation/${sessionId}/photo`, form, {
    timeoutMs: 360000,
  });
}

// Turn 4 (only reached if attachPhoto returned state "awaiting_location").
// Provide either {latitude, longitude} or {addressText}, not both.
export function submitLocation(sessionId, { latitude, longitude, addressText }) {
  return postJson(`${ORCHESTRATOR_URL}/conversation/${sessionId}/location`, {
    latitude: latitude ?? null,
    longitude: longitude ?? null,
    address_text: addressText ?? null,
  });
}

// Final turn. Returns { session_id, state, ticket, message } where ticket
// is Agent 3's ingest response (includes ticket_id).
export function finalizeReport(sessionId) {
  return request(`${ORCHESTRATOR_URL}/conversation/${sessionId}/finalize`, { method: "POST" });
}

// Voice bot's spoken side: hands the (always-English) conversational
// `message` text from any of the calls above to the Orchestrator's /speak
// proxy, which translates it into `language` and synthesizes it via
// Bhashini TTS server-side - this function only ever deals with English
// input and an audio Blob output, no translation logic here.
// Returns null (not an error) when speech isn't available for this
// language/text, exactly like the backend's own "204 = stay silent"
// contract - callers must treat voice as optional, same as the backend does.
// timeoutMs is generous (5 minutes) for the same reason as
// describeProblem() above - Santali/Urdu replies synthesize speech via
// the self-hosted model in santali-voice-service, not Bhashini's hosted
// API, and that can genuinely take a while under load. Voice replies are
// already optional/best-effort (see this function's own docstring), so a
// long wait here just delays a nice-to-have, it never blocks the citizen
// from continuing - unlike describeProblem(), where a premature timeout
// would incorrectly report the whole submission as failed.
export async function speakText(text, language) {
  if (!text) return null;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 300000);
  try {
    const res = await fetch(`${ORCHESTRATOR_URL}/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language: language || "en" }),
      signal: controller.signal,
    });
    if (res.status === 204 || !res.ok) return null;
    return await res.blob();
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

// "Ask Sahyog" RAG Q&A - proxied through the Orchestrator's /ask, which
// normalizes non-English questions via Agent 1 before handing them to
// Agent 3's retrieval+generation pipeline. Unlike speakText, a failure here
// throws (via request()/postJson()) so the ask page can show a real error.
export function askQuestion(question, language) {
  return postJson(`${ORCHESTRATOR_URL}/ask`, { question, language: language || "en" }, { timeoutMs: 90000 });
}

// ---------------------------------------------------------------------------
// Agent 3 - Triage & Route. Its /dno/* routes have no authentication at all
// (confirmed by reading "3.Triage and route/app/main.py") and are CORS-open
// to this origin - that's the citizen-facing home feed's real, on-purpose
// backend, called directly and unauthenticated below. The OPERATOR portal
// reads the identical data through a different, authenticated door instead
// (the Orchestrator's /api/tickets* proxy, gated by verifyStaffCredentials
// in lib/auth.js) because operator actions need real access control; the
// underlying ticket rows are the same either way, just two different
// front doors for two different trust levels onto one real database.
// ---------------------------------------------------------------------------

// Public citizen feed (home page) - no login, no staff token involved.
// status: "all" - without it, /dno/tickets defaults to active-only (its
// other caller, the operator queue's actual job queue), which silently
// drained this feed to empty the moment any ticket got triaged - see
// "3.Triage and route/app/main.py"'s get_dno_tickets docstring.
export function listPublicTickets(params = {}) {
  const qs = new URLSearchParams({ status: "all", ...params }).toString();
  return request(`${AGENT3_URL}/dno/tickets${qs ? `?${qs}` : ""}`);
}

export function listTickets(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`${ORCHESTRATOR_URL}/api/tickets${qs ? `?${qs}` : ""}`, {
    headers: authHeaders("operator"),
  });
}

export function getTicket(ticketId) {
  return request(`${ORCHESTRATOR_URL}/api/tickets/${ticketId}`, {
    headers: authHeaders("operator"),
  });
}

// decision is one of "track_a" | "track_b" | "reject_merge" - the real,
// complete set (see app/validation.py's VALID_DECISIONS). There is no
// separate "request more info" action or a granular duplicate-cluster
// picker on the real backend, so this UI doesn't offer either.
export function postDecision(ticketId, { decision, operatorId, notes }) {
  return postJson(
    `${ORCHESTRATOR_URL}/api/tickets/${ticketId}/decision`,
    { decision, operator_id: operatorId ?? null, notes: notes ?? null },
    { headers: authHeaders("operator") }
  );
}

export function recalculatePriority(ticketId) {
  return request(`${ORCHESTRATOR_URL}/api/tickets/${ticketId}/recalculate`, {
    method: "POST",
    headers: authHeaders("operator"),
  });
}

// ---------------------------------------------------------------------------
// Institution portal - Agents 6/7/8 have no browser-safe API of their own
// (internal-token service calls or server-rendered cookie sessions only),
// so these go through the Orchestrator's admin proxy routes, same as the
// operator portal above and the same shared staff credential.
// ---------------------------------------------------------------------------

export function getInstitutionMatches() {
  return request(`${ORCHESTRATOR_URL}/api/admin/track-b/matches`, {
    headers: authHeaders("institution"),
  });
}

export function decideInstitutionMatch(matchId, { decision, reason }) {
  return postJson(
    `${ORCHESTRATOR_URL}/api/admin/track-b/matches/${matchId}/decide`,
    { decision, reason: reason ?? null },
    { headers: authHeaders("institution") }
  );
}

// TB3 - only valid once decideInstitutionMatch() has accepted this match
// (form_team() in "6.Track B Innovation/app/teams.py" rejects it otherwise).
export function formInstitutionTeam(matchId, { teamName, mentorName, mentorEmail, students }) {
  return postJson(
    `${ORCHESTRATOR_URL}/api/admin/track-b/matches/${matchId}/team`,
    {
      team_name: teamName,
      faculty_mentor_name: mentorName,
      faculty_mentor_email: mentorEmail,
      student_names: students,
    },
    { headers: authHeaders("institution") }
  );
}

// TB4 - the "summary" field carries the institution's solution + researched
// analysis of the problem as free text; solutionDocument (a PDF) is optional
// and forwarded through the Orchestrator to Agent 6's object-storage upload
// (see "6.Track B Innovation/app/main.py"'s _upload_solution_document) -
// a failed upload there doesn't block the proposal itself, only its PDF.
export function submitInstitutionProposal(matchId, { title, summary, budget, timelineWeeks, solutionDocument }) {
  const form = new FormData();
  form.append("title", title);
  form.append("summary", summary);
  if (budget != null && budget !== "") form.append("requested_budget", String(budget));
  if (timelineWeeks != null && timelineWeeks !== "") form.append("timeline_weeks", String(timelineWeeks));
  if (solutionDocument) form.append("solution_document", solutionDocument);
  return postForm(`${ORCHESTRATOR_URL}/api/admin/track-b/matches/${matchId}/proposal`, form, {
    headers: authHeaders("institution"),
    timeoutMs: 60000,
  });
}

export function getInstitutionProjects() {
  return request(`${ORCHESTRATOR_URL}/api/admin/lifecycle/pending`, {
    headers: authHeaders("institution"),
  });
}

export function submitInstitutionDisposition(ticketId, { proposalId, disposition, notes, startupName, incubatorName }) {
  return postJson(
    `${ORCHESTRATOR_URL}/api/admin/lifecycle/${ticketId}/disposition`,
    {
      proposal_id: proposalId,
      disposition,
      notes: notes ?? null,
      startup_name: startupName ?? null,
      incubator_name: incubatorName ?? null,
    },
    { headers: authHeaders("institution") }
  );
}

export function getInstitutionPartners() {
  return request(`${ORCHESTRATOR_URL}/api/admin/industry/ledgers`, {
    headers: authHeaders("institution"),
  });
}

export function releasePartnerFunds(ledgerId, { amount, releasedBy, milestoneId }) {
  return postJson(
    `${ORCHESTRATOR_URL}/api/admin/industry/ledgers/${ledgerId}/release`,
    { amount, released_by: releasedBy, milestone_id: milestoneId ?? null },
    { headers: authHeaders("institution") }
  );
}

// ---------------------------------------------------------------------------
// Agent 9 - Transparency Layer
// ---------------------------------------------------------------------------

export function getTransparencyDashboard() {
  return request(`${AGENT9_URL}/transparency/dashboard.json`);
}

export function getTicketStatus(ticketId) {
  return request(`${AGENT9_URL}/status/${ticketId}.json`);
}

// Real audit-log read endpoint (added alongside the pre-existing write-only
// /audit/log) - public, same trust level as the dashboard/status endpoints
// above. params: entity_type, entity_id, service_name, from_date, to_date,
// limit, offset (all optional).
export function getAuditLog(params = {}) {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
  const qs = new URLSearchParams(clean).toString();
  return request(`${AGENT9_URL}/audit${qs ? `?${qs}` : ""}`);
}

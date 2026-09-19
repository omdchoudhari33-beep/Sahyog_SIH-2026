// Real credential check for the two staff portals, backed by the
// Orchestrator's existing HTTPBasic admin gate (ADMIN_PORTAL_PASSWORD),
// the same trust boundary that already protects /api/tickets* and
// /api/admin/* (see "4.Orchestrator/app/main.py"). Both portals share one
// admin credential - there's no separate per-institution login exposed as
// a JSON API yet (Agent 6's real per-HEI login is a server-rendered cookie
// session), so this is the honest scope: real auth, one shared role.
const ORCHESTRATOR_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://127.0.0.1:8005";
const TOKEN_PREFIX = "sahyog_staff_token_";

function buildBasicAuthHeader(password) {
  const encoded = typeof window !== "undefined" ? window.btoa(`staff:${password}`) : "";
  return `Basic ${encoded}`;
}

// Verifies the password against the live backend (a cheap already-admin-gated
// GET) before granting UI access. Returns { ok: true } or { ok: false, error }.
export async function verifyStaffCredentials(portal, password) {
  const authHeader = buildBasicAuthHeader(password);
  try {
    const res = await fetch(`${ORCHESTRATOR_URL}/api/tickets?limit=1`, {
      headers: { Authorization: authHeader },
    });
    if (!res.ok) {
      return { ok: false, error: res.status === 401 ? "invalid_credentials" : "server_error" };
    }
    try {
      window.sessionStorage.setItem(TOKEN_PREFIX + portal, authHeader);
    } catch {
      // Non-fatal: the portal just re-prompts for sign-in next render.
    }
    return { ok: true };
  } catch {
    return { ok: false, error: "network_error" };
  }
}

export function getStaffToken(portal) {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(TOKEN_PREFIX + portal);
  } catch {
    return null;
  }
}

export function isStaffSignedIn(portal) {
  return Boolean(getStaffToken(portal));
}

export function clearStaffSignedIn(portal) {
  try {
    window.sessionStorage.removeItem(TOKEN_PREFIX + portal);
  } catch {
    // Non-fatal.
  }
}

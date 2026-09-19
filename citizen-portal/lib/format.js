// Ticket IDs are plain integers server-side (Agent 3's PK). This is a purely
// cosmetic display wrapper - lookups always use the real numeric id.
export function formatTicketId(id) {
  if (id == null) return "";
  return `JH-2026-${String(id).padStart(4, "0")}`;
}

// Accepts either a real ticket id ("42" or "JH-2026-0042") and returns the
// underlying integer, or null if it doesn't parse.
export function parseTicketId(input) {
  if (input == null) return null;
  const digits = String(input).trim().match(/(\d+)\s*$/);
  if (!digits) return null;
  const n = Number(digits[1]);
  return Number.isFinite(n) ? n : null;
}

// Simple relative age ("3h", "2d") for a priority queue - operators care
// about how long a ticket has been waiting more than the exact timestamp.
export function formatAge(iso) {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const minutes = Math.max(0, Math.floor((Date.now() - then) / 60000));
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

// Shared with StepDescribe (pre-submit "understood" preview) and StepDone
// (post-submit brief receipt) - one severity->word mapping so the two
// never drift apart on what "High" means.
const SEVERITY_LABELS = {
  en: ["Low", "Medium", "High"],
  hi: ["कम", "मध्यम", "उच्च"],
  bn: ["কম", "মাঝারি", "বেশি"],
  or: ["କମ୍", "ମଧ୍ୟମ", "ଅଧିକ"],
  ur: ["کم", "درمیانہ", "زیادہ"],
};

export function severityWord(severity, lang) {
  const words = SEVERITY_LABELS[lang] || SEVERITY_LABELS.en;
  if (severity == null) return words[1];
  if (severity < 0.4) return words[0];
  if (severity < 0.7) return words[1];
  return words[2];
}

export function formatRupees(n) {
  if (n == null) return "—";
  return `₹${Number(n).toLocaleString("en-IN")}`;
}

export function formatDate(iso, lang) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

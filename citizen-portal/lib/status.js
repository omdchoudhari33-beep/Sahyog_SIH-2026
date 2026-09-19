// Maps the two different backend shapes we render status from onto one
// shared set of citizen-facing status keys (labelled via dict.status.*):
// "registered" | "in_progress" | "resolved" | "escalated_track_b" | "merged".
//
// Neither backend response has a field that already says one of these -
// each is derived from a combination of fields, so that logic lives here
// once instead of being re-guessed in every component that renders a badge.

export const STATUS_KEYS = [
  "registered",
  "in_progress",
  "resolved",
  "escalated_track_b",
  "merged",
];

// From Agent 3's /dno/tickets item shape: { status: "active"|"validated"|
// "merged", suggested_track/ai_suggested_track: "track_a"|"track_b"|
// "review_required" }. Used for the home page's public feed.
export function deriveFeedStatus(ticket) {
  if (!ticket) return "registered";
  if (ticket.status === "merged") return "merged";
  const track = ticket.ai_suggested_track || ticket.suggested_track;
  if (ticket.status === "validated") {
    return track === "track_b" ? "escalated_track_b" : "in_progress";
  }
  return "registered";
}

// From Agent 9's /status/{id}.json shape (see lib/api.js getTicketStatus).
// Used on the /track/[ticketId] page.
export function deriveTrackStatus(statusPayload) {
  if (!statusPayload) return "registered";
  if (statusPayload.status === "merged") return "merged";

  if (statusPayload.track === "track_a") {
    return statusPayload.track_a?.status === "resolved" ? "resolved" : "in_progress";
  }

  if (statusPayload.track === "track_b") {
    const verdict = statusPayload.track_b?.pilot_validation?.verdict;
    return verdict === "pass" ? "resolved" : "escalated_track_b";
  }

  return "registered";
}

// Index of the furthest-reached stop in the Submitted -> Under Review ->
// Routed -> In Progress -> Resolved stepper (0-based) for a given /status
// payload. "merged" tickets don't follow this pipeline, so they stop at
// Under Review with their own badge explaining why.
export function timelineStepIndex(statusPayload) {
  if (!statusPayload) return 0;
  if (statusPayload.status === "merged" || !statusPayload.track) return 1;

  if (statusPayload.track === "track_a") {
    if (statusPayload.track_a?.status === "resolved") return 4;
    return statusPayload.track_a ? 3 : 2;
  }

  if (statusPayload.track === "track_b") {
    const tb = statusPayload.track_b;
    if (tb?.pilot_validation?.verdict === "pass") return 4;
    if (tb?.proposal || tb?.match || (tb?.milestones && tb.milestones.length > 0)) return 3;
    return 2;
  }

  return 2;
}

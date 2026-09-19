// Derives citizen-facing summary numbers from Agent 9's real
// /transparency/dashboard.json shape (see app.dashboard.full_dashboard in
// "9.Transparency Layer"), which has no ready-made "complaints filed" /
// "complaints resolved" totals of its own - those are honest aggregates of
// what IS there, not invented fields.

export function computeHeadlineStats(dashboard) {
  const heatmap = dashboard.district_domain_heatmap || [];
  const filed = heatmap.reduce((sum, r) => sum + (r.ticket_count || 0), 0);
  const resolved =
    (dashboard.outcomes?.track_a_resolved || 0) + (dashboard.completion_rate?.pilots_passed || 0);
  const districts = new Set(heatmap.map((r) => r.district).filter((d) => d && d !== "unassigned"));
  const institutions =
    (dashboard.hei_participation?.active_heis || 0) + (dashboard.industry_engagement?.active_partners || 0);
  return { filed, resolved, districts: districts.size, institutions };
}

export function aggregateByDistrict(dashboard) {
  const totals = new Map();
  for (const row of dashboard.district_domain_heatmap || []) {
    if (!row.district || row.district === "unassigned") continue;
    totals.set(row.district, (totals.get(row.district) || 0) + (row.ticket_count || 0));
  }
  return [...totals.entries()].map(([district, count]) => ({ district, count })).sort((a, b) => b.count - a.count);
}

export function aggregateByDomain(dashboard) {
  const totals = new Map();
  for (const row of dashboard.district_domain_heatmap || []) {
    if (!row.domain) continue;
    totals.set(row.domain, (totals.get(row.domain) || 0) + (row.ticket_count || 0));
  }
  return [...totals.entries()].map(([domain, count]) => ({ domain, count })).sort((a, b) => b.count - a.count);
}

// Best available real proxy for "how much goes to each track": Track A's
// count of dispatches actually resolved vs. Track B's tickets that reached
// the pilot-validation stage (pass/fail/pending) - there's no single
// "tickets by track" field to read directly.
export function trackSplit(dashboard) {
  const trackA = dashboard.outcomes?.track_a_resolved || 0;
  const cr = dashboard.completion_rate || {};
  const trackB = (cr.pilots_passed || 0) + (cr.pilots_failed || 0) + (cr.pilots_pending || 0);
  return { trackA, trackB };
}

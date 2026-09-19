// Plain CSS horizontal bar chart - deliberately not a charting library, per
// the brief to keep dashboards to "a couple of simple charts, nothing
// elaborate". Shared by the citizen /transparency page and the deeper
// /government dashboard so the two don't drift into two different visual
// languages for the same kind of data.
export default function SimpleChart({ rows }) {
  const max = Math.max(...rows.map((r) => r.value), 1);

  return (
    <div>
      {rows.map((row) => {
        const pct = Math.max(4, Math.round((row.value / max) * 100));
        return (
          <div key={row.label} className="flex items-center gap-3 py-1.5 text-sm">
            <span className="w-40 shrink-0 truncate text-gray-700">{row.label}</span>
            <div className="h-3 flex-1 rounded-full bg-gov-blue-50">
              <div className="h-3 rounded-full bg-gov-blue-600" style={{ width: `${pct}%` }} />
            </div>
            <span className="w-10 shrink-0 text-right font-medium text-gov-blue-800">{row.value}</span>
          </div>
        );
      })}
    </div>
  );
}

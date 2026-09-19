"use client";

import { useMemo, useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import { useStaffGate } from "@/lib/useStaffGate";
import { listTickets } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { deriveFeedStatus, STATUS_KEYS } from "@/lib/status";
import { DOMAINS, domainLabel } from "@/lib/categories";
import { formatAge } from "@/lib/format";
import TicketRow from "@/components/TicketRow";
import StatCard from "@/components/StatCard";
import LoadError from "@/components/LoadError";
import MapPanel from "@/components/MapPanel";

export default function OperatorQueuePage() {
  const { t, lang } = useLanguage();
  const ready = useStaffGate("operator");
  const [tickets, setTickets] = useState(null);
  const [error, setError] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [pageSize, setPageSize] = useState(50);
  const [hasMore, setHasMore] = useState(true);

  usePolling(
    async () => {
      try {
        const data = await listTickets({ limit: pageSize });
        const items = Array.isArray(data.items) ? data.items : [];
        setTickets(items);
        setHasMore(items.length >= pageSize);
        setError(false);
      } catch {
        setError(true);
      }
    },
    { intervalMs: 15000, enabled: ready, deps: [pageSize] }
  );

  const filtered = useMemo(() => {
    if (!tickets) return [];
    return tickets.filter((tk) => {
      const statusOk = statusFilter === "all" || deriveFeedStatus(tk) === statusFilter;
      const categoryOk = categoryFilter === "all" || tk.domain === categoryFilter;
      return statusOk && categoryOk;
    });
  }, [tickets, statusFilter, categoryFilter]);

  const analytics = useMemo(() => {
    if (!tickets || tickets.length === 0) return null;
    const byStatus = {};
    let prioritySum = 0;
    let priorityCount = 0;
    let oldest = tickets[0];
    for (const tk of tickets) {
      const s = deriveFeedStatus(tk);
      byStatus[s] = (byStatus[s] || 0) + 1;
      if (typeof tk.priority_score === "number") {
        prioritySum += tk.priority_score;
        priorityCount += 1;
      }
      if (new Date(tk.created_at).getTime() < new Date(oldest.created_at).getTime()) oldest = tk;
    }
    return {
      total: tickets.length,
      active: byStatus.active || 0,
      avgPriority: priorityCount ? (prioritySum / priorityCount).toFixed(1) : "—",
      oldestAge: formatAge(oldest.created_at),
    };
  }, [tickets]);

  if (!ready) return null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-serif text-3xl font-semibold text-gov-blue-900">{t("operator.queueTitle")}</h1>
      <p className="mt-1 text-gray-600">{t("operator.queueSub")}</p>

      {analytics && (
        <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard value={analytics.total} label={t("operator.statTotal")} />
          <StatCard value={analytics.active} label={t("operator.statActive")} />
          <StatCard value={analytics.avgPriority} label={t("operator.statAvgPriority")} />
          <StatCard value={analytics.oldestAge} label={t("operator.statOldest")} />
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-3">
        <div>
          <label htmlFor="status-filter" className="gov-label">
            {t("operator.filterStatus")}
          </label>
          <select id="status-filter" className="gov-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">{t("operator.filterAllStatuses")}</option>
            {STATUS_KEYS.map((k) => (
              <option key={k} value={k}>
                {t(`status.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="category-filter" className="gov-label">
            {t("operator.filterCategory")}
          </label>
          <select id="category-filter" className="gov-input" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
            <option value="all">{t("operator.filterAllCategories")}</option>
            {DOMAINS.map((d) => (
              <option key={d.id} value={d.id}>
                {domainLabel(d.id, lang)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {tickets && tickets.length > 0 && (
        <div className="mt-5 max-w-md">
          <MapPanel tickets={filtered} heading={t("operator.mapHeading")} caption={t("operator.mapCaption")} />
        </div>
      )}

      {tickets === null ? (
        error ? (
          <div className="mt-5">
            <LoadError />
          </div>
        ) : (
          <p className="mt-5 text-sm text-gray-500">{t("common.loading")}</p>
        )
      ) : (
        <div className="mt-5 overflow-x-auto rounded-lg border border-gov-blue-100 bg-white">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="border-b border-gov-blue-100 bg-gov-blue-50 text-xs uppercase text-gov-blue-700">
              <tr>
                <th className="px-3 py-2">{t("operator.colId")}</th>
                <th className="px-3 py-2">{t("operator.colCategory")}</th>
                <th className="px-3 py-2">{t("operator.colDescription")}</th>
                <th className="px-3 py-2">{t("operator.colSeverity")}</th>
                <th className="px-3 py-2">{t("operator.colPriority")}</th>
                <th className="px-3 py-2">{t("operator.colCluster")}</th>
                <th className="px-3 py-2">{t("operator.colAge")}</th>
                <th className="px-3 py-2">{t("operator.colStatus")}</th>
                <th className="px-3 py-2">{t("operator.colActions")}</th>
              </tr>
            </thead>
            <tbody aria-live="polite">
              {filtered.map((tk) => (
                <TicketRow key={tk.ticket_id} ticket={tk} />
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && <p className="px-3 py-6 text-sm text-gray-500">{t("operator.noTickets")}</p>}
        </div>
      )}

      {tickets && tickets.length > 0 && hasMore && (
        <div className="mt-4 text-center">
          <button type="button" className="gov-btn-secondary" onClick={() => setPageSize((n) => n + 50)}>
            {t("operator.loadMore")}
          </button>
        </div>
      )}
    </div>
  );
}

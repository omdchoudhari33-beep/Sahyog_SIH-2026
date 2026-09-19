"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageProvider";
import { useStaffGate } from "@/lib/useStaffGate";
import { domainLabel } from "@/lib/categories";
import { formatDate } from "@/lib/format";
import { decideInstitutionMatch, getInstitutionMatches } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import StatCard from "@/components/StatCard";
import AdminBadge from "@/components/AdminBadge";
import LoadError from "@/components/LoadError";
import Pagination from "@/components/Pagination";
import MapPanel from "@/components/MapPanel";

const STATUS_TONE = { proposed: "pending", accepted: "success", declined: "neutral" };
const PAGE_SIZE = 10;

export default function InstitutionMatchesPage() {
  const { t, lang } = useLanguage();
  const ready = useStaffGate("institution");
  const [matches, setMatches] = useState(null);
  const [error, setError] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    try {
      const data = await getInstitutionMatches();
      setMatches(Array.isArray(data) ? data : []);
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  usePolling(load, { intervalMs: 20000, enabled: ready });

  const stats = useMemo(() => {
    if (!matches) return null;
    return {
      total: matches.length,
      pending: matches.filter((m) => m.status === "proposed").length,
      accepted: matches.filter((m) => m.status === "accepted").length,
      declined: matches.filter((m) => m.status === "declined").length,
    };
  }, [matches]);

  const filtered = useMemo(() => {
    if (!matches) return [];
    if (statusFilter === "all") return matches;
    return matches.filter((m) => m.status === statusFilter);
  }, [matches, statusFilter]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pagedMatches = useMemo(() => filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), [filtered, page]);

  // MapPanel expects {ticket_id, lat, lon, domain} (see its own usage on the
  // operator queue and citizen home feed) - this endpoint's fields are
  // prefixed ticket_* instead, since a match wraps a ticket rather than
  // being one, so they're remapped here rather than changing the shared
  // component to know about two different field-naming conventions.
  const mapPins = useMemo(
    () =>
      filtered
        .filter((m) => m.ticket_lat != null && m.ticket_lon != null)
        .map((m) => ({ ticket_id: m.ticket_id, lat: m.ticket_lat, lon: m.ticket_lon, domain: m.ticket_domain })),
    [filtered]
  );

  // Changing the status filter (or the underlying data shrinking below the
  // current page, e.g. after a decide() action) can leave `page` pointing
  // past the end - clamp back to the last real page instead of showing blank.
  if (page > pageCount) {
    setPage(pageCount);
  }

  if (!ready) return null;

  async function decide(id, decision) {
    const previous = matches;
    setMatches((prev) => prev.map((m) => (m.id === id ? { ...m, status: decision === "accept" ? "accepted" : "declined" } : m)));
    try {
      await decideInstitutionMatch(id, { decision });
    } catch {
      setMatches(previous);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="font-serif text-3xl font-semibold text-gov-blue-900">{t("institution.inboxTitle")}</h1>
      <p className="mt-1 text-gray-600">{t("institution.inboxSub")}</p>

      {stats && (
        <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard value={stats.total} label={t("institution.statTotalMatches")} />
          <StatCard value={stats.pending} label={t("institution.statPendingMatches")} />
          <StatCard value={stats.accepted} label={t("institution.statAcceptedMatches")} />
          <StatCard value={stats.declined} label={t("institution.statDeclinedMatches")} />
        </div>
      )}

      {mapPins.length > 0 && (
        <div className="mt-5 max-w-md">
          <MapPanel tickets={mapPins} heading={t("institution.mapHeading")} caption={t("institution.mapCaption")} />
        </div>
      )}

      <div className="mt-5">
        <label htmlFor="match-status-filter" className="gov-label">
          {t("institution.filterStatus")}
        </label>
        <select
          id="match-status-filter"
          className="gov-input max-w-xs"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="all">{t("institution.filterAllStatuses")}</option>
          <option value="proposed">{t("institution.filterPending")}</option>
          <option value="accepted">{t("institution.filterAccepted")}</option>
          <option value="declined">{t("institution.filterDeclined")}</option>
        </select>
      </div>

      {matches === null ? (
        error ? (
          <div className="mt-5">
            <LoadError onRetry={load} />
          </div>
        ) : (
          <p className="mt-5 text-sm text-gray-500">{t("common.loading")}</p>
        )
      ) : (
        <div className="mt-5 overflow-x-auto rounded-lg border border-gov-blue-100 bg-white">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b border-gov-blue-100 bg-gov-blue-50 text-xs uppercase text-gov-blue-700">
              <tr>
                <th className="px-3 py-2">{t("institution.colCase")}</th>
                <th className="px-3 py-2">{t("institution.colSimilarity")}</th>
                <th className="px-3 py-2">{t("institution.colStatus")}</th>
                <th className="px-3 py-2">{t("institution.colReceived")}</th>
                <th className="px-3 py-2">{t("common.viewAll")}</th>
              </tr>
            </thead>
            <tbody>
              {pagedMatches.map((m) => (
                <tr key={m.id} className="border-b border-gov-blue-50 last:border-0 hover:bg-gov-blue-50/50">
                  <td className="px-3 py-3">
                    <div className="font-medium text-gov-blue-800">
                      {m.ticket_domain ? domainLabel(m.ticket_domain, lang) : `Ticket #${m.ticket_id}`}
                    </div>
                    {m.ticket_problem_statement && (
                      <div className="max-w-xs truncate text-gray-500">{m.ticket_problem_statement}</div>
                    )}
                  </td>
                  <td className="px-3 py-3">{m.similarity_score != null ? `${Math.round(m.similarity_score * 100)}%` : "—"}</td>
                  <td className="px-3 py-3">
                    {m.status === "proposed" ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <AdminBadge tone={STATUS_TONE[m.status]} label={t("institution.statusProposed")} />
                        <button type="button" className="gov-btn-primary px-3 py-1 text-xs" onClick={() => decide(m.id, "accept")}>
                          {t("institution.actionAccept")}
                        </button>
                        <button type="button" className="gov-btn-secondary px-3 py-1 text-xs" onClick={() => decide(m.id, "decline")}>
                          {t("institution.actionDecline")}
                        </button>
                      </div>
                    ) : (
                      <AdminBadge
                        tone={STATUS_TONE[m.status] || "neutral"}
                        label={m.status === "accepted" ? t("institution.statusAccepted") : t("institution.statusDeclined")}
                      />
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-gray-600">{formatDate(m.created_at, lang)}</td>
                  <td className="px-3 py-3">
                    <Link href={`/institution/matches/${m.id}`} className="text-gov-blue-700 underline hover:text-gov-blue-900">
                      {t("common.viewAll")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && <p className="px-3 py-6 text-sm text-gray-500">{t("institution.noMatches")}</p>}
        </div>
      )}
      <Pagination page={page} pageCount={pageCount} onPageChange={setPage} />
      <p className="mt-3 text-xs text-gray-500">{t("institution.declineNote")}</p>
    </div>
  );
}

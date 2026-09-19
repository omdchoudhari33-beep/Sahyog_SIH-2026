"use client";

import { useCallback, useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import { useStaffGate } from "@/lib/useStaffGate";
import { formatDate } from "@/lib/format";
import { getInstitutionProjects, submitInstitutionDisposition } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import StatCard from "@/components/StatCard";
import AdminBadge from "@/components/AdminBadge";
import LoadError from "@/components/LoadError";

// Agent 8 (Lifecycle Outcome) data is a flat queue of tickets that passed
// pilot validation and are awaiting a handover/spinout disposition.
export default function InstitutionProjectsPage() {
  const { t, lang } = useLanguage();
  const ready = useStaffGate("institution");
  const [projects, setProjects] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [actionError, setActionError] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await getInstitutionProjects();
      setProjects(Array.isArray(data) ? data : []);
      setLoadError(false);
    } catch {
      setLoadError(true);
    }
  }, []);

  usePolling(load, { intervalMs: 20000, enabled: ready });

  if (!ready) return null;

  async function decideDisposition(row, disposition) {
    setBusyId(row.ticket_id);
    setActionError(null);
    try {
      await submitInstitutionDisposition(row.ticket_id, { proposalId: row.proposal_id, disposition });
      setProjects((prev) => prev.filter((p) => p.ticket_id !== row.ticket_id));
    } catch {
      setActionError(t("institution.dispositionError"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="font-serif text-3xl font-semibold text-gov-blue-900">{t("institution.projectsTitle")}</h1>
      <p className="mt-1 text-gray-600">{t("institution.projectsSub")}</p>

      {projects && (
        <div className="mt-5">
          <StatCard value={projects.length} label={t("institution.statActiveProjects")} />
        </div>
      )}

      {projects === null ? (
        loadError ? (
          <div className="mt-6">
            <LoadError onRetry={load} />
          </div>
        ) : (
          <p className="mt-6 text-sm text-gray-500">{t("common.loading")}</p>
        )
      ) : (
        <>
          <div className="mt-6 space-y-6">
            {projects.map((row) => (
              <div key={row.ticket_id} className="gov-card p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h2 className="font-serif text-lg font-semibold text-gov-blue-900">Ticket #{row.ticket_id}</h2>
                    <p className="mt-1 text-sm text-gray-600">Proposal #{row.proposal_id}</p>
                  </div>
                  {row.verdict === "pass" ? (
                    <AdminBadge tone="success" label={t("institution.pilotVerdictPass")} />
                  ) : (
                    <AdminBadge tone="neutral" label={row.verdict?.replace("_", " ") || "—"} />
                  )}
                </div>
                <p className="mt-2 text-xs text-gray-500">{formatDate(row.created_at, lang)}</p>

                <div className="mt-3 rounded-md bg-gov-blue-50 p-3">
                  <div className="text-xs font-semibold uppercase text-gov-blue-700">{t("institution.dispositionHeading")}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="gov-btn-primary px-3 py-1 text-xs"
                      disabled={busyId === row.ticket_id}
                      onClick={() => decideDisposition(row, "handover")}
                    >
                      {t("institution.dispositionHandover")}
                    </button>
                    <button
                      type="button"
                      className="gov-btn-secondary px-3 py-1 text-xs"
                      disabled={busyId === row.ticket_id}
                      onClick={() => decideDisposition(row, "spinout")}
                    >
                      {t("institution.dispositionSpinout")}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {actionError && <p className="mt-3 text-sm text-red-700">{actionError}</p>}
          {projects.length === 0 && <p className="mt-6 text-sm text-gray-500">{t("institution.noProjects")}</p>}
        </>
      )}
    </div>
  );
}

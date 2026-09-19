"use client";

import { useCallback, useMemo, useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import { useStaffGate } from "@/lib/useStaffGate";
import { getInstitutionPartners, releasePartnerFunds } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { formatRupees } from "@/lib/format";
import StatCard from "@/components/StatCard";
import AdminBadge from "@/components/AdminBadge";
import LoadError from "@/components/LoadError";

const LEDGER_TONE = { committed: "pending", partially_released: "info", fully_released: "success", cancelled: "neutral" };

export default function InstitutionPartnersPage() {
  const { t } = useLanguage();
  const ready = useStaffGate("institution");
  const [ledgers, setLedgers] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [actionError, setActionError] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await getInstitutionPartners();
      setLedgers(Array.isArray(data) ? data : []);
      setLoadError(false);
    } catch {
      setLoadError(true);
    }
  }, []);

  usePolling(load, { intervalMs: 20000, enabled: ready });

  const stats = useMemo(() => {
    if (!ledgers) return null;
    return {
      total: ledgers.length,
      fullyReleased: ledgers.filter((l) => l.status === "fully_released").length,
      totalCommitted: ledgers.reduce((sum, l) => sum + (Number(l.total_committed_amount) || 0), 0),
    };
  }, [ledgers]);

  if (!ready) return null;

  async function release(ledger) {
    setBusyId(ledger.id);
    setActionError(null);
    try {
      const updated = await releasePartnerFunds(ledger.id, {
        amount: ledger.total_committed_amount,
        releasedBy: "institution-portal",
      });
      setLedgers((prev) => prev.map((l) => (l.id === ledger.id ? { ...l, status: updated.status ?? "fully_released" } : l)));
    } catch {
      setActionError(t("institution.fundingError"));
    } finally {
      setBusyId(null);
    }
  }

  const ledgerLabel = (status) =>
    ({
      committed: t("institution.ledgerCommitted"),
      partially_released: t("institution.ledgerPartiallyReleased"),
      fully_released: t("institution.ledgerFullyReleased"),
      cancelled: t("institution.ledgerCancelled"),
    })[status] || status;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="font-serif text-3xl font-semibold text-gov-blue-900">{t("institution.partnersTitle")}</h1>
      <p className="mt-1 text-gray-600">{t("institution.partnersSub")}</p>

      {stats && (
        <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
          <StatCard value={stats.total} label={t("institution.statPartners")} />
          <StatCard value={stats.fullyReleased} label={t("institution.ledgerFullyReleased")} />
          <StatCard value={formatRupees(stats.totalCommitted)} label={t("institution.statCommittedFunding")} />
        </div>
      )}

      {ledgers === null ? (
        loadError ? (
          <div className="mt-5">
            <LoadError onRetry={load} />
          </div>
        ) : (
          <p className="mt-5 text-sm text-gray-500">{t("common.loading")}</p>
        )
      ) : (
        <div className="mt-5 overflow-x-auto rounded-lg border border-gov-blue-100 bg-white">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="border-b border-gov-blue-100 bg-gov-blue-50 text-xs uppercase text-gov-blue-700">
              <tr>
                <th className="px-3 py-2">{t("institution.colPartner")}</th>
                <th className="px-3 py-2">{t("institution.colStatus")}</th>
                <th className="px-3 py-2">{t("institution.colFunding")}</th>
                <th className="px-3 py-2">{t("common.viewAll")}</th>
              </tr>
            </thead>
            <tbody>
              {ledgers.map((l) => (
                <tr key={l.id} className="border-b border-gov-blue-50 last:border-0 hover:bg-gov-blue-50/50">
                  <td className="px-3 py-3">
                    <div className="font-medium text-gov-blue-800">Proposal #{l.proposal_id}</div>
                    <div className="text-gray-500">{l.escrow_provider || "—"}</div>
                  </td>
                  <td className="px-3 py-3">
                    <AdminBadge tone={LEDGER_TONE[l.status] || "neutral"} label={ledgerLabel(l.status)} />
                  </td>
                  <td className="px-3 py-3">
                    {formatRupees(l.total_committed_amount)} {l.currency}
                  </td>
                  <td className="px-3 py-3">
                    {l.status !== "fully_released" && (
                      <button
                        type="button"
                        className="gov-btn-primary px-3 py-1 text-xs"
                        disabled={busyId === l.id}
                        onClick={() => release(l)}
                      >
                        {t("institution.releaseFunds")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {ledgers.length === 0 && <p className="px-3 py-6 text-sm text-gray-500">{t("institution.noPartners")}</p>}
        </div>
      )}

      {actionError && <p className="mt-3 text-sm text-red-700">{actionError}</p>}
      <p className="mt-3 text-xs text-gray-500">{t("institution.fundingNote")}</p>
    </div>
  );
}

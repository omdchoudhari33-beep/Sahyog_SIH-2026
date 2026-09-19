"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageProvider";
import { useStaffGate } from "@/lib/useStaffGate";
import { getTicket, postDecision, recalculatePriority } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { domainLabel } from "@/lib/categories";
import MapPanel from "@/components/MapPanel";
import LoadError from "@/components/LoadError";

export default function OperatorTicketDetailPage() {
  const { ticketId } = useParams();
  const { t, lang } = useLanguage();
  const ready = useStaffGate("operator");

  const [ticket, setTicket] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [recalcMsg, setRecalcMsg] = useState(null);

  usePolling(
    async () => {
      try {
        const data = await getTicket(ticketId);
        setTicket(data);
        setLoadError(false);
        setNotFound(false);
      } catch (err) {
        if (err?.status === 404) {
          setNotFound(true);
        } else {
          setLoadError(true);
        }
      }
    },
    { intervalMs: 15000, enabled: ready, deps: [ticketId] }
  );

  async function handleDecision(decision) {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await postDecision(ticketId, { decision, operatorId: "demo-operator", notes });
      setTicket((prev) => ({ ...prev, status: result.status }));
      setSuccess(t("operator.decisionSuccess"));
    } catch {
      setError(t("operator.decisionError"));
    } finally {
      setBusy(false);
    }
  }

  async function handleRecalculate() {
    setBusy(true);
    setRecalcMsg(null);
    try {
      const result = await recalculatePriority(ticketId);
      setTicket((prev) => ({ ...prev, priority_score: result.priority_score }));
      setRecalcMsg(t("operator.recalculateSuccess"));
    } catch {
      setRecalcMsg(t("operator.recalculateError"));
    } finally {
      setBusy(false);
    }
  }

  if (!ready) return null;

  if (notFound) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-14 text-center">
        <p className="text-gray-700">{t("track.notFound")}</p>
        <Link href="/operator/queue" className="mt-4 inline-block text-gov-blue-700 underline">
          {t("operator.detailBack")}
        </Link>
      </div>
    );
  }

  if (!ticket) {
    if (loadError) {
      return (
        <div className="mx-auto max-w-3xl px-4 py-14">
          <LoadError />
        </div>
      );
    }
    return <div className="mx-auto max-w-3xl px-4 py-14 text-gray-500">{t("common.loading")}</div>;
  }

  const alreadyDecided = ticket.status !== "active";

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <Link href="/operator/queue" className="text-sm text-gov-blue-700 underline">
        {t("operator.detailBack")}
      </Link>

      <h1 className="mt-4 font-serif text-2xl font-semibold text-gov-blue-900">
        {t("operator.detailTitle").replace("{id}", ticket.ticket_id)}
      </h1>

      <dl className="gov-card mt-4 divide-y divide-gov-blue-50">
        <div className="p-4">
          <dt className="text-xs font-semibold uppercase text-gray-500">{t("operator.sectionDescription")}</dt>
          <dd className="mt-1 text-gray-800">{ticket.problem_statement}</dd>
        </div>

        <div className="p-4">
          <dt className="text-xs font-semibold uppercase text-gray-500">{t("operator.sectionClassification")}</dt>
          <dd className="mt-1 flex flex-wrap gap-4 text-gray-800">
            <span>{domainLabel(ticket.domain, lang)}</span>
            <span>{t("operator.priorityLabel")}: {ticket.priority_score?.toFixed?.(1) ?? "—"}</span>
          </dd>
        </div>

        <div className="p-4">
          <dt className="text-xs font-semibold uppercase text-gray-500">{t("operator.sectionEvidence")}</dt>
          <dd className="mt-2 space-y-2 text-gray-800">
            {ticket.report_photo_url ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img src={ticket.report_photo_url} alt="" className="h-40 w-56 rounded-md border border-gov-blue-100 object-cover" />
            ) : (
              <p className="text-sm text-gray-500">{t("operator.noPhoto")}</p>
            )}
            {!ticket.report_audio_url && <p className="text-sm text-gray-500">{t("operator.noAudio")}</p>}
          </dd>
        </div>

        {typeof ticket.lat === "number" && typeof ticket.lon === "number" && (
          <div className="p-4">
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("operator.sectionLocation")}</dt>
            <dd className="mt-2">
              <MapPanel tickets={[ticket]} heading={t("operator.sectionLocation")} caption="" />
            </dd>
          </div>
        )}

        {ticket.cluster_count > 1 && (
          <div className="p-4">
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("operator.sectionCluster")}</dt>
            <dd className="mt-1 text-gray-800">{t("operator.clusterNote").replace("{n}", ticket.cluster_count - 1)}</dd>
          </div>
        )}
      </dl>

      <div className="gov-card mt-6 p-4">
        <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("operator.sectionDecision")}</h2>

        {alreadyDecided ? (
          <p className="mt-2 text-sm text-gray-600">{t("operator.alreadyDecided")}</p>
        ) : (
          <>
            <div className="mt-3">
              <label htmlFor="decision-notes" className="gov-label">
                {t("operator.decisionNotesLabel")}
              </label>
              <textarea
                id="decision-notes"
                rows={2}
                className="gov-input"
                placeholder={t("operator.decisionNotesPlaceholder")}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-3">
              <button type="button" className="gov-btn-primary" disabled={busy} onClick={() => handleDecision("track_a")}>
                {t("operator.decisionApproveA")}
              </button>
              <button type="button" className="gov-btn-primary" disabled={busy} onClick={() => handleDecision("track_b")}>
                {t("operator.decisionApproveB")}
              </button>
              <button type="button" className="gov-btn-secondary" disabled={busy} onClick={() => handleDecision("reject_merge")}>
                {t("operator.decisionRejectMerge")}
              </button>
            </div>
          </>
        )}

        {success && <p className="mt-3 text-sm text-green-700">{success}</p>}
        {error && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {error}
          </p>
        )}
      </div>

      <div className="mt-4">
        <button type="button" className="gov-btn-secondary" disabled={busy} onClick={handleRecalculate}>
          {busy ? t("operator.recalculating") : t("operator.recalculate")}
        </button>
        {recalcMsg && <span className="ml-3 text-sm text-gray-600">{recalcMsg}</span>}
      </div>
    </div>
  );
}

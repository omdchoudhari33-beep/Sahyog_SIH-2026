"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageProvider";
import { getTicketStatus } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { deriveTrackStatus, timelineStepIndex } from "@/lib/status";
import { domainLabel } from "@/lib/categories";
import { formatTicketId } from "@/lib/format";
import StatusBadge from "@/components/StatusBadge";
import LoadError from "@/components/LoadError";

const TIMELINE_KEYS = ["submitted", "review", "routed", "inProgress", "resolved"];

export default function TrackStatusPage() {
  const { ticketId } = useParams();
  const { t, lang } = useLanguage();
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  usePolling(
    async () => {
      try {
        const data = await getTicketStatus(ticketId);
        setPayload(data);
        setNotFound(false);
      } catch (err) {
        if (err?.status === 404) {
          setNotFound(true);
        }
      } finally {
        setLoading(false);
      }
    },
    { intervalMs: 15000, deps: [ticketId] }
  );

  if (loading) {
    return <div className="mx-auto max-w-2xl px-4 py-14 text-gray-500">{t("common.loading")}</div>;
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-14 text-center">
        <p className="text-gray-700">{t("track.notFound")}</p>
        <Link href="/track" className="mt-4 inline-block text-gov-blue-700 underline">
          {t("track.backToSearch")}
        </Link>
      </div>
    );
  }

  if (!payload) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-14">
        <LoadError />
      </div>
    );
  }

  const status = deriveTrackStatus(payload);
  const stepIdx = timelineStepIndex(payload);
  const routedTo =
    payload.track === "track_a"
      ? payload.track_a?.correlation_code
      : payload.track === "track_b"
        ? payload.track_b?.proposal?.title
        : null;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <Link href="/track" className="text-sm text-gov-blue-700 underline">
        {t("track.backToSearch")}
      </Link>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-serif text-2xl font-semibold text-gov-blue-900">{formatTicketId(payload.ticket_id)}</h1>
        <StatusBadge status={status} />
      </div>

      <dl className="gov-card mt-4 divide-y divide-gov-blue-50">
        <div className="p-4">
          <dt className="text-xs font-semibold uppercase text-gray-500">{t("track.problemLabel")}</dt>
          <dd className="mt-1 text-gray-800">{payload.problem_statement}</dd>
        </div>
        <div className="p-4">
          <dt className="text-xs font-semibold uppercase text-gray-500">{t("track.categoryLabel")}</dt>
          <dd className="mt-1 text-gray-800">{domainLabel(payload.domain, lang)}</dd>
        </div>
        {routedTo && (
          <div className="p-4">
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("track.routedToLabel")}</dt>
            <dd className="mt-1 text-gray-800">
              {payload.track === "track_a" ? t("track.trackALabel") : t("track.trackBLabel")} · {routedTo}
            </dd>
          </div>
        )}
        {payload.report_photo_url && (
          <div className="p-4">
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("track.reportPhotoLabel")}</dt>
            <dd className="mt-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={payload.report_photo_url}
                alt={t("track.reportPhotoAlt")}
                className="h-48 w-full max-w-sm rounded-md border border-gov-blue-100 object-cover"
              />
            </dd>
          </div>
        )}
      </dl>

      {payload.track === "track_a" && payload.track_a?.closure_photo_url && (
        <div className="gov-card mt-4 p-4">
          <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("track.closurePhotoLabel")}</h2>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={payload.track_a.closure_photo_url}
            alt={t("track.closurePhotoAlt")}
            className="mt-3 h-48 w-full max-w-sm rounded-md border border-gov-blue-100 object-cover"
          />
        </div>
      )}

      {payload.track === "track_b" && payload.track_b && (
        <div className="gov-card mt-4 divide-y divide-gov-blue-50">
          {payload.track_b.match?.institution_name && (
            <div className="p-4">
              <dt className="text-xs font-semibold uppercase text-gray-500">{t("track.institutionLabel")}</dt>
              <dd className="mt-1 text-gray-800">{payload.track_b.match.institution_name}</dd>
              <dd className="mt-1 text-sm capitalize text-gray-600">
                {t("track.matchStatusLabel")}: {payload.track_b.match.status?.replace(/_/g, " ")}
              </dd>
            </div>
          )}

          {payload.track_b.proposal && (
            <div className="p-4">
              <dt className="text-xs font-semibold uppercase text-gray-500">{t("track.proposalStatusLabel")}</dt>
              <dd className="mt-1 text-gray-800">{payload.track_b.proposal.title}</dd>
              <dd className="mt-1 text-sm capitalize text-gray-600">{payload.track_b.proposal.status?.replace(/_/g, " ")}</dd>
            </div>
          )}

          {payload.track_b.candidates?.length > 0 && (
            <div className="p-4">
              <dt className="text-xs font-semibold uppercase text-gray-500">{t("track.candidatesHeading")}</dt>
              <dd className="mt-1 text-xs text-gray-500">{t("track.candidatesSub")}</dd>
              <dd className="mt-2 space-y-1">
                {payload.track_b.candidates.map((c) => (
                  <div key={c.rank} className="flex items-center justify-between text-sm text-gray-800">
                    <span>#{c.rank} {c.institution_name}</span>
                    {c.match_status && (
                      <span className="text-xs font-semibold uppercase text-gov-blue-700">
                        {c.match_status === "accepted" ? t("track.candidatesPrimary") : c.match_status.replace(/_/g, " ")}
                      </span>
                    )}
                  </div>
                ))}
              </dd>
            </div>
          )}

          {payload.track_b.milestones?.length > 0 && (
            <div className="p-4">
              <dt className="text-xs font-semibold uppercase text-gray-500">{t("track.milestonesHeading")}</dt>
              <dd className="mt-2 space-y-1">
                {payload.track_b.milestones.map((m) => (
                  <div key={m.title} className="flex items-center justify-between text-sm text-gray-800">
                    <span>{m.title}</span>
                    <span className="capitalize text-gray-600">{m.status?.replace(/_/g, " ")}</span>
                  </div>
                ))}
              </dd>
            </div>
          )}

          {payload.track_b.pilot_validation && (
            <div className="p-4">
              <dt className="text-xs font-semibold uppercase text-gray-500">{t("track.pilotVerdictLabel")}</dt>
              <dd className="mt-1 text-sm capitalize text-gray-800">{payload.track_b.pilot_validation.verdict}</dd>
              {payload.track_b.pilot_validation.photo_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={payload.track_b.pilot_validation.photo_url}
                  alt={t("track.closurePhotoAlt")}
                  className="mt-2 h-48 w-full max-w-sm rounded-md border border-gov-blue-100 object-cover"
                />
              )}
            </div>
          )}
        </div>
      )}

      <h2 className="mt-8 font-serif text-lg font-semibold text-gov-blue-900">{t("track.timelineHeading")}</h2>
      <ol className="mt-4 space-y-4">
        {TIMELINE_KEYS.map((key, i) => {
          const reached = i <= stepIdx;
          return (
            <li key={key} className="flex items-center gap-3">
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  reached ? "bg-gov-blue-700 text-white" : "border border-gov-blue-200 bg-gov-blue-50 text-gov-blue-300"
                }`}
              >
                {reached ? "✓" : i + 1}
              </span>
              <span className={reached ? "text-gray-800" : "text-gray-400"}>{t(`track.timeline.${key}`)}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

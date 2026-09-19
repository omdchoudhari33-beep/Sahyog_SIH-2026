"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageProvider";
import { domainLabel } from "@/lib/categories";
import { districtLabel } from "@/lib/districts";
import { formatTicketId, severityWord } from "@/lib/format";

export default function StepDone({ ticketId, domain, statement, severity, photoFile, district, address, usedGps, onRestart }) {
  const { t, lang } = useLanguage();
  const [previewUrl, setPreviewUrl] = useState(null);

  useEffect(() => {
    if (!photoFile) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(photoFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [photoFile]);

  return (
    <div className="text-center">
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-3xl text-green-700">
        ✓
      </div>
      <h2 className="mt-4 font-serif text-2xl font-semibold text-gov-blue-900">{t("submit.doneHeading")}</h2>

      <p className="mt-4 text-sm text-gray-500">{t("submit.ticketIdLabel")}</p>
      <p className="font-serif text-3xl font-bold text-gov-blue-800">{formatTicketId(ticketId)}</p>

      <div className="mt-6 flex flex-wrap justify-center gap-4">
        <Link href={`/track/${ticketId}`} className="gov-btn-accent">
          {t("submit.trackButton")}
        </Link>
        <button type="button" className="gov-btn-secondary" onClick={onRestart}>
          {t("submit.newReportButton")}
        </button>
      </div>

      {/* The "in-brief" report: exactly what was captured, as a receipt the
          citizen can check against - built entirely from state already
          collected during the wizard, no extra round-trip needed. */}
      <div className="gov-card mx-auto mt-10 max-w-xl p-5 text-left">
        <h3 className="font-serif text-lg font-semibold text-gov-blue-900">{t("submit.briefHeading")}</h3>
        <p className="mt-1 text-sm text-gray-600">{t("submit.briefSub")}</p>
        <dl className="mt-3 divide-y divide-gov-blue-50">
          <div className="flex items-start justify-between gap-4 py-3">
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("submit.reviewCategory")}</dt>
            <dd className="text-right text-gray-800">{domain ? domainLabel(domain, lang) : "—"}</dd>
          </div>
          <div className="flex items-start justify-between gap-4 py-3">
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("submit.reviewProblem")}</dt>
            <dd className="max-w-[70%] text-right text-gray-800">{statement || "—"}</dd>
          </div>
          <div className="flex items-start justify-between gap-4 py-3">
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("submit.understoodSeverity")}</dt>
            <dd className="text-right text-gray-800">{severityWord(severity, lang)}</dd>
          </div>
          <div className="flex items-start justify-between gap-4 py-3">
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("submit.reviewLocation")}</dt>
            <dd className="max-w-[70%] text-right text-gray-800">
              {usedGps
                ? t("submit.gpsSuccess")
                : [address, district ? districtLabel(district, lang) : null].filter(Boolean).join(", ") || "—"}
            </dd>
          </div>
          {previewUrl && (
            <div className="flex items-start justify-between gap-4 py-3">
              <dt className="text-xs font-semibold uppercase text-gray-500">{t("submit.reviewPhoto")}</dt>
              <dd>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={previewUrl} alt="" className="h-20 w-28 rounded-md border border-gov-blue-100 object-cover" />
              </dd>
            </div>
          )}
        </dl>
      </div>

      <div className="gov-card mx-auto mt-6 max-w-xl p-5 text-left">
        <h3 className="font-serif text-lg font-semibold text-gov-blue-900">{t("submit.whatNextHeading")}</h3>
        <ul className="mt-3 space-y-2 text-sm text-gray-700">
          <li>1. {t("submit.whatNextDedup")}</li>
          <li>2. {t("submit.whatNextPriority")}</li>
          <li>3. {t("submit.whatNextHuman")}</li>
          <li>4. {t("submit.whatNextRoute")}</li>
        </ul>
      </div>
    </div>
  );
}

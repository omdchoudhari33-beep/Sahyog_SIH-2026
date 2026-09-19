"use client";

import { useEffect, useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import { domainLabel } from "@/lib/categories";
import { districtLabel } from "@/lib/districts";

export default function StepReview({ domain, statement, photoFile, district, address, usedGps, busy, error, onEditStep, onSubmit }) {
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
    <div>
      <h2 className="font-serif text-2xl font-semibold text-gov-blue-900">{t("submit.reviewHeading")}</h2>
      <p className="mt-1 text-sm text-gray-600">{t("submit.reviewSub")}</p>

      <dl className="gov-card mt-5 divide-y divide-gov-blue-50">
        <div className="flex items-start justify-between gap-4 p-4">
          <div>
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("submit.reviewCategory")}</dt>
            <dd className="mt-1 text-gray-800">{domain ? domainLabel(domain, lang) : "—"}</dd>
          </div>
          <button type="button" onClick={() => onEditStep(0)} className="text-sm text-gov-blue-700 underline">
            {t("submit.reviewEditStep")}
          </button>
        </div>

        <div className="flex items-start justify-between gap-4 p-4">
          <div>
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("submit.reviewProblem")}</dt>
            <dd className="mt-1 text-gray-800">{statement}</dd>
          </div>
          <button type="button" onClick={() => onEditStep(0)} className="text-sm text-gov-blue-700 underline">
            {t("submit.reviewEditStep")}
          </button>
        </div>

        <div className="flex items-start justify-between gap-4 p-4">
          <div>
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("submit.reviewPhoto")}</dt>
            <dd className="mt-2">
              {previewUrl ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img src={previewUrl} alt="" className="h-20 w-28 rounded-md border border-gov-blue-100 object-cover" />
              ) : (
                "—"
              )}
            </dd>
          </div>
          <button type="button" onClick={() => onEditStep(1)} className="text-sm text-gov-blue-700 underline">
            {t("submit.reviewEditStep")}
          </button>
        </div>

        <div className="flex items-start justify-between gap-4 p-4">
          <div>
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("submit.reviewLocation")}</dt>
            <dd className="mt-1 text-gray-800">
              {usedGps
                ? t("submit.gpsSuccess")
                : [address, district ? districtLabel(district, lang) : null].filter(Boolean).join(", ") || "—"}
            </dd>
          </div>
          <button type="button" onClick={() => onEditStep(2)} className="text-sm text-gov-blue-700 underline">
            {t("submit.reviewEditStep")}
          </button>
        </div>
      </dl>

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="mt-6 flex justify-end">
        <button type="button" className="gov-btn-accent" disabled={busy} onClick={onSubmit}>
          {busy ? t("submit.submitting") : t("submit.submitButton")}
        </button>
      </div>
    </div>
  );
}

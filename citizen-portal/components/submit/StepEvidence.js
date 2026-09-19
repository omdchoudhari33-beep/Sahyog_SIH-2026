"use client";

import { useEffect, useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import { domainLabel } from "@/lib/categories";
import CameraCapture from "@/components/CameraCapture";

const SEVERITY_LABELS = {
  en: ["Low", "Medium", "High"],
  hi: ["कम", "मध्यम", "उच्च"],
  bn: ["কম", "মাঝারি", "বেশি"],
  or: ["କମ୍", "ମଧ୍ୟମ", "ଅଧିକ"],
  ur: ["کم", "درمیانہ", "زیادہ"],
};

function severityWord(severity, lang) {
  const words = SEVERITY_LABELS[lang] || SEVERITY_LABELS.en;
  if (severity == null) return words[1];
  if (severity < 0.4) return words[0];
  if (severity < 0.7) return words[1];
  return words[2];
}

export default function StepEvidence({ understood, photoFile, onPhotoChange, busy, error, matchWarning, onUpload }) {
  const { t, lang } = useLanguage();
  const [previewUrl, setPreviewUrl] = useState(null);
  const [localValidation, setLocalValidation] = useState(null);

  useEffect(() => {
    if (!photoFile) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(photoFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [photoFile]);

  function handleFileChange(e) {
    const file = e.target.files?.[0] || null;
    onPhotoChange(file);
    setLocalValidation(null);
  }

  function handleContinue() {
    if (!photoFile) {
      setLocalValidation(t("submit.photoRequired"));
      return;
    }
    onUpload({ force: false });
  }

  return (
    <div>
      <h2 className="font-serif text-2xl font-semibold text-gov-blue-900">{t("submit.evidenceHeading")}</h2>
      <p className="mt-1 text-sm text-gray-600">{t("submit.evidenceSub")}</p>

      {understood && (
        <div className="mt-4 flex flex-wrap gap-2" aria-live="polite">
          <span className="inline-flex items-center rounded-full border border-gov-blue-200 bg-gov-blue-50 px-3 py-1 text-xs font-semibold text-gov-blue-800">
            {t("submit.understoodDomain")}: {domainLabel(understood.domain, lang)}
          </span>
          <span className="inline-flex items-center rounded-full border border-gov-blue-200 bg-gov-blue-50 px-3 py-1 text-xs font-semibold text-gov-blue-800">
            {t("submit.understoodSeverity")}: {severityWord(understood.severity, lang)}
          </span>
        </div>
      )}

      {!previewUrl && (
        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <div className="gov-card p-4">
            <h3 className="mb-3 text-sm font-semibold text-gov-blue-800">{t("submit.evidenceCameraOption")}</h3>
            <CameraCapture onCapture={onPhotoChange} />
          </div>

          <div className="gov-card p-4">
            <h3 className="mb-3 text-sm font-semibold text-gov-blue-800">{t("submit.evidenceUploadOption")}</h3>
            <label htmlFor="photo-upload" className="gov-label">
              {t("submit.uploadLabel")}
            </label>
            <input
              id="photo-upload"
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              className="block w-full text-sm text-gray-700 file:mr-3 file:rounded-md file:border-0 file:bg-gov-blue-700 file:px-4 file:py-2 file:text-white hover:file:bg-gov-blue-800"
            />
            <p className="mt-1 text-xs text-gray-500">{t("submit.uploadHint")}</p>
          </div>
        </div>
      )}

      {previewUrl && (
        <div className="mt-5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={previewUrl}
            alt={t("submit.uploadedAlt")}
            className="max-h-64 rounded-md border border-gov-blue-100 object-cover"
          />
          <button
            type="button"
            onClick={() => onPhotoChange(null)}
            className="mt-2 block text-sm text-gov-blue-700 underline hover:text-gov-blue-900"
          >
            {t("submit.removePhoto")}
          </button>
        </div>
      )}

      {matchWarning && (
        <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-4">
          <p className="font-medium text-amber-900">{t("submit.matchWarningHeading")}</p>
          <p className="mt-1 text-sm text-amber-800">
            {matchWarning.discrepancy_notes || t("submit.matchWarningBody")}
          </p>
          <div className="mt-3 flex flex-wrap gap-3">
            <button type="button" className="gov-btn-secondary" onClick={() => onPhotoChange(null)}>
              {t("submit.tryDifferentPhoto")}
            </button>
            <button type="button" className="gov-btn-primary" disabled={busy} onClick={() => onUpload({ force: true })}>
              {t("submit.continueAnyway")}
            </button>
          </div>
        </div>
      )}

      {(localValidation || error) && !matchWarning && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {localValidation || error}
        </p>
      )}

      {!matchWarning && (
        <div className="mt-6 flex justify-end">
          <button type="button" className="gov-btn-primary" disabled={busy} onClick={handleContinue}>
            {busy ? t("submit.photoAnalyzing") : t("submit.uploadButton")}
          </button>
        </div>
      )}
    </div>
  );
}

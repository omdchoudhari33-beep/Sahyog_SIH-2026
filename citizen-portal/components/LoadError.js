"use client";

import { useLanguage } from "@/context/LanguageProvider";

// Shared "couldn't load live data" state - replaces the old pattern of
// silently swapping in mock/sample data on a failed fetch. Every page now
// shows this instead when it has no data to display.
export default function LoadError({ onRetry }) {
  const { t } = useLanguage();
  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-4 py-6 text-center">
      <p className="text-sm text-red-800">{t("common.networkError")}</p>
      {onRetry && (
        <button type="button" className="gov-btn-secondary mt-3" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

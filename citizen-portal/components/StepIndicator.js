"use client";

import { useLanguage } from "@/context/LanguageProvider";

const STEP_KEYS = ["describe", "evidence", "location", "review", "done"];

export default function StepIndicator({ currentIndex }) {
  const { t } = useLanguage();

  return (
    <ol aria-label={t("submit.wizardTitle")} className="mb-8 flex items-center justify-between">
      {STEP_KEYS.map((key, i) => {
        const done = i < currentIndex;
        const active = i === currentIndex;
        return (
          <li key={key} className="flex flex-1 flex-col items-center gap-1">
            <div className="flex w-full items-center">
              {i > 0 && (
                <div className={`h-0.5 flex-1 ${done || active ? "bg-gov-blue-600" : "bg-gov-blue-100"}`} />
              )}
              <div
                aria-current={active ? "step" : undefined}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold ${
                  done
                    ? "border-gov-blue-600 bg-gov-blue-600 text-white"
                    : active
                      ? "border-gov-orange-600 bg-white text-gov-orange-600"
                      : "border-gov-blue-100 bg-white text-gov-blue-300"
                } ${i === 0 ? "ml-0" : ""}`}
              >
                {done ? "✓" : i + 1}
              </div>
              {i < STEP_KEYS.length - 1 && (
                <div className={`h-0.5 flex-1 ${done ? "bg-gov-blue-600" : "bg-gov-blue-100"}`} />
              )}
            </div>
            <span
              className={`text-center text-xs font-medium ${active ? "text-gov-orange-700" : "text-gray-500"}`}
            >
              {t(`submit.steps.${key}`)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

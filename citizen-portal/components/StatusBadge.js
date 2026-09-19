"use client";

import { useLanguage } from "@/context/LanguageProvider";

// Tailwind class names must appear as full literal strings somewhere in the
// source for the JIT compiler to pick them up, so this stays a lookup
// object rather than string-building the classes from the status key.
const COLORS = {
  registered: "bg-gov-blue-50 text-gov-blue-800 border-gov-blue-200",
  in_progress: "bg-amber-50 text-amber-800 border-amber-300",
  resolved: "bg-green-50 text-green-800 border-green-300",
  escalated_track_b: "bg-purple-50 text-purple-800 border-purple-300",
  merged: "bg-gray-100 text-gray-700 border-gray-300",
};

export default function StatusBadge({ status }) {
  const { t } = useLanguage();
  const classes = COLORS[status] || COLORS.registered;

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${classes}`}
    >
      {t(`status.${status}`)}
    </span>
  );
}

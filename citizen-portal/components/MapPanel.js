"use client";

import { useLanguage } from "@/context/LanguageProvider";
import { domainLabel } from "@/lib/categories";

// Rough bounding box of Jharkhand, used only to place illustrative pins on a
// plain panel - not a real map (no tile/map library dependency, per the
// "keep it simple" brief). Coordinates outside this box are clamped.
const BOUNDS = { minLat: 21.9, maxLat: 25.35, minLon: 83.3, maxLon: 87.9 };

function toPercent(lat, lon) {
  const x = ((lon - BOUNDS.minLon) / (BOUNDS.maxLon - BOUNDS.minLon)) * 100;
  const y = 100 - ((lat - BOUNDS.minLat) / (BOUNDS.maxLat - BOUNDS.minLat)) * 100;
  return {
    left: `${Math.min(96, Math.max(4, x))}%`,
    top: `${Math.min(96, Math.max(4, y))}%`,
  };
}

export default function MapPanel({ tickets = [], heading, caption }) {
  const { t, lang } = useLanguage();
  const pins = tickets.filter((tk) => typeof tk.lat === "number" && typeof tk.lon === "number");

  return (
    <div className="gov-card p-4">
      <h3 className="font-serif text-lg font-semibold text-gov-blue-900">{heading ?? t("home.mapHeading")}</h3>
      {(caption ?? t("home.mapCaption")) && (
        <p className="mb-3 text-xs text-gray-500">{caption ?? t("home.mapCaption")}</p>
      )}

      <div className="relative aspect-[4/3] w-full overflow-hidden rounded-md border border-gov-blue-100 bg-gov-blue-50">
        {pins.map((tk) => (
          <span
            key={tk.ticket_id}
            title={`#${tk.ticket_id} · ${domainLabel(tk.domain, lang)}`}
            style={toPercent(tk.lat, tk.lon)}
            className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-gov-orange-600 shadow"
          />
        ))}
        {pins.length === 0 && (
          <div className="flex h-full items-center justify-center text-sm text-gray-400">
            {t("home.feedEmpty")}
          </div>
        )}
      </div>
    </div>
  );
}

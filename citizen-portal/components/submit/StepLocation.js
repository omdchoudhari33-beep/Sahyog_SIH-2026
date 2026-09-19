"use client";

import { useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import { DISTRICTS } from "@/lib/districts";

export default function StepLocation({ address, onAddressChange, district, onDistrictChange, busy, error, onSubmit }) {
  const { t, lang } = useLanguage();
  const [gpsState, setGpsState] = useState("idle"); // idle | detecting | success | failed
  const [localValidation, setLocalValidation] = useState(null);
  const gpsSupported = typeof navigator !== "undefined" && !!navigator.geolocation;

  function useGps() {
    setGpsState("detecting");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsState("success");
        onSubmit({ lat: pos.coords.latitude, lon: pos.coords.longitude });
      },
      () => setGpsState("failed"),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  function handleManualSubmit() {
    if (!address.trim()) {
      setLocalValidation(t("submit.locationRequired"));
      return;
    }
    setLocalValidation(null);
    onSubmit({ addressText: address.trim() });
  }

  return (
    <div>
      <h2 className="font-serif text-2xl font-semibold text-gov-blue-900">{t("submit.locationHeading")}</h2>
      <p className="mt-1 text-sm text-gray-600">{t("submit.locationSub")}</p>

      {gpsSupported && (
        <div className="mt-5">
          <button type="button" className="gov-btn-primary" disabled={busy || gpsState === "detecting"} onClick={useGps}>
            📍 {gpsState === "detecting" ? t("submit.gpsDetecting") : t("submit.gpsButton")}
          </button>
          {gpsState === "success" && <p className="mt-2 text-sm text-green-700">{t("submit.gpsSuccess")}</p>}
          {gpsState === "failed" && <p className="mt-2 text-sm text-amber-700">{t("submit.gpsFailed")}</p>}
        </div>
      )}

      <div className="mt-6 flex items-center gap-3">
        <div className="h-px flex-1 bg-gov-blue-100" />
        <span className="text-sm text-gray-500">{t("submit.orDivider")}</span>
        <div className="h-px flex-1 bg-gov-blue-100" />
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="district" className="gov-label">
            {t("submit.districtLabel")}
          </label>
          <select id="district" className="gov-input" value={district} onChange={(e) => onDistrictChange(e.target.value)}>
            <option value="">{t("submit.districtPlaceholder")}</option>
            {DISTRICTS.map((d) => (
              <option key={d.id} value={d.id}>
                {lang === "hi" ? d.hi : d.en}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="address" className="gov-label">
            {t("submit.addressLabel")}
          </label>
          <input
            id="address"
            type="text"
            className="gov-input"
            placeholder={t("submit.addressPlaceholder")}
            value={address}
            onChange={(e) => onAddressChange(e.target.value)}
          />
        </div>
      </div>

      {(localValidation || error) && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {localValidation || error}
        </p>
      )}

      <div className="mt-6 flex justify-end">
        <button type="button" className="gov-btn-primary" disabled={busy} onClick={handleManualSubmit}>
          {busy ? t("common.loading") : t("submit.locationButton")}
        </button>
      </div>
    </div>
  );
}

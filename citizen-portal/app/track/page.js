"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/context/LanguageProvider";
import { parseTicketId } from "@/lib/format";

export default function TrackSearchPage() {
  const { t } = useLanguage();
  const router = useRouter();
  const [value, setValue] = useState("");
  const [invalid, setInvalid] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    const id = parseTicketId(value);
    if (id == null) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    router.push(`/track/${id}`);
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-14">
      <h1 className="font-serif text-3xl font-semibold text-gov-blue-900">{t("track.searchHeading")}</h1>
      <p className="mt-2 text-gray-600">{t("track.searchSub")}</p>

      <form onSubmit={handleSubmit} className="mt-6">
        <label htmlFor="ticket-id" className="gov-label">
          {t("track.ticketIdLabel")}
        </label>
        <div className="flex gap-3">
          <input
            id="ticket-id"
            type="text"
            className="gov-input"
            placeholder={t("track.ticketIdPlaceholder")}
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <button type="submit" className="gov-btn-primary shrink-0">
            {t("track.searchButton")}
          </button>
        </div>
        {invalid && (
          <p role="alert" className="mt-2 text-sm text-red-700">
            {t("track.invalidId")}
          </p>
        )}
      </form>
    </div>
  );
}

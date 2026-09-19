"use client";

import { useLanguage } from "@/context/LanguageProvider";
import { domainLabel } from "@/lib/categories";
import { districtLabel } from "@/lib/districts";
import { deriveFeedStatus } from "@/lib/status";
import { formatDate } from "@/lib/format";
import StatusBadge from "@/components/StatusBadge";

export default function ProblemCard({ ticket }) {
  const { t, lang } = useLanguage();
  const status = deriveFeedStatus(ticket);

  return (
    <li className="gov-card flex flex-col gap-2 p-4">
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-gov-blue-600">
          {domainLabel(ticket.domain, lang)}
        </span>
        <StatusBadge status={status} />
      </div>

      <p className="text-sm text-gray-800">{ticket.problem_statement}</p>

      <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500">
        <span>{ticket.district ? districtLabel(ticket.district, lang) : ""}</span>
        <span>
          {t("track.ticketIdLabel")} #{ticket.ticket_id} · {formatDate(ticket.created_at, lang)}
        </span>
      </div>
    </li>
  );
}

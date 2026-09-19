"use client";

import Link from "next/link";
import { useLanguage } from "@/context/LanguageProvider";
import { domainLabel } from "@/lib/categories";
import { formatAge } from "@/lib/format";
import { deriveFeedStatus } from "@/lib/status";
import StatusBadge from "@/components/StatusBadge";

// The denser, tabular sibling of ProblemCard - same underlying ticket shape
// (Agent 3's /dno/tickets item) and the same StatusBadge vocabulary, just
// laid out for a staff queue instead of a citizen feed.
export default function TicketRow({ ticket }) {
  const { t, lang } = useLanguage();
  const status = deriveFeedStatus(ticket);

  return (
    <tr className="border-b border-gov-blue-50 last:border-0 hover:bg-gov-blue-50/50">
      <td className="whitespace-nowrap px-3 py-3 font-medium text-gov-blue-800">#{ticket.ticket_id}</td>
      <td className="px-3 py-3">{domainLabel(ticket.domain, lang)}</td>
      <td className="max-w-xs px-3 py-3 text-gray-700">
        <span className="line-clamp-2">{ticket.problem_statement || "—"}</span>
      </td>
      <td className="px-3 py-3">{ticket.severity != null ? ticket.severity.toFixed(2) : "—"}</td>
      <td className="px-3 py-3 font-semibold text-gov-orange-700">
        {ticket.priority_score != null ? ticket.priority_score.toFixed(1) : "—"}
      </td>
      <td className="px-3 py-3">
        {ticket.cluster_count > 1 ? (
          <span className="inline-flex items-center rounded-full border border-gov-orange-300 bg-gov-orange-50 px-2 py-0.5 text-xs font-semibold text-gov-orange-800">
            {t("operator.clusterBadge").replace("{n}", ticket.cluster_count - 1)}
          </span>
        ) : (
          "—"
        )}
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-gray-600">{formatAge(ticket.created_at)}</td>
      <td className="px-3 py-3">
        <StatusBadge status={status} />
      </td>
      <td className="whitespace-nowrap px-3 py-3">
        <Link href={`/operator/queue/${ticket.ticket_id}`} className="text-sm text-gov-blue-700 underline hover:text-gov-blue-900">
          {t("operator.viewDetail")}
        </Link>
      </td>
    </tr>
  );
}

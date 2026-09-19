"use client";

import { useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import { formatDate } from "@/lib/format";
import { domainLabel } from "@/lib/categories";
import { getAuditLog } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import LoadError from "@/components/LoadError";

const ENTITY_TYPES = ["ticket", "proposal", "milestone_fund_ledger"];
const SERVICES = ["3.triage_and_route", "5.ulb_dispatch", "6.trackb_innovation", "7.industry_partnership", "8.lifecycle_outcome"];

export default function GovernmentAuditPage() {
  const { t, lang } = useLanguage();
  const [entityType, setEntityType] = useState("");
  const [entityId, setEntityId] = useState("");
  const [service, setService] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [events, setEvents] = useState(null);
  const [error, setError] = useState(false);

  usePolling(
    async () => {
      try {
        const data = await getAuditLog({
          entity_type: entityType,
          entity_id: entityId,
          service_name: service,
          from_date: from,
          to_date: to,
          limit: 100,
        });
        setEvents(Array.isArray(data) ? data : []);
        setError(false);
      } catch {
        setError(true);
      }
    },
    { intervalMs: 30000, enabled: true, deps: [entityType, entityId, service, from, to] }
  );

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="font-serif text-3xl font-semibold text-gov-blue-900">{t("government.auditTitle")}</h1>
      <p className="mt-1 text-gray-600">{t("government.auditSub")}</p>

      <div className="mt-5 flex flex-wrap gap-3">
        <div>
          <label htmlFor="filter-entity-type" className="gov-label">
            {t("government.filterEntityType")}
          </label>
          <select id="filter-entity-type" className="gov-input" value={entityType} onChange={(e) => setEntityType(e.target.value)}>
            <option value="">{t("common.all")}</option>
            {ENTITY_TYPES.map((et) => (
              <option key={et} value={et}>
                {et}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="filter-entity-id" className="gov-label">
            {t("government.filterEntityId")}
          </label>
          <input id="filter-entity-id" className="gov-input" value={entityId} onChange={(e) => setEntityId(e.target.value)} />
        </div>
        <div>
          <label htmlFor="filter-service" className="gov-label">
            {t("government.filterService")}
          </label>
          <select id="filter-service" className="gov-input" value={service} onChange={(e) => setService(e.target.value)}>
            <option value="">{t("common.all")}</option>
            {SERVICES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="filter-from" className="gov-label">
            {t("government.filterFrom")}
          </label>
          <input id="filter-from" type="date" className="gov-input" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div>
          <label htmlFor="filter-to" className="gov-label">
            {t("government.filterTo")}
          </label>
          <input id="filter-to" type="date" className="gov-input" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      </div>

      {events === null ? (
        error ? (
          <div className="mt-5">
            <LoadError />
          </div>
        ) : (
          <p className="mt-5 text-sm text-gray-500">{t("common.loading")}</p>
        )
      ) : (
        <div className="mt-5 overflow-x-auto rounded-lg border border-gov-blue-100 bg-white">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-gov-blue-100 bg-gov-blue-50 text-xs uppercase text-gov-blue-700">
              <tr>
                <th className="px-3 py-2">{t("government.colTime")}</th>
                <th className="px-3 py-2">{t("government.colService")}</th>
                <th className="px-3 py-2">{t("government.colEntity")}</th>
                <th className="px-3 py-2">{t("government.colDomain")}</th>
                <th className="px-3 py-2">{t("government.colDescription")}</th>
                <th className="px-3 py-2">{t("government.colAction")}</th>
                <th className="px-3 py-2">{t("government.colActor")}</th>
              </tr>
            </thead>
            <tbody aria-live="polite">
              {events.map((e) => (
                <tr key={e.id} className="border-b border-gov-blue-50 last:border-0 align-top">
                  <td className="whitespace-nowrap px-3 py-2 text-gray-600">{formatDate(e.occurred_at, lang)}</td>
                  <td className="px-3 py-2">{e.service_name}</td>
                  <td className="px-3 py-2">
                    {e.entity_type} #{e.entity_id}
                  </td>
                  <td className="px-3 py-2">{e.domain ? domainLabel(e.domain, lang) : "—"}</td>
                  <td className="max-w-xs px-3 py-2 text-gray-700">{e.description || "—"}</td>
                  <td className="px-3 py-2 font-medium text-gov-blue-800">{e.action_summary}</td>
                  <td className="px-3 py-2 text-gray-600">{e.actor || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {events.length === 0 && <p className="px-3 py-6 text-sm text-gray-500">{t("government.noEvents")}</p>}
        </div>
      )}
    </div>
  );
}

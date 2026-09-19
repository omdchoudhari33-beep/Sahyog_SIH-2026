"use client";

import { useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import StatCard from "@/components/StatCard";
import SimpleChart from "@/components/SimpleChart";
import LoadError from "@/components/LoadError";
import MapPanel from "@/components/MapPanel";
import { getTransparencyDashboard, listPublicTickets } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { aggregateByDistrict, aggregateByDomain } from "@/lib/dashboard";
import { districtLabel } from "@/lib/districts";
import { domainLabel } from "@/lib/categories";

export default function GovernmentOverviewPage() {
  const { t, lang } = useLanguage();
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState(false);
  const [tickets, setTickets] = useState(null);

  usePolling(
    async () => {
      try {
        const data = await getTransparencyDashboard();
        setDashboard(data);
        setError(false);
      } catch {
        setError(true);
      }
    },
    { intervalMs: 30000 }
  );

  // Separate from the dashboard's own aggregate district/domain counts -
  // that endpoint reports totals, not individual ticket coordinates, so a
  // map needs this raw feed too (same public, unauthenticated endpoint the
  // citizen home page's map uses, just fetched at a higher limit here since
  // this view is meant to cover every complaint statewide).
  usePolling(
    async () => {
      try {
        const data = await listPublicTickets({ limit: 200 });
        setTickets(Array.isArray(data.items) ? data.items : []);
      } catch {
        // Non-fatal for this page: the charts/stats above still work even
        // if the map's own feed is briefly unavailable.
      }
    },
    { intervalMs: 30000 }
  );

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="font-serif text-3xl font-semibold text-gov-blue-900">{t("government.overviewTitle")}</h1>
      <p className="mt-2 max-w-2xl text-gray-600">{t("government.overviewSub")}</p>

      {dashboard === null ? (
        error ? (
          <div className="mt-6">
            <LoadError />
          </div>
        ) : (
          <p className="mt-6 text-sm text-gray-500">{t("common.loading")}</p>
        )
      ) : (
        <GovernmentBody dashboard={dashboard} tickets={tickets} lang={lang} t={t} />
      )}
    </div>
  );
}

function GovernmentBody({ dashboard, tickets, lang, t }) {
  const byDistrict = aggregateByDistrict(dashboard);
  const byDomain = aggregateByDomain(dashboard);
  const hei = dashboard.hei_participation || {};
  const industry = dashboard.industry_engagement || {};
  const cr = dashboard.completion_rate || {};
  const outcomes = dashboard.outcomes || {};

  return (
    <div className="mt-8 grid gap-8 md:grid-cols-2">
      <section className="gov-card p-5 md:col-span-2">
        <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("government.districtDomainHeading")}</h2>
        <div className="mt-4 grid gap-8 md:grid-cols-2">
          <SimpleChart rows={byDistrict.map((r) => ({ label: districtLabel(r.district, lang), value: r.count }))} />
          <SimpleChart rows={byDomain.map((r) => ({ label: domainLabel(r.domain, lang), value: r.count }))} />
        </div>
      </section>

      {tickets && tickets.length > 0 && (
        <section className="md:col-span-2">
          <MapPanel tickets={tickets} heading={t("government.mapHeading")} caption={t("government.mapCaption")} />
        </section>
      )}

      <section className="gov-card p-5">
        <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("government.heiHeading")}</h2>
        <div className="mt-4 grid grid-cols-3 gap-3">
          <StatCard value={hei.active_heis ?? "—"} label={t("government.heiActive")} />
          <StatCard value={hei.pending_matches ?? "—"} label={t("government.heiPending")} />
          <StatCard value={hei.declined_matches ?? "—"} label={t("government.heiDeclined")} />
        </div>
      </section>

      <section className="gov-card p-5">
        <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("government.industryHeading")}</h2>
        <div className="mt-4 grid grid-cols-3 gap-3">
          <StatCard value={industry.active_partners ?? "—"} label={t("government.industryActive")} />
          <StatCard value={industry.pending_matches ?? "—"} label={t("government.industryPending")} />
          <StatCard
            value={industry.total_committed_amount != null ? `₹${Number(industry.total_committed_amount).toLocaleString("en-IN")}` : "—"}
            label={t("government.industryFunding")}
          />
        </div>
      </section>

      <section className="gov-card p-5">
        <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("government.completionHeading")}</h2>
        <div className="mt-4">
          <SimpleChart
            rows={[
              { label: t("transparency.resolutionPassed"), value: cr.pilots_passed || 0 },
              { label: t("transparency.resolutionFailed"), value: cr.pilots_failed || 0 },
              { label: t("transparency.resolutionPending"), value: cr.pilots_pending || 0 },
            ]}
          />
        </div>
      </section>

      <section className="gov-card p-5">
        <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("government.outcomesHeading")}</h2>
        <div className="mt-4 grid grid-cols-3 gap-3">
          <StatCard value={outcomes.handovers ?? "—"} label={t("government.outcomeHandovers")} />
          <StatCard value={outcomes.spinouts ?? "—"} label={t("government.outcomeSpinouts")} />
          <StatCard value={outcomes.track_a_resolved ?? "—"} label={t("government.outcomeTrackAResolved")} />
        </div>
      </section>
    </div>
  );
}

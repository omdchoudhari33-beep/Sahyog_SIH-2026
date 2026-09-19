"use client";

import { useState } from "react";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageProvider";
import StatCard from "@/components/StatCard";
import SimpleChart from "@/components/SimpleChart";
import LoadError from "@/components/LoadError";
import { getTransparencyDashboard } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { computeHeadlineStats, aggregateByDistrict, aggregateByDomain, trackSplit } from "@/lib/dashboard";
import { districtLabel } from "@/lib/districts";
import { domainLabel } from "@/lib/categories";

export default function TransparencyPage() {
  const { t, lang } = useLanguage();
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState(false);

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

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="font-serif text-3xl font-semibold text-gov-blue-900">{t("transparency.heading")}</h1>
      <p className="mt-2 max-w-2xl text-gray-600">{t("transparency.sub")}</p>
      <p className="mt-1 text-xs text-gray-500">{t("transparency.dataNote")}</p>

      {dashboard === null ? (
        error ? (
          <div className="mt-6">
            <LoadError />
          </div>
        ) : (
          <p className="mt-6 text-sm text-gray-500">{t("common.loading")}</p>
        )
      ) : (
        <TransparencyBody dashboard={dashboard} lang={lang} t={t} />
      )}
    </div>
  );
}

function TransparencyBody({ dashboard, lang, t }) {
  const stats = computeHeadlineStats(dashboard);
  const byDistrict = aggregateByDistrict(dashboard).slice(0, 8);
  const byDomain = aggregateByDomain(dashboard);
  const { trackA, trackB } = trackSplit(dashboard);
  const cr = dashboard.completion_rate || {};

  return (
    <>
      <section className="mt-8">
        <h2 className="font-serif text-xl font-semibold text-gov-blue-900">{t("transparency.statsHeading")}</h2>
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard value={stats.filed} label={t("transparency.statFiled")} />
          <StatCard value={stats.resolved} label={t("transparency.statResolved")} />
          <StatCard value={stats.districts} label={t("transparency.statDistricts")} />
          <StatCard value={stats.institutions} label={t("transparency.statInstitutions")} />
        </div>
      </section>

      <div className="mt-10 grid gap-8 md:grid-cols-2">
        <section className="gov-card p-5">
          <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("transparency.districtHeading")}</h2>
          <div className="mt-4">
            <SimpleChart rows={byDistrict.map((r) => ({ label: districtLabel(r.district, lang), value: r.count }))} />
          </div>
        </section>

        <section className="gov-card p-5">
          <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("transparency.categoryHeading")}</h2>
          <div className="mt-4">
            <SimpleChart rows={byDomain.map((r) => ({ label: domainLabel(r.domain, lang), value: r.count }))} />
          </div>
        </section>

        <section className="gov-card p-5">
          <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("transparency.trackSplitHeading")}</h2>
          <p className="mt-1 text-xs text-gray-500">{t("transparency.trackSplitSub")}</p>
          <div className="mt-4">
            <SimpleChart
              rows={[
                { label: t("track.trackALabel"), value: trackA },
                { label: t("track.trackBLabel"), value: trackB },
              ]}
            />
          </div>
        </section>

        <section className="gov-card p-5">
          <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("transparency.resolutionHeading")}</h2>
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
      </div>

      <p className="mt-8 text-sm text-gray-600">
        <Link href="/government" className="text-gov-blue-700 underline hover:text-gov-blue-900">
          {t("transparency.moreDepthLink")}
        </Link>
      </p>
    </>
  );
}

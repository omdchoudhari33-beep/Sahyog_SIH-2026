"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageProvider";
import StatCard from "@/components/StatCard";
import ProblemCard from "@/components/ProblemCard";
import MapPanel from "@/components/MapPanel";
import LoadError from "@/components/LoadError";
import { getTransparencyDashboard, listPublicTickets } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { deriveFeedStatus, STATUS_KEYS } from "@/lib/status";
import { computeHeadlineStats } from "@/lib/dashboard";
import { DISTRICTS } from "@/lib/districts";

export default function HomePage() {
  const { t, lang } = useLanguage();
  const [dashboard, setDashboard] = useState(null);
  const [feed, setFeed] = useState(null);
  const [statsError, setStatsError] = useState(false);
  const [feedError, setFeedError] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [districtFilter, setDistrictFilter] = useState("all");

  // Two independent backends (Agent 9's dashboard, Agent 3's public feed) -
  // fetched and error-handled separately so one being down doesn't blank
  // the section that's still working.
  usePolling(
    async () => {
      try {
        setDashboard(await getTransparencyDashboard());
        setStatsError(false);
      } catch {
        setStatsError(true);
      }
    },
    { intervalMs: 30000 }
  );

  usePolling(
    async () => {
      try {
        const data = await listPublicTickets({ limit: 20 });
        setFeed(Array.isArray(data.items) ? data.items : []);
        setFeedError(false);
      } catch {
        setFeedError(true);
      }
    },
    { intervalMs: 30000 }
  );

  const stats = useMemo(() => (dashboard ? computeHeadlineStats(dashboard) : null), [dashboard]);

  const filteredFeed = useMemo(() => {
    if (!feed) return [];
    return feed.filter((tk) => {
      const status = deriveFeedStatus(tk);
      const statusOk = statusFilter === "all" || status === statusFilter;
      const districtOk = districtFilter === "all" || !tk.district || tk.district === districtFilter;
      return statusOk && districtOk;
    });
  }, [feed, statusFilter, districtFilter]);

  return (
    <div>
      <section className="bg-gradient-to-b from-gov-blue-700 to-gov-blue-800 text-white">
        <div className="mx-auto max-w-6xl px-4 py-16 text-center">
          <h1 className="font-serif text-4xl font-bold sm:text-5xl">{t("home.heroTitle")}</h1>
          <p className="mt-3 text-lg text-gov-orange-200">{t("home.heroTagline")}</p>
          <p className="mx-auto mt-4 max-w-2xl text-gov-blue-100">{t("home.heroSub")}</p>
          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <Link href="/submit" className="gov-btn-accent">
              {t("home.ctaPrimary")}
            </Link>
            <Link
              href="/track"
              className="inline-flex items-center justify-center gap-2 rounded-md border border-white px-5 py-2.5 font-medium text-white transition-colors hover:bg-white/10"
            >
              {t("home.ctaSecondary")}
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10">
        <h2 className="font-serif text-2xl font-semibold text-gov-blue-900">{t("home.statsHeading")}</h2>
        {stats ? (
          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard value={stats.filed} label={t("home.statFiled")} />
            <StatCard value={stats.resolved} label={t("home.statResolved")} />
            <StatCard value={stats.districts} label={t("home.statDistricts")} />
            <StatCard value={stats.institutions} label={t("home.statInstitutions")} />
          </div>
        ) : statsError ? (
          <div className="mt-4">
            <LoadError />
          </div>
        ) : (
          <p className="mt-4 text-sm text-gray-500">{t("common.loading")}</p>
        )}
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-14">
        <div className="grid gap-8 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="font-serif text-2xl font-semibold text-gov-blue-900">{t("home.feedHeading")}</h2>
                <p className="text-sm text-gray-600">{t("home.feedSubtitle")}</p>
              </div>
              <div className="flex flex-wrap gap-3">
                <div>
                  <label htmlFor="status-filter" className="gov-label">
                    {t("home.filterStatus")}
                  </label>
                  <select
                    id="status-filter"
                    className="gov-input"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="all">{t("home.filterAllStatuses")}</option>
                    {STATUS_KEYS.filter((k) => k !== "merged").map((k) => (
                      <option key={k} value={k}>
                        {t(`status.${k}`)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="district-filter" className="gov-label">
                    {t("home.filterDistrict")}
                  </label>
                  <select
                    id="district-filter"
                    className="gov-input"
                    value={districtFilter}
                    onChange={(e) => setDistrictFilter(e.target.value)}
                  >
                    <option value="all">{t("home.filterAllDistricts")}</option>
                    {DISTRICTS.map((d) => (
                      <option key={d.id} value={d.id}>
                        {lang === "hi" ? d.hi : d.en}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {feed === null ? (
              feedError ? (
                <div className="mt-4">
                  <LoadError />
                </div>
              ) : (
                <p className="mt-4 text-sm text-gray-500">{t("common.loading")}</p>
              )
            ) : (
              <>
                <ul aria-live="polite" className="mt-4 grid gap-3 sm:grid-cols-2">
                  {filteredFeed.map((tk) => (
                    <ProblemCard key={tk.ticket_id} ticket={tk} />
                  ))}
                </ul>
                {filteredFeed.length === 0 && <p className="mt-6 text-sm text-gray-500">{t("home.feedEmpty")}</p>}
              </>
            )}
          </div>

          <div>
            <MapPanel tickets={feed || []} />
          </div>
        </div>
      </section>
    </div>
  );
}

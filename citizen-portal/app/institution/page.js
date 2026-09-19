"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageProvider";
import { useStaffGate } from "@/lib/useStaffGate";
import { getInstitutionMatches, getInstitutionPartners, getInstitutionProjects } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import { domainLabel } from "@/lib/categories";
import { formatDate, formatRupees } from "@/lib/format";
import StatCard from "@/components/StatCard";
import AdminBadge from "@/components/AdminBadge";
import LoadError from "@/components/LoadError";

// The institution's front door - brandHref in Header.js points every staff
// portal at `/${portal}`, and this is what used to 404 there for
// "institution" (the three real pages only ever lived one level deeper, at
// /institution/matches|projects|partners). One combined overview, backed by
// the exact same three admin-proxy endpoints those pages already call - no
// new backend route needed.
export default function InstitutionDashboardPage() {
  const { t, lang } = useLanguage();
  const ready = useStaffGate("institution");

  const [matches, setMatches] = useState(null);
  const [matchesError, setMatchesError] = useState(false);
  const [projects, setProjects] = useState(null);
  const [projectsError, setProjectsError] = useState(false);
  const [partners, setPartners] = useState(null);
  const [partnersError, setPartnersError] = useState(false);

  usePolling(
    async () => {
      try {
        const data = await getInstitutionMatches();
        setMatches(Array.isArray(data) ? data : []);
        setMatchesError(false);
      } catch {
        setMatchesError(true);
      }
    },
    { intervalMs: 20000, enabled: ready }
  );

  usePolling(
    async () => {
      try {
        const data = await getInstitutionProjects();
        setProjects(Array.isArray(data) ? data : []);
        setProjectsError(false);
      } catch {
        setProjectsError(true);
      }
    },
    { intervalMs: 20000, enabled: ready }
  );

  usePolling(
    async () => {
      try {
        const data = await getInstitutionPartners();
        setPartners(Array.isArray(data) ? data : []);
        setPartnersError(false);
      } catch {
        setPartnersError(true);
      }
    },
    { intervalMs: 20000, enabled: ready }
  );

  const matchStats = useMemo(() => {
    if (!matches) return null;
    return {
      pending: matches.filter((m) => m.status === "proposed").length,
      accepted: matches.filter((m) => m.status === "accepted").length,
      declined: matches.filter((m) => m.status === "declined").length,
    };
  }, [matches]);

  const totalCommitted = useMemo(() => {
    if (!partners) return null;
    return partners.reduce((sum, l) => sum + (Number(l.total_committed_amount) || 0), 0);
  }, [partners]);

  if (!ready) return null;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="font-serif text-3xl font-semibold text-gov-blue-900">{t("institution.dashboardTitle")}</h1>
      <p className="mt-1 text-gray-600">{t("institution.dashboardSub")}</p>

      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard value={matchStats ? matchStats.pending : "—"} label={t("institution.statPendingMatches")} />
        <StatCard value={matchStats ? matchStats.accepted : "—"} label={t("institution.statAcceptedMatches")} />
        <StatCard value={matchStats ? matchStats.declined : "—"} label={t("institution.statDeclinedMatches")} />
        <StatCard value={projects ? projects.length : "—"} label={t("institution.statActiveProjects")} />
        <StatCard value={partners ? partners.length : "—"} label={t("institution.statPartners")} />
      </div>

      <div className="mt-4">
        <StatCard value={totalCommitted != null ? formatRupees(totalCommitted) : "—"} label={t("institution.statCommittedFunding")} />
      </div>

      <div className="mt-8 grid gap-6 md:grid-cols-3">
        <DashboardSection
          title={t("institution.recentMatchesHeading")}
          href="/institution/matches"
          linkLabel={t("institution.viewSection")}
        >
          {matches === null ? (
            matchesError ? <LoadError /> : <p className="text-sm text-gray-500">{t("common.loading")}</p>
          ) : matches.length === 0 ? (
            <p className="text-sm text-gray-500">{t("institution.noMatches")}</p>
          ) : (
            <ul className="space-y-3">
              {matches.slice(0, 4).map((m) => (
                <li key={m.id} className="flex items-start justify-between gap-2 text-sm">
                  <span className="text-gray-700">
                    {m.ticket_domain ? domainLabel(m.ticket_domain, lang) : `Ticket #${m.ticket_id}`}
                  </span>
                  <MatchStatusBadge status={m.status} t={t} />
                </li>
              ))}
            </ul>
          )}
        </DashboardSection>

        <DashboardSection
          title={t("institution.recentProjectsHeading")}
          href="/institution/projects"
          linkLabel={t("institution.viewSection")}
        >
          {projects === null ? (
            projectsError ? <LoadError /> : <p className="text-sm text-gray-500">{t("common.loading")}</p>
          ) : projects.length === 0 ? (
            <p className="text-sm text-gray-500">{t("institution.noProjects")}</p>
          ) : (
            <ul className="space-y-3">
              {projects.slice(0, 4).map((row) => (
                <li key={row.ticket_id} className="flex items-start justify-between gap-2 text-sm">
                  <span className="text-gray-700">Ticket #{row.ticket_id}</span>
                  <span className="whitespace-nowrap text-xs text-gray-500">{formatDate(row.created_at, lang)}</span>
                </li>
              ))}
            </ul>
          )}
        </DashboardSection>

        <DashboardSection
          title={t("institution.recentPartnersHeading")}
          href="/institution/partners"
          linkLabel={t("institution.viewSection")}
        >
          {partners === null ? (
            partnersError ? <LoadError /> : <p className="text-sm text-gray-500">{t("common.loading")}</p>
          ) : partners.length === 0 ? (
            <p className="text-sm text-gray-500">{t("institution.noPartners")}</p>
          ) : (
            <ul className="space-y-3">
              {partners.slice(0, 4).map((l) => (
                <li key={l.id} className="flex items-start justify-between gap-2 text-sm">
                  <span className="text-gray-700">Proposal #{l.proposal_id}</span>
                  <span className="whitespace-nowrap font-medium text-gov-blue-800">{formatRupees(l.total_committed_amount)}</span>
                </li>
              ))}
            </ul>
          )}
        </DashboardSection>
      </div>
    </div>
  );
}

function DashboardSection({ title, href, linkLabel, children }) {
  return (
    <div className="gov-card flex flex-col p-4">
      <h2 className="font-serif text-base font-semibold text-gov-blue-900">{title}</h2>
      <div className="mt-3 flex-1">{children}</div>
      <Link href={href} className="mt-4 text-sm font-medium text-gov-blue-700 underline hover:text-gov-blue-900">
        {linkLabel} →
      </Link>
    </div>
  );
}

function MatchStatusBadge({ status, t }) {
  if (status === "proposed") return <AdminBadge tone="pending" label={t("institution.statusProposed")} />;
  if (status === "accepted") return <AdminBadge tone="success" label={t("institution.statusAccepted")} />;
  if (status === "declined") return <AdminBadge tone="neutral" label={t("institution.statusDeclined")} />;
  return <AdminBadge tone="neutral" label={status} />;
}

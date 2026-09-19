"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useLanguage } from "@/context/LanguageProvider";
import { useStaffGate } from "@/lib/useStaffGate";
import { domainLabel } from "@/lib/categories";
import { decideInstitutionMatch, formInstitutionTeam, getInstitutionMatches, submitInstitutionProposal } from "@/lib/api";
import { usePolling } from "@/lib/usePolling";
import AdminBadge from "@/components/AdminBadge";
import LoadError from "@/components/LoadError";
import MapPanel from "@/components/MapPanel";

const STATUS_TONE = { proposed: "pending", accepted: "success", declined: "neutral" };

export default function InstitutionCaseDetailPage() {
  const { caseId } = useParams();
  const { t, lang } = useLanguage();
  const ready = useStaffGate("institution");

  const [matches, setMatches] = useState(null);
  const [error, setError] = useState(false);

  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionError, setDecisionError] = useState(null);

  // Neither getInstitutionMatches() nor any other admin-proxy endpoint
  // reports back whether a team/proposal already exists for a match (see
  // "6.Track B Innovation/app/schemas.py" - HeiMatchOut has no such field),
  // so this is session-local progress, not persisted state read back from
  // the server. Reloading this page after forming a team will re-show the
  // team form even though the team really was created - a known gap, not a
  // silent bug: form_team()/submit_proposal() are themselves idempotent
  // enough that re-submitting just errors clearly instead of duplicating.
  const [team, setTeam] = useState(null);
  const [teamForm, setTeamForm] = useState({ teamName: "", mentorName: "", mentorEmail: "", students: "" });
  const [teamBusy, setTeamBusy] = useState(false);
  const [teamError, setTeamError] = useState(null);

  const [proposal, setProposal] = useState(null);
  const [proposalForm, setProposalForm] = useState({ title: "", summary: "", budget: "", timeline: "", file: null });
  const [proposalBusy, setProposalBusy] = useState(false);
  const [proposalError, setProposalError] = useState(null);

  usePolling(
    async () => {
      try {
        const data = await getInstitutionMatches();
        setMatches(Array.isArray(data) ? data : []);
        setError(false);
      } catch {
        setError(true);
      }
    },
    { intervalMs: 20000, enabled: ready }
  );

  if (!ready) return null;

  if (matches === null) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-14">
        {error ? <LoadError /> : <p className="text-center text-gray-500">{t("common.loading")}</p>}
      </div>
    );
  }

  const match = matches.find((m) => String(m.id) === String(caseId));
  if (!match) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-14 text-center">
        <p className="text-gray-700">{t("track.notFound")}</p>
        <Link href="/institution/matches" className="mt-4 inline-block text-gov-blue-700 underline">
          {t("institution.caseBack")}
        </Link>
      </div>
    );
  }

  async function decide(decision) {
    setDecisionBusy(true);
    setDecisionError(null);
    try {
      await decideInstitutionMatch(match.id, { decision });
      setMatches((prev) => prev.map((m) => (m.id === match.id ? { ...m, status: decision === "accept" ? "accepted" : "declined" } : m)));
    } catch {
      setDecisionError(t("institution.decisionError"));
    } finally {
      setDecisionBusy(false);
    }
  }

  async function submitTeam(e) {
    e.preventDefault();
    setTeamBusy(true);
    setTeamError(null);
    try {
      const students = teamForm.students
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const result = await formInstitutionTeam(match.id, { ...teamForm, students });
      setTeam({ ...teamForm, teamId: result.team_id });
    } catch {
      setTeamError(t("institution.formTeamError"));
    } finally {
      setTeamBusy(false);
    }
  }

  async function submitProposal(e) {
    e.preventDefault();
    setProposalBusy(true);
    setProposalError(null);
    try {
      const result = await submitInstitutionProposal(match.id, {
        title: proposalForm.title,
        summary: proposalForm.summary,
        budget: proposalForm.budget,
        timelineWeeks: proposalForm.timeline,
        solutionDocument: proposalForm.file,
      });
      setProposal(result);
    } catch {
      setProposalError(t("institution.proposalSubmitError"));
    } finally {
      setProposalBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <Link href="/institution/matches" className="text-sm text-gov-blue-700 underline">
        {t("institution.caseBack")}
      </Link>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="font-serif text-2xl font-semibold text-gov-blue-900">
          {t("institution.caseTitle").replace("{id}", match.id)}
        </h1>
        <AdminBadge
          tone={STATUS_TONE[match.status] || "neutral"}
          label={
            match.status === "proposed"
              ? t("institution.statusProposed")
              : match.status === "accepted"
                ? t("institution.statusAccepted")
                : t("institution.statusDeclined")
          }
        />
      </div>

      <dl className="gov-card mt-4 divide-y divide-gov-blue-50">
        <div className="p-4">
          <dt className="text-xs font-semibold uppercase text-gray-500">{t("institution.sectionDescription")}</dt>
          <dd className="mt-1 text-gray-800">{match.ticket_problem_statement || `Ticket #${match.ticket_id}`}</dd>
        </div>
        <div className="p-4">
          <dt className="text-xs font-semibold uppercase text-gray-500">{t("track.categoryLabel")}</dt>
          <dd className="mt-1 text-gray-800">{match.ticket_domain ? domainLabel(match.ticket_domain, lang) : "—"}</dd>
        </div>
        {match.ticket_lat != null && match.ticket_lon != null && (
          <div className="p-4">
            <dt className="text-xs font-semibold uppercase text-gray-500">{t("institution.sectionLocation")}</dt>
            <dd className="mt-2 max-w-xs">
              <MapPanel
                tickets={[{ ticket_id: match.ticket_id, lat: match.ticket_lat, lon: match.ticket_lon, domain: match.ticket_domain }]}
                heading={t("institution.sectionLocation")}
                caption=""
              />
            </dd>
          </div>
        )}
      </dl>

      {match.status === "proposed" && (
        <div className="gov-card mt-6 p-4">
          <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("institution.decisionHeading")}</h2>
          <p className="mt-1 text-sm text-gray-600">{t("institution.decisionSub")}</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" className="gov-btn-primary" disabled={decisionBusy} onClick={() => decide("accept")}>
              {t("institution.actionAccept")}
            </button>
            <button type="button" className="gov-btn-secondary" disabled={decisionBusy} onClick={() => decide("decline")}>
              {t("institution.actionDecline")}
            </button>
          </div>
          {decisionError && <p className="mt-3 text-sm text-red-700">{decisionError}</p>}
        </div>
      )}

      {match.status === "declined" && (
        <div className="mt-6 rounded-md border border-gray-300 bg-gray-50 p-4 text-sm text-gray-700">
          {t("institution.declinedNotice")}
        </div>
      )}

      {match.status === "accepted" &&
        (!team ? (
          <form onSubmit={submitTeam} className="gov-card mt-6 space-y-3 p-4">
            <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("institution.formTeamHeading")}</h2>
            <div>
              <label htmlFor="team-name" className="gov-label">
                {t("institution.formTeamName")}
              </label>
              <input
                id="team-name"
                className="gov-input"
                required
                value={teamForm.teamName}
                onChange={(e) => setTeamForm({ ...teamForm, teamName: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="mentor-name" className="gov-label">
                {t("institution.formMentorName")}
              </label>
              <input
                id="mentor-name"
                className="gov-input"
                required
                value={teamForm.mentorName}
                onChange={(e) => setTeamForm({ ...teamForm, mentorName: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="mentor-email" className="gov-label">
                {t("institution.formMentorEmail")}
              </label>
              <input
                id="mentor-email"
                type="email"
                className="gov-input"
                required
                value={teamForm.mentorEmail}
                onChange={(e) => setTeamForm({ ...teamForm, mentorEmail: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="students" className="gov-label">
                {t("institution.formStudents")}
              </label>
              <input
                id="students"
                className="gov-input"
                value={teamForm.students}
                onChange={(e) => setTeamForm({ ...teamForm, students: e.target.value })}
              />
            </div>
            {teamError && <p className="text-sm text-red-700">{teamError}</p>}
            <button type="submit" className="gov-btn-primary" disabled={teamBusy}>
              {teamBusy ? t("common.loading") : t("institution.formTeamSubmit")}
            </button>
          </form>
        ) : !proposal ? (
          <form onSubmit={submitProposal} className="gov-card mt-6 space-y-3 p-4">
            <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("institution.proposalHeading")}</h2>
            <div>
              <label htmlFor="proposal-title" className="gov-label">
                {t("institution.proposalTitle")}
              </label>
              <input
                id="proposal-title"
                className="gov-input"
                required
                value={proposalForm.title}
                onChange={(e) => setProposalForm({ ...proposalForm, title: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="proposal-summary" className="gov-label">
                {t("institution.proposalSummary")}
              </label>
              <p className="mb-1 text-xs text-gray-500">{t("institution.proposalSummaryHelp")}</p>
              <textarea
                id="proposal-summary"
                rows={6}
                className="gov-input"
                required
                value={proposalForm.summary}
                onChange={(e) => setProposalForm({ ...proposalForm, summary: e.target.value })}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor="proposal-budget" className="gov-label">
                  {t("institution.proposalBudget")}
                </label>
                <input
                  id="proposal-budget"
                  type="number"
                  className="gov-input"
                  value={proposalForm.budget}
                  onChange={(e) => setProposalForm({ ...proposalForm, budget: e.target.value })}
                />
              </div>
              <div>
                <label htmlFor="proposal-timeline" className="gov-label">
                  {t("institution.proposalTimeline")}
                </label>
                <input
                  id="proposal-timeline"
                  type="number"
                  className="gov-input"
                  value={proposalForm.timeline}
                  onChange={(e) => setProposalForm({ ...proposalForm, timeline: e.target.value })}
                />
              </div>
            </div>
            <div>
              <label htmlFor="proposal-document" className="gov-label">
                {t("institution.proposalDocument")}
              </label>
              <p className="mb-1 text-xs text-gray-500">{t("institution.proposalDocumentHelp")}</p>
              <input
                id="proposal-document"
                type="file"
                accept="application/pdf"
                className="gov-input"
                onChange={(e) => setProposalForm({ ...proposalForm, file: e.target.files?.[0] || null })}
              />
            </div>
            {proposalError && <p className="text-sm text-red-700">{proposalError}</p>}
            <button type="submit" className="gov-btn-primary" disabled={proposalBusy}>
              {proposalBusy ? t("common.loading") : t("institution.proposalSubmit")}
            </button>
          </form>
        ) : (
          <div className="gov-card mt-6 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="font-serif text-lg font-semibold text-gov-blue-900">{t("institution.proposalSubmittedHeading")}</h2>
              <AdminBadge tone="pending" label={t("institution.proposalSubmittedSub")} />
            </div>
            <p className="mt-2 text-gray-800">{proposal.title}</p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-gray-600">{proposal.summary}</p>
            {proposal.solution_document_url && (
              <a
                href={proposal.solution_document_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block text-sm text-gov-blue-700 underline hover:text-gov-blue-900"
              >
                {t("institution.proposalDocument")} ↗
              </a>
            )}
          </div>
        ))}
    </div>
  );
}

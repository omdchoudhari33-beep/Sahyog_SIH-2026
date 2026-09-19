"use client";

import { useEffect, useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import StepIndicator from "@/components/StepIndicator";
import StepDescribe from "@/components/submit/StepDescribe";
import StepEvidence from "@/components/submit/StepEvidence";
import StepLocation from "@/components/submit/StepLocation";
import StepReview from "@/components/submit/StepReview";
import StepDone from "@/components/submit/StepDone";
import { districtLabel } from "@/lib/districts";
import { useVoiceBot } from "@/lib/useVoiceBot";
import {
  describeProblem as apiDescribeProblem,
  confirmProblem as apiConfirmProblem,
  attachPhoto as apiAttachPhoto,
  submitLocation as apiSubmitLocation,
  finalizeReport as apiFinalizeReport,
  uploadAudio,
} from "@/lib/api";

// A backend call's Error carries a real, actionable detail message (see
// lib/api.js's request()) - show that as-is. A timed-out request instead
// carries a raw browser AbortController exception (err.isTimeout, tagged by
// request()) whose own .message ("signal is aborted without reason" in
// Chromium) means nothing to a citizen, so that case gets the same
// translated copy the LoadError component already uses instead.
function describeError(err, t) {
  if (err?.isTimeout) return t("common.networkError");
  return err?.message || t("common.errorGeneric");
}

const INITIAL = {
  stepIndex: 0,
  sessionId: null,
  text: "",
  understood: null,
  photoFile: null,
  matchWarning: null,
  district: "",
  address: "",
  usedGps: false,
  ticket: null,
};

export default function SubmitPage() {
  const { t, lang } = useLanguage();
  const [state, setState] = useState(INITIAL);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const voiceBot = useVoiceBot(lang);

  const { stepIndex, sessionId, text, understood, photoFile, matchWarning, district, address, usedGps, ticket } = state;

  function patch(partial) {
    setState((prev) => ({ ...prev, ...partial }));
  }

  // Warn on tab close/refresh mid-flow - a citizen losing a half-filled
  // report to an accidental reload is exactly the kind of thing a real
  // government portal should guard against.
  useEffect(() => {
    function handler(e) {
      if (stepIndex > 0 && stepIndex < 4) {
        e.preventDefault();
        e.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [stepIndex]);

  function applyDescribeResult(result) {
    patch({
      sessionId: result.session_id,
      understood: {
        statement: result.understood_statement,
        domain: result.domain,
        severity: result.severity,
        warning: result.warning,
      },
    });
    voiceBot.speak(result.message);
  }

  async function handleSubmitText() {
    setBusy(true);
    setError(null);
    try {
      const result = await apiDescribeProblem({ text, sourceLanguage: lang });
      applyDescribeResult(result);
    } catch (err) {
      setError(describeError(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitAudio(blob) {
    setBusy(true);
    setError(null);
    try {
      const upload = await uploadAudio(blob);
      const result = await apiDescribeProblem({ localAudioPath: upload.local_audio_path, sourceLanguage: lang });
      applyDescribeResult(result);
    } catch (err) {
      setError(describeError(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm({ confirmed, correctedText }) {
    setBusy(true);
    setError(null);
    try {
      const result = await apiConfirmProblem(sessionId, { confirmed, correctedText });
      patch({
        understood: { ...understood, statement: result.understood_statement },
        stepIndex: 1,
      });
      voiceBot.speak(result.message);
    } catch (err) {
      setError(describeError(err, t));
    } finally {
      setBusy(false);
    }
  }

  function handlePhotoChange(file) {
    patch({ photoFile: file, matchWarning: null });
  }

  async function handleUploadPhoto({ force }) {
    setBusy(true);
    setError(null);
    try {
      const result = await apiAttachPhoto(sessionId, photoFile, { force });

      // The Orchestrator only BLOCKS on a mismatch when force is false (see
      // "4.Orchestrator/app/main.py"'s conversation_photo) - once the citizen
      // has already clicked "Continue anyway" (force=true), it proceeds and
      // still honestly echoes photo_matches:false in the success response,
      // which must NOT be treated as a fresh block or "Continue anyway"
      // would loop forever back to the same warning.
      if (result.photo_matches === false && !force) {
        patch({ matchWarning: { discrepancy_notes: result.discrepancy_notes } });
        voiceBot.speak(result.message);
        return;
      }
      patch({ matchWarning: null, stepIndex: result.state === "ready" ? 3 : 2 });
      voiceBot.speak(result.message);
    } catch (err) {
      setError(describeError(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitLocation({ lat, lon, addressText }) {
    setBusy(true);
    setError(null);
    try {
      const composedAddress =
        addressText && district ? `${addressText}, ${districtLabel(district, "en")} district, Jharkhand` : addressText;

      const result = await apiSubmitLocation(sessionId, { latitude: lat, longitude: lon, addressText: composedAddress });

      patch({
        usedGps: lat != null && lon != null,
        address: addressText || address,
        stepIndex: 3,
      });
      voiceBot.speak(result.message);
    } catch (err) {
      setError(describeError(err, t));
    } finally {
      setBusy(false);
    }
  }

  async function handleFinalSubmit() {
    setBusy(true);
    setError(null);
    try {
      const result = await apiFinalizeReport(sessionId);
      patch({ ticket: result.ticket, stepIndex: 4 });
      voiceBot.speak(result.message);
    } catch {
      setError(t("submit.submitFailed"));
    } finally {
      setBusy(false);
    }
  }

  function handleRestart() {
    setState(INITIAL);
    setError(null);
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="sr-only">{t("submit.wizardTitle")}</h1>
      <div className="mb-2 flex justify-end">
        <button
          type="button"
          onClick={voiceBot.toggle}
          className="flex items-center gap-1.5 rounded-full border border-gov-blue-200 px-3 py-1 text-xs font-medium text-gov-blue-700 hover:bg-gov-blue-50"
          aria-pressed={voiceBot.enabled}
        >
          <span aria-hidden="true">{voiceBot.enabled ? "🔊" : "🔇"}</span>
          {voiceBot.enabled ? t("common.voiceOn") : t("common.voiceOff")}
        </button>
      </div>
      <StepIndicator currentIndex={stepIndex} />

      {stepIndex === 0 && (
        <StepDescribe
          text={text}
          onTextChange={(v) => patch({ text: v })}
          understood={understood}
          busy={busy}
          error={error}
          onSubmitText={handleSubmitText}
          onSubmitAudio={handleSubmitAudio}
          onConfirm={handleConfirm}
        />
      )}

      {stepIndex === 1 && (
        <StepEvidence
          understood={understood}
          photoFile={photoFile}
          onPhotoChange={handlePhotoChange}
          busy={busy}
          error={error}
          matchWarning={matchWarning}
          onUpload={handleUploadPhoto}
        />
      )}

      {stepIndex === 2 && (
        <StepLocation
          address={address}
          onAddressChange={(v) => patch({ address: v })}
          district={district}
          onDistrictChange={(v) => patch({ district: v })}
          busy={busy}
          error={error}
          onSubmit={handleSubmitLocation}
        />
      )}

      {stepIndex === 3 && (
        <StepReview
          domain={understood?.domain}
          statement={understood?.statement}
          photoFile={photoFile}
          district={district}
          address={address}
          usedGps={usedGps}
          busy={busy}
          error={error}
          onEditStep={(i) => patch({ stepIndex: i })}
          onSubmit={handleFinalSubmit}
        />
      )}

      {stepIndex === 4 && ticket && (
        <StepDone
          ticketId={ticket.ticket_id}
          domain={understood?.domain}
          statement={understood?.statement}
          severity={understood?.severity}
          photoFile={photoFile}
          district={district}
          address={address}
          usedGps={usedGps}
          onRestart={handleRestart}
        />
      )}
    </div>
  );
}

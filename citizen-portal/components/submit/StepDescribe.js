"use client";

import { useEffect, useRef, useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import { domainLabel } from "@/lib/categories";
import { severityWord } from "@/lib/format";

export default function StepDescribe({
  text,
  onTextChange,
  understood,
  busy,
  error,
  onSubmitText,
  onSubmitAudio,
  onConfirm,
}) {
  const { t, lang } = useLanguage();
  const [recording, setRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState(null);
  const [micSupported, setMicSupported] = useState(true);
  const [correcting, setCorrecting] = useState(false);
  const [correctionText, setCorrectionText] = useState("");
  const [localValidation, setLocalValidation] = useState(null);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  useEffect(() => {
    setMicSupported(
      typeof navigator !== "undefined" && !!navigator.mediaDevices && typeof window !== "undefined" && !!window.MediaRecorder
    );
  }, []);

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setRecordedBlob(blob);
        stream.getTracks().forEach((tr) => tr.stop());
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setMicSupported(false);
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  function handleSubmit() {
    if (recordedBlob) {
      onSubmitAudio(recordedBlob);
      return;
    }
    if (!text || !text.trim()) {
      setLocalValidation(t("submit.validationNeedText"));
      return;
    }
    setLocalValidation(null);
    onSubmitText();
  }

  if (understood) {
    return (
      <div>
        <h2 className="font-serif text-2xl font-semibold text-gov-blue-900">{t("submit.understoodHeading")}</h2>

        <div className="gov-card mt-4 space-y-3 p-4">
          <p className="text-gray-800">&ldquo;{understood.statement}&rdquo;</p>
          {understood.domain != null ? (
            <div className="flex flex-wrap gap-4 text-sm text-gray-600">
              <span>
                <strong className="text-gov-blue-800">{t("submit.understoodDomain")}:</strong>{" "}
                {domainLabel(understood.domain, lang)}
              </span>
              <span>
                <strong className="text-gov-blue-800">{t("submit.understoodSeverity")}:</strong>{" "}
                {severityWord(understood.severity, lang)}
              </span>
            </div>
          ) : null}
          {understood.warning && (
            <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">{understood.warning}</p>
          )}
        </div>

        {error && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {error}
          </p>
        )}

        {!correcting ? (
          <div className="mt-5 flex flex-wrap gap-3">
            <button type="button" className="gov-btn-primary" disabled={busy} onClick={() => onConfirm({ confirmed: true })}>
              {t("submit.understoodConfirm")}
            </button>
            <button type="button" className="gov-btn-secondary" disabled={busy} onClick={() => setCorrecting(true)}>
              {t("submit.understoodEdit")}
            </button>
          </div>
        ) : (
          <div className="mt-5">
            <label htmlFor="correction" className="gov-label">
              {t("submit.correctionLabel")}
            </label>
            <textarea
              id="correction"
              rows={3}
              className="gov-input"
              placeholder={t("submit.correctionPlaceholder")}
              value={correctionText}
              onChange={(e) => setCorrectionText(e.target.value)}
            />
            <button
              type="button"
              className="gov-btn-primary mt-3"
              disabled={busy || !correctionText.trim()}
              onClick={() => onConfirm({ confirmed: false, correctedText: correctionText.trim() })}
            >
              {t("submit.correctionSave")}
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <h2 className="font-serif text-2xl font-semibold text-gov-blue-900">{t("submit.describeHeading")}</h2>
      <p className="mt-1 text-sm text-gray-600">{t("submit.describeSub")}</p>

      <div className="mt-5">
        <label htmlFor="describe-text" className="gov-label">
          {t("submit.textLabel")}
        </label>
        <textarea
          id="describe-text"
          rows={4}
          className="gov-input"
          placeholder={t("submit.textPlaceholder")}
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
        />
        <p className="mt-1 text-xs text-gray-500">{t("submit.textHelp")}</p>
      </div>

      {micSupported && (
        <div className="mt-4 flex items-center gap-3">
          <span className="text-sm text-gray-500">{t("submit.orDivider")}</span>
          {!recording ? (
            <button type="button" className="gov-btn-secondary" onClick={startRecording} disabled={busy}>
              🎙️ {t("submit.voiceStart")}
            </button>
          ) : (
            <button type="button" className="gov-btn-accent" onClick={stopRecording}>
              ⏹ {t("submit.voiceStop")}
            </button>
          )}
          {recording && <span className="text-sm text-gov-orange-700">{t("submit.voiceRecording")}</span>}
          {!recording && recordedBlob && <span className="text-sm text-green-700">{t("submit.voiceRecorded")}</span>}
        </div>
      )}

      {(localValidation || error) && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {localValidation || error}
        </p>
      )}

      <div className="mt-6 flex justify-end">
        <button type="button" className="gov-btn-primary" disabled={busy} onClick={handleSubmit}>
          {busy ? t("common.loading") : t("submit.describeSubmit")}
        </button>
      </div>
    </div>
  );
}

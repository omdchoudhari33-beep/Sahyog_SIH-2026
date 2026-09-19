"use client";

import { useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";
import { useVoiceBot } from "@/lib/useVoiceBot";
import { askQuestion } from "@/lib/api";

// Same pattern as app/submit/page.js's describeError: a backend call's
// Error carries a real, actionable detail message - show that as-is. A
// timed-out request instead carries a raw browser AbortController exception
// whose own .message means nothing to a citizen.
function describeError(err, t) {
  if (err?.isTimeout) return t("common.networkError");
  return err?.message || t("common.errorGeneric");
}

export default function AskPage() {
  const { t, lang } = useLanguage();
  const voiceBot = useVoiceBot(lang);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [sources, setSources] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!question.trim() || busy) return;
    setBusy(true);
    setError(null);
    setAnswer(null);
    try {
      const result = await askQuestion(question.trim(), lang);
      setAnswer(result.answer);
      setSources(result.sources || []);
      voiceBot.speak(result.answer);
    } catch (err) {
      setError(describeError(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-14">
      <h1 className="font-serif text-3xl font-semibold text-gov-blue-900">{t("ask.heading")}</h1>
      <p className="mt-2 text-gray-600">{t("ask.sub")}</p>

      <form onSubmit={handleSubmit} className="mt-6">
        <label htmlFor="ask-question" className="gov-label">
          {t("ask.questionLabel")}
        </label>
        <textarea
          id="ask-question"
          className="gov-input min-h-[6rem]"
          placeholder={t("ask.placeholder")}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button type="submit" className="gov-btn-primary mt-3" disabled={busy || !question.trim()}>
          {busy ? t("ask.asking") : t("ask.submitButton")}
        </button>
        {error && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {error}
          </p>
        )}
      </form>

      {answer && (
        <div className="gov-card mt-8">
          <p className="text-gray-900">{answer}</p>
          {sources.length > 0 && (
            <div className="mt-4 border-t border-gray-200 pt-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                {t("ask.sourcesLabel")}
              </p>
              <ul className="mt-2 space-y-1 text-sm text-gray-600">
                {sources.map((s, i) =>
                  s.type === "ticket" ? (
                    <li key={`ticket-${s.ticket_id}`}>
                      {t("ask.sourceTicket")} #{s.ticket_id} - {s.status}
                    </li>
                  ) : (
                    <li key={`kb-${s.source}-${i}`}>{s.title}</li>
                  )
                )}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

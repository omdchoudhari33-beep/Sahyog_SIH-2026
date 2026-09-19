"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { translate } from "@/lib/dict";
import { LANGUAGE_CODES, isRtl } from "@/lib/languages";

const STORAGE_KEY = "sahyog_lang";

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState("en");

  // Restore the citizen's last choice. Runs after mount only, so server and
  // first client render both output English and React never sees a
  // hydration mismatch.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (LANGUAGE_CODES.includes(saved)) setLangState(saved);
    } catch {
      // localStorage unavailable (private mode etc.) - default to English.
    }
  }, []);

  const setLang = useCallback((next) => {
    if (!LANGUAGE_CODES.includes(next)) return;
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Non-fatal: language choice just won't persist across visits.
    }
  }, []);

  const t = useCallback((path) => translate(lang, path), [lang]);

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {/* This div is body's only direct child, so it - not body - must
          carry the flex chain body -> main(flex-1) -> footer relies on to
          keep the footer pinned to the viewport bottom on short pages. */}
      <div lang={lang} dir={isRtl(lang) ? "rtl" : "ltr"} className="flex min-h-screen flex-col">
        {children}
      </div>
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useLanguage() must be called within a <LanguageProvider>");
  }
  return ctx;
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { speakText } from "@/lib/api";

const STORAGE_KEY = "sahyog_voice_bot_enabled";

// The voice bot's playback side: turns the English `message` text every
// conversation-flow call already returns into spoken audio in the
// citizen's chosen language, via the Orchestrator's /speak proxy
// (lib/api.js's speakText - translation + TTS happen server-side, this
// hook only ever plays back whatever Blob comes out).
export function useVoiceBot(lang) {
  const [enabled, setEnabled] = useState(true);
  const audioRef = useRef(null);
  const urlRef = useRef(null);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved != null) setEnabled(saved === "true");
    } catch {
      // localStorage unavailable (private mode etc.) - default stays on.
    }
  }, []);

  const cleanup = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
  }, []);

  // Stop any in-flight speech if the citizen navigates away mid-playback.
  useEffect(() => cleanup, [cleanup]);

  const toggle = useCallback(() => {
    setEnabled((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // Non-fatal: the toggle just won't persist across visits.
      }
      if (!next) cleanup();
      return next;
    });
  }, [cleanup]);

  const speak = useCallback(
    async (text) => {
      if (!enabled || !text) return;
      cleanup(); // a new message always interrupts whatever was still playing
      const blob = await speakText(text, lang);
      if (!blob) return; // backend had nothing to say - stay silent, text is already on screen
      const url = URL.createObjectURL(blob);
      urlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      // Autoplay can still be blocked in rare cases (e.g. a non-user-
      // gesture code path) - never let that surface as an error, the
      // citizen already has the text.
      audio.play().catch(() => {});
    },
    [enabled, lang, cleanup]
  );

  return { enabled, toggle, speak };
}

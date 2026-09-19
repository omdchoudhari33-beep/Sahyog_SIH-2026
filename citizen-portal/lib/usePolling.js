"use client";

import { useEffect, useRef } from "react";

// Calls `fn` immediately, then every `intervalMs`, until unmounted or
// `enabled` goes false. Skips starting a new call while a previous one is
// still in flight, so a slow/hung backend response doesn't pile up
// overlapping requests. This is the app's "real-time" mechanism - plain
// polling, not a websocket/SSE push channel.
// `deps` lets a caller (e.g. a page with filter inputs) restart the timer
// and re-fetch immediately when those values change, instead of waiting
// for the next scheduled tick.
export function usePolling(fn, { intervalMs = 20000, enabled = true, deps = [] } = {}) {
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const runningRef = useRef(false);

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;

    async function tick() {
      if (runningRef.current || cancelled) return;
      runningRef.current = true;
      try {
        await fnRef.current();
      } finally {
        runningRef.current = false;
      }
    }

    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, intervalMs, ...deps]);
}

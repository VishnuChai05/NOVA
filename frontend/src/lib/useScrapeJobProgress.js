import { useEffect, useRef, useState } from "react";

import { clearScrapeJobStatusCache, getScrapeJobStatus, peekScrapeJobStatus } from "./api";

function createInitialState(jobId) {
  const cached = jobId ? peekScrapeJobStatus(jobId) : null;
  return (
    cached || {
      job_id: jobId || "",
      status: "idle",
      progress_pct: 0,
      message: "",
      result: null,
    }
  );
}

export default function useScrapeJobProgress(jobId, { enabled = true, pollIntervalMs = 2500, onComplete } = {}) {
  const [state, setState] = useState(() => createInitialState(jobId));
  const onCompleteRef = useRef(onComplete);
  const timerRef = useRef(null);
  const activeRef = useRef(false);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    activeRef.current = false;

    if (!enabled || !jobId) {
      setState(createInitialState(null));
      return undefined;
    }

    let cancelled = false;
    let currentDelay = pollIntervalMs;
    setState(createInitialState(jobId));

    const poll = async (force = false) => {
      if (cancelled || activeRef.current) {
        return;
      }

      activeRef.current = true;
      try {
        const response = await getScrapeJobStatus(jobId, { force });
        if (cancelled) return;

        const next = response.data || null;
        if (!next) {
          return;
        }

        setState(next);
        const finished = next.status === "done" || next.status === "failed";
        if (finished) {
          clearScrapeJobStatusCache(jobId);
          onCompleteRef.current?.(next);
          return;
        }

        currentDelay = Math.min(Math.round(currentDelay * 1.5), 30000);
        timerRef.current = window.setTimeout(() => {
          void poll(true);
        }, currentDelay);
      } catch (error) {
        if (cancelled) return;
        setState((current) => ({
          ...current,
          status: current.status === "idle" ? "running" : current.status,
          message: error?.response?.data?.detail || "Unable to refresh scrape progress.",
        }));
        currentDelay = Math.min(Math.round(currentDelay * 1.5), 30000);
        timerRef.current = window.setTimeout(() => {
          void poll(true);
        }, currentDelay);
      } finally {
        activeRef.current = false;
      }
    };

    void poll(false);

    return () => {
      cancelled = true;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [enabled, jobId, pollIntervalMs]);

  return state;
}

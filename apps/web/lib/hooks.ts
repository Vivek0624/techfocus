"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage, isTerminal, type AgentRun } from "./api";

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
  setData: (d: T | null) => void;
}

/** Fetch on mount and whenever `deps` change. */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  });

  useEffect(() => {
    let alive = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loading flag for a fresh request
    setLoading(true);
    fnRef
      .current()
      .then((d) => {
        if (!alive) return;
        setData(d);
        setError(null);
      })
      .catch((e) => alive && setError(errorMessage(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload, setData };
}

export const POLL_MS = 1000;

/**
 * Poll an agent run until it reaches a terminal state.
 * `cancelling` is a client-side overlay: once cancel is requested we show "cancelling"
 * until the worker reports "cancelled" (or another terminal state). Never "cancelled" early.
 */
export function useRunPoller(onDone?: (run: AgentRun) => void) {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const doneRef = useRef(onDone);
  useEffect(() => {
    doneRef.current = onDone;
  });

  const stop = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const poll = useCallback(
    (id: number) => {
      stop();
      const tickFn = async () => {
        try {
          const r = await api.agentRun(id);
          setRun(r);
          setError(null);
          if (isTerminal(r.status)) {
            setCancelling(false);
            doneRef.current?.(r);
            return;
          }
        } catch (e) {
          setError(errorMessage(e));
        }
        timer.current = setTimeout(tickFn, POLL_MS);
      };
      timer.current = setTimeout(tickFn, POLL_MS);
    },
    [stop],
  );

  const track = useCallback(
    (r: AgentRun) => {
      setRun(r);
      setCancelling(false);
      setError(null);
      if (!isTerminal(r.status)) poll(r.id);
      else doneRef.current?.(r);
    },
    [poll],
  );

  const start = useCallback(
    async (agentId: string, input: Record<string, unknown>) => {
      setError(null);
      try {
        const r = await api.runAgent(agentId, input);
        track(r);
        return r;
      } catch (e) {
        setError(errorMessage(e));
        return null;
      }
    },
    [track],
  );

  const cancel = useCallback(async () => {
    if (!run) return;
    try {
      const res = await api.cancelRun(run.id);
      if (res.state === "cancelling" || !isTerminal(res.state)) setCancelling(true);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [run]);

  const retry = useCallback(async () => {
    if (!run) return;
    try {
      track(await api.retryRun(run.id));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [run, track]);

  useEffect(() => stop, [stop]);

  const status = run ? (cancelling && !isTerminal(run.status) ? "cancelling" : run.status) : null;
  return { run, status, error, start, track, cancel, retry, active: !!run && !isTerminal(run.status) };
}

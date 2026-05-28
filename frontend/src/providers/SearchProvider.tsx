'use client';

import {
  createContext,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type { SearchRunStatus, CompanyProgress } from '@/lib/types';
import api from '@/lib/api';
import { jobsApi, type ActiveSearchResponse } from '@/lib/api/jobs';
import { useProfile } from '@/hooks/useProfile';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';


// ─── Types ──────────────────────────────────────────────
interface SearchPollingSummary {
  companiesDone: number;
  companiesScanning: number;
  totalJobs: number;
  totalMatches: number;
}

export interface SearchContextValue {
  runId: number | null;
  status: SearchRunStatus | null;
  progress: CompanyProgress[];
  summary: SearchPollingSummary;
  isActive: boolean;
  starting: boolean;
  stopping: boolean;
  error: string | null;
  initializing: boolean;
  startSearch: () => Promise<void>;
  stopSearch: () => Promise<void>;
  retry: () => void;
  resetBatches: () => Promise<void>;
}

export const SearchContext = createContext<SearchContextValue | null>(null);

// ─── Constants ──────────────────────────────────────────
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'stopped']);
const POLL_INTERVAL = 2000;

// ─── Provider ───────────────────────────────────────────
export function SearchProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { refreshStats } = useProfile();
  const { addToast } = useToast();

  const [runId, setRunId] = useState<number | null>(null);
  const [status, setStatus] = useState<SearchRunStatus | null>(null);
  const [isActive, setIsActive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initializing, setInitializing] = useState(true);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const calledRefreshRef = useRef(false);

  // ── Stop polling ──
  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // ── Poll once ──
  const poll = useCallback(
    async (id: number) => {
      try {
        const { data } = await api.get<SearchRunStatus>(`/jobs/search/${id}`, { _silent: true } as Record<string, unknown>);
        setStatus(data);

        if (TERMINAL_STATUSES.has(data.status)) {
          setIsActive(false);
          stopPolling();
          if (!calledRefreshRef.current) {
            calledRefreshRef.current = true;
            refreshStats();
          }
        } else {
          setIsActive(true);
        }
      } catch {
        // Keep polling on transient errors
      }
    },
    [stopPolling, refreshStats],
  );

  // ── Start polling for a given runId ──
  const startPolling = useCallback(
    (id: number) => {
      stopPolling();
      calledRefreshRef.current = false;
      poll(id);
      intervalRef.current = setInterval(() => poll(id), POLL_INTERVAL);
    },
    [poll, stopPolling],
  );

  // ── Check for active search on mount (once per session) ──
  useEffect(() => {
    if (!user) {
      setInitializing(false);
      return;
    }

    api
      .get<ActiveSearchResponse>('/jobs/search/active', { _silent: true } as Record<string, unknown>)
      .then(({ data }) => {
        if (data.active && data.search_run_id) {
          setRunId(data.search_run_id);
          setStatus({
            id: data.search_run_id,
            status: data.status as SearchRunStatus['status'],
            companies_searched: data.companies_searched ?? 0,
            jobs_found: data.jobs_found ?? 0,
            jobs_matched: data.jobs_matched ?? 0,
            progress: data.progress ?? [],
          } as SearchRunStatus);
          startPolling(data.search_run_id);
        }
      })
      .catch(() => {})
      .finally(() => setInitializing(false));

    return stopPolling;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  // ── Start a new search ──
  const startSearch = useCallback(async () => {
    setStarting(true);
    setError(null);
    try {
      const { data } = await jobsApi.startSearch();
      setRunId(data.search_run_id);
      setStatus(null); // clear old status
      startPolling(data.search_run_id);
      addToast({
        type: 'info',
        message: `Search started — scanning ${data.companies_count} companies`,
      });
    } catch {
      setError('Failed to start search. Please try again.');
    } finally {
      setStarting(false);
    }
  }, [addToast, startPolling]);

  // ── Stop current search ──
  const stopSearchFn = useCallback(async () => {
    if (!runId) return;
    setStopping(true);
    try {
      await jobsApi.stopSearch(runId);
      addToast({ type: 'warning', message: 'Search stopped' });
    } catch {
      addToast({ type: 'error', message: 'Failed to stop search' });
    } finally {
      setStopping(false);
    }
  }, [runId, addToast]);

  // ── Retry ──
  const retry = useCallback(() => {
    setError(null);
    setRunId(null);
    setStatus(null);
    startSearch();
  }, [startSearch]);

  // ── Reset batches ──
  const resetBatches = useCallback(async () => {
    try {
      await api.post('/jobs/search/reset', {}, { _silent: true } as Record<string, unknown>);
      setRunId(null);
      setStatus(null);
      setError(null);
      addToast({ type: 'success', message: 'Search batches reset — next search starts from batch 1' });
    } catch {
      addToast({ type: 'error', message: 'Failed to reset' });
    }
  }, [addToast]);

  // ── Derived values ──
  const progress = status?.progress ?? [];

  const summary: SearchPollingSummary = {
    companiesDone: progress.filter((c) => c.status === 'done').length,
    companiesScanning: progress.filter((c) => c.status === 'scanning').length,
    totalJobs: status?.jobs_found ?? 0,
    totalMatches: status?.jobs_matched ?? 0,
  };

  return (
    <SearchContext.Provider
      value={{
        runId,
        status,
        progress,
        summary,
        isActive,
        starting,
        stopping,
        error,
        initializing,
        startSearch,
        stopSearch: stopSearchFn,
        retry,
        resetBatches,
      }}
    >
      {children}
    </SearchContext.Provider>
  );
}

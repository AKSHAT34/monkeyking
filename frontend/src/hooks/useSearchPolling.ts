'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { SearchRunStatus, CompanyProgress } from '@/lib/types';
import { jobsApi } from '@/lib/api/jobs';
import { useProfile } from '@/hooks/useProfile';

interface SearchPollingSummary {
  companiesDone: number;
  companiesScanning: number;
  totalJobs: number;
  totalMatches: number;
}

export interface SearchPollingResult {
  status: SearchRunStatus | null;
  progress: CompanyProgress[];
  summary: SearchPollingSummary;
  isActive: boolean;
}

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'stopped']);
const POLL_INTERVAL = 2000;

export function useSearchPolling(runId: number | null): SearchPollingResult {
  const { refreshStats } = useProfile();
  const [status, setStatus] = useState<SearchRunStatus | null>(null);
  const [isActive, setIsActive] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const calledRefreshRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const poll = useCallback(async (id: number) => {
    try {
      const { data } = await jobsApi.getSearchStatus(id);
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
      // Keep polling on transient errors — the retry interceptor handles network issues
    }
  }, [stopPolling, refreshStats]);

  useEffect(() => {
    stopPolling();
    calledRefreshRef.current = false;

    if (runId == null) {
      setStatus(null);
      setIsActive(false);
      return;
    }

    // Initial fetch
    poll(runId);

    // Start interval
    intervalRef.current = setInterval(() => poll(runId), POLL_INTERVAL);

    return stopPolling;
  }, [runId, poll, stopPolling]);

  const progress = status?.progress ?? [];

  const summary: SearchPollingSummary = {
    companiesDone: progress.filter((c) => c.status === 'done').length,
    companiesScanning: progress.filter((c) => c.status === 'scanning').length,
    totalJobs: status?.jobs_found ?? 0,
    totalMatches: status?.jobs_matched ?? 0,
  };

  return { status, progress, summary, isActive };
}

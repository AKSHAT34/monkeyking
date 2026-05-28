'use client';

import {
  createContext,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import type { JobMatch, TrackedJob, Company, UploadedCV } from '@/lib/types';
import api from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';

export interface DataCacheContextValue {
  // Matches
  matches: JobMatch[];
  matchesLoading: boolean;
  matchesError: string | null;
  refreshMatches: () => Promise<void>;

  // Tracking
  trackedJobs: TrackedJob[];
  trackingLoading: boolean;
  trackingError: string | null;
  refreshTracking: () => Promise<void>;
  updateTrackedJob: (id: number, updates: Partial<TrackedJob>) => void;

  // Companies
  companies: Company[];
  companiesLoading: boolean;
  refreshCompanies: () => Promise<void>;

  // CVs
  cvs: UploadedCV[];
  cvsLoading: boolean;
  refreshCVs: () => Promise<void>;
}

export const DataCacheContext = createContext<DataCacheContextValue | null>(null);

// Silent API calls — bypass the global error toast interceptor
const silent = { _silent: true } as Record<string, unknown>;

export function DataCacheProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  // ── Matches ──
  const [matches, setMatches] = useState<JobMatch[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [matchesError, setMatchesError] = useState<string | null>(null);
  const [matchesFetched, setMatchesFetched] = useState(false);

  const refreshMatches = useCallback(async () => {
    setMatchesLoading(true);
    setMatchesError(null);
    try {
      const { data } = await api.get<JobMatch[]>('/jobs/matches', { params: { limit: 1000 }, ...silent });
      setMatches(data.sort((a, b) => b.match_score - a.match_score));
      setMatchesFetched(true);
    } catch {
      setMatchesError('Failed to load matches.');
    } finally {
      setMatchesLoading(false);
    }
  }, []);

  // ── Tracking ──
  const [trackedJobs, setTrackedJobs] = useState<TrackedJob[]>([]);
  const [trackingLoading, setTrackingLoading] = useState(false);
  const [trackingError, setTrackingError] = useState<string | null>(null);
  const [trackingFetched, setTrackingFetched] = useState(false);

  const refreshTracking = useCallback(async () => {
    setTrackingLoading(true);
    setTrackingError(null);
    try {
      const { data } = await api.get<TrackedJob[]>('/jobs/saved', silent);
      setTrackedJobs(data);
      setTrackingFetched(true);
    } catch {
      setTrackingError('Failed to load tracked jobs.');
    } finally {
      setTrackingLoading(false);
    }
  }, []);

  const updateTrackedJob = useCallback((id: number, updates: Partial<TrackedJob>) => {
    setTrackedJobs((prev) =>
      prev.map((j) => (j.user_job_id === id ? { ...j, ...updates } : j)),
    );
  }, []);

  // ── Companies ──
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(false);
  const [companiesFetched, setCompaniesFetched] = useState(false);

  const refreshCompanies = useCallback(async () => {
    setCompaniesLoading(true);
    try {
      const { data } = await api.get<Company[]>('/companies', silent);
      setCompanies(data);
      setCompaniesFetched(true);
    } catch {
      // silent
    } finally {
      setCompaniesLoading(false);
    }
  }, []);

  // ── CVs ──
  const [cvs, setCvs] = useState<UploadedCV[]>([]);
  const [cvsLoading, setCvsLoading] = useState(false);
  const [cvsFetched, setCvsFetched] = useState(false);

  const refreshCVs = useCallback(async () => {
    setCvsLoading(true);
    try {
      const { data } = await api.get<UploadedCV[]>('/cv/list', silent);
      setCvs(data);
      setCvsFetched(true);
    } catch {
      // silent
    } finally {
      setCvsLoading(false);
    }
  }, []);

  // ── Fetch all on auth ──
  useEffect(() => {
    if (!user) {
      setMatches([]);
      setTrackedJobs([]);
      setCompanies([]);
      setCvs([]);
      setMatchesFetched(false);
      setTrackingFetched(false);
      setCompaniesFetched(false);
      setCvsFetched(false);
      return;
    }
    if (!matchesFetched) refreshMatches();
    if (!trackingFetched) refreshTracking();
    if (!companiesFetched) refreshCompanies();
    if (!cvsFetched) refreshCVs();
  }, [user, matchesFetched, trackingFetched, companiesFetched, cvsFetched, refreshMatches, refreshTracking, refreshCompanies, refreshCVs]);

  return (
    <DataCacheContext.Provider
      value={{
        matches, matchesLoading, matchesError, refreshMatches,
        trackedJobs, trackingLoading, trackingError, refreshTracking, updateTrackedJob,
        companies, companiesLoading, refreshCompanies,
        cvs, cvsLoading, refreshCVs,
      }}
    >
      {children}
    </DataCacheContext.Provider>
  );
}

'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { MatchCard } from '@/components/matches/MatchCard';
import { MatchFilters, type MatchFilterValues } from '@/components/matches/MatchFilters';
import { BatchActions } from '@/components/matches/BatchActions';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { useToast } from '@/hooks/useToast';
import { useDataCache } from '@/hooks/useDataCache';
import { useProfile } from '@/hooks/useProfile';
import { matchesApi } from '@/lib/api/matches';
import { locationMatches } from '@/utils/locationMatch';

const PAGE_SIZE = 30;

export default function MatchesPage() {
  const { matches, matchesLoading, matchesError, refreshMatches, refreshTracking } = useDataCache();
  const { profile } = useProfile();
  const preferredLocations = profile?.preferred_locations ?? [];

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<MatchFilterValues>({
    minScore: 0,
    company: '',
    locations: [],
  });
  const { addToast } = useToast();

  // Auto-select preferred locations once profile loads
  const [locationInitialized, setLocationInitialized] = useState(false);
  useEffect(() => {
    if (!locationInitialized && preferredLocations.length > 0) {
      setFilters((prev) => ({ ...prev, locations: preferredLocations }));
      setLocationInitialized(true);
    }
  }, [preferredLocations, locationInitialized]);

  const filtered = useMemo(() => {
    const minScoreDecimal = filters.minScore / 100;
    const companyLower = filters.company.toLowerCase();

    return matches.filter((m) => {
      if (m.match_score < minScoreDecimal) return false;
      if (companyLower && !m.company.toLowerCase().includes(companyLower)) return false;
      if (filters.locations.length > 0) {
        if (!locationMatches(m.location || '', filters.locations)) return false;
      }
      return true;
    });
  }, [matches, filters]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [filters]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const toggleSelect = useCallback((jobId: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  }, []);

  const handleSave = useCallback(async () => {
    if (selected.size === 0) return;
    setSaving(true);
    try {
      const { data } = await matchesApi.saveJobs(Array.from(selected));
      addToast({ type: 'success', message: `${data.added} job${data.added !== 1 ? 's' : ''} saved to tracking` });
      setSelected(new Set());
      await Promise.all([refreshMatches(), refreshTracking()]);
    } catch {
      addToast({ type: 'error', message: 'Failed to save jobs' });
    } finally {
      setSaving(false);
    }
  }, [selected, addToast, refreshMatches, refreshTracking]);

  if (matchesLoading && matches.length === 0) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton variant="text" width="200px" height="28px" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><Skeleton variant="card" count={6} /></div>
      </div>
    );
  }

  if (matchesError && matches.length === 0) {
    return <div className="p-6"><ErrorState message={matchesError} onRetry={refreshMatches} /></div>;
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-h2 text-white">
          🎯 Matches{' '}
          <span className="text-sm font-normal text-gray-400">({filtered.length} of {matches.length})</span>
        </h1>
        <BatchActions selectedCount={selected.size} loading={saving} onSave={handleSave} />
      </div>

      <MatchFilters filters={filters} onChange={setFilters} preferredLocations={preferredLocations} />

      {preferredLocations.length === 0 && matches.length > 0 && (
        <div className="rounded-lg border border-yellow-700/50 bg-yellow-900/20 px-4 py-3 text-sm text-yellow-300">
          💡 Set your preferred locations in{' '}
          <a href="/mk2026/profile" className="underline text-mk-orange hover:text-orange-400">Profile → Preferences</a>
          {' '}to filter matches by location.
        </div>
      )}

      {filtered.length === 0 && matches.length === 0 ? (
        <EmptyState icon={<span className="text-4xl">🔍</span>} title="No matches yet"
          description="Run a job search to discover matches based on your profile."
          action={{ label: 'Go to Search', onClick: () => (window.location.href = '/mk2026/search') }} />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<span className="text-4xl">🎯</span>} title="No matches for these filters"
          description="Try adjusting the minimum score, company, or location filters." />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {paginated.map((match) => (
              <MatchCard key={match.match_id} match={match}
                selected={selected.has(match.job_id)} onToggle={toggleSelect} />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-4">
              <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                ← Previous
              </Button>
              <span className="text-sm text-gray-400">Page {page} of {totalPages}</span>
              <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                Next →
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

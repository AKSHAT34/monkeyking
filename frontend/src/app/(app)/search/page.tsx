'use client';

import { useState } from 'react';
import { SearchControls } from '@/components/search/SearchControls';
import { CompanyProgressGrid } from '@/components/search/CompanyProgressGrid';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { ErrorState } from '@/components/ui/ErrorState';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { useSearch } from '@/hooks/useSearch';
import { useToast } from '@/hooks/useToast';
import api from '@/lib/api';

export default function SearchPage() {
  const {
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
    stopSearch,
    retry,
  } = useSearch();
  const { addToast } = useToast();
  const [resetting, setResetting] = useState(false);

  const handleReset = async () => {
    if (!confirm('Reset search history? Next search will start from batch 1 with the highest-priority companies.')) return;
    setResetting(true);
    try {
      await api.post('/jobs/search/reset');
      addToast({ type: 'success', message: 'Search reset — next search starts from batch 1' });
      window.location.reload();
    } catch {
      addToast({ type: 'error', message: 'Reset failed' });
    } finally {
      setResetting(false);
    }
  };

  // Compute progress percentage
  const total = progress.length;
  const done = progress.filter(
    (c) => c.status === 'done' || c.status === 'skipped',
  ).length;
  const percent = total > 0 ? (done / total) * 100 : 0;

  const isCompleted = status?.status === 'completed';
  const isFailed = status?.status === 'failed';
  const hasRun = runId !== null;

  if (initializing) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size="lg" className="text-mk-orange" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-h2 text-white">Job Search</h1>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={handleReset} loading={resetting}>
            🔄 Reset
          </Button>
          {isCompleted && (
            <SearchControls
              onStart={startSearch}
              onStop={stopSearch}
              isActive={false}
              loading={starting}
            />
          )}
          {!isCompleted && (
            <SearchControls
              onStart={startSearch}
              onStop={stopSearch}
              isActive={isActive}
              loading={starting || stopping}
            />
          )}
        </div>
      </div>

      {error && !hasRun && (
        <ErrorState message={error} onRetry={retry} />
      )}

      {isFailed && (
        <ErrorState
          message="Search failed. Something went wrong during scanning."
          onRetry={retry}
        />
      )}

      {hasRun && !isFailed && (
        <>
          <ProgressBar value={percent} showLabel />

          <CompanyProgressGrid progress={progress} summary={summary} />

          {isCompleted && (
            <Card padding="md" className="border-green-700/50">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-green-400 mb-1">
                    Search Complete
                  </h3>
                  <p className="text-xs text-gray-300">
                    Scanned {status.companies_searched} companies · Found{' '}
                    {status.jobs_found} jobs · {status.jobs_matched} matched your profile
                  </p>
                </div>
                <p className="text-xs text-gray-500">
                  Click &quot;Search Jobs&quot; to scan the next batch of companies
                </p>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

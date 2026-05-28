'use client';

import { useCallback, useMemo, useState } from 'react';
import { TrackedJobCard } from '@/components/tracking/TrackedJobCard';
import { TrackingFilters, type TrackingFilterValues } from '@/components/tracking/TrackingFilters';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Badge } from '@/components/ui/Badge';
import { useToast } from '@/hooks/useToast';
import { useDataCache } from '@/hooks/useDataCache';
import { trackingApi } from '@/lib/api/tracking';
import type { ApplicationStatus } from '@/lib/types';

const STATUS_LABEL: Record<ApplicationStatus, string> = {
  not_started: 'Not Started',
  started: 'Started',
  in_process: 'In Process',
  document_missing: 'Document Missing',
  applied: 'Applied',
  interview_scheduled: 'Interview Scheduled',
  rejected: 'Rejected',
  offer_received: 'Offer Received',
};

type BadgeColor = 'gray' | 'blue' | 'yellow' | 'orange' | 'green' | 'purple' | 'red' | 'emerald';

const STATUS_BADGE_COLOR: Record<ApplicationStatus, BadgeColor> = {
  not_started: 'gray',
  started: 'blue',
  in_process: 'yellow',
  document_missing: 'orange',
  applied: 'green',
  interview_scheduled: 'purple',
  rejected: 'red',
  offer_received: 'emerald',
};

export default function TrackingPage() {
  const { trackedJobs, trackingLoading, trackingError, refreshTracking, updateTrackedJob } = useDataCache();
  const [filters, setFilters] = useState<TrackingFilterValues>({ status: '', company: '' });
  const { addToast } = useToast();

  const filtered = useMemo(() => {
    const companyLower = filters.company.toLowerCase();
    return trackedJobs.filter(
      (j) =>
        (filters.status === '' || j.status === filters.status) &&
        (companyLower === '' || j.company.toLowerCase().includes(companyLower)),
    );
  }, [trackedJobs, filters]);

  const statusBreakdown = useMemo(() => {
    const counts: Partial<Record<ApplicationStatus, number>> = {};
    for (const j of trackedJobs) {
      counts[j.status] = (counts[j.status] || 0) + 1;
    }
    return counts;
  }, [trackedJobs]);

  const handleStatusChange = useCallback(
    async (id: number, status: ApplicationStatus) => {
      try {
        await trackingApi.updateJobStatus(id, status);
        updateTrackedJob(id, { status });
        addToast({ type: 'success', message: `Status updated to ${STATUS_LABEL[status]}` });
      } catch {
        addToast({ type: 'error', message: 'Failed to update status' });
      }
    },
    [addToast, updateTrackedJob],
  );

  if (trackingLoading && trackedJobs.length === 0) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton variant="text" width="240px" height="28px" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton variant="card" count={6} />
        </div>
      </div>
    );
  }

  if (trackingError && trackedJobs.length === 0) {
    return (
      <div className="p-6">
        <ErrorState message={trackingError} onRetry={refreshTracking} />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-h2 text-white">
          📋 Tracking{' '}
          <span className="text-sm font-normal text-gray-400">({trackedJobs.length})</span>
        </h1>
        {trackedJobs.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {(Object.entries(statusBreakdown) as [ApplicationStatus, number][]).map(
              ([status, count]) => (
                <Badge key={status} color={STATUS_BADGE_COLOR[status]}>
                  {STATUS_LABEL[status]}: {count}
                </Badge>
              ),
            )}
          </div>
        )}
      </div>

      {trackedJobs.length === 0 ? (
        <EmptyState
          icon={<span className="text-4xl">📋</span>}
          title="No tracked jobs yet"
          description="Save jobs from the Matches page to start tracking your applications."
          action={{
            label: 'Go to Matches',
            onClick: () => (window.location.href = '/mk2026/matches'),
          }}
        />
      ) : (
        <>
          <TrackingFilters filters={filters} onChange={setFilters} />

          {filtered.length === 0 ? (
            <EmptyState
              icon={<span className="text-4xl">🔍</span>}
              title="No jobs match these filters"
              description="Try adjusting the status or company filter."
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((job) => (
                <TrackedJobCard
                  key={job.user_job_id}
                  job={job}
                  onStatusChange={handleStatusChange}
                  onCVGenerated={refreshTracking}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

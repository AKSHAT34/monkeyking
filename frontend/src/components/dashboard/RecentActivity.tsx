'use client';

import { useMemo } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDataCache } from '@/hooks/useDataCache';
import type { ApplicationStatus } from '@/lib/types';

const STATUS_BADGE_COLOR: Record<ApplicationStatus, 'green' | 'yellow' | 'red' | 'blue' | 'purple' | 'orange' | 'gray' | 'emerald'> = {
  not_started: 'gray',
  started: 'blue',
  in_process: 'yellow',
  document_missing: 'orange',
  applied: 'green',
  interview_scheduled: 'purple',
  rejected: 'red',
  offer_received: 'emerald',
};

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

export function RecentActivity() {
  const { trackedJobs, trackingLoading } = useDataCache();

  const recentJobs = useMemo(() => {
    return [...trackedJobs]
      .filter((j) => j.updated_at)
      .sort((a, b) => new Date(b.updated_at!).getTime() - new Date(a.updated_at!).getTime())
      .slice(0, 5);
  }, [trackedJobs]);

  if (trackingLoading && trackedJobs.length === 0) {
    return (
      <div className="space-y-3">
        <Skeleton variant="text" count={3} />
      </div>
    );
  }

  if (recentJobs.length === 0) {
    return <p className="text-sm text-gray-500">No recent activity yet.</p>;
  }

  return (
    <div className="space-y-3">
      {recentJobs.map((job) => (
        <Card key={job.user_job_id} padding="sm">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-medium text-white truncate">{job.title}</p>
              <p className="text-xs text-gray-400 truncate">{job.company}</p>
            </div>
            <Badge color={STATUS_BADGE_COLOR[job.status]}>
              {STATUS_LABEL[job.status]}
            </Badge>
          </div>
        </Card>
      ))}
    </div>
  );
}

'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';
import type { CompanyProgress } from '@/lib/types';

interface CompanyProgressCardProps {
  company: CompanyProgress;
  onClick?: () => void;
}

export const CompanyProgressCard = React.memo(function CompanyProgressCard({ company, onClick }: CompanyProgressCardProps) {
  const { status, jobs_found = 0, matched = 0 } = company;
  const isDoneWithJobs = status === 'done' && jobs_found > 0;
  const isDoneNoJobs = status === 'done' && jobs_found === 0;

  return (
    <Card
      padding="sm"
      hoverable={isDoneWithJobs}
      onClick={isDoneWithJobs ? onClick : undefined}
      className={getCardClassName(status, isDoneNoJobs)}
    >
      <p className="text-sm font-medium text-white truncate">{company.company}</p>
      <StatusLabel
        status={status}
        jobsFound={jobs_found}
        matched={matched}
        isDoneNoJobs={isDoneNoJobs}
        source={company.source}
      />
    </Card>
  );
});

function getCardClassName(
  status: CompanyProgress['status'],
  isDoneNoJobs: boolean,
): string {
  if (status === 'scanning') return 'border-yellow-600/50 animate-pulse';
  if (status === 'done' && !isDoneNoJobs) return 'border-green-700/50';
  if (status === 'done' && isDoneNoJobs) return 'border-red-700/30 opacity-60';
  return '';
}

const SOURCE_ICONS: Record<string, string> = {
  api: '⚡', browser: '🌐', html: '📄', vision: '🔭', none: '',
};

function StatusLabel({
  status,
  jobsFound,
  matched,
  isDoneNoJobs,
  source,
}: {
  status: CompanyProgress['status'];
  jobsFound: number;
  matched: number;
  isDoneNoJobs: boolean;
  source?: string;
}) {
  const icon = SOURCE_ICONS[source || ''] || '';
  switch (status) {
    case 'pending':
      return <p className="text-xs text-gray-500 mt-1">Waiting</p>;
    case 'scanning':
      return (
        <p className="text-xs text-yellow-400 mt-1 flex items-center gap-1">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
          Scanning...
        </p>
      );
    case 'done':
      if (isDoneNoJobs) {
        return <p className="text-xs text-red-400 mt-1">No jobs found</p>;
      }
      return (
        <p className="text-xs text-green-400 mt-1">
          {icon} {jobsFound} jobs · {matched} matched
        </p>
      );
    case 'skipped':
      return <p className="text-xs text-gray-500 mt-1">Skipped</p>;
    default:
      return null;
  }
}

'use client';

import { useEffect, useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { companiesApi } from '@/lib/api/companies';
import { matchScoreColor } from '@/lib/types';
import type { Job } from '@/lib/types';

interface CompanyJobModalProps {
  companyName: string | null;
  onClose: () => void;
}

function ScoreBadge({ score }: { score: number }) {
  const colorClass = matchScoreColor(score);
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
      {Math.round(score * 100)}%
    </span>
  );
}

function JobEntry({ job }: { job: Job }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-mk-border rounded-lg p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-semibold text-white truncate">{job.title}</h4>
          <p className="text-xs text-gray-400 mt-0.5">{job.location}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {job.match_score != null && <ScoreBadge score={job.match_score} />}
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-mk-orange hover:underline whitespace-nowrap"
          >
            View Job ↗
          </a>
        </div>
      </div>

      {job.match_reason && (
        <p className="text-xs text-gray-300 mt-2">{job.match_reason}</p>
      )}

      {(job.matched_skills?.length || job.missing_skills?.length) && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {job.matched_skills?.map((s) => (
            <Badge key={s} color="green">{s}</Badge>
          ))}
          {job.missing_skills?.map((s) => (
            <Badge key={s} color="red">{s}</Badge>
          ))}
        </div>
      )}

      {job.description && (
        <div className="mt-2">
          <p className={`text-xs text-gray-400 ${expanded ? '' : 'line-clamp-2'}`}>
            {job.description}
          </p>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-mk-orange hover:underline mt-1"
          >
            {expanded ? 'Collapse' : 'Read Job Description'}
          </button>
        </div>
      )}
    </div>
  );
}


export function CompanyJobModal({ companyName, onClose }: CompanyJobModalProps) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!companyName) return;
    setLoading(true);
    companiesApi
      .jobsByCompany(companyName)
      .then((res) => setJobs(res.data))
      .catch(() => setJobs([]))
      .finally(() => setLoading(false));
  }, [companyName]);

  return (
    <Modal
      isOpen={!!companyName}
      onClose={onClose}
      title={companyName ? `Jobs at ${companyName}` : 'Jobs'}
      size="lg"
    >
      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner size="lg" className="text-mk-orange" />
        </div>
      ) : jobs.length === 0 ? (
        <EmptyState
          icon={<span className="text-3xl">📭</span>}
          title="No jobs found"
          description={`No jobs have been discovered for ${companyName} yet. Run a search to scan this company.`}
        />
      ) : (
        <div className="flex flex-col gap-3 max-h-[60vh] overflow-y-auto">
          {jobs.map((job) => (
            <JobEntry key={job.id} job={job} />
          ))}
        </div>
      )}
    </Modal>
  );
}

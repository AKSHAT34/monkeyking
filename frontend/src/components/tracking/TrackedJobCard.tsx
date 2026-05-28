'use client';

import React, { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { StatusDropdown } from './StatusDropdown';
import { cvApi } from '@/lib/api/cv';
import { useToast } from '@/hooks/useToast';
import { STATUS_COLORS } from '@/lib/types';
import type { ApplicationStatus, TrackedJob } from '@/lib/types';

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

export interface TrackedJobCardProps {
  job: TrackedJob;
  onStatusChange: (id: number, status: ApplicationStatus) => void;
  onCVGenerated: () => void;
}

export const TrackedJobCard = React.memo(function TrackedJobCard({ job, onStatusChange, onCVGenerated }: TrackedJobCardProps) {
  const [generatingCV, setGeneratingCV] = useState(false);
  const [generatingCL, setGeneratingCL] = useState(false);
  const { addToast } = useToast();

  const hasCvPdf = !!job.tailored_cv_path;
  const hasCvDocx = !!job.tailored_cv_docx_path;
  const hasClPdf = !!job.cover_letter_path;
  const hasClDocx = !!job.cover_letter_docx_path;

  const handleGenerateCV = async () => {
    setGeneratingCV(true);
    try {
      await cvApi.generateCV(job.job_id);
      addToast({ type: 'success', message: 'Tailored CV generated!' });
      onCVGenerated();
    } catch {
      addToast({ type: 'error', message: 'CV generation failed.' });
    } finally {
      setGeneratingCV(false);
    }
  };

  const handleGenerateCL = async () => {
    setGeneratingCL(true);
    try {
      await cvApi.generateCoverLetter(job.job_id);
      addToast({ type: 'success', message: 'Cover letter generated!' });
      onCVGenerated();
    } catch {
      addToast({ type: 'error', message: 'Cover letter generation failed.' });
    } finally {
      setGeneratingCL(false);
    }
  };

  const handleDownloadCV = async (format: 'pdf' | 'docx') => {
    try { await cvApi.downloadCV(job.user_job_id, format); }
    catch { addToast({ type: 'error', message: `Download failed.` }); }
  };

  const handleDownloadCL = async (format: 'pdf' | 'docx') => {
    try { await cvApi.downloadCoverLetter(job.user_job_id, format); }
    catch { addToast({ type: 'error', message: `Download failed.` }); }
  };

  return (
    <Card padding="md" className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-white truncate">{job.title}</h3>
          <p className="text-xs text-gray-400 truncate">{job.company} · {job.location}</p>
        </div>
        <Badge className={STATUS_COLORS[job.status]}>
          {STATUS_LABEL[job.status]}
        </Badge>
      </div>

      <StatusDropdown value={job.status} onChange={(status) => onStatusChange(job.user_job_id, status)} />

      {/* Apply link */}
      <a href={job.url} target="_blank" rel="noopener noreferrer"
        className="text-xs text-mk-orange hover:underline">Apply here ↗</a>

      {/* CV section */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-gray-500 w-8">CV:</span>
        {!hasCvPdf && !hasCvDocx ? (
          <Button size="sm" variant="secondary" loading={generatingCV}
            onClick={handleGenerateCV} disabled={generatingCV}>
            {generatingCV ? 'Generating...' : 'Generate CV'}
          </Button>
        ) : (
          <>
            {hasCvPdf && <Button size="sm" variant="secondary" onClick={() => handleDownloadCV('pdf')}>PDF</Button>}
            {hasCvDocx && <Button size="sm" variant="secondary" onClick={() => handleDownloadCV('docx')}>DOCX</Button>}
          </>
        )}
      </div>

      {/* Cover Letter section */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-gray-500 w-8">CL:</span>
        {!hasClPdf && !hasClDocx ? (
          <Button size="sm" variant="ghost" loading={generatingCL}
            onClick={handleGenerateCL} disabled={generatingCL}>
            {generatingCL ? 'Generating...' : '✉️ Generate Cover Letter'}
          </Button>
        ) : (
          <>
            {hasClPdf && <Button size="sm" variant="ghost" onClick={() => handleDownloadCL('pdf')}>✉️ PDF</Button>}
            {hasClDocx && <Button size="sm" variant="ghost" onClick={() => handleDownloadCL('docx')}>✉️ DOCX</Button>}
          </>
        )}
      </div>
    </Card>
  );
});

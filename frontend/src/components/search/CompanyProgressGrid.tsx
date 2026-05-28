'use client';

import { useState } from 'react';
import type { CompanyProgress } from '@/lib/types';
import { CompanyProgressCard } from './CompanyProgressCard';
import { CompanyJobModal } from '@/components/companies/CompanyJobModal';

interface CompanyProgressGridProps {
  progress: CompanyProgress[];
  summary: {
    companiesDone: number;
    companiesScanning: number;
    totalJobs: number;
    totalMatches: number;
  };
}

export function CompanyProgressGrid({ progress, summary }: CompanyProgressGridProps) {
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-400">
        {summary.companiesDone} done · {summary.companiesScanning} scanning ·{' '}
        {summary.totalJobs} jobs · {summary.totalMatches} matches
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {progress.map((c) => (
          <CompanyProgressCard
            key={c.company}
            company={c}
            onClick={() => setSelectedCompany(c.company)}
          />
        ))}
      </div>

      <CompanyJobModal
        companyName={selectedCompany}
        onClose={() => setSelectedCompany(null)}
      />
    </div>
  );
}

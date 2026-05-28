'use client';

import React from 'react';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import type { ApplicationStatus } from '@/lib/types';

export interface TrackingFilterValues {
  status: ApplicationStatus | '';
  company: string;
}

export interface TrackingFiltersProps {
  filters: TrackingFilterValues;
  onChange: (filters: TrackingFilterValues) => void;
}

export function TrackingFilters({ filters, onChange }: TrackingFiltersProps) {
  return (
    <div className="flex flex-col sm:flex-row gap-3">
      <Select
        value={filters.status}
        onChange={(e) => onChange({ ...filters, status: e.target.value as ApplicationStatus | '' })}
        className="text-xs"
        aria-label="Filter by status"
      >
        <option value="">All Statuses</option>
        <option value="not_started">Not Started</option>
        <option value="started">Started</option>
        <option value="in_process">In Process</option>
        <option value="document_missing">Document Missing</option>
        <option value="applied">Applied</option>
        <option value="interview_scheduled">Interview Scheduled</option>
        <option value="rejected">Rejected</option>
        <option value="offer_received">Offer Received</option>
      </Select>
      <Input
        placeholder="Filter by company..."
        value={filters.company}
        onChange={(e) => onChange({ ...filters, company: e.target.value })}
        className="text-xs"
      />
    </div>
  );
}

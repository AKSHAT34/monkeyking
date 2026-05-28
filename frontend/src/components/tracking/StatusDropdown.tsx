'use client';

import React from 'react';
import { Select } from '@/components/ui/Select';
import type { ApplicationStatus } from '@/lib/types';

const STATUS_OPTIONS: { value: ApplicationStatus; label: string }[] = [
  { value: 'not_started', label: 'Not Started' },
  { value: 'started', label: 'Started' },
  { value: 'in_process', label: 'In Process' },
  { value: 'document_missing', label: 'Document Missing' },
  { value: 'applied', label: 'Applied' },
  { value: 'interview_scheduled', label: 'Interview Scheduled' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'offer_received', label: 'Offer Received' },
];

export interface StatusDropdownProps {
  value: ApplicationStatus;
  onChange: (status: ApplicationStatus) => void;
  disabled?: boolean;
}

export function StatusDropdown({ value, onChange, disabled }: StatusDropdownProps) {
  return (
    <Select
      value={value}
      onChange={(e) => onChange(e.target.value as ApplicationStatus)}
      disabled={disabled}
      className="text-xs py-1 px-2"
      aria-label="Application status"
    >
      {STATUS_OPTIONS.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </Select>
  );
}

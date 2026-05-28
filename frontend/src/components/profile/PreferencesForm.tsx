'use client';

import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { LocationSelector } from '@/components/profile/LocationSelector';
import type { UserProfile } from '@/lib/types';

interface PreferencesFormProps {
  values: Pick<
    UserProfile,
    | 'phone'
    | 'location'
    | 'linkedin'
    | 'notice_period'
    | 'current_salary'
    | 'expected_salary'
    | 'work_authorization'
    | 'preferred_locations'
  >;
  onChange: (field: string, value: string | string[]) => void;
}

export function PreferencesForm({ values, onChange }: PreferencesFormProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Input
        label="Phone"
        value={values.phone || ''}
        onChange={(e) => onChange('phone', e.target.value)}
        placeholder="+1 234 567 8900"
      />
      <Input
        label="Location"
        value={values.location || ''}
        onChange={(e) => onChange('location', e.target.value)}
        placeholder="City, Country"
      />
      <Input
        label="LinkedIn URL"
        value={values.linkedin || ''}
        onChange={(e) => onChange('linkedin', e.target.value)}
        placeholder="https://linkedin.com/in/..."
      />
      <Input
        label="Notice Period"
        value={values.notice_period || ''}
        onChange={(e) => onChange('notice_period', e.target.value)}
        placeholder="e.g. 30 days"
      />
      <Input
        label="Current Salary"
        value={values.current_salary || ''}
        onChange={(e) => onChange('current_salary', e.target.value)}
        placeholder="e.g. $120,000"
      />
      <Input
        label="Expected Salary"
        value={values.expected_salary || ''}
        onChange={(e) => onChange('expected_salary', e.target.value)}
        placeholder="e.g. $150,000"
      />
      <Select
        label="Work Authorization"
        value={values.work_authorization || ''}
        onChange={(e) => onChange('work_authorization', e.target.value)}
      >
        <option value="">Select...</option>
        <option value="citizen">Citizen</option>
        <option value="permanent_resident">Permanent Resident</option>
        <option value="work_visa">Work Visa</option>
        <option value="student_visa">Student Visa</option>
        <option value="requires_sponsorship">Requires Sponsorship</option>
      </Select>
      <div className="md:col-span-2">
        <LocationSelector
          selected={values.preferred_locations || []}
          onChange={(locations) => onChange('preferred_locations', locations)}
        />
      </div>
    </div>
  );
}

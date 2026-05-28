'use client';

import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';

const CATEGORIES = [
  'All Categories',
  'Tech Giants',
  'AI Companies',
  'Cloud & SaaS',
  'Indian Startups',
  'Fintech',
  'E-commerce',
  'Consulting',
  'Banking',
  'IT Services',
  'Other',
];

export interface CompanyFilterValues {
  search: string;
  category: string;
  country: string;
}

interface CompanyFiltersProps {
  filters: CompanyFilterValues;
  onChange: (filters: CompanyFilterValues) => void;
  countries: string[];
}

export function CompanyFilters({ filters, onChange, countries }: CompanyFiltersProps) {
  return (
    <div className="flex flex-col sm:flex-row gap-3">
      <div className="flex-1">
        <Input
          placeholder="Search companies..."
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          aria-label="Search companies"
        />
      </div>
      <div className="w-full sm:w-48">
        <Select
          value={filters.category}
          onChange={(e) => onChange({ ...filters, category: e.target.value })}
          aria-label="Filter by category"
        >
          {CATEGORIES.map((cat) => (
            <option key={cat} value={cat === 'All Categories' ? '' : cat}>
              {cat}
            </option>
          ))}
        </Select>
      </div>
      <div className="w-full sm:w-40">
        <Select
          value={filters.country}
          onChange={(e) => onChange({ ...filters, country: e.target.value })}
          aria-label="Filter by country"
        >
          <option value="">All Countries</option>
          {countries.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </Select>
      </div>
    </div>
  );
}

'use client';

import React from 'react';
import { Input } from '@/components/ui/Input';

export interface MatchFilterValues {
  minScore: number;
  company: string;
  locations: string[];
}

export interface MatchFiltersProps {
  filters: MatchFilterValues;
  onChange: (filters: MatchFilterValues) => void;
  preferredLocations: string[];
}

export function MatchFilters({ filters, onChange, preferredLocations }: MatchFiltersProps) {
  const toggleLocation = (loc: string) => {
    const current = filters.locations;
    const next = current.includes(loc)
      ? current.filter((l) => l !== loc)
      : [...current, loc];
    onChange({ ...filters, locations: next });
  };

  const clearLocations = () => {
    onChange({ ...filters, locations: [] });
  };

  const selectAll = () => {
    onChange({ ...filters, locations: [...preferredLocations] });
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex items-center gap-2 min-w-[200px]">
          <label htmlFor="min-score" className="text-xs text-gray-400 whitespace-nowrap">
            Min Score
          </label>
          <input
            id="min-score"
            type="range"
            min={0}
            max={100}
            value={filters.minScore}
            onChange={(e) =>
              onChange({ ...filters, minScore: Number(e.target.value) })
            }
            className="flex-1 accent-orange-500"
          />
          <span className="text-xs text-gray-300 w-8 text-right">
            {filters.minScore}%
          </span>
        </div>
        <Input
          placeholder="Filter by company..."
          value={filters.company}
          onChange={(e) => onChange({ ...filters, company: e.target.value })}
          className="text-xs"
        />
      </div>

      {/* Location filter chips */}
      {preferredLocations.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-500">Locations:</span>
          {preferredLocations.map((loc) => {
            const active = filters.locations.includes(loc);
            return (
              <button
                key={loc}
                type="button"
                onClick={() => toggleLocation(loc)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors border ${
                  active
                    ? 'bg-mk-orange/20 border-mk-orange text-mk-orange'
                    : 'bg-mk-card border-mk-border text-gray-400 hover:border-gray-500'
                }`}
              >
                {loc}
              </button>
            );
          })}
          <button
            type="button"
            onClick={filters.locations.length > 0 ? clearLocations : selectAll}
            className="text-xs text-gray-500 hover:text-white transition-colors ml-1"
          >
            {filters.locations.length > 0 ? 'Clear all' : 'Select all'}
          </button>
        </div>
      )}
    </div>
  );
}

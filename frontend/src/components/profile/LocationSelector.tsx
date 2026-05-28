'use client';

import { useState, useCallback } from 'react';
import { Input } from '@/components/ui/Input';

const COMMON_LOCATIONS = [
  'Remote - India',
  'Remote - Worldwide',
  'India',
  'Bangalore',
  'Mumbai',
  'Delhi NCR',
  'Hyderabad',
  'Pune',
  'Chennai',
  'Gurgaon',
  'Noida',
  'US',
  'San Francisco',
  'New York',
  'Seattle',
  'Austin',
  'London',
  'Singapore',
  'Dubai',
  'Toronto',
  'Berlin',
];

interface LocationSelectorProps {
  selected: string[];
  onChange: (locations: string[]) => void;
}

export function LocationSelector({ selected, onChange }: LocationSelectorProps) {
  const [input, setInput] = useState('');

  const addLocation = useCallback(
    (loc: string) => {
      const trimmed = loc.trim();
      if (trimmed && !selected.some((s) => s.toLowerCase() === trimmed.toLowerCase())) {
        onChange([...selected, trimmed]);
      }
      setInput('');
    },
    [selected, onChange],
  );

  const removeLocation = useCallback(
    (loc: string) => {
      onChange(selected.filter((s) => s !== loc));
    },
    [selected, onChange],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.key === 'Enter' || e.key === ',') && input.trim()) {
      e.preventDefault();
      addLocation(input);
    }
    if (e.key === 'Backspace' && !input && selected.length > 0) {
      removeLocation(selected[selected.length - 1]);
    }
  };

  // Suggestions: common locations not already selected
  const suggestions = COMMON_LOCATIONS.filter(
    (loc) => !selected.some((s) => s.toLowerCase() === loc.toLowerCase()),
  );

  return (
    <div className="space-y-3">
      <label className="text-label text-gray-400">Preferred Locations</label>

      {/* Selected tags */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selected.map((loc) => (
            <span
              key={loc}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-mk-orange/10 text-mk-orange border border-mk-orange/30"
            >
              {loc}
              <button
                type="button"
                onClick={() => removeLocation(loc)}
                className="ml-0.5 hover:text-white transition-colors"
                aria-label={`Remove ${loc}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Input */}
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type a location and press Enter..."
      />

      {/* Quick-add suggestions */}
      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {suggestions.slice(0, 12).map((loc) => (
            <button
              key={loc}
              type="button"
              onClick={() => addLocation(loc)}
              className="px-2 py-1 rounded text-xs text-gray-400 border border-mk-border hover:border-gray-500 hover:text-white transition-colors"
            >
              + {loc}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

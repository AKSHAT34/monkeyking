'use client';

import React from 'react';
import { cn } from '@/utils/cn';

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, className, id, children, ...props }, ref) => {
    const selectId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={selectId} className="text-label text-gray-300">
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={cn(
            'rounded-lg border bg-mk-dark px-3 py-2 text-sm text-white transition-colors',
            'focus:border-mk-orange focus:outline-none focus:ring-1 focus:ring-mk-orange',
            error ? 'border-error' : 'border-mk-border',
            className,
          )}
          {...props}
        >
          {children}
        </select>
        {error && <p className="text-caption text-error">{error}</p>}
      </div>
    );
  },
);

Select.displayName = 'Select';

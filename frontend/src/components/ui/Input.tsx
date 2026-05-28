'use client';

import React from 'react';
import { cn } from '@/utils/cn';

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-label text-gray-300">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            'rounded-lg border bg-mk-dark px-3 py-2 text-sm text-white placeholder-gray-500 transition-colors',
            'focus:border-mk-orange focus:outline-none focus:ring-1 focus:ring-mk-orange',
            error ? 'border-error' : 'border-mk-border',
            className,
          )}
          {...props}
        />
        {error && <p className="text-caption text-error">{error}</p>}
      </div>
    );
  },
);

Input.displayName = 'Input';

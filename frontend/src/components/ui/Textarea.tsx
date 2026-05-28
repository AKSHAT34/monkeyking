'use client';

import React from 'react';
import { cn } from '@/utils/cn';

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  maxLength?: number;
  showCount?: boolean;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, maxLength, showCount = !!maxLength, className, id, value, ...props }, ref) => {
    const textareaId = id || label?.toLowerCase().replace(/\s+/g, '-');
    const charCount = typeof value === 'string' ? value.length : 0;

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={textareaId} className="text-label text-gray-300">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          maxLength={maxLength}
          value={value}
          className={cn(
            'rounded-lg border bg-mk-dark px-3 py-2 text-sm text-white placeholder-gray-500 transition-colors resize-y min-h-[80px]',
            'focus:border-mk-orange focus:outline-none focus:ring-1 focus:ring-mk-orange',
            error ? 'border-error' : 'border-mk-border',
            className,
          )}
          {...props}
        />
        <div className="flex justify-between">
          {error && <p className="text-caption text-error">{error}</p>}
          {showCount && (
            <p className="text-caption text-gray-500 ml-auto">
              {charCount}{maxLength ? `/${maxLength}` : ''}
            </p>
          )}
        </div>
      </div>
    );
  },
);

Textarea.displayName = 'Textarea';

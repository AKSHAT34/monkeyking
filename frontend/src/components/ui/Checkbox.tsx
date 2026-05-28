'use client';

import React from 'react';
import { cn } from '@/utils/cn';

export interface CheckboxProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, className, id, ...props }, ref) => {
    const checkboxId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <label
        htmlFor={checkboxId}
        className={cn('inline-flex items-center gap-2 cursor-pointer', className)}
      >
        <input
          ref={ref}
          type="checkbox"
          id={checkboxId}
          className="h-4 w-4 rounded border-mk-border bg-mk-dark accent-orange-500 focus:ring-mk-orange"
          {...props}
        />
        {label && <span className="text-sm text-gray-300">{label}</span>}
      </label>
    );
  },
);

Checkbox.displayName = 'Checkbox';

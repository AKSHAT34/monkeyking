'use client';

import React from 'react';
import { cn } from '@/utils/cn';
import { Button } from './Button';

export interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({ message, onRetry, className }: ErrorStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-16 px-4 text-center',
        className,
      )}
    >
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-900/50">
        <span className="text-xl font-bold text-red-400">×</span>
      </div>
      <p className="text-sm text-gray-300 max-w-sm mb-6">{message}</p>
      {onRetry && (
        <Button variant="danger" onClick={onRetry}>
          Try Again
        </Button>
      )}
    </div>
  );
}

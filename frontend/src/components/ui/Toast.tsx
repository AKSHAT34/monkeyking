'use client';

import { useEffect } from 'react';
import { cn } from '@/utils/cn';

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
}

const typeConfig = {
  success: { border: 'border-l-green-500', icon: '✓', iconColor: 'text-green-400' },
  error: { border: 'border-l-red-500', icon: '✕', iconColor: 'text-red-400' },
  warning: { border: 'border-l-yellow-500', icon: '⚠', iconColor: 'text-yellow-400' },
  info: { border: 'border-l-blue-500', icon: 'ℹ', iconColor: 'text-blue-400' },
} as const;

interface ToastItemProps {
  toast: Toast;
  onDismiss: (id: string) => void;
}

export function ToastItem({ toast, onDismiss }: ToastItemProps) {
  const config = typeConfig[toast.type];

  useEffect(() => {
    const timer = setTimeout(
      () => onDismiss(toast.id),
      toast.duration ?? 4000,
    );
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, onDismiss]);

  return (
    <div
      className={cn(
        'flex items-start gap-3 w-80 bg-mk-card border border-mk-border rounded-lg p-4 shadow-xl border-l-4',
        config.border,
      )}
      role="alert"
    >
      <span className={cn('text-lg leading-none mt-0.5', config.iconColor)}>
        {config.icon}
      </span>
      <p className="flex-1 text-sm text-gray-200">{toast.message}</p>
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-gray-500 hover:text-white transition-colors text-sm leading-none"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}

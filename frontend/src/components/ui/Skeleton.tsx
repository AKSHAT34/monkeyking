'use client';

import React from 'react';
import { cn } from '@/utils/cn';

const variantPresets = {
  text: 'h-4 w-full rounded',
  card: 'h-32 w-full rounded-xl',
  stat: 'h-20 w-full rounded-xl',
  avatar: 'h-10 w-10 rounded-full',
  button: 'h-10 w-24 rounded-lg',
} as const;

export interface SkeletonProps {
  variant?: keyof typeof variantPresets;
  width?: string;
  height?: string;
  count?: number;
  className?: string;
}

export function Skeleton({
  variant = 'text',
  width,
  height,
  count = 1,
  className,
}: SkeletonProps) {
  const items = Array.from({ length: count }, (_, i) => i);

  return (
    <>
      {items.map((i) => (
        <div
          key={i}
          className={cn(
            'animate-pulse bg-mk-border rounded',
            variantPresets[variant],
            className,
          )}
          style={{
            ...(width ? { width } : {}),
            ...(height ? { height } : {}),
          }}
        />
      ))}
    </>
  );
}

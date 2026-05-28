'use client';

import React from 'react';
import { cn } from '@/utils/cn';
import { Spinner } from './Spinner';

const variantStyles = {
  primary: 'bg-mk-orange text-white hover:bg-orange-600',
  secondary: 'bg-mk-card border border-mk-border text-gray-300 hover:text-white',
  ghost: 'text-gray-400 hover:text-white hover:bg-mk-card',
  danger: 'bg-red-700 text-white hover:bg-red-600',
} as const;

const sizeStyles = {
  sm: 'px-3 py-1.5 text-sm gap-1.5',
  md: 'px-4 py-2 text-sm gap-2',
  lg: 'px-6 py-3 text-base gap-2',
} as const;

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variantStyles;
  size?: keyof typeof sizeStyles;
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      icon,
      children,
      className,
      disabled,
      ...props
    },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        className={cn(
          'inline-flex items-center justify-center rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-mk-orange focus:ring-offset-2 focus:ring-offset-mk-dark',
          variantStyles[variant],
          sizeStyles[size],
          loading && 'pointer-events-none opacity-70',
          disabled && 'pointer-events-none opacity-50',
          className,
        )}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? <Spinner size={size === 'lg' ? 'md' : 'sm'} /> : icon}
        {children}
      </button>
    );
  },
);

Button.displayName = 'Button';

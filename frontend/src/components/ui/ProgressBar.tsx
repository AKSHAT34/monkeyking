import { cn } from '@/utils/cn';

export interface ProgressBarProps {
  value: number;
  className?: string;
  showLabel?: boolean;
}

export function ProgressBar({ value, className, showLabel = false }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div className={cn('w-full', className)}>
      <div className="h-2.5 bg-mk-dark rounded-full overflow-hidden">
        <div
          className="h-full bg-mk-orange rounded-full transition-all duration-500"
          style={{ width: `${clamped}%` }}
          role="progressbar"
          aria-valuenow={clamped}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
      {showLabel && (
        <span className="block mt-1 text-xs text-gray-400 text-right">
          {Math.round(clamped)}%
        </span>
      )}
    </div>
  );
}

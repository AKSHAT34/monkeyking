import { cn } from '@/utils/cn';

const paddingMap = {
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
} as const;

export interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: keyof typeof paddingMap;
  hoverable?: boolean;
  onClick?: () => void;
}

export function Card({
  children,
  className,
  padding = 'md',
  hoverable = false,
  onClick,
}: CardProps) {
  return (
    <div
      className={cn(
        'bg-mk-card border border-mk-border rounded-xl',
        paddingMap[padding],
        hoverable && 'hover:border-mk-orange cursor-pointer transition-colors',
        className,
      )}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      {children}
    </div>
  );
}

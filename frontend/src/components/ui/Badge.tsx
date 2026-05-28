import { cn } from '@/utils/cn';

const colorMap: Record<string, string> = {
  green: 'bg-green-900/50 text-green-300',
  yellow: 'bg-yellow-900/50 text-yellow-300',
  red: 'bg-red-900/50 text-red-300',
  blue: 'bg-blue-900/50 text-blue-300',
  purple: 'bg-purple-900/50 text-purple-300',
  orange: 'bg-orange-900/50 text-orange-300',
  gray: 'bg-gray-900/50 text-gray-300',
  emerald: 'bg-emerald-900/50 text-emerald-300',
};

export interface BadgeProps {
  children: React.ReactNode;
  color?: keyof typeof colorMap;
  className?: string;
}

export function Badge({ children, color = 'gray', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
        colorMap[color] ?? colorMap.gray,
        className,
      )}
    >
      {children}
    </span>
  );
}

'use client';

import Link from 'next/link';
import { cn } from '@/utils/cn';

export interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  href: string;
  active: boolean;
  collapsed: boolean;
}

export function NavItem({ icon, label, href, active, collapsed }: NavItemProps) {
  return (
    <Link
      href={href}
      className={cn(
        'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
        active
          ? 'bg-mk-orange/10 text-mk-orange border-l-2 border-mk-orange'
          : 'text-gray-400 hover:text-white hover:bg-mk-card',
        collapsed && 'justify-center px-2',
      )}
      title={collapsed ? label : undefined}
    >
      <span className="text-lg shrink-0">{icon}</span>
      {!collapsed && <span>{label}</span>}
    </Link>
  );
}

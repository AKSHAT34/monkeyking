'use client';

import { usePathname } from 'next/navigation';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { NavItem } from './NavItem';
import { UserMenu } from './UserMenu';

const NAV_ITEMS = [
  { icon: '📊', label: 'Dashboard', href: '/dashboard' },
  { icon: '🔍', label: 'Search', href: '/search' },
  { icon: '🎯', label: 'Matches', href: '/matches' },
  { icon: '📋', label: 'Tracking', href: '/tracking' },
  { icon: '🏢', label: 'Companies', href: '/companies' },
  { icon: '👤', label: 'Profile', href: '/profile' },
  { icon: '📄', label: 'CVs', href: '/cvs' },
  { icon: '⚙️', label: 'Settings', href: '/settings' },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isTablet } = useMediaQuery();
  const collapsed = isTablet;

  return (
    <aside
      className={`fixed top-0 left-0 h-screen bg-mk-card border-r border-mk-border flex flex-col z-30 transition-all ${
        collapsed ? 'w-16' : 'w-[240px]'
      }`}
    >
      {/* Logo */}
      <div className={`flex items-center gap-2 px-4 py-5 border-b border-mk-border ${collapsed ? 'justify-center px-2' : ''}`}>
        <span className="text-2xl">🐵</span>
        {!collapsed && (
          <div className="flex flex-col">
            <span className="text-lg font-bold text-mk-orange leading-tight">MonkeyKing</span>
            <span className="text-[10px] text-gray-500 leading-tight">Help you climb your career ladder</span>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 flex flex-col gap-1 p-2 overflow-y-auto">
        {NAV_ITEMS.map((item) => (
          <NavItem
            key={item.href}
            icon={item.icon}
            label={item.label}
            href={item.href}
            active={pathname === item.href || pathname.startsWith(item.href + '/')}
            collapsed={collapsed}
          />
        ))}
      </nav>

      {/* User menu */}
      <div className="border-t border-mk-border p-2">
        <UserMenu collapsed={collapsed} />
      </div>
    </aside>
  );
}

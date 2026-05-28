'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/utils/cn';

const PRIMARY_ITEMS = [
  { icon: '📊', label: 'Home', href: '/dashboard' },
  { icon: '🔍', label: 'Search', href: '/search' },
  { icon: '🎯', label: 'Matches', href: '/matches' },
  { icon: '📋', label: 'Track', href: '/tracking' },
];

const MORE_ITEMS = [
  { icon: '🏢', label: 'Companies', href: '/companies' },
  { icon: '👤', label: 'Profile', href: '/profile' },
  { icon: '📄', label: 'CVs', href: '/cvs' },
  { icon: '⚙️', label: 'Settings', href: '/settings' },
];

export function BottomNav() {
  const pathname = usePathname();
  const [showMore, setShowMore] = useState(false);
  const moreActive = MORE_ITEMS.some((i) => pathname === i.href || pathname.startsWith(i.href + '/'));

  return (
    <>
      {/* More menu overlay */}
      {showMore && (
        <div className="fixed inset-0 z-40" onClick={() => setShowMore(false)}>
          <div className="absolute bottom-16 right-2 bg-mk-card border border-mk-border rounded-xl shadow-xl p-2 min-w-[160px]"
            onClick={(e) => e.stopPropagation()}>
            {MORE_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <Link key={item.href} href={item.href}
                  onClick={() => setShowMore(false)}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm',
                    active ? 'text-mk-orange bg-mk-orange/10' : 'text-gray-300 hover:bg-mk-border',
                  )}>
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Bottom bar */}
      <nav className="fixed bottom-0 left-0 right-0 bg-mk-card border-t border-mk-border flex items-center justify-around z-30 h-16 px-1">
        {PRIMARY_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + '/');
          return (
            <Link key={item.href} href={item.href}
              className={cn(
                'flex flex-col items-center gap-0.5 py-1 px-2 rounded-lg text-[10px] font-medium transition-colors',
                active ? 'text-mk-orange' : 'text-gray-500 hover:text-gray-300',
              )}>
              <span className="text-xl">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
        <button onClick={() => setShowMore(!showMore)}
          className={cn(
            'flex flex-col items-center gap-0.5 py-1 px-2 rounded-lg text-[10px] font-medium transition-colors',
            moreActive || showMore ? 'text-mk-orange' : 'text-gray-500 hover:text-gray-300',
          )}>
          <span className="text-xl">•••</span>
          <span>More</span>
        </button>
      </nav>
    </>
  );
}

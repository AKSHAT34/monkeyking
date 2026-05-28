'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Sidebar } from '@/components/layout/Sidebar';
import { BottomNav } from '@/components/layout/BottomNav';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { useAuth } from '@/hooks/useAuth';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const { isMobile, isDesktop, isTablet } = useMediaQuery();

  // Scroll position preservation per route
  const scrollMap = useRef<Record<string, number>>({});
  const mainRef = useRef<HTMLElement>(null);
  const prevPathRef = useRef(pathname);

  // Save scroll position when navigating away
  const saveScroll = useCallback(() => {
    if (mainRef.current && prevPathRef.current) {
      scrollMap.current[prevPathRef.current] = mainRef.current.scrollTop;
    }
  }, []);

  useEffect(() => {
    if (pathname !== prevPathRef.current) {
      saveScroll();
      prevPathRef.current = pathname;

      // Restore scroll position for the new route
      requestAnimationFrame(() => {
        if (mainRef.current) {
          mainRef.current.scrollTop = scrollMap.current[pathname] ?? 0;
        }
      });
    }
  }, [pathname, saveScroll]);

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex">
      {!isMobile && <Sidebar />}
      <main
        ref={mainRef}
        className={`flex-1 min-h-screen overflow-y-auto ${isMobile ? 'pb-16' : ''} ${isDesktop ? 'ml-[240px]' : isTablet ? 'ml-16' : ''}`}
      >
        {children}
      </main>
      {isMobile && <BottomNav />}
    </div>
  );
}

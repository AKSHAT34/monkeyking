'use client';

import {
  createContext,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import type { UserProfile, Stats } from '@/lib/types';
import { profileApi } from '@/lib/api/profile';
import { statsApi } from '@/lib/api/stats';
import { useAuth } from '@/hooks/useAuth';

// ─── State ──────────────────────────────────────────────
export interface UserState {
  profile: UserProfile | null;
  stats: Stats | null;
  loading: boolean;
}

// ─── Context ────────────────────────────────────────────
export interface UserContextValue extends UserState {
  refreshProfile: () => Promise<void>;
  refreshStats: () => Promise<void>;
}

export const UserContext = createContext<UserContextValue | null>(null);

// ─── Provider ───────────────────────────────────────────
export function UserProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);

  const refreshProfile = useCallback(async () => {
    try {
      const { data } = await profileApi.getProfile();
      setProfile(data);
    } catch {
      // Silently fail — pages can handle missing profile
    }
  }, []);

  const refreshStats = useCallback(async () => {
    try {
      const { data } = await statsApi.getStats();
      setStats(data);
    } catch {
      // Silently fail — pages can handle missing stats
    }
  }, []);

  // Fetch profile and stats when user is authenticated
  useEffect(() => {
    if (!user) {
      setProfile(null);
      setStats(null);
      return;
    }

    setLoading(true);
    Promise.all([refreshProfile(), refreshStats()]).finally(() =>
      setLoading(false),
    );
  }, [user, refreshProfile, refreshStats]);

  return (
    <UserContext.Provider
      value={{ profile, stats, loading, refreshProfile, refreshStats }}
    >
      {children}
    </UserContext.Provider>
  );
}

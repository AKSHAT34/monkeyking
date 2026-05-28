'use client';

import { useAuth } from '@/hooks/useAuth';
import { useProfile } from '@/hooks/useProfile';
import { StatCard } from '@/components/dashboard/StatCard';
import { RecentActivity } from '@/components/dashboard/RecentActivity';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { useRouter } from 'next/navigation';

const STAT_CARDS = [
  { key: 'matches' as const, icon: '🎯', label: 'Matches' },
  { key: 'saved' as const, icon: '💾', label: 'Saved Jobs' },
  { key: 'applied' as const, icon: '✅', label: 'Applied' },
  { key: 'interviews' as const, icon: '📅', label: 'Interviews' },
  { key: 'offers' as const, icon: '🎉', label: 'Offers' },
  { key: 'total_companies' as const, icon: '🏢', label: 'Total Companies' },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const { stats, loading, refreshStats } = useProfile();
  const router = useRouter();

  // Error state: stats failed to load (not loading, no stats)
  const hasError = !loading && stats === null;

  // Empty state: all user-specific stats are zero (no CVs uploaded scenario)
  const isEmpty =
    !loading &&
    stats !== null &&
    stats.matches === 0 &&
    stats.saved === 0 &&
    stats.applied === 0 &&
    stats.interviews === 0 &&
    stats.offers === 0;

  return (
    <div className="p-6 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-h2 text-white">📊 Dashboard</h1>
        <p className="text-gray-400 mt-1">
          Welcome back{user?.name ? `, ${user.name}` : ''}
        </p>
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {STAT_CARDS.map((s) => (
            <Skeleton key={s.key} variant="stat" />
          ))}
        </div>
      )}

      {/* Error state */}
      {hasError && (
        <ErrorState
          message="Failed to load dashboard stats. Please try again."
          onRetry={refreshStats}
        />
      )}

      {/* Empty state */}
      {isEmpty && (
        <EmptyState
          icon={<span className="text-4xl">📄</span>}
          title="No activity yet"
          description="Upload your CV to get started with AI-powered job matching."
          action={{
            label: 'Upload CV',
            onClick: () => router.push('/cvs'),
          }}
        />
      )}

      {/* Stat cards */}
      {!loading && stats && !isEmpty && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {STAT_CARDS.map((s) => (
            <StatCard
              key={s.key}
              icon={s.icon}
              value={stats[s.key]}
              label={s.label}
            />
          ))}
        </div>
      )}

      {/* Recent Activity */}
      {!loading && stats && !isEmpty && (
        <div>
          <h2 className="text-h3 text-white mb-4">Recent Activity</h2>
          <RecentActivity />
        </div>
      )}
    </div>
  );
}

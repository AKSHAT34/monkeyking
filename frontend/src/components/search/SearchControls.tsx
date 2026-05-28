'use client';

import { Button } from '@/components/ui/Button';
import { useProfile } from '@/hooks/useProfile';

interface SearchControlsProps {
  onStart: () => void;
  onStop: () => void;
  isActive: boolean;
  loading: boolean;
}

export function SearchControls({
  onStart,
  onStop,
  isActive,
  loading,
}: SearchControlsProps) {
  const { profile } = useProfile();
  const hasRoles = (profile?.target_roles?.length ?? 0) > 0;

  if (isActive) {
    return (
      <Button variant="danger" onClick={onStop} loading={loading}>
        Stop Search
      </Button>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <Button
        variant="primary"
        onClick={onStart}
        disabled={!hasRoles}
        loading={loading}
      >
        Search Jobs
      </Button>
      {!hasRoles && (
        <p className="text-sm text-yellow-400">
          ⚠ No target roles selected. Go to{' '}
          <a href="/mk2026/profile" className="underline text-mk-orange hover:text-orange-400">
            Profile
          </a>{' '}
          to set your target roles before searching.
        </p>
      )}
    </div>
  );
}

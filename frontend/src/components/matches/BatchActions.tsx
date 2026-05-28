'use client';

import React from 'react';
import { Button } from '@/components/ui/Button';

export interface BatchActionsProps {
  selectedCount: number;
  loading: boolean;
  onSave: () => void;
}

export function BatchActions({ selectedCount, loading, onSave }: BatchActionsProps) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-gray-400">
        {selectedCount} selected
      </span>
      <Button
        size="sm"
        onClick={onSave}
        loading={loading}
        disabled={selectedCount === 0}
      >
        Save Selected
      </Button>
    </div>
  );
}

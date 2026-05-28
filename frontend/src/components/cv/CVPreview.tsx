'use client';

import React from 'react';
import { cvApi } from '@/lib/api/cv';
import { Button } from '@/components/ui/Button';

interface CVPreviewProps {
  cvId: number;
  filename: string;
  onClose: () => void;
}

export function CVPreview({ cvId, filename, onClose }: CVPreviewProps) {
  const viewUrl = cvApi.viewCV(cvId);

  return (
    <div className="rounded-xl border border-mk-border bg-mk-card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-mk-border">
        <p className="text-sm font-medium text-gray-200 truncate">{filename}</p>
        <Button size="sm" variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>
      <iframe
        src={viewUrl}
        title={`Preview of ${filename}`}
        className="w-full h-[600px] bg-white"
      />
    </div>
  );
}

'use client';

import React from 'react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { cvApi } from '@/lib/api/cv';
import type { UploadedCV } from '@/lib/types';

interface CVListItemProps {
  cv: UploadedCV;
  onPreview: (cv: UploadedCV) => void;
}

export function CVListItem({ cv, onPreview }: CVListItemProps) {
  const viewUrl = cvApi.viewCV(cv.id);

  return (
    <Card padding="sm" className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        {/* File type icon */}
        <div className="flex-shrink-0 text-gray-400">
          {cv.file_type === 'pdf' ? (
            <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
          ) : (
            <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
          )}
        </div>

        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-200 truncate">{cv.filename}</p>
          <p className="text-xs text-gray-500">
            {new Date(cv.uploaded_at).toLocaleDateString()} · {cv.file_type.toUpperCase()}
          </p>
        </div>

        {cv.is_primary && (
          <Badge color="orange">Primary</Badge>
        )}
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        <Button size="sm" variant="secondary" onClick={() => onPreview(cv)}>
          Preview
        </Button>
        <a
          href={viewUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-mk-orange hover:underline whitespace-nowrap"
        >
          Open in new tab
        </a>
      </div>
    </Card>
  );
}

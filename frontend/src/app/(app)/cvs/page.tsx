'use client';

import React, { useCallback, useState } from 'react';
import { useToast } from '@/hooks/useToast';
import { useDataCache } from '@/hooks/useDataCache';
import { CVUploadZone } from '@/components/cv/CVUploadZone';
import { CVListItem } from '@/components/cv/CVListItem';
import { CVPreview } from '@/components/cv/CVPreview';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import type { CVUploadResponse, UploadedCV } from '@/lib/types';

export default function CVsPage() {
  const { addToast } = useToast();
  const { cvs, cvsLoading, refreshCVs } = useDataCache();
  const [previewCv, setPreviewCv] = useState<UploadedCV | null>(null);

  const handleUploadComplete = useCallback(
    (response: CVUploadResponse) => {
      addToast({
        type: 'success',
        message: `CV uploaded. ${response.total_cvs} CV${response.total_cvs !== 1 ? 's' : ''} parsed.`,
      });
      refreshCVs();
    },
    [addToast, refreshCVs],
  );

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-h2 text-white">📄 CVs</h1>

      <CVUploadZone onUploadComplete={handleUploadComplete} />

      {previewCv && (
        <CVPreview cvId={previewCv.id} filename={previewCv.filename} onClose={() => setPreviewCv(null)} />
      )}

      <div className="space-y-3">
        <h2 className="text-h4 text-gray-300">Uploaded CVs</h2>

        {cvsLoading && cvs.length === 0 ? (
          <div className="space-y-3">
            <Skeleton variant="card" count={3} />
          </div>
        ) : cvs.length === 0 ? (
          <EmptyState
            icon={<span className="text-3xl">📄</span>}
            title="No CVs uploaded yet"
            description="Upload your first CV to get started. We'll extract your skills, experience, and education automatically."
          />
        ) : (
          <div className="space-y-2">
            {cvs.map((cv) => (
              <CVListItem key={cv.id} cv={cv} onPreview={setPreviewCv} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

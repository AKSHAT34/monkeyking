'use client';

import React, { useCallback, useRef, useState } from 'react';
import { cn } from '@/utils/cn';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { cvApi } from '@/lib/api/cv';
import type { CVUploadResponse } from '@/lib/types';

const ACCEPTED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];
const ACCEPTED_EXTENSIONS = ['.pdf', '.docx'];
const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10MB

interface CVUploadZoneProps {
  onUploadComplete: (response: CVUploadResponse) => void;
  className?: string;
}

export function CVUploadZone({ onUploadComplete, className }: CVUploadZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
    if (!ACCEPTED_EXTENSIONS.includes(ext) && !ACCEPTED_TYPES.includes(file.type)) {
      return 'Only PDF and DOCX files are accepted.';
    }
    if (file.size > MAX_SIZE_BYTES) {
      return 'File size must be under 10MB.';
    }
    return null;
  };

  const handleUpload = useCallback(
    async (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }

      setError(null);
      setUploading(true);
      setProgress(0);

      // Simulate progress since axios onUploadProgress may not fire for small files
      const progressInterval = setInterval(() => {
        setProgress((prev) => Math.min(prev + 10, 90));
      }, 200);

      try {
        const response = await cvApi.uploadCV(file);
        clearInterval(progressInterval);
        setProgress(100);
        onUploadComplete(response.data);
      } catch (err: unknown) {
        clearInterval(progressInterval);
        const message =
          err instanceof Error ? err.message : 'Upload failed. Please try again.';
        setError(message);
      } finally {
        setTimeout(() => {
          setUploading(false);
          setProgress(0);
        }, 500);
      }
    },
    [onUploadComplete],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (uploading) return;
      const file = e.dataTransfer.files[0];
      if (file) handleUpload(file);
    },
    [uploading, handleUpload],
  );

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleUpload(file);
      // Reset input so the same file can be re-selected
      e.target.value = '';
    },
    [handleUpload],
  );

  return (
    <div className={className}>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!uploading) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !uploading && inputRef.current?.click()}
        className={cn(
          'relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-colors cursor-pointer',
          dragOver && !uploading
            ? 'border-mk-orange bg-mk-orange/5'
            : 'border-mk-border hover:border-gray-500',
          uploading && 'pointer-events-none opacity-60',
        )}
        role="button"
        tabIndex={uploading ? -1 : 0}
        aria-label="Upload CV file"
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !uploading) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          onChange={onFileChange}
          className="hidden"
          aria-hidden="true"
        />

        <svg
          className="mb-3 h-10 w-10 text-gray-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.338-2.32 3.75 3.75 0 013.572 5.345A3.75 3.75 0 0117.25 19.5H6.75z"
          />
        </svg>

        <p className="text-sm text-gray-300">
          {uploading ? 'Uploading...' : 'Drag & drop your CV here, or click to browse'}
        </p>
        <p className="mt-1 text-xs text-gray-500">PDF or DOCX, max 10MB</p>

        {uploading && (
          <div className="mt-4 w-full max-w-xs">
            <ProgressBar value={progress} showLabel />
          </div>
        )}
      </div>

      {error && (
        <p className="mt-2 text-sm text-red-400" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

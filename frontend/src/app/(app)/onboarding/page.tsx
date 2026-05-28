'use client';

import { useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { Spinner } from '@/components/ui/Spinner';
import { useToast } from '@/hooks/useToast';
import api from '@/lib/api';
import type { CVUploadResponse } from '@/lib/types';

const TOTAL_STEPS = 4;

const ACCEPTED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

const DEFAULT_ROLES = [
  'Software Engineer',
  'Product Manager',
  'Data Scientist',
  'Engineering Manager',
  'DevOps Engineer',
  'UX Designer',
  'Data Engineer',
  'Solutions Architect',
  'Technical Program Manager',
  'Machine Learning Engineer',
];

export default function OnboardingPage() {
  const router = useRouter();
  const { addToast } = useToast();

  const [step, setStep] = useState(1);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [parsedData, setParsedData] = useState<CVUploadResponse | null>(null);
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const goToDashboard = useCallback(() => {
    router.push('/dashboard');
  }, [router]);

  const nextStep = useCallback(() => {
    setStep((s) => Math.min(s + 1, TOTAL_STEPS));
  }, []);

  const prevStep = useCallback(() => {
    setStep((s) => Math.max(s - 1, 1));
  }, []);

  // ── File validation ──
  const validateFile = (file: File): string | null => {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      return 'Only PDF and DOCX files are accepted.';
    }
    if (file.size > MAX_FILE_SIZE) {
      return 'File size must be under 10 MB.';
    }
    return null;
  };

  // ── Upload handler ──
  const handleUpload = useCallback(
    async (file: File) => {
      const error = validateFile(file);
      if (error) {
        setUploadError(error);
        return;
      }

      setUploadError(null);
      setUploading(true);

      try {
        const formData = new FormData();
        formData.append('file', file);

        const { data } = await api.post<CVUploadResponse>(
          '/cv/upload',
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } },
        );

        setParsedData(data);

        // Pre-select suggested roles from parsed data
        const suggested = (data.parsed?.suggested_roles as string[]) ?? [];
        setSelectedRoles(suggested);

        addToast({ type: 'success', message: `CV "${data.filename}" uploaded and parsed.` });
        nextStep();
      } catch (err: unknown) {
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data
            ?.detail ?? 'Upload failed. Please try again.';
        setUploadError(msg);
        addToast({ type: 'error', message: msg });
      } finally {
        setUploading(false);
      }
    },
    [addToast, nextStep],
  );

  // ── Drag & drop handlers ──
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleUpload(file);
    },
    [handleUpload],
  );

  const onFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleUpload(file);
    },
    [handleUpload],
  );

  // ── Role toggle ──
  const toggleRole = (role: string) => {
    setSelectedRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role],
    );
  };

  // ── Derive available roles for step 3 ──
  const suggestedRoles = (parsedData?.parsed?.suggested_roles as string[]) ?? [];
  const allRoles = Array.from(new Set([...suggestedRoles, ...DEFAULT_ROLES]));

  // ── Parsed helpers ──
  const skills = (parsedData?.parsed?.skills ?? {}) as Record<string, string[]>;
  const experience = (parsedData?.parsed?.experience ?? []) as Array<{
    company?: string;
    title?: string;
    duration?: string;
  }>;
  const education = (parsedData?.parsed?.education ?? []) as Array<{
    institution?: string;
    degree?: string;
    year?: string;
  }>;

  // ── Step indicator ──
  const StepIndicator = () => (
    <div className="flex items-center justify-center gap-2 mb-8">
      {Array.from({ length: TOTAL_STEPS }, (_, i) => {
        const s = i + 1;
        const isActive = s === step;
        const isDone = s < step;
        return (
          <div key={s} className="flex items-center gap-2">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-mk-orange text-white'
                  : isDone
                    ? 'bg-mk-orange/20 text-mk-orange'
                    : 'bg-mk-border text-gray-500'
              }`}
            >
              {isDone ? '✓' : s}
            </div>
            {s < TOTAL_STEPS && (
              <div
                className={`w-12 h-0.5 ${isDone ? 'bg-mk-orange' : 'bg-mk-border'}`}
              />
            )}
          </div>
        );
      })}
    </div>
  );

  // ── Step 1: Welcome ──
  const WelcomeStep = () => (
    <div className="text-center max-w-xl mx-auto">
      <div className="text-5xl mb-4">🐵</div>
      <h2 className="text-h2 text-white mb-3">Welcome to MonkeyKing</h2>
      <p className="text-gray-400 mb-8">
        Help you climb your career ladder. Let&apos;s get you set up in a few quick steps.
      </p>

      <div className="grid gap-4 text-left">
        <Card padding="md">
          <div className="flex items-start gap-3">
            <span className="text-2xl">📄</span>
            <div>
              <h3 className="text-white font-medium">Smart CV Parsing</h3>
              <p className="text-gray-400 text-sm">
                Upload your CV and our AI extracts skills, experience, and education automatically.
              </p>
            </div>
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-start gap-3">
            <span className="text-2xl">🔍</span>
            <div>
              <h3 className="text-white font-medium">AI Job Matching</h3>
              <p className="text-gray-400 text-sm">
                Search 623+ companies and get AI-scored matches based on your profile.
              </p>
            </div>
          </div>
        </Card>
        <Card padding="md">
          <div className="flex items-start gap-3">
            <span className="text-2xl">🎯</span>
            <div>
              <h3 className="text-white font-medium">Tailored CVs</h3>
              <p className="text-gray-400 text-sm">
                Generate ATS-optimized CVs tailored to each job with one click.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );

  // ── Step 2: CV Upload ──
  const UploadStep = () => (
    <div className="max-w-xl mx-auto">
      <h2 className="text-h2 text-white text-center mb-2">Upload Your CV</h2>
      <p className="text-gray-400 text-center mb-6">
        We&apos;ll extract your skills, experience, and education using AI.
      </p>

      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
          uploading
            ? 'border-mk-border bg-mk-card/50 pointer-events-none opacity-70'
            : dragOver
              ? 'border-mk-orange bg-mk-orange/5'
              : 'border-mk-border hover:border-mk-orange/50 bg-mk-card'
        }`}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !uploading) {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        aria-label="Upload CV file"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={onFileSelect}
          className="hidden"
          aria-hidden="true"
        />

        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <Spinner size="lg" />
            <p className="text-gray-300">Uploading and parsing your CV...</p>
            <ProgressBar value={60} className="max-w-xs" />
          </div>
        ) : (
          <>
            <div className="text-4xl mb-3">📁</div>
            <p className="text-white font-medium mb-1">
              Drag & drop your CV here
            </p>
            <p className="text-gray-500 text-sm">
              or click to browse — PDF or DOCX, max 10 MB
            </p>
          </>
        )}
      </div>

      {uploadError && (
        <p className="mt-3 text-sm text-error text-center">{uploadError}</p>
      )}
    </div>
  );

  // ── Step 3: Review Profile ──
  const ReviewStep = () => (
    <div className="max-w-2xl mx-auto">
      <h2 className="text-h2 text-white text-center mb-2">
        Your Extracted Profile
      </h2>
      <p className="text-gray-400 text-center mb-6">
        Here&apos;s what our AI found. Select the roles you&apos;re targeting.
      </p>

      <div className="space-y-6">
        {/* Skills */}
        {Object.keys(skills).length > 0 && (
          <Card padding="md">
            <h3 className="text-white font-medium mb-3">Skills</h3>
            <div className="space-y-2">
              {Object.entries(skills).map(([category, items]) => (
                <div key={category}>
                  <span className="text-xs text-gray-500 uppercase tracking-wide">
                    {category}
                  </span>
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {items.map((skill) => (
                      <Badge key={skill} color="orange">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Experience */}
        {experience.length > 0 && (
          <Card padding="md">
            <h3 className="text-white font-medium mb-3">Experience</h3>
            <div className="space-y-3">
              {experience.map((exp, i) => (
                <div key={i} className="flex justify-between items-start">
                  <div>
                    <p className="text-white text-sm">{exp.title}</p>
                    <p className="text-gray-400 text-xs">{exp.company}</p>
                  </div>
                  {exp.duration && (
                    <span className="text-gray-500 text-xs shrink-0">
                      {exp.duration}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Education */}
        {education.length > 0 && (
          <Card padding="md">
            <h3 className="text-white font-medium mb-3">Education</h3>
            <div className="space-y-2">
              {education.map((edu, i) => (
                <div key={i}>
                  <p className="text-white text-sm">{edu.degree}</p>
                  <p className="text-gray-400 text-xs">
                    {edu.institution}
                    {edu.year ? ` · ${edu.year}` : ''}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Target Roles */}
        <Card padding="md">
          <h3 className="text-white font-medium mb-3">Target Roles</h3>
          <p className="text-gray-400 text-xs mb-3">
            Select the roles you want to search for. These power your AI job matching.
          </p>
          <div className="flex flex-wrap gap-2">
            {allRoles.map((role) => {
              const isSelected = selectedRoles.includes(role);
              return (
                <button
                  key={role}
                  onClick={() => toggleRole(role)}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors border ${
                    isSelected
                      ? 'bg-mk-orange/20 border-mk-orange text-mk-orange'
                      : 'bg-mk-card border-mk-border text-gray-400 hover:border-gray-500'
                  }`}
                >
                  {role}
                </button>
              );
            })}
          </div>
        </Card>
      </div>
    </div>
  );

  // ── Step 4: Get Started ──
  const GetStartedStep = () => (
    <div className="text-center max-w-xl mx-auto">
      <div className="text-5xl mb-4">🎉</div>
      <h2 className="text-h2 text-white mb-3">You&apos;re All Set!</h2>
      <p className="text-gray-400 mb-8">
        Your profile is ready. What would you like to do first?
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card
          padding="lg"
          hoverable
          onClick={() => router.push('/search')}
        >
          <div className="text-3xl mb-2">🔍</div>
          <h3 className="text-white font-medium mb-1">Start a Job Search</h3>
          <p className="text-gray-400 text-sm">
            Scan companies and find AI-matched jobs for your profile.
          </p>
        </Card>
        <Card
          padding="lg"
          hoverable
          onClick={() => router.push('/companies')}
        >
          <div className="text-3xl mb-2">🏢</div>
          <h3 className="text-white font-medium mb-1">Explore Companies</h3>
          <p className="text-gray-400 text-sm">
            Browse 623+ companies and manage your target list.
          </p>
        </Card>
      </div>
    </div>
  );

  // ── Render ──
  return (
    <div className="p-6 max-w-3xl mx-auto">
      <StepIndicator />

      <div className="mb-8">
        {step === 1 && <WelcomeStep />}
        {step === 2 && <UploadStep />}
        {step === 3 && <ReviewStep />}
        {step === 4 && <GetStartedStep />}
      </div>

      {/* Navigation buttons */}
      <div className="flex items-center justify-between max-w-xl mx-auto">
        <div>
          {step > 1 && step < 4 && (
            <Button variant="ghost" onClick={prevStep}>
              ← Back
            </Button>
          )}
        </div>

        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={goToDashboard}>
            Skip
          </Button>

          {step === 1 && (
            <Button onClick={nextStep}>Get Started →</Button>
          )}
          {step === 3 && (
            <Button onClick={nextStep}>Continue →</Button>
          )}
        </div>
      </div>
    </div>
  );
}

'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { Skeleton } from '@/components/ui/Skeleton';
import { SkillTags } from '@/components/profile/SkillTags';
import { ExperienceEditor } from '@/components/profile/ExperienceEditor';
import { EducationEditor } from '@/components/profile/EducationEditor';
import { RoleSelector } from '@/components/profile/RoleSelector';
import { PreferencesForm } from '@/components/profile/PreferencesForm';
import { useProfile } from '@/hooks/useProfile';
import { useToast } from '@/hooks/useToast';
import { profileApi } from '@/lib/api/profile';
import type { UserProfile, Experience, Education } from '@/lib/types';

type FormData = Partial<UserProfile>;

export default function ProfilePage() {
  const { profile, loading, refreshProfile } = useProfile();
  const { addToast } = useToast();

  const [form, setForm] = useState<FormData>({});
  const [saving, setSaving] = useState(false);
  const [initialized, setInitialized] = useState(false);

  // Populate form when profile loads
  useEffect(() => {
    if (profile && !initialized) {
      setForm({
        extracted_summary: profile.extracted_summary || '',
        extracted_skills: profile.extracted_skills || {},
        extracted_experience: profile.extracted_experience || [],
        extracted_education: profile.extracted_education || [],
        target_roles: profile.target_roles || [],
        phone: profile.phone || '',
        location: profile.location || '',
        linkedin: profile.linkedin || '',
        notice_period: profile.notice_period || '',
        current_salary: profile.current_salary || '',
        expected_salary: profile.expected_salary || '',
        work_authorization: profile.work_authorization || '',
        preferred_locations: profile.preferred_locations || [],
      });
      setInitialized(true);
    }
  }, [profile, initialized]);

  // Dirty check
  const isDirty = useMemo(() => {
    if (!profile || !initialized) return false;
    return JSON.stringify({
      extracted_summary: profile.extracted_summary || '',
      extracted_skills: profile.extracted_skills || {},
      extracted_experience: profile.extracted_experience || [],
      extracted_education: profile.extracted_education || [],
      target_roles: profile.target_roles || [],
      phone: profile.phone || '',
      location: profile.location || '',
      linkedin: profile.linkedin || '',
      notice_period: profile.notice_period || '',
      current_salary: profile.current_salary || '',
      expected_salary: profile.expected_salary || '',
      work_authorization: profile.work_authorization || '',
      preferred_locations: profile.preferred_locations || [],
    }) !== JSON.stringify(form);
  }, [profile, form, initialized]);

  const updateField = useCallback((field: string, value: unknown) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await profileApi.updateProfile(form);
      addToast({ type: 'success', message: 'Profile saved successfully' });
      await refreshProfile();
      setInitialized(false); // re-sync from server
    } catch {
      addToast({ type: 'error', message: 'Failed to save profile. Your changes are preserved.' });
    } finally {
      setSaving(false);
    }
  };

  if (loading && !initialized) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton variant="text" width="200px" height="32px" />
          <Skeleton variant="button" />
        </div>
        <Skeleton variant="card" count={4} />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-h2 text-white">Profile</h1>
          {isDirty && (
            <span className="inline-flex items-center gap-1.5 text-xs text-yellow-400">
              <span className="h-2 w-2 rounded-full bg-yellow-400" />
              Unsaved changes
            </span>
          )}
        </div>
        <Button
          onClick={handleSave}
          disabled={!isDirty}
          loading={saving}
        >
          Save Profile
        </Button>
      </div>

      {/* Summary */}
      <Card>
        <h3 className="text-h4 text-white mb-3">Professional Summary</h3>
        <Textarea
          value={form.extracted_summary || ''}
          onChange={(e) => updateField('extracted_summary', e.target.value)}
          placeholder="Your professional summary..."
          maxLength={2000}
          showCount
        />
      </Card>

      {/* Skills */}
      <Card>
        <h3 className="text-h4 text-white mb-3">Skills</h3>
        <SkillTags
          skills={(form.extracted_skills as Record<string, string[]>) || {}}
          onChange={(skills) => updateField('extracted_skills', skills)}
        />
      </Card>

      {/* Target Roles */}
      <Card>
        <h3 className="text-h4 text-white mb-3">Target Roles</h3>
        <RoleSelector
          suggestedRoles={profile?.suggested_roles || []}
          selectedRoles={(form.target_roles as string[]) || []}
          onChange={(roles) => updateField('target_roles', roles)}
        />
      </Card>

      {/* Experience */}
      <Card>
        <h3 className="text-h4 text-white mb-3">Experience</h3>
        <ExperienceEditor
          experiences={(form.extracted_experience as Experience[]) || []}
          onChange={(exp) => updateField('extracted_experience', exp)}
        />
      </Card>

      {/* Education */}
      <Card>
        <h3 className="text-h4 text-white mb-3">Education</h3>
        <EducationEditor
          education={(form.extracted_education as Education[]) || []}
          onChange={(edu) => updateField('extracted_education', edu)}
        />
      </Card>

      {/* Preferences */}
      <Card>
        <h3 className="text-h4 text-white mb-3">Preferences</h3>
        <PreferencesForm
          values={{
            phone: form.phone as string,
            location: form.location as string,
            linkedin: form.linkedin as string,
            notice_period: form.notice_period as string,
            current_salary: form.current_salary as string,
            expected_salary: form.expected_salary as string,
            work_authorization: form.work_authorization as string,
            preferred_locations: form.preferred_locations as string[],
          }}
          onChange={(field, value) => updateField(field, value)}
        />
      </Card>
    </div>
  );
}

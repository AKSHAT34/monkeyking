'use client';

import { useState } from 'react';
import type { Experience } from '@/lib/types';

interface ExperienceEditorProps {
  experiences: Experience[];
  onChange: (experiences: Experience[]) => void;
}

function InlineField({
  value,
  placeholder,
  onSave,
  multiline,
}: {
  value: string;
  placeholder: string;
  onSave: (val: string) => void;
  multiline?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const commit = () => {
    setEditing(false);
    if (draft !== value) onSave(draft);
  };

  if (editing) {
    if (multiline) {
      return (
        <textarea
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setDraft(value);
              setEditing(false);
            }
          }}
          className="w-full rounded border border-mk-border bg-mk-dark px-2 py-1 text-sm text-white resize-y min-h-[60px] focus:border-mk-orange focus:outline-none"
          placeholder={placeholder}
        />
      );
    }
    return (
      <input
        autoFocus
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
          if (e.key === 'Escape') {
            setDraft(value);
            setEditing(false);
          }
        }}
        className="rounded border border-mk-border bg-mk-dark px-2 py-1 text-sm text-white focus:border-mk-orange focus:outline-none"
        placeholder={placeholder}
      />
    );
  }

  return (
    <span
      onClick={() => {
        setDraft(value);
        setEditing(true);
      }}
      className="cursor-pointer hover:text-mk-orange transition-colors"
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          setDraft(value);
          setEditing(true);
        }
      }}
    >
      {value || <span className="text-gray-500 italic">{placeholder}</span>}
    </span>
  );
}

export function ExperienceEditor({ experiences, onChange }: ExperienceEditorProps) {
  const updateField = (index: number, field: keyof Experience, value: string) => {
    const updated = experiences.map((exp, i) =>
      i === index ? { ...exp, [field]: value } : exp,
    );
    onChange(updated);
  };

  if (experiences.length === 0) {
    return <p className="text-gray-500 text-sm">No experience entries yet.</p>;
  }

  return (
    <div className="space-y-4">
      {experiences.map((exp, i) => (
        <div key={i} className="border border-mk-border rounded-lg p-3 space-y-1">
          <div className="flex items-center gap-2 text-white font-medium">
            <InlineField value={exp.title} placeholder="Job title" onSave={(v) => updateField(i, 'title', v)} />
            <span className="text-gray-500">at</span>
            <InlineField value={exp.company} placeholder="Company" onSave={(v) => updateField(i, 'company', v)} />
          </div>
          <div className="text-caption text-gray-400">
            <InlineField value={exp.duration || ''} placeholder="Duration (e.g. 2020–2023)" onSave={(v) => updateField(i, 'duration', v)} />
          </div>
          <div className="text-sm text-gray-300">
            <InlineField
              value={exp.description || ''}
              placeholder="Description"
              onSave={(v) => updateField(i, 'description', v)}
              multiline
            />
          </div>
        </div>
      ))}
    </div>
  );
}

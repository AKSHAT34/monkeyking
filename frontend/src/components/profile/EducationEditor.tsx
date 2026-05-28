'use client';

import { useState } from 'react';
import type { Education } from '@/lib/types';

interface EducationEditorProps {
  education: Education[];
  onChange: (education: Education[]) => void;
}

function InlineField({
  value,
  placeholder,
  onSave,
}: {
  value: string;
  placeholder: string;
  onSave: (val: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const commit = () => {
    setEditing(false);
    if (draft !== value) onSave(draft);
  };

  if (editing) {
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

export function EducationEditor({ education, onChange }: EducationEditorProps) {
  const updateField = (index: number, field: keyof Education, value: string) => {
    const updated = education.map((edu, i) =>
      i === index ? { ...edu, [field]: value } : edu,
    );
    onChange(updated);
  };

  if (education.length === 0) {
    return <p className="text-gray-500 text-sm">No education entries yet.</p>;
  }

  return (
    <div className="space-y-3">
      {education.map((edu, i) => (
        <div key={i} className="border border-mk-border rounded-lg p-3 space-y-1">
          <div className="text-white font-medium">
            <InlineField value={edu.degree} placeholder="Degree" onSave={(v) => updateField(i, 'degree', v)} />
          </div>
          <div className="text-sm text-gray-300">
            <InlineField value={edu.institution} placeholder="Institution" onSave={(v) => updateField(i, 'institution', v)} />
          </div>
          <div className="text-caption text-gray-400">
            <InlineField value={edu.year || ''} placeholder="Year" onSave={(v) => updateField(i, 'year', v)} />
          </div>
        </div>
      ))}
    </div>
  );
}

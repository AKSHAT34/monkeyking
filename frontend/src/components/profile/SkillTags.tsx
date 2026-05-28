'use client';

import { Card } from '@/components/ui/Card';

interface SkillTagsProps {
  skills: Record<string, string[]>;
  onChange: (skills: Record<string, string[]>) => void;
}

export function SkillTags({ skills, onChange }: SkillTagsProps) {
  const categories = Object.keys(skills);

  const removeSkill = (category: string, skill: string) => {
    const updated = { ...skills };
    updated[category] = updated[category].filter((s) => s !== skill);
    if (updated[category].length === 0) {
      delete updated[category];
    }
    onChange(updated);
  };

  if (categories.length === 0) {
    return (
      <Card>
        <p className="text-gray-500 text-sm">No skills extracted yet. Upload a CV to get started.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {categories.map((category) => (
        <div key={category}>
          <h4 className="text-label text-gray-400 mb-2">{category}</h4>
          <div className="flex flex-wrap gap-2">
            {skills[category].map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-mk-orange/10 text-mk-orange border border-mk-orange/30"
              >
                {skill}
                <button
                  type="button"
                  onClick={() => removeSkill(category, skill)}
                  className="ml-0.5 hover:text-white transition-colors"
                  aria-label={`Remove ${skill}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

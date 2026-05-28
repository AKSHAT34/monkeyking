'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Checkbox } from '@/components/ui/Checkbox';
import { matchScoreColor } from '@/lib/types';
import type { JobMatch } from '@/lib/types';
import { cn } from '@/utils/cn';

export interface MatchCardProps {
  match: JobMatch;
  selected: boolean;
  onToggle: (jobId: number) => void;
}

export const MatchCard = React.memo(function MatchCard({ match, selected, onToggle }: MatchCardProps) {
  const scorePercent = Math.round(match.match_score * 100);
  const scoreClasses = matchScoreColor(match.match_score);

  return (
    <Card padding="md" className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          {match.is_saved ? (
            <Badge color="green" className="shrink-0 mt-0.5">Saved</Badge>
          ) : (
            <Checkbox
              checked={selected}
              onChange={() => onToggle(match.job_id)}
              aria-label={`Select ${match.title}`}
              className="mt-0.5 shrink-0"
            />
          )}
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-white truncate">
              {match.title}
            </h3>
            <p className="text-xs text-gray-400 truncate">
              {match.company} · {match.location}
            </p>
          </div>
        </div>

        <span
          className={cn(
            'inline-flex items-center px-2 py-0.5 rounded text-xs font-bold shrink-0',
            scoreClasses,
          )}
        >
          {scorePercent}%
        </span>
      </div>

      <p className="text-xs text-gray-300 leading-relaxed">
        {match.match_reason}
      </p>

      {match.relevance_summary && (
        <p className="text-xs text-gray-400 italic">
          {match.relevance_summary}
        </p>
      )}

      {match.matched_skills.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {match.matched_skills.map((skill) => (
            <Badge key={skill} color="green">{skill}</Badge>
          ))}
        </div>
      )}

      {match.missing_skills.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {match.missing_skills.map((skill) => (
            <Badge key={skill} color="red">{skill}</Badge>
          ))}
        </div>
      )}

      <div className="pt-1">
        <a
          href={match.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-mk-orange hover:underline"
        >
          View Job ↗
        </a>
      </div>
    </Card>
  );
});

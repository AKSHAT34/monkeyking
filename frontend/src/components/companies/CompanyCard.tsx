'use client';

import React from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import type { Company } from '@/lib/types';

const categoryColors: Record<string, 'blue' | 'purple' | 'orange' | 'green' | 'yellow' | 'red' | 'emerald' | 'gray'> = {
  'Tech Giants': 'blue', 'AI Companies': 'purple', 'Cloud & SaaS': 'orange',
  'Indian Startups': 'green', 'Fintech': 'yellow', 'E-commerce': 'red',
  'Consulting': 'emerald', 'Banking': 'blue', 'IT Services': 'gray', 'Other': 'gray',
};

interface CompanyCardProps {
  company: Company;
  onClick: () => void;
  isAdmin?: boolean;
  onEdit?: (company: Company) => void;
  onDelete?: (company: Company) => void;
}

export const CompanyCard = React.memo(function CompanyCard({ company, onClick, isAdmin, onEdit, onDelete }: CompanyCardProps) {
  return (
    <Card hoverable onClick={onClick} padding="md">
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-white truncate">{company.name}</h3>
        <div className="flex items-center gap-2 flex-wrap">
          <Badge color={categoryColors[company.category] ?? 'gray'}>
            {company.category || 'Other'}
          </Badge>
          {company.country && (
            <span className="text-xs text-gray-400">{company.country}</span>
          )}
        </div>
        <a
          href={company.careers_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-mk-orange hover:underline truncate"
          onClick={(e) => e.stopPropagation()}
        >
          {company.careers_url.replace('https://', '').replace('http://', '').slice(0, 40)}... ↗
        </a>
        {isAdmin && (
          <div className="flex gap-2 pt-1" onClick={(e) => e.stopPropagation()}>
            <button onClick={() => onEdit?.(company)}
              className="text-xs text-blue-400 hover:text-blue-300">✏️ Edit</button>
            <button onClick={() => onDelete?.(company)}
              className="text-xs text-red-400 hover:text-red-300">🗑️ Delete</button>
            <button onClick={async () => {
              try {
                const { default: api } = await import('@/lib/api');
                const { data } = await api.post(`/companies/${company.id}/test-url`);
                alert(data.reachable
                  ? `✅ Reachable (${data.status})${data.has_jobs_content ? ' — has job content' : ' — no job keywords found'}${data.redirect ? `\nRedirects to: ${data.final_url}` : ''}`
                  : `❌ Unreachable${data.error ? `: ${data.error}` : ''}`);
              } catch { alert('Test failed'); }
            }} className="text-xs text-yellow-400 hover:text-yellow-300">🔗 Test</button>
          </div>
        )}
      </div>
    </Card>
  );
});

'use client';

import { Card } from '@/components/ui/Card';

interface StatCardProps {
  icon: string;
  value: number;
  label: string;
}

export function StatCard({ icon, value, label }: StatCardProps) {
  return (
    <Card padding="md">
      <div className="flex items-center gap-3">
        <span className="text-2xl" role="img" aria-label={label}>
          {icon}
        </span>
        <div>
          <p className="text-2xl font-bold text-white">{value}</p>
          <p className="text-sm text-gray-400">{label}</p>
        </div>
      </div>
    </Card>
  );
}

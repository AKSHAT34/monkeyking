'use client';

import { cn } from '@/utils/cn';

export interface Tab {
  key: string;
  label: string;
}

export interface TabsProps {
  tabs: Tab[];
  activeKey: string;
  onChange: (key: string) => void;
  className?: string;
}

export function Tabs({ tabs, activeKey, onChange, className }: TabsProps) {
  return (
    <div className={cn('flex gap-1 rounded-lg bg-mk-dark p-1', className)} role="tablist">
      {tabs.map((tab) => {
        const isActive = tab.key === activeKey;
        return (
          <button
            key={tab.key}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.key)}
            className={cn(
              'px-4 py-2 rounded-md text-sm font-medium transition-colors',
              isActive
                ? 'bg-mk-orange text-white'
                : 'text-gray-400 border border-mk-border hover:text-white',
            )}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

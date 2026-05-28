'use client';

import { useContext } from 'react';
import { SearchContext, type SearchContextValue } from '@/providers/SearchProvider';

export function useSearch(): SearchContextValue {
  const ctx = useContext(SearchContext);
  if (!ctx) {
    throw new Error('useSearch must be used within a SearchProvider');
  }
  return ctx;
}

'use client';

import { useContext } from 'react';
import { DataCacheContext, type DataCacheContextValue } from '@/providers/DataCacheProvider';

export function useDataCache(): DataCacheContextValue {
  const ctx = useContext(DataCacheContext);
  if (!ctx) {
    throw new Error('useDataCache must be used within a DataCacheProvider');
  }
  return ctx;
}

'use client';

import { useContext } from 'react';
import { UserContext, type UserContextValue } from '@/providers/UserProvider';

export function useProfile(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) {
    throw new Error('useProfile must be used within a UserProvider');
  }
  return ctx;
}

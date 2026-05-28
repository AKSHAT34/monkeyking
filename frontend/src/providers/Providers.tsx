'use client';

import type { ReactNode } from 'react';
import { AuthProvider } from '@/providers/AuthProvider';
import { UserProvider } from '@/providers/UserProvider';
import { ToastProvider } from '@/providers/ToastProvider';
import { SearchProvider } from '@/providers/SearchProvider';
import { DataCacheProvider } from '@/providers/DataCacheProvider';
import { ConnectionStatus } from '@/components/ui/ConnectionStatus';

export function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <UserProvider>
        <ToastProvider>
          <DataCacheProvider>
            <SearchProvider>
              <ConnectionStatus />
              {children}
            </SearchProvider>
          </DataCacheProvider>
        </ToastProvider>
      </UserProvider>
    </AuthProvider>
  );
}

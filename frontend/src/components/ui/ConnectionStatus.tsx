'use client';

import { useEffect, useState } from 'react';
import { connectionStatus } from '@/lib/toast-events';

export function ConnectionStatus() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    return connectionStatus.subscribe(setOffline);
  }, []);

  if (!offline) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[60] bg-red-700 text-white text-center text-sm py-2 px-4">
      Unable to reach the server — retrying...
    </div>
  );
}

'use client';

import { useRouter } from 'next/navigation';
import { Dropdown } from '@/components/ui/Dropdown';

interface UserMenuProps {
  collapsed?: boolean;
}

export function UserMenu({ collapsed = false }: UserMenuProps) {
  const router = useRouter();

  const userName = typeof window !== 'undefined'
    ? (() => { try { return JSON.parse(localStorage.getItem('mk_user') || '{}').name; } catch { return null; } })()
    : null;

  const handleLogout = () => {
    localStorage.removeItem('mk_token');
    localStorage.removeItem('mk_user');
    router.push('/login');
  };

  const initials = userName
    ? userName.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
    : '??';

  return (
    <Dropdown
      trigger={
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-mk-card transition-colors cursor-pointer">
          <div className="w-8 h-8 rounded-full bg-mk-orange/20 text-mk-orange flex items-center justify-center text-xs font-bold shrink-0">
            {initials}
          </div>
          {!collapsed && (
            <span className="text-sm text-gray-300 truncate">{userName || 'User'}</span>
          )}
        </div>
      }
      items={[
        { label: '👤 Profile', onClick: () => router.push('/profile') },
        { label: '🚪 Logout', onClick: handleLogout },
      ]}
      align="left"
    />
  );
}

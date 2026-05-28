import api from '@/lib/api';
import type { UserProfile } from '@/lib/types';

export const profileApi = {
  getProfile: () => api.get<UserProfile>('/profile'),
  updateProfile: (data: Partial<UserProfile>) => api.put('/profile', data),
};

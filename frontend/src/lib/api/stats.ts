import api from '@/lib/api';
import type { Stats } from '@/lib/types';

export const statsApi = {
  getStats: () => api.get<Stats>('/stats'),
};

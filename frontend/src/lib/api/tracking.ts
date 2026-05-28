import api from '@/lib/api';
import type { ApplicationStatus, TrackedJob } from '@/lib/types';

export const trackingApi = {
  getSavedJobs: () => api.get<TrackedJob[]>('/jobs/saved'),

  updateJobStatus: (id: number, status: ApplicationStatus, notes?: string) =>
    api.put<{ status: string }>(`/jobs/saved/${id}`, { status, ...(notes !== undefined && { notes }) }),
};

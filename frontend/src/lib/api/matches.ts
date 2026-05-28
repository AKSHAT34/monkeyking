import api from '@/lib/api';
import type { JobMatch } from '@/lib/types';

export interface SaveJobsResponse {
  added: number;
}

export const matchesApi = {
  getMatches: (params?: { limit?: number; min_score?: number }) =>
    api.get<JobMatch[]>('/jobs/matches', { params }),

  saveJobs: (jobIds: number[]) =>
    api.post<SaveJobsResponse>('/jobs/save', { job_ids: jobIds }),
};

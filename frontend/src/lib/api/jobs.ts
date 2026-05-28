import api from '@/lib/api';
import type { SearchStartResponse, SearchRunStatus } from '@/lib/types';

export interface ActiveSearchResponse {
  active: boolean;
  search_run_id?: number;
  status?: string;
  companies_searched?: number;
  jobs_found?: number;
  jobs_matched?: number;
  progress?: Array<{ company: string; status: string; jobs_found?: number; matched?: number }>;
}

export interface StopSearchResponse {
  status: string;
}

export const jobsApi = {
  startSearch: () =>
    api.post<SearchStartResponse>('/jobs/search'),

  getSearchStatus: (id: number) =>
    api.get<SearchRunStatus>(`/jobs/search/${id}`),

  getActiveSearch: () =>
    api.get<ActiveSearchResponse>('/jobs/search/active'),

  stopSearch: (id: number) =>
    api.post<StopSearchResponse>(`/jobs/search/stop/${id}`),
};

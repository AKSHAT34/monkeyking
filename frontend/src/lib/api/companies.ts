import api from '@/lib/api';
import type { Company, Job } from '@/lib/types';

export interface ListCompaniesParams {
  category?: string;
  country?: string;
  search?: string;
}

export interface AddCompanyPayload {
  name: string;
  careers_url: string;
  category?: string;
  country?: string;
}

export interface AddCompanyResponse {
  id: number;
  message: string;
}

export const companiesApi = {
  listCompanies: (params?: ListCompaniesParams) =>
    api.get<Company[]>('/companies', { params }),

  addCompany: (data: AddCompanyPayload) =>
    api.post<AddCompanyResponse>('/companies', data),

  updateCompany: (id: number, data: Partial<AddCompanyPayload>) =>
    api.put(`/companies/${id}`, data),

  deleteCompany: (id: number) =>
    api.delete(`/companies/${id}`),

  jobsByCompany: (company: string) =>
    api.get<Job[]>('/jobs/by-company', { params: { company } }),
};

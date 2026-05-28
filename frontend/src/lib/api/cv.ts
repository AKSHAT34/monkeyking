import api from '@/lib/api';
import type { CVUploadResponse, UploadedCV } from '@/lib/types';

export const cvApi = {
  uploadCV: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<CVUploadResponse>('/cv/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  listCVs: () => api.get<UploadedCV[]>('/cv/list'),

  viewCV: (id: number): string => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('mk_token') : null;
    return `/mk2026/api/cv/view/${id}${token ? `?token=${token}` : ''}`;
  },

  generateCV: (jobId: number) =>
    api.post<{ pdf_path: string; docx_path: string }>(`/cv/generate/${jobId}`),

  generateCoverLetter: (jobId: number) =>
    api.post<{ pdf_path: string; docx_path: string }>(`/cover-letter/generate/${jobId}`),

  downloadCV: async (id: number, format: 'pdf' | 'docx') => {
    const response = await api.get(`/cv/download/${id}`, {
      params: { format },
      responseType: 'blob',
    });

    const contentDisposition = response.headers['content-disposition'];
    let filename = `cv_${id}.${format}`;
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^";\n]+)"?/);
      if (match?.[1]) filename = match[1];
    }

    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  downloadCoverLetter: async (id: number, format: 'pdf' | 'docx') => {
    const response = await api.get(`/cover-letter/download/${id}`, {
      params: { format },
      responseType: 'blob',
    });

    const contentDisposition = response.headers['content-disposition'];
    let filename = `cover_letter_${id}.${format}`;
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^";\n]+)"?/);
      if (match?.[1]) filename = match[1];
    }

    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};

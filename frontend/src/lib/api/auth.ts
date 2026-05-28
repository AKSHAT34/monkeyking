import api from '@/lib/api';
import type { AuthResponse, User } from '@/lib/types';

export const authApi = {
  login: (email: string, password: string) =>
    api.post<AuthResponse>('/auth/login', { email, password }),

  register: (name: string, email: string, password: string) =>
    api.post<AuthResponse>('/auth/register', { name, email, password }),

  googleAuth: (credential: string) =>
    api.post<AuthResponse>('/auth/google', { credential }),

  getMe: () => api.get<User>('/auth/me'),
};

import axios, { InternalAxiosRequestConfig } from 'axios';
import { toastEvents, connectionStatus } from '@/lib/toast-events';

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retryCount?: number;
  _silent?: boolean;
}

const api = axios.create({ baseURL: '/mk2026/api' });

// JWT token injection
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('mk_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 interceptor — clear token and redirect to login
api.interceptors.response.use(
  (res) => {
    // Successful response means we're connected
    connectionStatus.setOffline(false);
    return res;
  },
  (err) => {
    if (err.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('mk_token');
      window.location.href = '/mk2026/login';
    }
    return Promise.reject(err);
  }
);

// Retry interceptor for GET requests (network errors only, exponential backoff)
api.interceptors.response.use(undefined, async (error) => {
  const config = error.config as RetryableConfig | undefined;
  if (!config || config.method !== 'get' || (config._retryCount ?? 0) >= 3) {
    return Promise.reject(error);
  }
  // Only retry on network errors (no response received)
  if (!error.response) {
    config._retryCount = (config._retryCount || 0) + 1;
    const delay = Math.pow(2, config._retryCount - 1) * 1000; // 1s, 2s, 4s
    await new Promise((r) => setTimeout(r, delay));
    return api(config);
  }
  return Promise.reject(error);
});

// Global error toast interceptor (fires for non-401 errors)
api.interceptors.response.use(undefined, (error) => {
  const config = error.config as RetryableConfig | undefined;

  // Skip toast if the caller opted out
  if (config?._silent) {
    return Promise.reject(error);
  }

  // 401 is already handled above — don't toast for it
  if (error.response?.status === 401) {
    return Promise.reject(error);
  }

  if (!error.response) {
    // Network error — all retries exhausted
    connectionStatus.setOffline(true);
    toastEvents.emit({
      type: 'error',
      message: 'Network error — check your connection and try again',
      duration: 6000,
    });
  } else {
    // Server error — parse detail from backend
    const raw = error.response.data?.detail ?? error.response.data?.message;
    let message: string;
    if (!raw) {
      message = `Request failed (${error.response.status})`;
    } else if (typeof raw === 'string') {
      message = raw;
    } else if (Array.isArray(raw)) {
      // FastAPI validation errors: [{msg, type, loc}]
      message = raw.map((e: { msg?: string }) => e.msg || JSON.stringify(e)).join('; ');
    } else if (typeof raw === 'object' && raw.msg) {
      message = raw.msg;
    } else {
      message = `Request failed (${error.response.status})`;
    }
    toastEvents.emit({ type: 'error', message });
  }

  return Promise.reject(error);
});

export default api;

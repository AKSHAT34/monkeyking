import api from '@/lib/api';

export interface LLMProviderInfo {
  has_key: boolean;
  masked_key: string | null;
}

export interface LLMSettings {
  active_provider: string;
  providers: Record<string, LLMProviderInfo>;
}

export interface LLMTestResult {
  provider: string;
  response: string;
  status: string;
}

export interface NotificationSettings {
  enabled: boolean;
}

export interface ScheduleSettings {
  frequency: string;
}

export interface LinkedInSettings {
  url: string;
  scraping_enabled: boolean;
}

export const settingsApi = {
  getLLMSettings: () => api.get<LLMSettings>('/settings/llm'),

  updateLLMSettings: (data: Record<string, string | null>) =>
    api.put('/settings/llm', data),

  testLLM: () => api.post<LLMTestResult>('/settings/llm/test'),

  // Notifications
  getNotificationSettings: () =>
    api.get<NotificationSettings>('/settings/notifications'),
  updateNotificationSettings: (data: { enabled: boolean }) =>
    api.post('/settings/notifications', data),

  // Schedule
  getScheduleSettings: () =>
    api.get<ScheduleSettings>('/settings/schedule'),
  updateScheduleSettings: (data: { frequency: string }) =>
    api.put('/settings/schedule', data),

  // LinkedIn
  getLinkedInSettings: () =>
    api.get<LinkedInSettings>('/settings/linkedin'),
  updateLinkedInSettings: (data: LinkedInSettings) =>
    api.put('/settings/linkedin', data),
};

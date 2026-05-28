'use client';

import { useCallback, useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { useToast } from '@/hooks/useToast';
import { Select } from '@/components/ui/Select';
import {
  settingsApi,
  type LLMSettings,
  type NotificationSettings,
  type ScheduleSettings,
  type LinkedInSettings,
} from '@/lib/api/settings';

const PROVIDERS = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    model: 'deepseek-chat',
    description: 'Fast & affordable. Great for most tasks.',
    color: 'blue' as const,
    placeholder: 'sk-...',
    docsUrl: 'https://platform.deepseek.com/api_keys',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    model: 'GPT-4o',
    description: 'Industry standard. Best overall quality.',
    color: 'green' as const,
    placeholder: 'sk-...',
    docsUrl: 'https://platform.openai.com/api-keys',
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    model: 'Claude Sonnet 4',
    description: 'Excellent reasoning and analysis.',
    color: 'orange' as const,
    placeholder: 'sk-ant-...',
    docsUrl: 'https://console.anthropic.com/settings/keys',
  },
  {
    id: 'google',
    name: 'Google',
    model: 'Gemini 1.5 Pro',
    description: 'Large context window. Good for long docs.',
    color: 'yellow' as const,
    placeholder: 'AIza...',
    docsUrl: 'https://aistudio.google.com/apikey',
  },
  {
    id: 'groq',
    name: 'Groq',
    model: 'Llama 3.3 70B',
    description: 'Ultra-fast inference. Free tier available.',
    color: 'purple' as const,
    placeholder: 'gsk_...',
    docsUrl: 'https://console.groq.com/keys',
  },
  {
    id: 'mistral',
    name: 'Mistral AI',
    model: 'Mistral Large',
    description: 'European AI. Strong multilingual support.',
    color: 'emerald' as const,
    placeholder: '...',
    docsUrl: 'https://console.mistral.ai/api-keys',
  },
];

export default function SettingsPage() {
  const { addToast } = useToast();
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [activeProvider, setActiveProvider] = useState('deepseek');

  // Notification, Schedule, LinkedIn state
  const [notifEnabled, setNotifEnabled] = useState(false);
  const [scheduleFreq, setScheduleFreq] = useState('off');
  const [linkedInUrl, setLinkedInUrl] = useState('');
  const [scrapingEnabled, setScrapingEnabled] = useState(false);
  const [savingLinkedIn, setSavingLinkedIn] = useState(false);

  const fetchSettings = useCallback(async () => {
    try {
      const { data } = await settingsApi.getLLMSettings();
      setSettings(data);
      setActiveProvider(data.active_provider || 'deepseek');
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  // Fetch notification, schedule, and LinkedIn settings on mount
  useEffect(() => {
    const fetchExtraSettings = async () => {
      try {
        const [notifRes, schedRes, liRes] = await Promise.allSettled([
          settingsApi.getNotificationSettings(),
          settingsApi.getScheduleSettings(),
          settingsApi.getLinkedInSettings(),
        ]);
        if (notifRes.status === 'fulfilled') setNotifEnabled(notifRes.value.data.enabled);
        if (schedRes.status === 'fulfilled') setScheduleFreq(schedRes.value.data.frequency);
        if (liRes.status === 'fulfilled') {
          setLinkedInUrl(liRes.value.data.url || '');
          setScrapingEnabled(liRes.value.data.scraping_enabled);
        }
      } catch {
        // silent — individual failures handled by allSettled
      }
    };
    fetchExtraSettings();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: Record<string, string | null> = { active_provider: activeProvider };
      // Only send keys that were actually typed (non-empty)
      for (const [provider, key] of Object.entries(keys)) {
        if (key !== undefined) {
          payload[`${provider}_key`] = key || null;
        }
      }
      await settingsApi.updateLLMSettings(payload);
      addToast({ type: 'success', message: 'LLM settings saved' });
      setKeys({}); // Clear typed keys
      await fetchSettings(); // Refresh masked keys
    } catch {
      addToast({ type: 'error', message: 'Failed to save settings' });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const { data } = await settingsApi.testLLM();
      setTestResult(`✅ ${data.provider}: ${data.response}`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Test failed';
      setTestResult(`❌ ${typeof msg === 'string' ? msg : 'Test failed'}`);
    } finally {
      setTesting(false);
    }
  };

  const handleNotificationToggle = async () => {
    const newVal = !notifEnabled;
    setNotifEnabled(newVal);
    try {
      await settingsApi.updateNotificationSettings({ enabled: newVal });
      addToast({ type: 'success', message: `Email notifications ${newVal ? 'enabled' : 'disabled'}` });
    } catch {
      setNotifEnabled(!newVal);
      addToast({ type: 'error', message: 'Failed to update notification settings' });
    }
  };

  const handleScheduleChange = async (freq: string) => {
    const prev = scheduleFreq;
    setScheduleFreq(freq);
    try {
      await settingsApi.updateScheduleSettings({ frequency: freq });
      addToast({ type: 'success', message: 'Schedule updated' });
    } catch {
      setScheduleFreq(prev);
      addToast({ type: 'error', message: 'Failed to update schedule' });
    }
  };

  const handleLinkedInSave = async () => {
    setSavingLinkedIn(true);
    try {
      await settingsApi.updateLinkedInSettings({ url: linkedInUrl, scraping_enabled: scrapingEnabled });
      addToast({ type: 'success', message: 'LinkedIn settings saved' });
    } catch {
      addToast({ type: 'error', message: 'Failed to save LinkedIn settings' });
    } finally {
      setSavingLinkedIn(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 space-y-6 max-w-3xl">
        <Skeleton variant="text" width="200px" height="32px" />
        <Skeleton variant="card" count={3} />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-h2 text-white">⚙️ Settings</h1>
          <p className="text-sm text-gray-400 mt-1">
            Configure your AI provider. Your API keys are stored securely and used only for your tasks.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleTest} loading={testing} size="sm">
            Test Connection
          </Button>
          <Button onClick={handleSave} loading={saving}>
            Save Settings
          </Button>
        </div>
      </div>

      {testResult && (
        <div className={`rounded-lg border px-4 py-3 text-sm ${
          testResult.startsWith('✅')
            ? 'border-green-700/50 bg-green-900/20 text-green-300'
            : 'border-red-700/50 bg-red-900/20 text-red-300'
        }`}>
          {testResult}
        </div>
      )}

      {/* Info banner */}
      <Card padding="md" className="border-blue-700/30 bg-blue-900/10">
        <p className="text-sm text-blue-300">
          💡 MonkeyKing uses AI for CV parsing, job matching, and CV generation.
          If you don&apos;t configure a key, the system default (DeepSeek) will be used.
          You only pay for what you use through your own API provider.
        </p>
      </Card>

      {/* Provider cards */}
      <div className="space-y-4">
        {PROVIDERS.map((provider) => {
          const info = settings?.providers?.[provider.id];
          const isActive = activeProvider === provider.id;
          const hasKey = info?.has_key || !!keys[provider.id];
          const typedKey = keys[provider.id];

          return (
            <Card
              key={provider.id}
              padding="md"
              className={isActive ? 'border-mk-orange/50 bg-mk-orange/5' : ''}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-semibold text-white">{provider.name}</h3>
                    <Badge color={provider.color}>{provider.model}</Badge>
                    {isActive && <Badge color="orange">Active</Badge>}
                    {hasKey && !isActive && <Badge color="gray">Key saved</Badge>}
                  </div>
                  <p className="text-xs text-gray-400 mb-3">{provider.description}</p>

                  <div className="flex items-center gap-2">
                    <div className="flex-1">
                      <Input
                        type="password"
                        placeholder={info?.masked_key || provider.placeholder}
                        value={typedKey ?? ''}
                        onChange={(e) => setKeys((prev) => ({ ...prev, [provider.id]: e.target.value }))}
                        autoComplete="off"
                      />
                    </div>
                    <a
                      href={provider.docsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-mk-orange hover:underline whitespace-nowrap"
                    >
                      Get key ↗
                    </a>
                  </div>
                </div>

                <Button
                  variant={isActive ? 'primary' : 'secondary'}
                  size="sm"
                  onClick={() => setActiveProvider(provider.id)}
                  disabled={!hasKey && provider.id !== 'deepseek'}
                >
                  {isActive ? 'Active' : 'Use this'}
                </Button>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Notification Settings */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-white">Notification Settings</h2>
        <Card padding="md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white">Email Notifications</p>
              <p className="text-xs text-gray-400">Get notified when new matching jobs are found</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={notifEnabled}
              onClick={handleNotificationToggle}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                notifEnabled ? 'bg-mk-orange' : 'bg-gray-600'
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  notifEnabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </Card>
      </div>

      {/* Schedule Settings */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-white">Schedule Settings</h2>
        <Card padding="md">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm text-white">Auto-Search Frequency</p>
              <p className="text-xs text-gray-400">How often to automatically search for new jobs</p>
            </div>
            <Select
              value={scheduleFreq}
              onChange={(e) => handleScheduleChange(e.target.value)}
              className="w-40"
            >
              <option value="off">Off</option>
              <option value="daily">Daily</option>
              <option value="every_3_days">Every 3 days</option>
              <option value="weekly">Weekly</option>
            </Select>
          </div>
        </Card>
      </div>

      {/* LinkedIn Settings */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-white">LinkedIn Settings</h2>
        <Card padding="md">
          <div className="space-y-4">
            <div>
              <p className="text-sm text-white mb-1">LinkedIn Profile URL</p>
              <Input
                type="url"
                placeholder="https://linkedin.com/in/your-profile"
                value={linkedInUrl}
                onChange={(e) => setLinkedInUrl(e.target.value)}
              />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-white">Profile Scraping</p>
                <p className="text-xs text-gray-400">Periodically scrape your LinkedIn profile for enhanced matching</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={scrapingEnabled}
                onClick={() => setScrapingEnabled(!scrapingEnabled)}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                  scrapingEnabled ? 'bg-mk-orange' : 'bg-gray-600'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                    scrapingEnabled ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
            <div className="flex justify-end">
              <Button onClick={handleLinkedInSave} loading={savingLinkedIn} size="sm">
                Save LinkedIn Settings
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

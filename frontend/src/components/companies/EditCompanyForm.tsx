'use client';

import { useState } from 'react';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/hooks/useToast';
import { companiesApi } from '@/lib/api/companies';
import api from '@/lib/api';
import type { Company } from '@/lib/types';

const CATEGORIES = [
  'Tech Giants', 'AI Companies', 'Cloud & SaaS', 'Indian Startups',
  'Fintech', 'E-commerce', 'Consulting', 'Banking', 'IT Services', 'Other',
];

interface EditCompanyFormProps {
  company: Company;
  onSuccess: () => void;
  onCancel: () => void;
}

export function EditCompanyForm({ company, onSuccess, onCancel }: EditCompanyFormProps) {
  const { addToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [form, setForm] = useState({
    name: company.name,
    careers_url: company.careers_url,
    category: company.category || 'Other',
    country: company.country || '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await companiesApi.updateCompany(company.id, form);
      addToast({ type: 'success', message: `${form.name} updated` });
      onSuccess();
    } catch {
      addToast({ type: 'error', message: 'Failed to update company' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <Input label="Company Name" value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      <Input label="Careers URL" value={form.careers_url} type="url"
        onChange={(e) => setForm({ ...form, careers_url: e.target.value })} required />
      <div className="flex items-center gap-2">
        <Button type="button" variant="ghost" size="sm" loading={testing} onClick={async () => {
          setTesting(true); setTestResult(null);
          try {
            const { data } = await api.post(`/companies/${company.id}/test-url`);
            if (data.ok) {
              setTestResult(`✅ ${data.status} — ${data.has_job_content ? 'Has job content' : '⚠️ No job keywords found'}${data.redirected ? ' (redirected to ' + data.final_url?.slice(0, 50) + ')' : ''}`);
            } else {
              setTestResult(`❌ ${data.error || 'Unreachable'}`);
            }
          } catch { setTestResult('❌ Test failed'); }
          finally { setTesting(false); }
        }}>🔗 Test URL</Button>
        {testResult && <span className="text-xs">{testResult}</span>}
      </div>
      <Select label="Category" value={form.category}
        onChange={(e) => setForm({ ...form, category: e.target.value })}>
        {CATEGORIES.map((cat) => <option key={cat} value={cat}>{cat}</option>)}
      </Select>
      <Input label="Country" value={form.country}
        onChange={(e) => setForm({ ...form, country: e.target.value })} />
      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="submit" loading={loading}>Save Changes</Button>
      </div>
    </form>
  );
}

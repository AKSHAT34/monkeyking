'use client';

import { useState } from 'react';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/hooks/useToast';
import { companiesApi } from '@/lib/api/companies';

const CATEGORIES = [
  'Tech Giants',
  'AI Companies',
  'Cloud & SaaS',
  'Indian Startups',
  'Fintech',
  'E-commerce',
  'Consulting',
  'Banking',
  'IT Services',
  'Other',
];

interface AddCompanyFormProps {
  onSuccess: () => void;
  onCancel: () => void;
}

export function AddCompanyForm({ onSuccess, onCancel }: AddCompanyFormProps) {
  const { addToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    name: '',
    careers_url: '',
    category: 'Other',
    country: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.careers_url.trim()) return;

    setLoading(true);
    try {
      await companiesApi.addCompany({
        name: form.name.trim(),
        careers_url: form.careers_url.trim(),
        category: form.category,
        country: form.country.trim() || undefined,
      });
      addToast({ type: 'success', message: `${form.name} added successfully` });
      onSuccess();
    } catch (err: unknown) {
      const error = err as { response?: { status?: number; data?: { detail?: string } } };
      if (error.response?.status === 400) {
        addToast({
          type: 'warning',
          message: error.response.data?.detail || 'Company already exists',
        });
      } else {
        addToast({ type: 'error', message: 'Failed to add company' });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <Input
        label="Company Name"
        placeholder="e.g. Google"
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
        required
      />
      <Input
        label="Careers URL"
        placeholder="https://careers.google.com"
        type="url"
        value={form.careers_url}
        onChange={(e) => setForm({ ...form, careers_url: e.target.value })}
        required
      />
      <Select
        label="Category"
        value={form.category}
        onChange={(e) => setForm({ ...form, category: e.target.value })}
      >
        {CATEGORIES.map((cat) => (
          <option key={cat} value={cat}>{cat}</option>
        ))}
      </Select>
      <Input
        label="Country"
        placeholder="e.g. India"
        value={form.country}
        onChange={(e) => setForm({ ...form, country: e.target.value })}
      />
      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={loading}>
          Add Company
        </Button>
      </div>
    </form>
  );
}

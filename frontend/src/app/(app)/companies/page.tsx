'use client';

import { useCallback, useEffect, useState, useMemo } from 'react';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Modal } from '@/components/ui/Modal';
import { CompanyCard } from '@/components/companies/CompanyCard';
import { CompanyFilters, type CompanyFilterValues } from '@/components/companies/CompanyFilters';
import { AddCompanyForm } from '@/components/companies/AddCompanyForm';
import { EditCompanyForm } from '@/components/companies/EditCompanyForm';
import { CompanyJobModal } from '@/components/companies/CompanyJobModal';
import { useDataCache } from '@/hooks/useDataCache';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/useToast';
import api from '@/lib/api';
import { companiesApi } from '@/lib/api/companies';
import type { Company } from '@/lib/types';

const PAGE_SIZE = 50;

export default function CompaniesPage() {
  const { companies, companiesLoading, refreshCompanies } = useDataCache();
  const { user } = useAuth();
  const { addToast } = useToast();
  const isAdmin = user?.is_admin ?? false;

  const [filters, setFilters] = useState<CompanyFilterValues>({ search: '', category: '', country: '' });
  const [page, setPage] = useState(1);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editCompany, setEditCompany] = useState<Company | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);

  const countries = useMemo(() => {
    const set = new Set(companies.map((c) => c.country).filter(Boolean));
    return Array.from(set).sort();
  }, [companies]);

  const filtered = useMemo(() => {
    let result = companies;
    if (filters.search) {
      const q = filters.search.toLowerCase();
      result = result.filter((c) => c.name.toLowerCase().includes(q) || c.careers_url.toLowerCase().includes(q));
    }
    if (filters.category) result = result.filter((c) => c.category === filters.category);
    if (filters.country) result = result.filter((c) => c.country === filters.country);
    return result;
  }, [companies, filters]);

  useEffect(() => { setPage(1); }, [filters]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleDelete = useCallback(async (company: Company) => {
    if (!confirm(`Delete "${company.name}"? This cannot be undone.`)) return;
    try {
      await companiesApi.deleteCompany(company.id);
      addToast({ type: 'success', message: `${company.name} deleted` });
      refreshCompanies();
    } catch {
      addToast({ type: 'error', message: 'Failed to delete company' });
    }
  }, [addToast, refreshCompanies]);

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-h2 text-white">🏢 Companies</h1>
          {!companiesLoading && (
            <p className="text-sm text-gray-400 mt-1">
              {filtered.length} of {companies.length} companies
              {isAdmin && <span className="text-mk-orange ml-2">· Admin</span>}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isAdmin && (
            <>
              <Button variant="ghost" size="sm" onClick={async () => {
                try {
                  const resp = await api.get('/companies/export/csv', { responseType: 'blob' });
                  const url = window.URL.createObjectURL(new Blob([resp.data]));
                  const a = document.createElement('a'); a.href = url;
                  a.download = 'monkeyking_companies.csv'; a.click();
                  window.URL.revokeObjectURL(url);
                } catch { addToast({ type: 'error', message: 'Export failed' }); }
              }}>📥 Export CSV</Button>
              <Button variant="ghost" size="sm" onClick={() => {
                const input = document.createElement('input');
                input.type = 'file'; input.accept = '.csv';
                input.onchange = async (e) => {
                  const file = (e.target as HTMLInputElement).files?.[0];
                  if (!file) return;
                  const formData = new FormData();
                  formData.append('file', file);
                  try {
                    const { data } = await api.post('/companies/import/csv', formData);
                    addToast({ type: 'success', message: `Updated ${data.updated}, added ${data.added} companies` });
                    refreshCompanies();
                  } catch { addToast({ type: 'error', message: 'Import failed' }); }
                };
                input.click();
              }}>📤 Import CSV</Button>
            </>
          )}
          {isAdmin && (
            <>
              <Button variant="ghost" size="sm" onClick={async () => {
                try {
                  const resp = await api.get('/companies/export/csv', { responseType: 'blob' });
                  const url = window.URL.createObjectURL(new Blob([resp.data]));
                  const a = document.createElement('a'); a.href = url;
                  a.download = 'monkeyking_companies.csv'; a.click();
                  window.URL.revokeObjectURL(url);
                } catch { addToast({ type: 'error', message: 'Export failed' }); }
              }}>📥 Export CSV</Button>
              <Button variant="ghost" size="sm" onClick={() => {
                const input = document.createElement('input');
                input.type = 'file'; input.accept = '.csv';
                input.onchange = async (e) => {
                  const file = (e.target as HTMLInputElement).files?.[0];
                  if (!file) return;
                  const formData = new FormData(); formData.append('file', file);
                  try {
                    const { data } = await api.post('/companies/import/csv', formData);
                    addToast({ type: 'success', message: `Updated ${data.updated}, added ${data.added} companies` });
                    refreshCompanies();
                  } catch { addToast({ type: 'error', message: 'Import failed' }); }
                };
                input.click();
              }}>📤 Import CSV</Button>
            </>
          )}
          <Button onClick={() => setShowAddModal(true)} size="sm">+ Add Company</Button>
        </div>
      </div>

      <CompanyFilters filters={filters} onChange={setFilters} countries={countries} />

      {companiesLoading && companies.length === 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} variant="card" />)}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={<span className="text-3xl">🔍</span>} title="No companies found"
          description="Try adjusting your search or filters." />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {paginated.map((company) => (
              <CompanyCard
                key={company.id}
                company={company}
                onClick={() => setSelectedCompany(company.name)}
                isAdmin={isAdmin}
                onEdit={setEditCompany}
                onDelete={handleDelete}
              />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <Button variant="secondary" size="sm" disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}>Previous</Button>
              <span className="text-sm text-gray-400">Page {page} of {totalPages}</span>
              <Button variant="secondary" size="sm" disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}>Next</Button>
            </div>
          )}
        </>
      )}

      <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)} title="Add Company">
        <AddCompanyForm onSuccess={() => { setShowAddModal(false); refreshCompanies(); }}
          onCancel={() => setShowAddModal(false)} />
      </Modal>

      {editCompany && (
        <Modal isOpen={true} onClose={() => setEditCompany(null)} title={`Edit ${editCompany.name}`}>
          <EditCompanyForm company={editCompany}
            onSuccess={() => { setEditCompany(null); refreshCompanies(); }}
            onCancel={() => setEditCompany(null)} />
        </Modal>
      )}

      <CompanyJobModal companyName={selectedCompany} onClose={() => setSelectedCompany(null)} />
    </div>
  );
}

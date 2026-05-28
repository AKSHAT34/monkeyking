// ─── Auth ───────────────────────────────────────────────
export interface User {
  id: number;
  email: string;
  name: string;
  avatar?: string;
  is_admin?: boolean;
}

export interface AuthResponse {
  token: string;
  user: User;
}

// ─── Profile ────────────────────────────────────────────
export interface UserProfile {
  phone?: string;
  location?: string;
  linkedin?: string;
  notice_period?: string;
  current_salary?: string;
  expected_salary?: string;
  preferred_locations?: string[];
  target_roles?: string[];
  work_authorization?: string;
  willing_to_relocate?: boolean;
  years_experience?: number;
  extracted_skills?: Record<string, string[]>;
  extracted_experience?: Experience[];
  extracted_education?: Education[];
  extracted_certifications?: string[];
  extracted_projects?: Project[];
  extracted_summary?: string;
  suggested_roles?: string[];
}

export interface Experience {
  company: string;
  title: string;
  duration?: string;
  description?: string;
}

export interface Education {
  institution: string;
  degree: string;
  year?: string;
}


export interface Project {
  name: string;
  description?: string;
  technologies?: string[];
}

// ─── CV ─────────────────────────────────────────────────
export interface UploadedCV {
  id: number;
  filename: string;
  is_primary: boolean;
  uploaded_at: string;
  file_type: string;
}

export interface CVUploadResponse {
  cv_id: number;
  parsed: Record<string, unknown>;
  filename: string;
  total_cvs: number;
}

// ─── Jobs & Matching ────────────────────────────────────
export interface Job {
  id: number;
  title: string;
  company: string;
  location: string;
  url: string;
  description?: string;
  match_score?: number;
  match_reason?: string;
  matched_skills?: string[];
  missing_skills?: string[];
}

export interface JobMatch {
  match_id: number;
  job_id: number;
  title: string;
  company: string;
  location: string;
  url: string;
  match_score: number;
  match_reason: string;
  matched_skills: string[];
  missing_skills: string[];
  relevance_summary?: string;
  is_saved: boolean;
  discovered_at?: string;
}

// ─── Tracking ───────────────────────────────────────────
export type ApplicationStatus =
  | 'not_started'
  | 'started'
  | 'in_process'
  | 'document_missing'
  | 'applied'
  | 'interview_scheduled'
  | 'rejected'
  | 'offer_received';

export interface TrackedJob {
  user_job_id: number;
  job_id: number;
  title: string;
  company: string;
  location: string;
  url: string;
  status: ApplicationStatus;
  tailored_cv_path?: string;
  tailored_cv_docx_path?: string;
  cover_letter_path?: string;
  cover_letter_docx_path?: string;
  notes?: string;
  created_at: string;
  updated_at?: string;
}

// ─── Search ─────────────────────────────────────────────
export interface SearchRunStatus {
  id: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped';
  companies_searched: number;
  jobs_found: number;
  jobs_matched: number;
  started_at?: string;
  completed_at?: string;
  progress: CompanyProgress[];
}

export interface CompanyProgress {
  company: string;
  status: 'pending' | 'scanning' | 'done' | 'skipped';
  jobs_found?: number;
  matched?: number;
  source?: string;
}

export interface SearchStartResponse {
  search_run_id: number;
  status: string;
  companies_count: number;
  excluded_employers: string[];
  already_searched: number;
}

// ─── Companies ──────────────────────────────────────────
export interface Company {
  id: number;
  name: string;
  careers_url: string;
  category: string;
  country: string;
}

// ─── Stats ──────────────────────────────────────────────
export interface Stats {
  matches: number;
  saved: number;
  applied: number;
  interviews: number;
  offers: number;
  total_companies: number;
}

// ─── Status Color Map ───────────────────────────────────
export const STATUS_COLORS: Record<ApplicationStatus, string> = {
  not_started: 'bg-gray-700 text-gray-300',
  started: 'bg-blue-900 text-blue-300',
  in_process: 'bg-yellow-900 text-yellow-300',
  document_missing: 'bg-orange-900 text-orange-300',
  applied: 'bg-green-900 text-green-300',
  interview_scheduled: 'bg-purple-900 text-purple-300',
  rejected: 'bg-red-900 text-red-300',
  offer_received: 'bg-emerald-900 text-emerald-300',
};

// ─── Match Score Color Logic ────────────────────────────
export function matchScoreColor(score: number): string {
  if (score >= 0.7) return 'bg-green-900 text-green-300';
  if (score >= 0.5) return 'bg-yellow-900 text-yellow-300';
  return 'bg-red-900 text-red-300';
}
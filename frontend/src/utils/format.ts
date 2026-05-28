/**
 * Format an ISO date string to a human-readable format.
 * Returns "N/A" for falsy inputs.
 */
export function formatDate(dateStr?: string | null): string {
  if (!dateStr) return 'N/A';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return 'N/A';
  }
}

/**
 * Format a 0–1 match score as a percentage string (e.g. "85%").
 * Returns "—" for null/undefined.
 */
export function formatScore(score?: number | null): string {
  if (score == null) return '—';
  return `${Math.round(score * 100)}%`;
}

/**
 * Format an application status slug into a human-readable label.
 * e.g. "not_started" → "Not Started", "interview_scheduled" → "Interview Scheduled"
 */
export function formatStatus(status: string): string {
  return status
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

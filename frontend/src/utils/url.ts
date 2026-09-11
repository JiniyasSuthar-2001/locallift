/**
 * URL Normalization and Security Utility for LocalLift.
 * 
 * Safely sanitizes and validates external URLs:
 * - Trims whitespace
 * - Rejects unsafe schemes (javascript:, data:, vbscript:)
 * - Adds https:// to bare domains (e.g. example.com -> https://example.com)
 * - Preserves valid http:// and https:// URLs
 * - Handles malformed inputs gracefully without throwing exceptions
 */

const UNSAFE_PROTOCOL_REGEX = /^(?:javascript|data|vbscript):/i;

export function normalizeExternalUrl(rawUrl: string | null | undefined): string | null {
  if (!rawUrl || typeof rawUrl !== 'string') {
    return null;
  }

  const trimmed = rawUrl.trim();
  if (!trimmed) {
    return null;
  }

  // Reject dangerous pseudo-protocols
  if (UNSAFE_PROTOCOL_REGEX.test(trimmed)) {
    return null;
  }

  // If URL already starts with http:// or https://, validate structure
  if (/^https?:\/\//i.test(trimmed)) {
    try {
      const parsed = new URL(trimmed);
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
        return parsed.href;
      }
      return null;
    } catch {
      return null;
    }
  }

  // For bare domains or paths, prepend https://
  try {
    const candidate = `https://${trimmed}`;
    const parsed = new URL(candidate);
    if (parsed.hostname && parsed.hostname.includes('.')) {
      return parsed.href;
    }
    return null;
  } catch {
    return null;
  }
}

export function formatDisplayUrl(rawUrl: string | null | undefined): string {
  if (!rawUrl || typeof rawUrl !== 'string') {
    return '—';
  }
  const trimmed = rawUrl.trim();
  // Strip protocol and trailing slash for cleaner UI presentation
  return trimmed.replace(/^https?:\/\//i, '').replace(/\/$/, '');
}

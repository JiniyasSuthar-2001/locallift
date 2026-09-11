import { describe, it, expect } from 'vitest';
import { normalizeExternalUrl, formatDisplayUrl } from '../utils/url';
import { parseApiError } from '../utils/error';

describe('Interaction & Quality Regression Test Suite', () => {
  describe('URL Normalization & Protocol Security', () => {
    it('normalizes bare domains to secure https:// URLs', () => {
      expect(normalizeExternalUrl('example.com')).toBe('https://example.com/');
      expect(normalizeExternalUrl('sub.domain.org')).toBe('https://sub.domain.org/');
      expect(normalizeExternalUrl('my-business.com.au/contact')).toBe('https://my-business.com.au/contact');
    });

    it('rejects XSS and unsafe protocol injection attempts', () => {
      expect(normalizeExternalUrl('javascript:alert(document.cookie)')).toBeNull();
      expect(normalizeExternalUrl('JAVASCRIPT:void(0)')).toBeNull();
      expect(normalizeExternalUrl('data:text/html,<script>evil()</script>')).toBeNull();
      expect(normalizeExternalUrl('vbscript:msgbox(1)')).toBeNull();
    });

    it('preserves existing valid http and https protocols without double prefixing', () => {
      expect(normalizeExternalUrl('https://example.com')).toBe('https://example.com/');
      expect(normalizeExternalUrl('http://example.com')).toBe('http://example.com/');
      expect(normalizeExternalUrl('https://example.com/services/seo?ref=1')).toBe('https://example.com/services/seo?ref=1');
    });

    it('formats clean, human-friendly display URLs', () => {
      expect(formatDisplayUrl('https://www.example.com/')).toBe('www.example.com');
      expect(formatDisplayUrl('http://subdomain.test.org/services/')).toBe('subdomain.test.org/services');
    });
  });

  describe('API Error Parsing & Safe Feedback', () => {
    it('handles 401 session expiration cleanly', () => {
      const parsed = parseApiError({ response: { status: 401, data: {} } });
      expect(parsed.statusCode).toBe(401);
      expect(parsed.message).toContain('session has expired');
    });

    it('handles 403 permission boundaries cleanly', () => {
      const parsed = parseApiError({ response: { status: 403, data: {} } });
      expect(parsed.statusCode).toBe(403);
      expect(parsed.message).toContain('permission');
    });

    it('handles Pydantic 422 validation error arrays', () => {
      const parsed = parseApiError({
        response: {
          status: 422,
          data: {
            detail: [
              { loc: ['body', 'domain'], msg: 'Domain must be a valid URL or hostname.' }
            ]
          }
        }
      });
      expect(parsed.statusCode).toBe(422);
      expect(parsed.message).toContain('domain: Domain must be a valid URL');
    });

    it('handles server network failure and timeouts', () => {
      const netErr = parseApiError({ message: 'Network Error' });
      expect(netErr.isNetworkError).toBe(true);

      const timeoutErr = parseApiError({ code: 'ECONNABORTED', message: 'timeout of 5000ms exceeded' });
      expect(timeoutErr.isTimeout).toBe(true);
    });

    it('preserves request IDs for troubleshooting', () => {
      const err = parseApiError({
        response: {
          status: 500,
          data: {
            message: 'Database query timed out',
            request_id: 'abc-123'
          }
        }
      });
      expect(err.requestId).toBe('abc-123');
      expect(err.message).toContain('abc-123');
    });
  });
});

import { describe, it, expect } from 'vitest';
import { normalizeExternalUrl, formatDisplayUrl } from './url';

describe('URL Normalization & Security Utility', () => {
  describe('normalizeExternalUrl', () => {
    it('returns null for empty, null, or undefined inputs', () => {
      expect(normalizeExternalUrl(null)).toBeNull();
      expect(normalizeExternalUrl(undefined)).toBeNull();
      expect(normalizeExternalUrl('')).toBeNull();
      expect(normalizeExternalUrl('   ')).toBeNull();
    });

    it('rejects unsafe javascript:, data:, and vbscript: protocols', () => {
      expect(normalizeExternalUrl('javascript:alert(1)')).toBeNull();
      expect(normalizeExternalUrl('javascript:void(0)')).toBeNull();
      expect(normalizeExternalUrl('data:text/html,<script>alert(1)</script>')).toBeNull();
      expect(normalizeExternalUrl('vbscript:msgbox(1)')).toBeNull();
    });

    it('preserves valid https:// and http:// URLs', () => {
      expect(normalizeExternalUrl('https://example.com')).toBe('https://example.com/');
      expect(normalizeExternalUrl('http://subdomain.test.org/path?q=1')).toBe('http://subdomain.test.org/path?q=1');
    });

    it('adds https:// to bare domains without duplicating protocol', () => {
      expect(normalizeExternalUrl('acmeplumbing.com')).toBe('https://acmeplumbing.com/');
      expect(normalizeExternalUrl('www.google.com/maps')).toBe('https://www.google.com/maps');
    });

    it('handles malformed inputs safely without throwing', () => {
      expect(normalizeExternalUrl('http://')).toBeNull();
      expect(normalizeExternalUrl('not a url')).toBeNull();
      expect(normalizeExternalUrl(':::')).toBeNull();
    });
  });

  describe('formatDisplayUrl', () => {
    it('formats clean domain without protocol', () => {
      expect(formatDisplayUrl('https://example.com/')).toBe('example.com');
      expect(formatDisplayUrl('http://mybusiness.com')).toBe('mybusiness.com');
    });

    it('returns fallback dash for empty values', () => {
      expect(formatDisplayUrl(null)).toBe('—');
      expect(formatDisplayUrl('')).toBe('—');
    });
  });
});

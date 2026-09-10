import { describe, it, expect } from 'vitest';
import { isMetricAvailable, formatScore, formatScoreOutOf100, formatPercentage } from './metrics';

describe('Data Integrity Metrics Utility', () => {
  describe('isMetricAvailable', () => {
    it('returns false for null', () => {
      expect(isMetricAvailable(null)).toBe(false);
    });

    it('returns false for undefined', () => {
      expect(isMetricAvailable(undefined)).toBe(false);
    });

    it('returns false for NaN', () => {
      expect(isMetricAvailable(NaN)).toBe(false);
    });

    it('returns true for 0 (strict zero preservation)', () => {
      expect(isMetricAvailable(0)).toBe(true);
    });

    it('returns true for valid positive scores', () => {
      expect(isMetricAvailable(82)).toBe(true);
      expect(isMetricAvailable(100)).toBe(true);
    });
  });

  describe('formatScore', () => {
    it('returns placeholder when metric is null', () => {
      expect(formatScore(null, 'Awaiting audit')).toBe('Awaiting audit');
    });

    it('returns placeholder when metric is undefined', () => {
      expect(formatScore(undefined, 'Not yet checked')).toBe('Not yet checked');
    });

    it('preserves genuine zero (0)', () => {
      expect(formatScore(0)).toBe('0');
      expect(formatScore(0, 'Not yet audited', '%')).toBe('0%');
    });

    it('formats valid positive numbers accurately', () => {
      expect(formatScore(82)).toBe('82');
      expect(formatScore(95, 'Not yet audited', '/100')).toBe('95/100');
    });
  });

  describe('formatScoreOutOf100', () => {
    it('returns placeholder when metric is uncalculated', () => {
      expect(formatScoreOutOf100(null)).toBe('Not yet calculated');
      expect(formatScoreOutOf100(undefined, 'Awaiting crawl')).toBe('Awaiting crawl');
    });

    it('formats genuine 0 as 0 / 100 without fallback replacement', () => {
      expect(formatScoreOutOf100(0)).toBe('0 / 100');
    });

    it('formats 100 as 100 / 100', () => {
      expect(formatScoreOutOf100(100)).toBe('100 / 100');
    });

    it('formats real score 85 as 85 / 100', () => {
      expect(formatScoreOutOf100(85)).toBe('85 / 100');
    });
  });

  describe('formatPercentage', () => {
    it('returns placeholder when metric is missing', () => {
      expect(formatPercentage(null)).toBe('Not yet calculated');
      expect(formatPercentage(undefined, 'Not yet checked')).toBe('Not yet checked');
    });

    it('preserves genuine 0% without replacing with fallback', () => {
      expect(formatPercentage(0)).toBe('0%');
    });

    it('formats 100% and positive numbers', () => {
      expect(formatPercentage(88)).toBe('88%');
      expect(formatPercentage(100)).toBe('100%');
    });
  });
});

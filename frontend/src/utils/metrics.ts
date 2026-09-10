/**
 * Metrics Formatting & Integrity Utility for LocalLift.
 * 
 * Strict Data-Integrity Rule:
 * 1. Real value (e.g. 82) -> Displays real value (82)
 * 2. Legitimate zero (0)   -> Displays genuine zero (0)
 * 3. Missing / uncalculated (null, undefined) -> Displays honest contextual placeholder (e.g. "Not yet audited")
 * 4. NEVER silently substitute missing data with arbitrary numbers (80, 75, 70, 85, 88, 100).
 */

export function isMetricAvailable(value: number | null | undefined): value is number {
  return value !== null && value !== undefined && !Number.isNaN(value);
}

export function formatScore(
  value: number | null | undefined,
  placeholder: string = 'Not yet audited',
  suffix: string = ''
): string {
  if (!isMetricAvailable(value)) {
    return placeholder;
  }
  return `${value}${suffix}`;
}

export function formatScoreOutOf100(
  value: number | null | undefined,
  placeholder: string = 'Not yet calculated'
): string {
  if (!isMetricAvailable(value)) {
    return placeholder;
  }
  return `${value} / 100`;
}

export function formatPercentage(
  value: number | null | undefined,
  placeholder: string = 'Not yet calculated'
): string {
  if (!isMetricAvailable(value)) {
    return placeholder;
  }
  return `${value}%`;
}

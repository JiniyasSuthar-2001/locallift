import React from 'react';

export interface HealthScoreRingProps {
  score?: number | null;
  size?: number;
  strokeWidth?: number;
  label?: string;
  sublabel?: string;
}

export const HealthScoreRing: React.FC<HealthScoreRingProps> = ({
  score,
  size = 140,
  strokeWidth = 10,
  label = "SEO HEALTH",
  sublabel = "Overall Score"
}) => {
  const isAvailable = score !== null && score !== undefined && !Number.isNaN(score);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const safeScore = isAvailable ? Math.min(100, Math.max(0, score)) : 0;
  const strokeDashoffset = isAvailable ? circumference - (safeScore / 100) * circumference : circumference;

  let strokeColor = '#8DAAA0'; // Botanical slate fallback
  let gradientId = 'score-neutral-gradient';

  if (isAvailable) {
    if (safeScore >= 80) {
      strokeColor = '#236B4F'; // Forest Green
      gradientId = 'score-forest-gradient';
    } else if (safeScore >= 65) {
      strokeColor = '#D97706'; // Warm Amber
      gradientId = 'score-amber-gradient';
    } else {
      strokeColor = '#DC2626'; // Red
      gradientId = 'score-red-gradient';
    }
  }

  return (
    <div className="flex flex-col items-center justify-center p-2">
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          <defs>
            <linearGradient id="score-forest-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#236B4F" />
              <stop offset="50%" stopColor="#2FA878" />
              <stop offset="100%" stopColor="#62C9A0" />
            </linearGradient>
            <linearGradient id="score-amber-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#B45309" />
              <stop offset="100%" stopColor="#F59E0B" />
            </linearGradient>
            <linearGradient id="score-red-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#991B1B" />
              <stop offset="100%" stopColor="#EF4444" />
            </linearGradient>
            <linearGradient id="score-neutral-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#B8DFC9" />
              <stop offset="100%" stopColor="#DCE8DC" />
            </linearGradient>
          </defs>

          {/* Background circle track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="#EAF2EA"
            strokeWidth={strokeWidth}
            fill="transparent"
          />

          {/* Animated score circle */}
          {isAvailable && (
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              stroke={`url(#${gradientId})`}
              strokeWidth={strokeWidth}
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              fill="transparent"
              style={{
                transition: 'stroke-dashoffset 1s ease-in-out',
              }}
            />
          )}
        </svg>

        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-2">
          {isAvailable ? (
            <>
              <span className="text-3xl font-extrabold tracking-tight text-[#142820]">
                {Math.round(safeScore)}
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#587568] mt-0.5">
                / 100
              </span>
            </>
          ) : (
            <span className="text-xs font-semibold text-[#587568] uppercase tracking-wider">
              Not Audited
            </span>
          )}
        </div>
      </div>

      {(label || sublabel) && (
        <div className="mt-3 text-center">
          {label && <p className="text-xs font-bold text-[#142820] uppercase tracking-wider">{label}</p>}
          {sublabel && <p className="text-[11px] text-[#587568] mt-0.5">{sublabel}</p>}
        </div>
      )}
    </div>
  );
};

import React from 'react';

interface HealthScoreRingProps {
  score: number;
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
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const safeScore = Math.min(100, Math.max(0, score || 0));
  const strokeDashoffset = circumference - (safeScore / 100) * circumference;

  let strokeColor = '#10b981'; // Emerald >= 80
  let glowColor = 'rgba(16, 185, 129, 0.4)';
  if (safeScore < 60) {
    strokeColor = '#f43f5e'; // Rose
    glowColor = 'rgba(244, 63, 94, 0.4)';
  } else if (safeScore < 75) {
    strokeColor = '#f97316'; // Orange
    glowColor = 'rgba(249, 115, 22, 0.4)';
  } else if (safeScore < 80) {
    strokeColor = '#eab308'; // Yellow
    glowColor = 'rgba(234, 179, 8, 0.4)';
  }

  return (
    <div className="flex flex-col items-center justify-center p-4">
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="#1F293D"
            strokeWidth={strokeWidth}
            fill="transparent"
          />
          {/* Animated score circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
            style={{
              transition: 'stroke-dashoffset 1s ease-in-out, stroke 0.5s ease',
              filter: `drop-shadow(0 0 8px ${glowColor})`
            }}
          />
        </svg>
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className="text-3xl font-extrabold tracking-tight text-white font-sans">
            {safeScore}
          </span>
          <span className="text-[10px] font-semibold text-gray-400 tracking-wider uppercase">
            / 100
          </span>
        </div>
      </div>
      <div className="mt-3 text-center">
        <div className="text-xs font-bold tracking-widest text-emerald-400 uppercase">{label}</div>
        <div className="text-[11px] text-gray-400 mt-0.5">{sublabel}</div>
      </div>
    </div>
  );
};

import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';

export interface StatCardProps {
  title: string;
  value: string | number | null | undefined;
  subtitle?: string;
  trend?: {
    value: string;
    isPositive: boolean;
  };
  icon: LucideIcon;
  iconColor?: string;
  badge?: string;
  accentGradient?: boolean;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  trend,
  icon: Icon,
  iconColor = 'text-[#236B4F] bg-[#F1F7F1] border-[#B8DFC9]',
  badge,
  accentGradient = false
}) => {
  const displayValue = value !== null && value !== undefined && value !== '' ? value : '—';

  return (
    <div 
      className={`card-nature p-5 flex flex-col justify-between ${
        accentGradient ? 'relative overflow-hidden before:absolute before:top-0 before:left-0 before:right-0 before:h-1 before:bg-gradient-to-r before:from-[#236B4F] before:via-[#2FA878] before:to-[#62C9A0]' : ''
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-[#587568]">{title}</span>
        <div className={`p-2 rounded-lg border flex items-center justify-center ${iconColor}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <div className="mt-4">
        <div className="flex items-baseline space-x-2">
          <span className="text-2xl font-bold tracking-tight text-[#142820]">{displayValue}</span>
          {badge && (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#EAF2EA] text-[#236B4F] border border-[#B8DFC9]">
              {badge}
            </span>
          )}
        </div>

        {(subtitle || trend) && (
          <div className="mt-2.5 flex items-center justify-between text-xs text-[#587568]">
            {subtitle && <span className="truncate pr-2">{subtitle}</span>}
            {trend && (
              <span className={`inline-flex items-center font-bold px-1.5 py-0.5 rounded ${
                trend.isPositive 
                  ? 'text-[#065F46] bg-[#ECFDF5] border border-[#A7F3D0]' 
                  : 'text-[#991B1B] bg-[#FEF2F2] border border-[#FECACA]'
              }`}>
                {trend.isPositive ? <TrendingUp className="w-3 h-3 mr-1 inline" /> : <TrendingDown className="w-3 h-3 mr-1 inline" />}
                {trend.value}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: {
    value: string;
    isPositive: boolean;
  };
  icon: LucideIcon;
  iconColor?: string;
  badge?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  trend,
  icon: Icon,
  iconColor = 'text-emerald-400 bg-emerald-950/40 border-emerald-800/40',
  badge
}) => {
  return (
    <div className="glass-panel p-5 rounded-xl flex flex-col justify-between hover:border-emerald-500/30 transition-all duration-200">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">{title}</span>
        <div className={`p-2 rounded-lg border ${iconColor}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>

      <div className="mt-4">
        <div className="flex items-baseline space-x-2">
          <span className="text-2xl font-bold tracking-tight text-white">{value}</span>
          {badge && (
            <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-gray-800 text-gray-300 border border-gray-700">
              {badge}
            </span>
          )}
        </div>

        {(subtitle || trend) && (
          <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
            {subtitle && <span>{subtitle}</span>}
            {trend && (
              <span className={`font-semibold ${trend.isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                {trend.isPositive ? '↑' : '↓'} {trend.value}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

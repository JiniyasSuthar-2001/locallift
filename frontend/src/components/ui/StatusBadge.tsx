import React from 'react';

interface StatusBadgeProps {
  status: string;
  variant?: 'green' | 'yellow' | 'orange' | 'red' | 'blue' | 'purple' | 'gray';
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, variant, size = 'sm' }) => {
  const getStyle = () => {
    if (variant) {
      switch (variant) {
        case 'green':
          return 'bg-emerald-50 text-emerald-800 border-emerald-200';
        case 'yellow':
          return 'bg-amber-50 text-amber-900 border-amber-200';
        case 'orange':
          return 'bg-orange-50 text-orange-900 border-orange-200';
        case 'red':
          return 'bg-rose-50 text-rose-800 border-rose-200';
        case 'blue':
          return 'bg-blue-50 text-blue-800 border-blue-200';
        case 'purple':
          return 'bg-purple-50 text-purple-800 border-purple-200';
        default:
          return 'bg-slate-100 text-slate-800 border-slate-200';
      }
    }

    const s = status.toLowerCase();
    if (s.includes('critical') || s.includes('error') || s.includes('fail') || s.includes('high') || s.includes('negative')) {
      return 'bg-rose-50 text-rose-800 border-rose-200';
    }
    if (s.includes('warn') || s.includes('moderate') || s.includes('medium') || s.includes('in_progress')) {
      return 'bg-amber-50 text-amber-900 border-amber-200';
    }
    if (s.includes('pass') || s.includes('good') || s.includes('healthy') || s.includes('complete') || s.includes('positive') || s.includes('low')) {
      return 'bg-emerald-50 text-emerald-800 border-emerald-200';
    }
    if (s.includes('likely') || s.includes('info') || s.includes('draft')) {
      return 'bg-blue-50 text-blue-800 border-blue-200';
    }
    if (s.includes('confirmed') || s.includes('important') || s.includes('verified')) {
      return 'bg-purple-50 text-purple-800 border-purple-200';
    }
    return 'bg-slate-100 text-slate-800 border-slate-200';
  };

  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-3 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center font-bold uppercase tracking-wider rounded-md border ${getStyle()} ${sizeClass}`}
    >
      {status.replace(/_/g, ' ')}
    </span>
  );
};

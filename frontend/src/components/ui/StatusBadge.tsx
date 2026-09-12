import React from 'react';
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Clock, 
  RefreshCw, 
  HelpCircle, 
  Slash,
  ShieldCheck
} from 'lucide-react';

export interface StatusBadgeProps {
  status: string;
  variant?: 'green' | 'teal' | 'yellow' | 'orange' | 'red' | 'blue' | 'gray';
  size?: 'sm' | 'md';
  showIcon?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ 
  status, 
  variant, 
  size = 'sm',
  showIcon = true 
}) => {
  const s = (status || '').toLowerCase().trim();

  // Automatic contrast-safe styling based on status keyword or variant
  const getBadgeConfig = (): { classes: string; icon: React.ReactNode } => {
    if (variant) {
      switch (variant) {
        case 'green':
        case 'teal':
          return {
            classes: 'bg-emerald-50 text-emerald-900 border-emerald-300',
            icon: <CheckCircle2 className="w-3 h-3 text-emerald-700 mr-1" />
          };
        case 'yellow':
        case 'orange':
          return {
            classes: 'bg-amber-50 text-amber-950 border-amber-300',
            icon: <AlertTriangle className="w-3 h-3 text-amber-700 mr-1" />
          };
        case 'red':
          return {
            classes: 'bg-rose-50 text-rose-950 border-rose-300',
            icon: <XCircle className="w-3 h-3 text-rose-700 mr-1" />
          };
        case 'blue':
          return {
            classes: 'bg-blue-50 text-blue-950 border-blue-300',
            icon: <HelpCircle className="w-3 h-3 text-blue-700 mr-1" />
          };
        default:
          return {
            classes: 'bg-stone-100 text-stone-800 border-stone-300',
            icon: <Slash className="w-3 h-3 text-stone-600 mr-1" />
          };
      }
    }

    if (s === 'connected' || s === 'synced' || s === 'pass' || s === 'passed' || s === 'healthy' || s === 'complete' || s === 'active') {
      return {
        classes: 'bg-emerald-50 text-emerald-900 border-emerald-300 font-semibold',
        icon: <ShieldCheck className="w-3 h-3 text-emerald-700 mr-1" />
      };
    }
    if (s === 'syncing' || s === 'in_progress' || s === 'loading') {
      return {
        classes: 'bg-teal-50 text-teal-950 border-teal-300 font-semibold',
        icon: <RefreshCw className="w-3 h-3 text-teal-700 animate-spin mr-1" />
      };
    }
    if (s.includes('warn') || s.includes('moderate') || s.includes('pending')) {
      return {
        classes: 'bg-amber-50 text-amber-950 border-amber-300 font-semibold',
        icon: <Clock className="w-3 h-3 text-amber-700 mr-1" />
      };
    }
    if (s.includes('error') || s.includes('fail') || s.includes('critical') || s.includes('disconnected') || s.includes('blocked')) {
      return {
        classes: 'bg-rose-50 text-rose-950 border-rose-300 font-semibold',
        icon: <XCircle className="w-3 h-3 text-rose-700 mr-1" />
      };
    }
    if (s.includes('not configured') || s.includes('not_configured') || s.includes('not measured') || s.includes('no data') || s.includes('unmeasured')) {
      return {
        classes: 'bg-stone-100 text-stone-800 border-stone-300 font-medium',
        icon: <Slash className="w-3 h-3 text-stone-600 mr-1" />
      };
    }

    return {
      classes: 'bg-stone-100 text-stone-800 border-stone-300 font-medium',
      icon: <HelpCircle className="w-3 h-3 text-stone-600 mr-1" />
    };
  };

  const config = getBadgeConfig();
  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center rounded-md border tracking-wide select-none ${config.classes} ${sizeClass}`}
    >
      {showIcon && config.icon}
      <span>{status ? status.replace(/_/g, ' ') : 'N/A'}</span>
    </span>
  );
};

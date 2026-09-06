import React from 'react';
import { LucideIcon, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  actionText?: string;
  actionLink?: string;
  onAction?: () => void;
  badge?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon,
  title,
  description,
  actionText,
  actionLink,
  onAction,
  badge
}) => {
  return (
    <div className="card-vibrant p-10 text-center flex flex-col items-center justify-center space-y-4 max-w-lg mx-auto my-6">
      <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-purple-100 to-pink-100 border border-purple-200 flex items-center justify-center text-purple-600 shadow-sm">
        <Icon className="w-7 h-7 stroke-[1.8]" />
      </div>

      {badge && (
        <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-purple-100 text-purple-800 border border-purple-200">
          {badge}
        </span>
      )}

      <div className="space-y-1">
        <h3 className="text-base font-extrabold text-slate-900">{title}</h3>
        <p className="text-xs text-slate-500 leading-relaxed max-w-sm">{description}</p>
      </div>

      {actionText && (
        <div className="pt-2">
          {actionLink ? (
            <Link
              to={actionLink}
              className="inline-flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{actionText}</span>
            </Link>
          ) : (
            <button
              onClick={onAction}
              className="inline-flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{actionText}</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
};

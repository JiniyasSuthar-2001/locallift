import React, { useState } from 'react';
import { AuditCategoryKey, AUDIT_CATEGORY_LABELS, LocalAuditFinding } from '../../types';
import { FindingCard } from './FindingCard';
import {
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle
} from 'lucide-react';

interface CategoryScoreCardProps {
  categoryKey: AuditCategoryKey;
  score: number | null | any;
  findings: LocalAuditFinding[];
  defaultExpanded?: boolean;
}

export const CategoryScoreCard: React.FC<CategoryScoreCardProps> = ({
  categoryKey,
  score,
  findings,
  defaultExpanded = false,
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const label = AUDIT_CATEGORY_LABELS[categoryKey] || categoryKey.replace(/_/g, ' ');

  const actualScore: number | null = typeof score === 'object' && score !== null ? (score.score ?? null) : (typeof score === 'number' ? score : null);

  const passCount = findings.filter(f => f.status === 'PASS').length;
  const failCount = findings.filter(f => f.status === 'FAIL').length;
  const partialCount = findings.filter(f => f.status === 'PARTIAL').length;
  const notVerifiedCount = findings.filter(f => f.status === 'NOT_VERIFIED').length;

  const getScoreColor = (s: number | null) => {
    if (s === null) return 'text-slate-500';
    if (s >= 80) return 'text-emerald-700';
    if (s >= 60) return 'text-amber-700';
    if (s >= 40) return 'text-orange-700';
    return 'text-rose-700';
  };

  const getScoreBg = (s: number | null) => {
    if (s === null) return 'bg-slate-100';
    if (s >= 80) return 'bg-emerald-50';
    if (s >= 60) return 'bg-amber-50';
    if (s >= 40) return 'bg-orange-50';
    return 'bg-rose-50';
  };

  const getScoreBorder = (s: number | null) => {
    if (s === null) return 'border-slate-200';
    if (s >= 80) return 'border-emerald-200';
    if (s >= 60) return 'border-amber-200';
    if (s >= 40) return 'border-orange-200';
    return 'border-rose-200';
  };

  return (
    <div className={`rounded-2xl border ${getScoreBorder(actualScore)} bg-white overflow-hidden transition-all`}>
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={`w-full px-5 py-3.5 flex items-center justify-between hover:bg-slate-50/50 transition-colors`}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-11 h-11 rounded-xl ${getScoreBg(actualScore)} border ${getScoreBorder(actualScore)} flex items-center justify-center`}>
            <span className={`text-sm font-black ${getScoreColor(actualScore)}`}>
              {actualScore !== null ? actualScore : '—'}
            </span>
          </div>
          <div className="text-left min-w-0">
            <div className="text-sm font-bold text-slate-900 truncate">{label}</div>
            <div className="flex items-center gap-2 mt-0.5">
              {passCount > 0 && (
                <span className="flex items-center gap-0.5 text-[10px] font-semibold text-emerald-700">
                  <CheckCircle2 className="w-3 h-3" /> {passCount}
                </span>
              )}
              {failCount > 0 && (
                <span className="flex items-center gap-0.5 text-[10px] font-semibold text-rose-700">
                  <XCircle className="w-3 h-3" /> {failCount}
                </span>
              )}
              {partialCount > 0 && (
                <span className="flex items-center gap-0.5 text-[10px] font-semibold text-amber-700">
                  <AlertTriangle className="w-3 h-3" /> {partialCount}
                </span>
              )}
              {notVerifiedCount > 0 && (
                <span className="flex items-center gap-0.5 text-[10px] font-semibold text-slate-500">
                  <HelpCircle className="w-3 h-3" /> {notVerifiedCount}
                </span>
              )}
              {findings.length === 0 && (
                <span className="text-[10px] text-slate-400 font-medium">No checks</span>
              )}
            </div>
          </div>
        </div>
        {findings.length > 0 && (
          expanded
            ? <ChevronUp className="w-4 h-4 text-slate-400 shrink-0" />
            : <ChevronDown className="w-4 h-4 text-slate-400 shrink-0" />
        )}
      </button>

      {/* Expanded findings list */}
      {expanded && findings.length > 0 && (
        <div className="px-5 pb-4 space-y-3 border-t border-slate-100 pt-3">
          {findings.map((f) => (
            <FindingCard key={f.id} finding={f} />
          ))}
        </div>
      )}
    </div>
  );
};

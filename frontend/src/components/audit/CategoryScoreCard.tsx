import React, { useState } from 'react';
import { AuditCategoryKey, AUDIT_CATEGORY_LABELS, LocalAuditFinding } from '../../types';
import { FindingCard } from './FindingCard';
import {
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Layers,
  Sparkles,
  RotateCw,
  Globe
} from 'lucide-react';

interface CategoryScoreCardProps {
  categoryKey: AuditCategoryKey;
  score: number | null | any;
  findings: LocalAuditFinding[];
  defaultExpanded?: boolean;
  onRunTechnicalScan?: () => void;
  isScanningTechnical?: boolean;
}

export const CategoryScoreCard: React.FC<CategoryScoreCardProps> = ({
  categoryKey,
  score,
  findings,
  defaultExpanded = false,
  onRunTechnicalScan,
  isScanningTechnical = false
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const label = AUDIT_CATEGORY_LABELS[categoryKey] || categoryKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

  const actualScore: number | null = typeof score === 'object' && score !== null ? (score.score ?? null) : (typeof score === 'number' ? score : null);

  const passCount = findings.filter(f => f.status === 'PASS').length;
  const failCount = findings.filter(f => f.status === 'FAIL').length;
  const partialCount = findings.filter(f => f.status === 'PARTIAL').length;
  const notVerifiedCount = findings.filter(f => f.status === 'NOT_VERIFIED' || f.status === 'ERROR').length;

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
    <div className={`rounded-xl border ${getScoreBorder(actualScore)} bg-white shadow-2xs overflow-hidden transition-all`}>
      {/* ─── Header Bar ─── */}
      <div className="w-full px-4 py-3 sm:px-5 sm:py-3.5 flex items-center justify-between hover:bg-[#F9FAF9] transition-colors">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-3.5 min-w-0 text-left flex-1"
        >
          <div className={`w-10 h-10 rounded-xl ${getScoreBg(actualScore)} border ${getScoreBorder(actualScore)} flex items-center justify-center shrink-0`}>
            <span className={`text-sm font-black ${getScoreColor(actualScore)}`}>
              {actualScore !== null ? actualScore : '—'}
            </span>
          </div>

          <div className="min-w-0">
            <div className="text-xs sm:text-sm font-extrabold text-[#142820] truncate">
              {label}
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-0.5">
              {passCount > 0 && (
                <span className="flex items-center gap-1 text-[11px] font-bold text-emerald-700">
                  <CheckCircle2 className="w-3 h-3" /> {passCount} Pass
                </span>
              )}
              {failCount > 0 && (
                <span className="flex items-center gap-1 text-[11px] font-bold text-rose-700">
                  <XCircle className="w-3 h-3" /> {failCount} Fail
                </span>
              )}
              {partialCount > 0 && (
                <span className="flex items-center gap-1 text-[11px] font-bold text-amber-700">
                  <AlertTriangle className="w-3 h-3" /> {partialCount} Partial
                </span>
              )}
              {notVerifiedCount > 0 && (
                <span className="flex items-center gap-1 text-[11px] font-bold text-slate-500">
                  <HelpCircle className="w-3 h-3" /> {notVerifiedCount} Data Pending
                </span>
              )}
              {findings.length === 0 && (
                <span className="text-[11px] text-slate-400 font-medium">No checks</span>
              )}
            </div>
          </div>
        </button>

        <div className="flex items-center gap-3 shrink-0 ml-3">
          {categoryKey === 'technical_seo' && onRunTechnicalScan && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onRunTechnicalScan();
              }}
              disabled={isScanningTechnical}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 transition-colors disabled:opacity-50"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isScanningTechnical ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Run Technical Scan</span>
              <span className="sm:hidden">Scan</span>
            </button>
          )}

          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1.5 text-slate-500 hover:text-slate-800"
          >
            <span className="text-[11px] font-semibold text-[#587568] hidden sm:inline">
              {findings.length} {findings.length === 1 ? 'check' : 'checks'}
            </span>
            {findings.length > 0 && (
              expanded
                ? <ChevronUp className="w-4 h-4 text-[#587568]" />
                : <ChevronDown className="w-4 h-4 text-[#587568]" />
            )}
          </button>
        </div>
      </div>

      {/* ─── Expanded Findings List ─── */}
      {expanded && findings.length > 0 && (
        <div className="px-4 pb-4 pt-2 border-t border-[#EBF2EB] bg-[#F7FAF7] space-y-2.5">
          {findings.map((f) => (
            <FindingCard key={f.id} finding={f} />
          ))}
        </div>
      )}
    </div>
  );
};

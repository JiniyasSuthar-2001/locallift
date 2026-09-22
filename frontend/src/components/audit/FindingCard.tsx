import React from 'react';
import { LocalAuditFinding } from '../../types';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  MinusCircle,
  AlertOctagon,
  ExternalLink,
  ShieldCheck,
  Eye,
  User,
  Scan,
  Brain,
  ShieldOff
} from 'lucide-react';

interface FindingCardProps {
  finding: LocalAuditFinding;
  compact?: boolean;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; border: string; icon: React.ComponentType<{ className?: string }> }> = {
  PASS: { label: 'Pass', color: 'text-emerald-800', bg: 'bg-emerald-50', border: 'border-emerald-200', icon: CheckCircle2 },
  PARTIAL: { label: 'Partial', color: 'text-amber-800', bg: 'bg-amber-50', border: 'border-amber-200', icon: AlertTriangle },
  FAIL: { label: 'Fail', color: 'text-rose-800', bg: 'bg-rose-50', border: 'border-rose-200', icon: XCircle },
  NOT_VERIFIED: { label: 'Not Verified', color: 'text-slate-700', bg: 'bg-slate-50', border: 'border-slate-200', icon: HelpCircle },
  NOT_APPLICABLE: { label: 'N/A', color: 'text-slate-500', bg: 'bg-slate-50', border: 'border-slate-200', icon: MinusCircle },
  ERROR: { label: 'Error', color: 'text-red-800', bg: 'bg-red-50', border: 'border-red-200', icon: AlertOctagon },
};

const SEVERITY_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  critical: { label: 'Critical', color: 'text-red-900', bg: 'bg-red-100' },
  CRITICAL: { label: 'Critical', color: 'text-red-900', bg: 'bg-red-100' },
  warning: { label: 'Warning', color: 'text-amber-900', bg: 'bg-amber-100' },
  WARNING: { label: 'Warning', color: 'text-amber-900', bg: 'bg-amber-100' },
  opportunity: { label: 'Opportunity', color: 'text-blue-900', bg: 'bg-blue-100' },
  OPPORTUNITY: { label: 'Opportunity', color: 'text-blue-900', bg: 'bg-blue-100' },
  info: { label: 'Info', color: 'text-slate-700', bg: 'bg-slate-100' },
  INFO: { label: 'Info', color: 'text-slate-700', bg: 'bg-slate-100' },
};

const PROVENANCE_CONFIG: Record<string, { label: string; icon: React.ComponentType<{ className?: string }> }> = {
  VERIFIED: { label: 'Verified', icon: ShieldCheck },
  OBSERVED: { label: 'Observed', icon: Eye },
  USER_PROVIDED: { label: 'User Provided', icon: User },
  DETECTED: { label: 'Detected', icon: Scan },
  INFERRED: { label: 'Inferred', icon: Brain },
  NOT_VERIFIED: { label: 'Not Verified', icon: ShieldOff },
  FAILED: { label: 'Failed', icon: XCircle },
  NOT_APPLICABLE: { label: 'N/A', icon: MinusCircle },
};

export const FindingCard: React.FC<FindingCardProps> = ({ finding, compact }) => {
  const status = STATUS_CONFIG[finding.status] || STATUS_CONFIG.NOT_VERIFIED;
  const severity = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.info;
  const provenance = PROVENANCE_CONFIG[finding.verification_status] || PROVENANCE_CONFIG.NOT_VERIFIED;
  const StatusIcon = status.icon;
  const ProvenanceIcon = provenance.icon;

  if (compact) {
    return (
      <div className={`flex items-start gap-3 p-3 rounded-xl border ${status.border} ${status.bg}`}>
        <StatusIcon className={`w-4 h-4 mt-0.5 shrink-0 ${status.color}`} />
        <div className="min-w-0 flex-1">
          <div className="text-xs font-bold text-slate-900">{finding.title}</div>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${severity.bg} ${severity.color}`}>
              {severity.label}
            </span>
            <span className="text-[10px] text-slate-500">{finding.category.replace(/_/g, ' ')}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-2xl border ${status.border} bg-white overflow-hidden`}>
      {/* Header */}
      <div className={`px-5 py-3 flex items-center justify-between ${status.bg} border-b ${status.border}`}>
        <div className="flex items-center gap-2">
          <StatusIcon className={`w-4.5 h-4.5 ${status.color}`} />
          <span className={`text-xs font-black uppercase tracking-wider ${status.color}`}>{status.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${severity.bg} ${severity.color}`}>
            {severity.label}
          </span>
          <span className="flex items-center gap-1 text-[10px] font-semibold text-slate-500 bg-white/60 px-2 py-0.5 rounded-md border border-slate-200">
            <ProvenanceIcon className="w-3 h-3" />
            {provenance.label}
          </span>
        </div>
      </div>

      {/* Body */}
      <div className="px-5 py-4 space-y-3">
        {/* Title */}
        <h4 className="text-sm font-bold text-slate-900">{finding.title}</h4>

        {/* Category */}
        <div className="text-[11px] text-slate-500">
          <span className="font-semibold text-slate-700">Category:</span>{' '}
          {finding.category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
        </div>

        {/* Evidence */}
        {finding.evidence && (
          <div className="space-y-1">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Evidence</div>
            <div className="text-xs text-slate-700 bg-slate-50 rounded-lg p-3 border border-slate-100 leading-relaxed">
              {typeof finding.evidence === 'string' ? finding.evidence : JSON.stringify(finding.evidence)}
            </div>
          </div>
        )}

        {/* Source */}
        {finding.source && (
          <div className="flex items-center gap-2 text-[11px]">
            <span className="font-semibold text-slate-500">Source:</span>
            <span className="text-slate-700">{finding.source}</span>
            {finding.source_url && (
              <a
                href={finding.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#236B4F] hover:underline flex items-center gap-0.5"
              >
                <ExternalLink className="w-3 h-3" /> View
              </a>
            )}
          </div>
        )}

        {/* Recommendation */}
        {finding.recommendation && (
          <div className="space-y-1">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Recommended Action</div>
            <div className="text-xs text-slate-800 bg-[#F1F7F1] rounded-lg p-3 border border-[#DCE8DC] leading-relaxed">
              {finding.recommendation}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

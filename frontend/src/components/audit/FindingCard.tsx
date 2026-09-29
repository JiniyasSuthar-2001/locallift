import React, { useState } from 'react';
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
  ShieldOff,
  ChevronDown,
  ChevronUp,
  FileText,
  Sparkles,
  Search,
  CheckSquare,
  Clock,
  Layers,
  Link2
} from 'lucide-react';

interface FindingCardProps {
  finding: LocalAuditFinding;
  compact?: boolean;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; border: string; badgeBg: string; icon: React.ComponentType<{ className?: string }> }> = {
  PASS: { label: 'Pass', color: 'text-emerald-700', bg: 'bg-emerald-50/60', border: 'border-emerald-200', badgeBg: 'bg-emerald-100 text-emerald-800 border-emerald-300', icon: CheckCircle2 },
  PARTIAL: { label: 'Partial', color: 'text-amber-700', bg: 'bg-amber-50/60', border: 'border-amber-200', badgeBg: 'bg-amber-100 text-amber-800 border-amber-300', icon: AlertTriangle },
  FAIL: { label: 'Fail', color: 'text-rose-700', bg: 'bg-rose-50/60', border: 'border-rose-200', badgeBg: 'bg-rose-100 text-rose-800 border-rose-300', icon: XCircle },
  NOT_VERIFIED: { label: 'Not Verified', color: 'text-slate-600', bg: 'bg-slate-50/60', border: 'border-slate-200', badgeBg: 'bg-slate-100 text-slate-700 border-slate-300', icon: HelpCircle },
  NOT_APPLICABLE: { label: 'N/A', color: 'text-slate-500', bg: 'bg-slate-50/60', border: 'border-slate-200', badgeBg: 'bg-slate-100 text-slate-600 border-slate-300', icon: MinusCircle },
  ERROR: { label: 'Error', color: 'text-rose-800', bg: 'bg-rose-50/60', border: 'border-rose-200', badgeBg: 'bg-rose-100 text-rose-800 border-rose-300', icon: AlertOctagon },
};

const SEVERITY_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  critical: { label: 'Critical', color: 'text-rose-800', bg: 'bg-rose-50', border: 'border-rose-200' },
  CRITICAL: { label: 'Critical', color: 'text-rose-800', bg: 'bg-rose-50', border: 'border-rose-200' },
  warning: { label: 'Warning', color: 'text-amber-800', bg: 'bg-amber-50', border: 'border-amber-200' },
  WARNING: { label: 'Warning', color: 'text-amber-800', bg: 'bg-amber-50', border: 'border-amber-200' },
  opportunity: { label: 'Opportunity', color: 'text-blue-800', bg: 'bg-blue-50', border: 'border-blue-200' },
  OPPORTUNITY: { label: 'Opportunity', color: 'text-blue-800', bg: 'bg-blue-50', border: 'border-blue-200' },
  info: { label: 'Info', color: 'text-slate-700', bg: 'bg-slate-100', border: 'border-slate-200' },
  INFO: { label: 'Info', color: 'text-slate-700', bg: 'bg-slate-100', border: 'border-slate-200' },
};

const PROVENANCE_CONFIG: Record<string, { label: string; icon: React.ComponentType<{ className?: string }> }> = {
  VERIFIED: { label: 'Verified Evidence', icon: ShieldCheck },
  OBSERVED: { label: 'Live Observed', icon: Eye },
  USER_PROVIDED: { label: 'Canonical Profile', icon: User },
  DETECTED: { label: 'Automated Scan', icon: Scan },
  INFERRED: { label: 'Inferred Data', icon: Brain },
  NOT_VERIFIED: { label: 'Awaiting Data', icon: ShieldOff },
  FAILED: { label: 'Execution Failed', icon: XCircle },
  NOT_APPLICABLE: { label: 'Not Applicable', icon: MinusCircle },
};

export const FindingCard: React.FC<FindingCardProps> = ({ finding, compact }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const status = STATUS_CONFIG[finding.status] || STATUS_CONFIG.NOT_VERIFIED;
  const severity = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.info;
  const provenance = PROVENANCE_CONFIG[finding.verification_status || 'DETECTED'] || PROVENANCE_CONFIG.DETECTED;
  const StatusIcon = status.icon;
  const ProvenanceIcon = provenance.icon;

  const affectedUrls: string[] = Array.isArray(finding.affected_urls)
    ? finding.affected_urls
    : (finding.source_url ? [finding.source_url] : []);

  const remediationSteps: string[] = Array.isArray(finding.remediation_steps) && finding.remediation_steps.length > 0
    ? finding.remediation_steps
    : (finding.recommendation ? [finding.recommendation] : []);

  const verificationSteps: string[] = Array.isArray(finding.verification_steps) && finding.verification_steps.length > 0
    ? finding.verification_steps
    : [];

  if (compact) {
    return (
      <div className={`flex items-start gap-2.5 p-3 rounded-xl border ${status.border} ${status.bg} transition-all`}>
        <StatusIcon className={`w-4 h-4 mt-0.5 shrink-0 ${status.color}`} />
        <div className="min-w-0 flex-1">
          <div className="text-xs font-bold text-[#142820] truncate">{finding.title}</div>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${severity.border} ${severity.bg} ${severity.color}`}>
              {severity.label}
            </span>
            <span className="text-[10px] text-[#587568]">{finding.category.replace(/_/g, ' ')}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border ${status.border} bg-white shadow-2xs overflow-hidden transition-all hover:border-[#236B4F]/40`}>
      {/* ─── Header Row ─── */}
      <div className="p-3.5 sm:p-4 flex items-start sm:items-center justify-between gap-3 bg-gradient-to-r from-white via-white to-[#F8FAF8]">
        <div className="flex items-start sm:items-center gap-3 min-w-0">
          <div className={`p-1.5 rounded-lg ${status.bg} border ${status.border} shrink-0 mt-0.5 sm:mt-0`}>
            <StatusIcon className={`w-4 h-4 ${status.color}`} />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="text-xs sm:text-sm font-extrabold text-[#142820] leading-snug">
                {finding.title}
              </h4>
              <span className={`px-2 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider border ${status.badgeBg}`}>
                {status.label}
              </span>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${severity.border} ${severity.bg} ${severity.color}`}>
                {severity.label} Severity
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-1 text-[11px] text-[#587568]">
              <span className="font-semibold text-slate-700 capitalize">
                {finding.category.replace(/_/g, ' ')}
              </span>
              <span>•</span>
              <span>Rule: <code className="text-slate-800 font-mono text-[10px]">{finding.rule_id}</code></span>
              {finding.source && (
                <>
                  <span>•</span>
                  <span>Source: <b className="text-slate-800">{finding.source}</b></span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Action Toggle */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="px-3 py-1.5 rounded-lg text-xs font-bold text-[#236B4F] bg-[#F1F7F1] hover:bg-[#E2EFE2] border border-[#D0E4D0] transition-colors flex items-center gap-1 shrink-0"
        >
          <span>{isExpanded ? 'Hide Details' : 'View Findings'}</span>
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* ─── Expandable Structured Forensic Evidence Drawer ─── */}
      {isExpanded && (
        <div className="px-4 pb-4 pt-3 border-t border-[#EBF2EB] bg-[#F9FAF9] space-y-3.5 text-xs">
          {/* 1. WHAT WE CHECKED */}
          {(finding.what_was_checked || finding.rule_definition) && (
            <div className="p-3 bg-white rounded-lg border border-[#E2EAE2] space-y-1">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#236B4F] flex items-center gap-1.5">
                <Search className="w-3.5 h-3.5 text-[#236B4F]" />
                <span>What We Checked</span>
              </div>
              <p className="text-xs text-slate-800 leading-relaxed font-normal">
                {finding.what_was_checked || finding.rule_definition}
              </p>
            </div>
          )}

          {/* 2. WHAT WE FOUND (OBSERVED VS EXPECTED) */}
          {(finding.observed_value || finding.expected_value) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
              {finding.observed_value && (
                <div className="p-3 bg-white rounded-lg border border-[#E2EAE2] space-y-1">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-rose-700 flex items-center gap-1">
                    <XCircle className="w-3 h-3 text-rose-600" />
                    <span>Observed Condition</span>
                  </div>
                  <p className="text-xs text-slate-800 font-medium leading-relaxed">
                    {finding.observed_value}
                  </p>
                </div>
              )}
              {finding.expected_value && (
                <div className="p-3 bg-white rounded-lg border border-[#E2EAE2] space-y-1">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                    <span>Expected Condition</span>
                  </div>
                  <p className="text-xs text-slate-800 font-medium leading-relaxed">
                    {finding.expected_value}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* 3. AFFECTED PAGES */}
          {affectedUrls.length > 0 && (
            <div className="p-3 bg-white rounded-lg border border-[#E2EAE2] space-y-1.5">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#236B4F] flex items-center gap-1.5">
                <Link2 className="w-3.5 h-3.5 text-[#236B4F]" />
                <span>Affected Pages ({affectedUrls.length})</span>
              </div>
              <ul className="space-y-1 max-h-36 overflow-y-auto pr-1">
                {affectedUrls.map((url, uIdx) => (
                  <li key={uIdx} className="flex items-center gap-2 text-[11px] font-mono text-slate-800 bg-[#F5F8F5] px-2.5 py-1 rounded border border-[#E2ECE2]">
                    <span className="truncate flex-1">{url}</span>
                    <a
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#236B4F] hover:underline flex items-center gap-0.5 shrink-0"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 4. TECHNICAL EVIDENCE */}
          {(finding.evidence || finding.technical_evidence) && (
            <div className="p-3 bg-white rounded-lg border border-[#E2EAE2] space-y-1">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#587568] flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-[#236B4F]" />
                <span>Technical Evidence & Metrics</span>
              </div>
              <div className="text-[11px] text-slate-800 bg-[#F8FAF8] rounded-md p-2.5 border border-[#DCE8DC] font-mono leading-relaxed break-words max-h-48 overflow-y-auto">
                {typeof finding.evidence === 'string'
                  ? finding.evidence
                  : JSON.stringify(finding.technical_evidence || finding.evidence, null, 2)}
              </div>
            </div>
          )}

          {/* 5. WHY IT MATTERS */}
          {finding.why_it_matters && (
            <div className="p-3 bg-[#F4F9F4] rounded-lg border border-[#D0E6D0] space-y-1">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#236B4F] flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-[#236B4F]" />
                <span>Why It Matters for Local SEO</span>
              </div>
              <p className="text-xs text-[#142820] leading-relaxed">
                {finding.why_it_matters}
              </p>
            </div>
          )}

          {/* 6. RECOMMENDED REMEDIATION STEPS */}
          {remediationSteps.length > 0 && (
            <div className="p-3.5 rounded-lg bg-[#EAF4EB] border border-[#B8DFC9] space-y-2">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#1A5C43] flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Recommended Fix</span>
              </div>
              <ol className="space-y-1.5 text-xs text-[#142820] list-decimal list-inside font-medium leading-relaxed">
                {remediationSteps.map((step, sIdx) => (
                  <li key={sIdx} className="pl-1">
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* 7. HOW TO VERIFY */}
          {verificationSteps.length > 0 && (
            <div className="p-3 rounded-lg bg-white border border-[#E2EAE2] space-y-1.5">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                <CheckSquare className="w-3.5 h-3.5 text-[#236B4F]" />
                <span>How to Verify Fix</span>
              </div>
              <ul className="space-y-1 text-xs text-slate-700">
                {verificationSteps.map((vStep, vIdx) => (
                  <li key={vIdx} className="flex items-start gap-2">
                    <span className="text-emerald-600 font-bold">✓</span>
                    <span>{vStep}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 8. PROVENANCE, TIMESTAMP & CONFIDENCE STRIP */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[#EBF2EB] text-[11px] text-slate-600">
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex items-center gap-1 bg-white px-2 py-0.5 rounded-md border border-[#DCE8DC] font-semibold text-[#142820]">
                <ProvenanceIcon className="w-3 h-3 text-[#236B4F]" />
                {provenance.label}
              </span>
              {finding.crawl_id && (
                <span className="bg-white px-2 py-0.5 rounded-md border border-[#DCE8DC] text-[10px] font-mono">
                  Crawl Snapshot #{finding.crawl_id}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-[10px] text-[#587568]">
              {finding.source_timestamp && (
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {new Date(finding.source_timestamp).toLocaleString()}
                </span>
              )}
              {finding.confidence && (
                <span>
                  Confidence: <b className="text-slate-800 uppercase">{finding.confidence}</b>
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

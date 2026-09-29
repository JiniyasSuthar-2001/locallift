import React from 'react';
import {
  X,
  Award,
  AlertCircle,
  AlertTriangle,
  Info,
  CheckCircle2,
  ExternalLink,
  ShieldCheck,
  ChevronRight,
  HelpCircle,
  Layers,
  ArrowRight,
  FileText,
  ListChecks,
  Check
} from 'lucide-react';
import { SEOIssue } from '../../types';
import { StatusBadge } from '../ui/StatusBadge';
import { Modal } from '../ui/Modal';

export interface AffectedPageItem {
  url: string;
  issue?: string;
  status_code?: number;
  recommendation?: string;
}

export interface PillarDetailContext {
  id: string; // 'overall' | 'crawl' | 'onpage' | 'schema' | 'gbp' | 'citations' | 'reviews'
  name: string;
  score: number | null;
  status: string; // 'optimal' | 'needs_attention' | 'critical' | 'not_connected' | 'not_verified' | 'no_data' | 'pass' | 'warning' | 'error'
  statusLabel?: string;
  weight?: string;
  description: string;
  whatWeChecked: string;
  whatWeFound: string[];
  affectedPages?: AffectedPageItem[];
  whatToDo: string;
  pillarScores?: {
    crawl_health: number | null;
    onpage_content: number | null;
    schema_structured_data: number | null;
    gbp_alignment: number | null;
    citations_nap: number | null;
    reviews_reputation: number | null;
  };
  pillarWeights?: Record<string, string>;
}

interface MetricDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  context: PillarDetailContext | null;
  issues: SEOIssue[];
  onSelectPillar?: (pillarId: string) => void;
}

export const MetricDetailModal: React.FC<MetricDetailModalProps> = ({
  isOpen,
  onClose,
  context,
  issues,
  onSelectPillar
}) => {
  if (!isOpen || !context) return null;

  const isOverall = context.id === 'overall';

  // Strict issue category filtering per pillar
  const filteredIssues = issues.filter((i) => {
    if (isOverall) return true;
    const cat = (i.category || '').toLowerCase();
    switch (context.id) {
      case 'crawl':
        return cat.includes('crawl') || cat.includes('technical') || cat.includes('http') || cat.includes('canonical') || cat.includes('indexability');
      case 'onpage':
        return cat.includes('on-page') || cat.includes('content') || cat.includes('title') || cat.includes('meta') || cat.includes('h1') || cat.includes('geo');
      case 'schema':
        return cat.includes('schema') || cat.includes('structured');
      case 'gbp':
        return cat.includes('google business') || cat.includes('gbp') || cat.includes('identity') || cat.includes('match');
      case 'citations':
        return cat.includes('citation') || cat.includes('directory') || cat.includes('nap');
      case 'reviews':
        return cat.includes('review') || cat.includes('reputation');
      default:
        return false;
    }
  });

  const criticalIssues = filteredIssues.filter((i) => (i.severity || '').toLowerCase() === 'critical');
  const warningIssues = filteredIssues.filter((i) => (i.severity || '').toLowerCase() === 'warning');

  const getScoreColor = (s: number | null) => {
    if (s === null || s === undefined) return 'text-slate-400';
    if (s >= 80) return 'text-emerald-600';
    if (s >= 50) return 'text-amber-600';
    return 'text-rose-600';
  };

  const getStatusBadge = () => {
    const s = (context.status || '').toLowerCase().trim();
    if (s === 'not_connected') {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-slate-100 text-slate-700 border border-slate-200">
          Not Connected
        </span>
      );
    }
    if (s === 'not_verified') {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-blue-50 text-blue-700 border border-blue-200">
          Not Verified
        </span>
      );
    }
    if (s === 'no_data' || s === 'n/a' || s === 'not_applicable') {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-slate-100 text-slate-700 border border-slate-200">
          No Data
        </span>
      );
    }
    if (s === 'pass' || s === 'matched' || s === 'optimal') {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200">
          Optimal
        </span>
      );
    }
    if (s === 'warning' || s === 'partial' || s === 'partial_match' || s === 'needs_attention') {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-amber-50 text-amber-700 border border-amber-200">
          Needs Attention
        </span>
      );
    }
    if (s === 'error' || s === 'fail' || s === 'failed' || s === 'critical' || s === 'critical_fixes') {
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-rose-50 text-rose-700 border border-rose-200">
          Critical Fixes
        </span>
      );
    }
    // Only fall back to score if no explicit status was supplied
    if (context.score !== null && context.score !== undefined) {
      if (context.score >= 80) {
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200">
            Optimal
          </span>
        );
      }
      if (context.score >= 50) {
        return (
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-amber-50 text-amber-700 border border-amber-200">
            Needs Attention
          </span>
        );
      }
      return (
        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-rose-50 text-rose-700 border border-rose-200">
          Critical Fixes
        </span>
      );
    }
    return (
      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-slate-100 text-slate-700 border border-slate-200">
        No Data
      </span>
    );
  };

  const headerContent = (
    <div className="flex items-center space-x-4 min-w-0 pr-2">
      <div className="w-14 h-14 rounded-2xl bg-white border border-[#DCE8DC] shadow-sm flex flex-col items-center justify-center shrink-0">
        <span className={`text-xl font-black ${getScoreColor(context.score)} leading-none`}>
          {context.score !== null ? context.score : '—'}
        </span>
        <span className="text-[9px] font-bold text-[#587568] mt-1 uppercase tracking-wider">
          {context.score !== null ? '/ 100' : 'No Score'}
        </span>
      </div>

      <div className="min-w-0">
        <div className="flex items-center space-x-2">
          {context.weight && (
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-[#EAF2EA] text-[#174A38] border border-[#B8DFC9]">
              Weight: {context.weight}
            </span>
          )}
          {getStatusBadge()}
        </div>
        <h2 className="text-lg font-black text-[#142820] tracking-tight mt-1 truncate">{context.name}</h2>
        <p className="text-xs text-[#587568] truncate">{context.description}</p>
      </div>
    </div>
  );

  const footerContent = (
    <div className="flex items-center justify-between w-full text-xs">
      <span className="text-[#587568] font-medium">LocalLift Intelligence Engine</span>
      <button
        onClick={onClose}
        className="px-5 py-2 btn-primary-gradient rounded-xl text-xs font-bold text-white shadow-sm cursor-pointer"
      >
        Close Drill-down
      </button>
    </div>
  );

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      maxWidth="3xl"
      headerContent={headerContent}
      footer={footerContent}
      showCloseButton={true}
      bodyClassName="p-6 space-y-6 text-[#2E4E40]"
    >
          {/* Section 1: What We Checked */}
          <div className="bg-slate-50/90 rounded-2xl p-4 border border-slate-200/70 space-y-2">
            <div className="flex items-center space-x-2 text-xs font-black uppercase tracking-wider text-slate-900">
              <ListChecks className="w-4 h-4 text-purple-600" />
              <span>What We Checked</span>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed font-medium">
              {context.whatWeChecked}
            </p>
          </div>

          {/* Section 2: What We Found */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-xs font-black uppercase tracking-wider text-slate-900">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>What We Found</span>
              </div>
              <span className="text-[10px] font-bold text-slate-400">Live Crawl & Audit Signals</span>
            </div>

            <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-xs space-y-2">
              {context.whatWeFound && context.whatWeFound.length > 0 ? (
                context.whatWeFound.map((finding, idx) => {
                  const isWarning = finding.startsWith('⚠') || finding.toLowerCase().includes('missing') || finding.toLowerCase().includes('error') || finding.toLowerCase().includes('mismatch') || finding.toLowerCase().includes('differs');
                  const isSuccess = finding.startsWith('✓') || finding.toLowerCase().includes('found') || finding.toLowerCase().includes('match') || finding.toLowerCase().includes('passed');
                  return (
                    <div
                      key={idx}
                      className={`text-xs p-2.5 rounded-xl flex items-start space-x-2 font-medium ${
                        isWarning
                          ? 'bg-amber-50/70 text-amber-900 border border-amber-200/60'
                          : isSuccess
                          ? 'bg-emerald-50/60 text-emerald-950 border border-emerald-200/50'
                          : 'bg-slate-50 text-slate-800'
                      }`}
                    >
                      <span className="font-bold shrink-0 mt-0.5">
                        {isWarning ? '⚠' : isSuccess ? '✓' : '•'}
                      </span>
                      <span className="leading-snug">{finding.replace(/^[✓⚠•]\s*/, '')}</span>
                    </div>
                  );
                })
              ) : (
                <p className="text-xs text-slate-500 italic">No specific signals recorded for this category.</p>
              )}
            </div>
          </div>

          {/* Section 3: Affected Pages (if any) */}
          {context.affectedPages && context.affectedPages.length > 0 && (
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-xs font-black uppercase tracking-wider text-slate-900">
                  <FileText className="w-4 h-4 text-rose-600" />
                  <span>Affected Pages ({context.affectedPages.length})</span>
                </div>
                <span className="text-[10px] font-bold text-slate-400">Pages needing attention</span>
              </div>

              <div className="divide-y divide-slate-100 border border-slate-200 rounded-2xl overflow-hidden bg-white shadow-xs">
                {context.affectedPages.map((ap, idx) => (
                  <div key={idx} className="p-3.5 hover:bg-slate-50 transition-colors text-xs space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <a
                        href={ap.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono font-bold text-purple-700 hover:underline truncate max-w-md flex items-center gap-1"
                      >
                        <span>{ap.url}</span>
                        <ExternalLink className="w-3 h-3 shrink-0 opacity-70" />
                      </a>
                      {ap.status_code && (
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                            ap.status_code === 200
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-rose-50 text-rose-700 border border-rose-200'
                          }`}
                        >
                          HTTP {ap.status_code}
                        </span>
                      )}
                    </div>
                    {ap.issue && (
                      <div className="text-slate-600 text-[11px] font-medium">
                        <span className="font-bold text-slate-800">Issue: </span>
                        {ap.issue}
                      </div>
                    )}
                    {ap.recommendation && (
                      <div className="text-emerald-800 text-[11px] font-semibold bg-emerald-50/50 p-2 rounded-lg border border-emerald-100">
                        <span className="font-bold">Fix: </span>
                        {ap.recommendation}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section 4: What To Do */}
          <div className="bg-gradient-to-br from-emerald-50/80 to-purple-50/50 rounded-2xl p-4 border border-emerald-200/80 space-y-2">
            <div className="flex items-center space-x-2 text-xs font-black uppercase tracking-wider text-emerald-950">
              <ArrowRight className="w-4 h-4 text-emerald-700" />
              <span>What To Do</span>
            </div>
            <p className="text-xs text-slate-800 font-medium leading-relaxed">
              {context.whatToDo}
            </p>
          </div>

          {/* Section 5: Overall Composite View (If Overall was clicked) */}
          {isOverall && context.pillarScores && (
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-black uppercase tracking-wider text-slate-900 flex items-center space-x-1.5">
                  <Layers className="w-4 h-4 text-purple-600" />
                  <span>Contribution Across 6 Local SEO Pillars</span>
                </h3>
                <span className="text-[10px] font-bold text-purple-700">Client-Friendly Local Score</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {[
                  {
                    key: 'crawl',
                    label: 'Local Crawl Health',
                    score: context.pillarScores.crawl_health,
                    weight: context.pillarWeights?.crawl_health || '20%'
                  },
                  {
                    key: 'onpage',
                    label: 'Local On-Page & Geo-Content',
                    score: context.pillarScores.onpage_content,
                    weight: context.pillarWeights?.onpage_content || '25%'
                  },
                  {
                    key: 'schema',
                    label: 'Schema & Structured Data',
                    score: context.pillarScores.schema_structured_data,
                    weight: context.pillarWeights?.schema_structured_data || '15%'
                  },
                  {
                    key: 'gbp',
                    label: 'Google Business Profile Match',
                    score: context.pillarScores.gbp_alignment,
                    weight: context.pillarWeights?.gbp_alignment || '10%'
                  },
                  {
                    key: 'citations',
                    label: 'Citations & Directory NAP',
                    score: context.pillarScores.citations_nap,
                    weight: context.pillarWeights?.citations_nap || '10%'
                  },
                  {
                    key: 'reviews',
                    label: 'Reviews & Reputation',
                    score: context.pillarScores.reviews_reputation,
                    weight: context.pillarWeights?.reviews_reputation || '20%'
                  }
                ].map((p) => (
                  <div
                    key={p.key}
                    onClick={() => onSelectPillar && onSelectPillar(p.key)}
                    className="p-3 bg-white rounded-xl border border-slate-200/80 hover:border-purple-300 hover:shadow-sm transition-all cursor-pointer flex items-center justify-between group"
                  >
                    <div>
                      <div className="text-xs font-bold text-slate-900 group-hover:text-purple-700 transition-colors">
                        {p.label}
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5">Weight: {p.weight}</div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`text-base font-black ${getScoreColor(p.score)}`}>
                        {p.score !== null ? p.score : '—'}
                      </span>
                      <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-purple-600 transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Section 6: Specific Issue Action Cards */}
          {filteredIssues.length > 0 && (
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-900">
                    Action Items ({filteredIssues.length})
                  </h3>
                  {criticalIssues.length > 0 && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-700">
                      {criticalIssues.length} Critical
                    </span>
                  )}
                  {warningIssues.length > 0 && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">
                      {warningIssues.length} Warnings
                    </span>
                  )}
                </div>
                <span className="text-[10px] font-bold text-slate-400">Actionable Tasks</span>
              </div>

              <div className="space-y-2.5">
                {filteredIssues.map((issue, idx) => (
                  <div
                    key={issue.id || idx}
                    className="p-4 bg-white rounded-2xl border border-slate-200/80 shadow-xs space-y-2.5 hover:border-purple-200 transition-all"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center space-x-2">
                        {issue.severity === 'critical' ? (
                          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                        ) : issue.severity === 'warning' ? (
                          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                        ) : (
                          <Info className="w-4 h-4 text-blue-600 shrink-0" />
                        )}
                        <h4 className="text-xs font-bold text-slate-900">{issue.title}</h4>
                      </div>
                      <StatusBadge status={issue.severity} />
                    </div>

                    {issue.why_it_matters && (
                      <div className="text-[11px] text-slate-600 bg-slate-50 p-2.5 rounded-xl space-y-1">
                        <div>
                          <span className="font-bold text-slate-700">Why it matters: </span>
                          {issue.why_it_matters}
                        </div>
                        {issue.evidence && (
                          <div className="text-slate-500 italic">
                            <span className="font-bold text-slate-600 not-italic">Evidence: </span>
                            {issue.evidence}
                          </div>
                        )}
                      </div>
                    )}

                    {issue.affected_url && (
                      <div className="flex items-center space-x-1.5 text-[11px] text-purple-700 font-mono">
                        <span className="text-slate-400 font-sans font-bold text-[10px] uppercase tracking-wider">
                          Affected URL:
                        </span>
                        <a
                          href={issue.affected_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:underline truncate max-w-md flex items-center"
                        >
                          <span>{issue.affected_url}</span>
                          <ExternalLink className="w-2.5 h-2.5 ml-1 shrink-0" />
                        </a>
                      </div>
                    )}

                    {issue.recommended_solution && (
                      <div className="text-[11px] bg-emerald-50/70 text-emerald-950 p-2.5 rounded-xl border border-emerald-200/60">
                        <span className="font-bold text-emerald-900">Recommended Solution: </span>
                        {issue.recommended_solution}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
    </Modal>
  );
};


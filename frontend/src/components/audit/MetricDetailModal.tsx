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
  TrendingDown,
  FileText,
  Calculator,
  HelpCircle,
  Layers,
  ArrowRight
} from 'lucide-react';
import { SEOIssue } from '../../types';
import { StatusBadge } from '../ui/StatusBadge';

export interface PillarDetailContext {
  id: string; // 'overall' | 'crawl' | 'onpage' | 'schema' | 'gbp' | 'citations' | 'reviews'
  name: string;
  score: number | null;
  weight: string;
  weightFraction: number;
  description: string;
  whatIsThis: string;
  whyImportant: string;
  methodology: {
    startingScore: number;
    deductions: string;
    formula: string;
  };
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
        return cat.includes('crawl') || cat.includes('technical') || cat.includes('http') || cat.includes('canonical');
      case 'onpage':
        return cat.includes('on-page') || cat.includes('content') || cat.includes('title') || cat.includes('meta') || cat.includes('h1');
      case 'schema':
        return cat.includes('schema') || cat.includes('structured');
      case 'gbp':
        return cat.includes('google business') || cat.includes('gbp') || cat.includes('identity') || cat.includes('nap');
      case 'citations':
        return cat.includes('citation') || cat.includes('directory');
      case 'reviews':
        return cat.includes('review') || cat.includes('reputation');
      default:
        return false;
    }
  });

  const criticalIssues = filteredIssues.filter((i) => (i.severity || '').toLowerCase() === 'critical');
  const warningIssues = filteredIssues.filter((i) => (i.severity || '').toLowerCase() === 'warning');
  const oppIssues = filteredIssues.filter((i) => (i.severity || '').toLowerCase() === 'opportunity');

  const getScoreColor = (s: number | null) => {
    if (s === null || s === undefined) return 'text-slate-400';
    if (s >= 80) return 'text-emerald-600';
    if (s >= 50) return 'text-amber-600';
    return 'text-rose-600';
  };

  const getScoreBadgeBg = (s: number | null) => {
    if (s === null || s === undefined) return 'bg-slate-100 text-slate-700';
    if (s >= 80) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (s >= 50) return 'bg-amber-50 text-amber-700 border-amber-200';
    return 'bg-rose-50 text-rose-700 border-rose-200';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-md animate-fade-in">
      <div
        className="bg-white rounded-3xl max-w-3xl w-full max-h-[92vh] flex flex-col shadow-2xl border border-slate-200/80 overflow-hidden relative"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-6 border-b border-slate-100 bg-gradient-to-r from-slate-50/80 via-white to-purple-50/40 flex items-start justify-between">
          <div className="flex items-center space-x-4">
            <div className="w-16 h-16 rounded-2xl bg-white border border-slate-200/80 shadow-md flex flex-col items-center justify-center shrink-0">
              <span className={`text-2xl font-black ${getScoreColor(context.score)} leading-none`}>
                {context.score !== null ? context.score : '—'}
              </span>
              <span className="text-[9px] font-bold text-slate-400 mt-1 uppercase tracking-wider">
                {context.score !== null ? '/ 100' : 'No Data'}
              </span>
            </div>

            <div>
              <div className="flex items-center space-x-2">
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-purple-100/80 text-purple-700 border border-purple-200">
                  Weight: {context.weight}
                </span>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider border ${getScoreBadgeBg(
                    context.score
                  )}`}
                >
                  {context.score !== null && context.score >= 80
                    ? 'Optimal'
                    : context.score !== null && context.score >= 50
                    ? 'Needs Attention'
                    : context.score !== null
                    ? 'Critical Fixes'
                    : 'Awaiting Audit'}
                </span>
              </div>
              <h2 className="text-xl font-black text-slate-900 tracking-tight mt-1.5">{context.name}</h2>
              <p className="text-xs text-slate-500">{context.description}</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content Scroll Area */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-slate-700">
          {/* Section 1: What is this & Why is it important */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-slate-50/80 rounded-2xl p-4 border border-slate-100 space-y-1.5">
              <div className="flex items-center space-x-1.5 text-xs font-black uppercase tracking-wider text-slate-900">
                <HelpCircle className="w-3.5 h-3.5 text-purple-600" />
                <span>What Does This Measure?</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">{context.whatIsThis}</p>
            </div>

            <div className="bg-purple-50/50 rounded-2xl p-4 border border-purple-100 space-y-1.5">
              <div className="flex items-center space-x-1.5 text-xs font-black uppercase tracking-wider text-purple-900">
                <ShieldCheck className="w-3.5 h-3.5 text-purple-600" />
                <span>Why It Matters For Ranking</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">{context.whyImportant}</p>
            </div>
          </div>

          {/* Section 2: How was the score calculated? (Transparent Scoring Methodology) */}
          <div className="card-vibrant p-4 space-y-2.5 bg-gradient-to-br from-white to-slate-50/60 border border-slate-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-xs font-black uppercase tracking-wider text-slate-900">
                <Calculator className="w-4 h-4 text-purple-600" />
                <span>Authoritative Scoring Calculation</span>
              </div>
              <span className="text-[10px] font-bold text-slate-400">Single Source of Truth: Backend Engine</span>
            </div>

            <div className="bg-white rounded-xl p-3.5 border border-slate-100 text-xs space-y-2">
              <div className="flex items-center justify-between text-[11px] pb-1.5 border-b border-slate-100">
                <span className="font-semibold text-slate-600">Starting Base Score:</span>
                <span className="font-mono font-bold text-slate-900">{context.methodology.startingScore} pts</span>
              </div>
              <div className="text-xs text-slate-600">
                <span className="font-bold text-slate-700">Deduction Rules: </span>
                {context.methodology.deductions}
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg font-mono text-[11px] text-purple-900 flex items-center justify-between">
                <span className="text-slate-500 font-sans font-bold text-[10px] uppercase tracking-wider">Formula:</span>
                <span className="font-bold">{context.methodology.formula}</span>
              </div>
            </div>
          </div>

          {/* Section 3: Overall Composite View (If Overall Score was clicked) */}
          {isOverall && context.pillarScores && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-black uppercase tracking-wider text-slate-900 flex items-center space-x-1.5">
                  <Layers className="w-4 h-4 text-purple-600" />
                  <span>Contribution Across 6 Local SEO Pillars</span>
                </h3>
                <span className="text-[10px] font-bold text-purple-700">Sums to 100% normalized</span>
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
                    weight: context.pillarWeights?.onpage_content || '20%'
                  },
                  {
                    key: 'schema',
                    label: 'Schema & Structured Data',
                    score: context.pillarScores.schema_structured_data,
                    weight: context.pillarWeights?.schema_structured_data || '25%'
                  },
                  {
                    key: 'gbp',
                    label: 'Google Business Profile Match',
                    score: context.pillarScores.gbp_alignment,
                    weight: context.pillarWeights?.gbp_alignment || '15%'
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
                    weight: context.pillarWeights?.reviews_reputation || '10%'
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

          {/* Section 4: Real Problems Detected Affecting This Score */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <h3 className="text-xs font-black uppercase tracking-wider text-slate-900">
                  Problems Affecting This Score ({filteredIssues.length})
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
              <span className="text-[10px] font-bold text-slate-400">Derived from Crawl & Audit Data</span>
            </div>

            {filteredIssues.length > 0 ? (
              <div className="space-y-2.5">
                {filteredIssues.map((issue, idx) => (
                  <div
                    key={issue.id || idx}
                    className="p-4 bg-white rounded-2xl border border-slate-200/80 shadow-sm space-y-2.5 hover:border-purple-200 transition-all"
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

                    {/* What it means & why it matters */}
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

                    {/* Affected URL */}
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

                    {/* How to Fix */}
                    {issue.recommended_solution && (
                      <div className="text-[11px] bg-emerald-50/70 text-emerald-950 p-2.5 rounded-xl border border-emerald-200/60">
                        <span className="font-bold text-emerald-900">Recommended Solution: </span>
                        {issue.recommended_solution}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 bg-slate-50 rounded-2xl border border-slate-100 text-center space-y-1.5">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
                <h4 className="text-xs font-bold text-slate-900">No Issues Detected For This Pillar</h4>
                <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                  All automated checks for {context.name} passed with 100% compliance.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/60 flex items-center justify-between text-xs">
          <span className="text-slate-400 font-medium">LocalLift Intelligence Engine</span>
          <button
            onClick={onClose}
            className="px-5 py-2 btn-vibrant-primary rounded-xl text-xs font-bold shadow-sm"
          >
            Close Drill-down
          </button>
        </div>
      </div>
    </div>
  );
};

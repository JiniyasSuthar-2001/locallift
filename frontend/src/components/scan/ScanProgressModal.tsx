import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  XCircle,
  HelpCircle,
  Clock,
  X,
  ShieldCheck,
  Star,
  MapPin,
  Globe,
  Layers,
  Activity,
  Award,
  ExternalLink,
  FileText,
  AlertOctagon,
  Ban,
  TrendingUp,
  Search
} from 'lucide-react';
import { useProjectScan, ScanStageInfo } from '../../context/ScanContext';
import { useProject } from '../../context/ProjectContext';
import { Portal } from '../ui/Portal';

export const ScanProgressModal: React.FC = () => {
  const navigate = useNavigate();
  const { activeScan, isProgressModalOpen, closeProgressModal, cancelScan } = useProjectScan();
  const { activeProject } = useProject();
  const [isCancelling, setIsCancelling] = useState(false);

  if (!isProgressModalOpen || !activeScan) return null;

  const stages = activeScan.stages ? Object.values(activeScan.stages) : [];
  const completedCount = activeScan.completed_stages_count || 0;
  const totalCount = activeScan.total_stages_count || 13;
  const progressPct = activeScan.progress_pct || Math.round((completedCount / totalCount) * 100);

  const isTerminal = ['COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED'].includes(activeScan.status);
  const isSuccess = activeScan.status === 'COMPLETED';
  const isPartial = activeScan.status === 'PARTIAL';
  const isFailed = activeScan.status === 'FAILED';
  const isCancelled = activeScan.status === 'CANCELLED';

  const summary = activeScan.results_summary || {};

  const handleCancel = async () => {
    try {
      setIsCancelling(true);
      await cancelScan();
    } catch (e) {
      console.error('Cancel scan error:', e);
    } finally {
      setIsCancelling(false);
    }
  };

  const getStageIcon = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />;
      case 'RUNNING':
        return <RotateCw className="w-4 h-4 text-purple-600 animate-spin shrink-0" />;
      case 'PARTIAL':
        return <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />;
      case 'FAILED':
        return <XCircle className="w-4 h-4 text-rose-500 shrink-0" />;
      case 'NOT_CONFIGURED':
        return <HelpCircle className="w-4 h-4 text-slate-400 shrink-0" />;
      case 'SKIPPED':
        return <Ban className="w-4 h-4 text-slate-400 shrink-0" />;
      default:
        return <div className="w-3.5 h-3.5 rounded-full border-2 border-slate-300 shrink-0" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">Done</span>;
      case 'RUNNING':
        return <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">Scanning</span>;
      case 'PARTIAL':
        return <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">Notice</span>;
      case 'FAILED':
        return <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">Error</span>;
      case 'NOT_CONFIGURED':
        return <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200">Not Configured</span>;
      case 'SKIPPED':
        return <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200">Skipped</span>;
      default:
        return <span className="text-[10px] font-medium text-slate-400">Waiting</span>;
    }
  };

  const formatDuration = (ms?: number | null) => {
    if (ms === undefined || ms === null) return '';
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    const mins = Math.floor(ms / 60000);
    const secs = Math.round((ms % 60000) / 1000);
    return `${mins}m ${secs}s`;
  };

  const getScanDuration = () => {
    if (summary.scan_duration_ms) {
      return formatDuration(summary.scan_duration_ms);
    }
    if (activeScan.started_at && activeScan.completed_at) {
      const start = new Date(activeScan.started_at).getTime();
      const end = new Date(activeScan.completed_at).getTime();
      const diff = Math.max(0, end - start);
      return formatDuration(diff);
    }
    const totalMs = stages.reduce((acc, s) => acc + (s.execution_time_ms || 0), 0);
    if (totalMs > 0) return formatDuration(totalMs);
    return '—';
  };

  return (
    <Portal>
      <div className="fixed inset-0 z-[9999] flex items-center justify-center p-3 sm:p-4 bg-slate-900/75 backdrop-blur-[2px] animate-fade-in">
        <div className="bg-white border border-[#DCE8DC] rounded-2xl sm:rounded-3xl shadow-2xl w-full max-w-3xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Modal Header */}
        <div className={`p-5 border-b border-slate-100 flex items-center justify-between ${
          !isTerminal
            ? 'bg-gradient-to-r from-purple-50 via-indigo-50/50 to-white'
            : isSuccess
            ? 'bg-emerald-50/60'
            : isPartial
            ? 'bg-amber-50/60'
            : isCancelled
            ? 'bg-slate-100'
            : 'bg-rose-50/60'
        }`}>
          <div className="flex items-center space-x-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shadow-md ${
              !isTerminal
                ? 'bg-purple-600 text-white shadow-purple-600/20'
                : isSuccess
                ? 'bg-emerald-600 text-white shadow-emerald-600/20'
                : isPartial
                ? 'bg-amber-500 text-white shadow-amber-500/20'
                : isCancelled
                ? 'bg-slate-600 text-white shadow-slate-600/20'
                : 'bg-rose-600 text-white shadow-rose-600/20'
            }`}>
              {!isTerminal ? (
                <Sparkles className="w-5 h-5 animate-pulse" />
              ) : isSuccess ? (
                <CheckCircle2 className="w-5 h-5" />
              ) : isPartial ? (
                <AlertTriangle className="w-5 h-5" />
              ) : isCancelled ? (
                <Ban className="w-5 h-5" />
              ) : (
                <XCircle className="w-5 h-5" />
              )}
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 tracking-tight flex items-center space-x-2">
                <span>
                  {!isTerminal
                    ? 'Running Local SEO Intelligence Scan'
                    : isSuccess
                    ? 'Scan Complete Summary'
                    : isPartial
                    ? 'Scan Complete Summary (with Notices)'
                    : isCancelled
                    ? 'Scan Complete Summary (Cancelled)'
                    : 'Scan Summary (Failed)'}
                </span>
              </h2>
              <p className="text-xs text-slate-500 font-medium truncate max-w-sm">
                {activeProject?.name} {activeProject?.domain ? `(${activeProject.domain})` : ''}
              </p>
            </div>
          </div>
          <button
            onClick={closeProgressModal}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
            title="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Live Progress Bar (Shown during active execution) */}
        {!isTerminal && (
          <div className="p-5 border-b border-slate-100 bg-slate-50/50 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2 font-bold text-slate-800">
                <RotateCw className="w-3.5 h-3.5 text-purple-600 animate-spin" />
                <span className="truncate">{activeScan.current_stage_label || 'Executing Local SEO modules...'}</span>
              </div>
              <span className="font-mono font-black text-purple-700">
                {completedCount} / {totalCount} ({progressPct}%)
              </span>
            </div>

            <div className="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
              <div
                className="bg-gradient-to-r from-purple-600 to-indigo-600 h-full rounded-full transition-all duration-500 ease-out"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
        )}

        {/* Scan Complete Summary — 10 Required Metric Cards (Shown upon scan completion) */}
        {isTerminal && (
          <div className="p-4 border-b border-slate-100 bg-slate-50/70">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
              {/* 1. Overall Local SEO Score */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-500">Overall Score</span>
                  <Award className="w-3.5 h-3.5 text-indigo-500" />
                </div>
                <div className="mt-1">
                  <span className="text-base font-black text-slate-900">
                    {summary.overall_score !== undefined && summary.overall_score !== null
                      ? `${summary.overall_score}/100`
                      : 'Audited'}
                  </span>
                </div>
              </div>

              {/* 2. Technical Health */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-500">Technical Health</span>
                  <Globe className="w-3.5 h-3.5 text-purple-500" />
                </div>
                <div className="mt-1">
                  <span className="text-base font-black text-slate-900">
                    {summary.technical_health !== undefined && summary.technical_health !== null
                      ? `${summary.technical_health}/100`
                      : 'Audited'}
                  </span>
                </div>
              </div>

              {/* 3. NAP Consistency */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-500">NAP Consistency</span>
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                </div>
                <div className="mt-1">
                  <span className="text-base font-black text-slate-900">
                    {summary.nap_consistency !== undefined && summary.nap_consistency !== null
                      ? `${summary.nap_consistency}%`
                      : 'Audited'}
                  </span>
                </div>
              </div>

              {/* 4. Reviews Found */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-500">Reviews Found</span>
                  <Star className="w-3.5 h-3.5 text-amber-500" />
                </div>
                <div className="mt-1 flex items-baseline space-x-1">
                  <span className="text-base font-black text-slate-900">
                    {summary.reviews_found ?? 0}
                  </span>
                  {summary.average_rating ? (
                    <span className="text-[10px] font-bold text-amber-600">
                      ({summary.average_rating}★)
                    </span>
                  ) : null}
                </div>
              </div>

              {/* 5. Citations Found */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-500">Citations Found</span>
                  <Layers className="w-3.5 h-3.5 text-blue-500" />
                </div>
                <div className="mt-1 flex items-baseline space-x-1">
                  <span className="text-base font-black text-slate-900">
                    {summary.citations_found ?? summary.citations_detected ?? 0}
                  </span>
                  {summary.citations_matching !== undefined && (
                    <span className="text-[10px] font-semibold text-slate-400">
                      ({summary.citations_matching} match)
                    </span>
                  )}
                </div>
              </div>

              {/* 6. Pages Crawled */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-500">Pages Crawled</span>
                  <FileText className="w-3.5 h-3.5 text-cyan-500" />
                </div>
                <div className="mt-1">
                  <span className="text-base font-black text-slate-900">
                    {summary.pages_crawled ?? (summary.website_audit?.pages_analyzed ?? 1)}
                  </span>
                </div>
              </div>

              {/* 7. Issues Found */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-500">Issues Found</span>
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                </div>
                <div className="mt-1">
                  <span className="text-base font-black text-slate-900">
                    {summary.issues_found ?? (summary.local_audit?.findings_count ?? 0)}
                  </span>
                </div>
              </div>

              {/* 8. Critical Issues */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-500">Critical Issues</span>
                  <AlertOctagon className="w-3.5 h-3.5 text-rose-500" />
                </div>
                <div className="mt-1">
                  <span className={`text-base font-black ${(summary.critical_issues ?? 0) > 0 ? 'text-rose-600' : 'text-slate-900'}`}>
                    {summary.critical_issues ?? (summary.local_audit?.critical_count ?? 0)}
                  </span>
                </div>
              </div>

              {/* 9. Scan Duration */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-500">Scan Duration</span>
                  <Clock className="w-3.5 h-3.5 text-slate-500" />
                </div>
                <div className="mt-1">
                  <span className="text-base font-black text-slate-900">
                    {getScanDuration()}
                  </span>
                </div>
              </div>

              {/* 10. Completed Modules */}
              <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase text-slate-500">Completed Modules</span>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                </div>
                <div className="mt-1">
                  <span className="text-base font-black text-slate-900">
                    {summary.completed_modules ?? completedCount} / {summary.total_modules ?? totalCount}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Stage Checklist & Live Execution List */}
        <div className="p-5 overflow-y-auto space-y-2 flex-1 divide-y divide-slate-100">
          <div className="text-[11px] font-bold uppercase text-slate-400 tracking-wider pb-1">
            Provider Execution Detail
          </div>
          {stages.map((st: ScanStageInfo) => (
            <div key={st.key} className="pt-2 first:pt-0 flex items-start justify-between gap-3 text-xs">
              <div className="flex items-start space-x-2.5 min-w-0">
                <div className="mt-0.5">{getStageIcon(st.status)}</div>
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-slate-900">{st.label}</span>
                    {st.execution_time_ms !== undefined && st.execution_time_ms !== null && (
                      <span className="text-[10px] font-mono text-slate-400">
                        {formatDuration(st.execution_time_ms)}
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-500 font-medium truncate">
                    {st.message}
                  </div>
                  {st.action === 'reconnect' && (
                    <button
                      onClick={() => {
                        closeProgressModal();
                        navigate('/connections');
                      }}
                      className="mt-1 text-[11px] font-bold text-purple-600 hover:text-purple-700 flex items-center space-x-1 cursor-pointer"
                    >
                      <span>Reconnect in Connections</span>
                      <ExternalLink className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>
              <div className="shrink-0">{getStatusBadge(st.status)}</div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-xs">
          <span className="text-slate-500 font-medium">
            {!isTerminal
              ? 'Scan coordinates live across all connected providers.'
              : 'All workspaces and audit metrics refreshed with live evidence.'}
          </span>
          <div className="flex items-center space-x-2">
            {!isTerminal ? (
              <>
                <button
                  onClick={handleCancel}
                  disabled={isCancelling}
                  className="px-4 py-2 border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded-xl font-bold transition-all text-xs flex items-center space-x-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Ban className="w-3.5 h-3.5 text-rose-600" />
                  <span>{isCancelling ? 'Cancelling...' : 'Cancel Scan'}</span>
                </button>
                <button
                  onClick={closeProgressModal}
                  className="btn-secondary text-xs px-4 py-2 rounded-xl font-bold transition-all shadow-xs cursor-pointer"
                >
                  Run in Background
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => {
                    closeProgressModal();
                    navigate('/audits/local');
                  }}
                  className="px-5 py-2.5 bg-purple-50 hover:bg-purple-100 border border-purple-200 text-purple-700 rounded-xl font-bold text-xs transition-all shadow-xs flex items-center space-x-1.5 cursor-pointer"
                >
                  <FileText className="w-3.5 h-3.5 text-purple-600" />
                  <span>View Full Report</span>
                </button>
                <button
                  onClick={closeProgressModal}
                  className="btn-primary-gradient text-xs px-6 py-2.5 rounded-xl font-bold transition-all shadow-sm cursor-pointer text-white"
                >
                  Close
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
    </Portal>
  );
};

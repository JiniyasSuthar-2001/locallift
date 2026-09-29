import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Globe,
  Search,
  MapPin,
  Building2,
  Star,
  Layers,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  X,
  ShieldAlert,
  Info,
  ExternalLink
} from 'lucide-react';
import { useProjectScan, ScanStageInfo } from '../../context/ScanContext';
import { useProject } from '../../context/ProjectContext';
import { Portal } from '../ui/Portal';

export const ScanCompleteModal: React.FC = () => {
  const { activeScan, isCompleteModalOpen, closeCompleteModal, refreshAllProjectData } = useProjectScan();
  const { activeProject } = useProject();
  const [expandedModule, setExpandedModule] = useState<string | null>(null);

  if (!isCompleteModalOpen || !activeScan) return null;

  const stages = activeScan.stages ? Object.values(activeScan.stages) : [];
  const successfulStages = stages.filter(s => s.status === 'SUCCESS').length;
  const partialStages = stages.filter(s => s.status === 'PARTIAL').length;
  const failedStages = stages.filter(s => s.status === 'FAILED').length;
  const notConfiguredStages = stages.filter(s => s.status === 'NOT_CONFIGURED').length;
  const totalStages = stages.length || 13;

  const status = activeScan.status;
  const isCompleted = status === 'COMPLETED';
  const isPartial = status === 'PARTIAL';
  const isFailed = status === 'FAILED';
  const isCancelled = status === 'CANCELLED';

  // Calculate Duration
  let durationStr = 'N/A';
  if (activeScan.started_at && activeScan.completed_at) {
    const start = new Date(activeScan.started_at).getTime();
    const end = new Date(activeScan.completed_at).getTime();
    const diffSec = Math.max(0, Math.floor((end - start) / 1000));
    const mins = Math.floor(diffSec / 60);
    const secs = diffSec % 60;
    durationStr = mins > 0 ? `${mins} min ${secs.toString().padStart(2, '0')} sec` : `${secs} sec`;
  }

  const summary = activeScan.results_summary || {};
  const modulesData = summary.modules || {};

  const handleRefreshAndClose = async () => {
    await refreshAllProjectData();
    closeCompleteModal();
  };

  const toggleModule = (key: string) => {
    setExpandedModule(prev => (prev === key ? null : key));
  };

  // Safe helper to extract status pill styling
  const getStatusBadge = (st: string) => {
    switch (st) {
      case 'SUCCESS':
        return (
          <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-300">
            Success
          </span>
        );
      case 'PARTIAL':
        return (
          <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-300">
            Partial
          </span>
        );
      case 'FAILED':
        return (
          <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-300">
            Failed
          </span>
        );
      case 'NOT_CONFIGURED':
        return (
          <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-300">
            Not Configured
          </span>
        );
      case 'SKIPPED':
        return (
          <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-gray-100 text-gray-600 border border-gray-300">
            Skipped
          </span>
        );
      default:
        return (
          <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-500 border border-slate-200">
            {st}
          </span>
        );
    }
  };

  // High-level summary extraction from real scan data
  const crawlData = modulesData.website_crawl || {};
  const webAuditData = modulesData.website_audit || {};
  const localAuditData = modulesData.local_audit || {};
  const rankingsData = modulesData.rankings || {};
  const geoData = modulesData.geo || {};
  const gbpData = modulesData.gbp || {};
  const reviewsData = modulesData.reviews || {};
  const citationsData = modulesData.citations || {};
  const napData = modulesData.nap || {};

  return (
    <Portal>
      <div className="fixed inset-0 z-[9999] flex items-center justify-center p-3 sm:p-5 bg-slate-900/80 backdrop-blur-sm animate-fade-in">
        <div className="bg-white border border-slate-200 rounded-2xl sm:rounded-3xl shadow-2xl w-full max-w-3xl overflow-hidden flex flex-col max-h-[92vh]">
          {/* Header */}
          <div
            className={`p-5 sm:p-6 border-b flex items-start justify-between ${
              isCompleted
                ? 'bg-gradient-to-r from-emerald-50 to-teal-50/50 border-emerald-100'
                : isPartial
                ? 'bg-gradient-to-r from-amber-50 to-yellow-50/50 border-amber-100'
                : isCancelled
                ? 'bg-gradient-to-r from-slate-50 to-gray-50/50 border-slate-200'
                : 'bg-gradient-to-r from-rose-50 to-red-50/50 border-rose-100'
            }`}
          >
            <div className="flex items-start space-x-3.5">
              <div
                className={`w-11 h-11 rounded-2xl flex items-center justify-center shadow-md shrink-0 mt-0.5 ${
                  isCompleted
                    ? 'bg-emerald-600 text-white shadow-emerald-600/20'
                    : isPartial
                    ? 'bg-amber-500 text-white shadow-amber-500/20'
                    : isCancelled
                    ? 'bg-slate-600 text-white shadow-slate-600/20'
                    : 'bg-rose-600 text-white shadow-rose-600/20'
                }`}
              >
                {isCompleted && <CheckCircle2 className="w-6 h-6" />}
                {isPartial && <AlertTriangle className="w-6 h-6" />}
                {isCancelled && <Clock className="w-6 h-6" />}
                {isFailed && <XCircle className="w-6 h-6" />}
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-base sm:text-lg font-black text-slate-900 tracking-tight">
                    {isCompleted && 'LOCAL SEO INTELLIGENCE SCAN COMPLETE'}
                    {isPartial && 'LOCAL SEO SCAN COMPLETED WITH WARNINGS'}
                    {isCancelled && 'LOCAL SEO INTELLIGENCE SCAN CANCELLED'}
                    {isFailed && 'LOCAL SEO INTELLIGENCE SCAN FAILED'}
                  </h2>
                  <span
                    className={`text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full border ${
                      isCompleted
                        ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                        : isPartial
                        ? 'bg-amber-100 text-amber-800 border-amber-300'
                        : isCancelled
                        ? 'bg-slate-100 text-slate-700 border-slate-300'
                        : 'bg-rose-100 text-rose-800 border-rose-300'
                    }`}
                  >
                    {status}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-600 mt-1 flex-wrap">
                  <span className="font-semibold text-slate-900">
                    {activeProject?.domain || activeProject?.name || 'Target Project'}
                  </span>
                  <span>•</span>
                  <span>Scan #{activeScan.scan_id}</span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    {durationStr}
                  </span>
                </div>
              </div>
            </div>
            <button
              onClick={closeCompleteModal}
              className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-white/80 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Module Counters Bar */}
          <div className="p-3.5 sm:p-4 border-b border-slate-100 bg-slate-50/80 grid grid-cols-2 sm:grid-cols-5 gap-2 text-center text-xs">
            <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-2xs">
              <span className="text-[10px] font-bold uppercase text-slate-500 block">Total Modules</span>
              <span className="text-base font-black text-slate-900">{totalStages}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-white border border-emerald-200 shadow-2xs">
              <span className="text-[10px] font-bold uppercase text-emerald-600 block">Successful</span>
              <span className="text-base font-black text-emerald-700">{successfulStages}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-white border border-amber-200 shadow-2xs">
              <span className="text-[10px] font-bold uppercase text-amber-600 block">Partial</span>
              <span className="text-base font-black text-amber-700">{partialStages}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-white border border-rose-200 shadow-2xs">
              <span className="text-[10px] font-bold uppercase text-rose-600 block">Failed</span>
              <span className="text-base font-black text-rose-700">{failedStages}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-2xs col-span-2 sm:col-span-1">
              <span className="text-[10px] font-bold uppercase text-slate-500 block">Not Configured</span>
              <span className="text-base font-black text-slate-700">{notConfiguredStages}</span>
            </div>
          </div>

          {/* Body Content (Scrollable) */}
          <div className="p-5 sm:p-6 overflow-y-auto space-y-5 flex-1 divide-y divide-slate-100">
            {/* 1. Concise Results Summary Grid */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Key Scan Results Summary
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                {/* Website Analysis Card */}
                <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1.5 shadow-2xs">
                  <div className="flex items-center gap-2 font-bold text-slate-900">
                    <Globe className="w-4 h-4 text-emerald-600" />
                    <span>Website & On-Page Technical</span>
                  </div>
                  <div className="text-slate-600 text-[11px] leading-relaxed">
                    {crawlData.pages_analyzed != null ? (
                      <>
                        <span className="font-semibold text-slate-900">{crawlData.pages_analyzed} pages</span> analyzed
                        {webAuditData.rule_evaluations_completed != null && (
                          <span> • <span className="font-semibold text-slate-900">{webAuditData.rule_evaluations_completed}</span> rule checks</span>
                        )}
                        {webAuditData.critical_issues != null && (
                          <span> • <span className="font-semibold text-rose-600">{webAuditData.critical_issues} critical</span></span>
                        )}
                        {webAuditData.warnings != null && (
                          <span> • <span className="font-semibold text-amber-600">{webAuditData.warnings} warnings</span></span>
                        )}
                      </>
                    ) : (
                      <span className="text-slate-400 italic">Not available</span>
                    )}
                  </div>
                </div>

                {/* Local SEO 20-Category Audit Card */}
                <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1.5 shadow-2xs">
                  <div className="flex items-center gap-2 font-bold text-slate-900">
                    <Layers className="w-4 h-4 text-indigo-600" />
                    <span>20-Category Local SEO Audit</span>
                  </div>
                  <div className="text-slate-600 text-[11px] leading-relaxed">
                    {localAuditData.categories_evaluated != null ? (
                      <>
                        <span className="font-semibold text-slate-900">{localAuditData.categories_evaluated} categories</span> evaluated
                        {localAuditData.passed_count != null && (
                          <span> • <span className="font-semibold text-emerald-600">{localAuditData.passed_count} passed</span></span>
                        )}
                        {localAuditData.failed_count != null && (
                          <span> • <span className="font-semibold text-rose-600">{localAuditData.failed_count} failed</span></span>
                        )}
                        {localAuditData.not_verified_count != null && (
                          <span> • <span className="font-semibold text-slate-500">{localAuditData.not_verified_count} not verified</span></span>
                        )}
                      </>
                    ) : (
                      <span className="text-slate-400 italic">Not verified</span>
                    )}
                  </div>
                </div>

                {/* Keyword Rankings Card */}
                <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1.5 shadow-2xs">
                  <div className="flex items-center gap-2 font-bold text-slate-900">
                    <Search className="w-4 h-4 text-blue-600" />
                    <span>Keyword Rank Tracking</span>
                  </div>
                  <div className="text-slate-600 text-[11px] leading-relaxed">
                    {rankingsData.keywords_attempted != null ? (
                      <>
                        <span className="font-semibold text-slate-900">{rankingsData.keywords_configured ?? rankingsData.keywords_attempted} tracked</span>
                        <span> • <span className="font-semibold text-slate-900">{rankingsData.keywords_attempted} attempted</span></span>
                        {rankingsData.keywords_successful != null && (
                          <span> • <span className="font-semibold text-emerald-600">{rankingsData.keywords_successful} verified</span></span>
                        )}
                        {rankingsData.keywords_failed != null && rankingsData.keywords_failed > 0 && (
                          <span> • <span className="font-semibold text-rose-600">{rankingsData.keywords_failed} failed</span></span>
                        )}
                      </>
                    ) : (
                      <span className="text-slate-400 italic">Not verified</span>
                    )}
                  </div>
                </div>

                {/* 5x5 Geo-Grid Card */}
                <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1.5 shadow-2xs">
                  <div className="flex items-center gap-2 font-bold text-slate-900">
                    <MapPin className="w-4 h-4 text-emerald-600" />
                    <span>5x5 Geo-Grid Visibility</span>
                  </div>
                  <div className="text-slate-600 text-[11px] leading-relaxed">
                    {geoData.points_attempted != null ? (
                      <>
                        <span className="font-semibold text-slate-900">{geoData.points_configured ?? 25} points</span> configured
                        <span> • <span className="font-semibold text-slate-900">{geoData.points_attempted} attempted</span></span>
                        {geoData.points_successful != null && (
                          <span> • <span className="font-semibold text-emerald-600">{geoData.points_successful} successful</span></span>
                        )}
                        {geoData.points_failed != null && geoData.points_failed > 0 && (
                          <span> • <span className="font-semibold text-rose-600">{geoData.points_failed} failed</span></span>
                        )}
                      </>
                    ) : (
                      <span className="text-slate-400 italic">Not scanned</span>
                    )}
                  </div>
                </div>

                {/* GBP & Reviews Card */}
                <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1.5 shadow-2xs">
                  <div className="flex items-center gap-2 font-bold text-slate-900">
                    <Building2 className="w-4 h-4 text-amber-600" />
                    <span>Google Business Profile & Reviews</span>
                  </div>
                  <div className="text-slate-600 text-[11px] leading-relaxed">
                    <span className="font-semibold text-slate-900">GBP: </span>
                    {gbpData.status === 'SUCCESS' || gbpData.status === 'CONNECTED' ? (
                      <span className="text-emerald-700 font-semibold">Connected</span>
                    ) : gbpData.status === 'NOT_CONFIGURED' ? (
                      <span className="text-slate-500 font-semibold">Not Connected</span>
                    ) : (
                      <span className="text-amber-700 font-semibold">{gbpData.status || 'Not Connected'}</span>
                    )}
                    {reviewsData.total != null && (
                      <span> • <span className="font-semibold text-slate-900">{reviewsData.total} reviews</span></span>
                    )}
                    {reviewsData.average_rating != null && (
                      <span> • <span className="font-semibold text-amber-600">{reviewsData.average_rating} ★</span></span>
                    )}
                  </div>
                </div>

                {/* Citations & NAP Card */}
                <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1.5 shadow-2xs">
                  <div className="flex items-center gap-2 font-bold text-slate-900">
                    <Star className="w-4 h-4 text-purple-600" />
                    <span>Citations & NAP Consistency</span>
                  </div>
                  <div className="text-slate-600 text-[11px] leading-relaxed">
                    {citationsData.total != null ? (
                      <>
                        <span className="font-semibold text-slate-900">{citationsData.total} detected</span>
                        {citationsData.matching != null && (
                          <span> • <span className="font-semibold text-emerald-600">{citationsData.matching} matching</span></span>
                        )}
                        {citationsData.mismatched != null && (
                          <span> • <span className="font-semibold text-rose-600">{citationsData.mismatched} mismatched</span></span>
                        )}
                        {napData.consistency_pct != null && (
                          <span> • <span className="font-semibold text-slate-900">{napData.consistency_pct}% NAP score</span></span>
                        )}
                      </>
                    ) : (
                      <span className="text-slate-400 italic">Not available</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Detailed 13-Module Execution Breakdown */}
            <div className="pt-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Detailed Module Execution Breakdown ({stages.length})
                </h3>
                <span className="text-[11px] text-slate-400">Click a module to inspect runtime details</span>
              </div>

              <div className="space-y-2">
                {stages.map((st: ScanStageInfo) => {
                  const isExpanded = expandedModule === st.key;
                  return (
                    <div
                      key={st.key}
                      className="border border-slate-200 rounded-xl bg-white overflow-hidden transition-all duration-150"
                    >
                      <button
                        onClick={() => toggleModule(st.key)}
                        className="w-full p-3.5 text-left flex items-center justify-between gap-3 hover:bg-slate-50/70 transition-colors cursor-pointer"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="font-bold text-xs text-slate-900 truncate">
                            {st.label}
                          </div>
                          <div className="hidden sm:block text-[11px] text-slate-500 truncate max-w-xs">
                            {st.message}
                          </div>
                        </div>

                        <div className="flex items-center gap-2.5 shrink-0">
                          {getStatusBadge(st.status)}
                          {isExpanded ? (
                            <ChevronUp className="w-4 h-4 text-slate-400" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-slate-400" />
                          )}
                        </div>
                      </button>

                      {isExpanded && (
                        <div className="p-3.5 pt-0 border-t border-slate-100 bg-slate-50/50 space-y-2 text-xs">
                          <div className="text-slate-700 text-[11px] pt-2">
                            <span className="font-semibold text-slate-900">Execution Result: </span>
                            {st.message || 'No additional summary recorded.'}
                          </div>

                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] text-slate-600 pt-1">
                            <div>
                              <span className="text-slate-400 block">Records Found</span>
                              <span className="font-bold text-slate-800">
                                {st.records_found != null ? st.records_found : 'N/A'}
                              </span>
                            </div>
                            <div>
                              <span className="text-slate-400 block">Records Saved</span>
                              <span className="font-bold text-slate-800">
                                {st.records_saved != null ? st.records_saved : 'N/A'}
                              </span>
                            </div>
                            <div>
                              <span className="text-slate-400 block">Execution Time</span>
                              <span className="font-bold text-slate-800">
                                {st.execution_time_ms != null ? `${st.execution_time_ms} ms` : 'N/A'}
                              </span>
                            </div>
                            <div>
                              <span className="text-slate-400 block">Completed At</span>
                              <span className="font-bold text-slate-800">
                                {st.completed_at ? new Date(st.completed_at).toLocaleTimeString() : 'N/A'}
                              </span>
                            </div>
                          </div>

                          {st.error && (
                            <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-[11px] flex items-start gap-2">
                              <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                              <div>
                                <span className="font-bold">Error Detail: </span>
                                <span>{st.error}</span>
                              </div>
                            </div>
                          )}

                          {st.action && (
                            <div className="p-2 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-800 text-[11px] flex items-center gap-1.5">
                              <Info className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
                              <span>{st.action}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Action Footer */}
          <div className="p-4 sm:p-5 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs">
            <span className="text-slate-500 hidden sm:inline">
              Project workspaces and reporting caches have been updated with truthful telemetry.
            </span>
            <button
              onClick={handleRefreshAndClose}
              className="btn-primary-gradient text-xs px-5 py-2.5 rounded-xl font-bold flex items-center space-x-2 text-white shadow-md cursor-pointer ml-auto"
            >
              <span>Apply & View Refreshed Data</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </Portal>
  );
};

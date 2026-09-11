import React, { useState, useEffect } from 'react';
import {
  FileText,
  Printer,
  Sparkles,
  CheckCircle,
  ShieldCheck,
  Building2,
  Calendar
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const ReportsView: React.FC = () => {
  const { activeProject } = useProject();
  const [reportData, setReportData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchReport = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/reports/${activeProject.id}/executive`);
      setReportData(resp.data);
    } catch (e) {
      console.error('Failed to load report:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [activeProject?.id]);

  const handlePrint = () => {
    window.print();
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={FileText}
        badge="Executive Reports"
        title="Select a Project"
        description="Select a business project to compile white-label executive Local SEO performance reports."
      />
    );
  }

  if (loading || !reportData) {
    return (
      <div className="card-vibrant p-12 text-center space-y-3">
        <Sparkles className="w-8 h-8 mx-auto text-purple-600 animate-spin" />
        <p className="text-xs font-semibold text-slate-600">Compiling executive performance report for {activeProject.name}...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <FileText className="w-6 h-6 text-purple-600" />
            <span>Executive Performance Report</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            White-label executive summary aggregating website health, local pack visibility, GBP insights, and completed tasks.
          </p>
        </div>

        <button
          onClick={handlePrint}
          className="flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all self-start"
        >
          <Printer className="w-4 h-4" />
          <span>Print / Save as PDF</span>
        </button>
      </div>

      {/* Printable Report Document Card */}
      <div className="card-vibrant p-8 sm:p-10 space-y-8 print:p-0 print:border-none print:shadow-none bg-white">
        {/* Report Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 border-b border-slate-200 pb-6">
          <div>
            <div className="text-[10px] font-black text-purple-700 uppercase tracking-wider">
              Local SEO Monthly Performance Review
            </div>
            <h2 className="text-2xl font-black text-slate-900 mt-1">{reportData.project?.name || activeProject.name}</h2>
            <div className="text-xs text-slate-500 font-mono mt-0.5">{reportData.project?.domain || activeProject.domain}</div>
          </div>

          <div className="text-left sm:text-right text-xs text-slate-500">
            <div className="font-bold text-slate-800">Generated for: {activeProject.name}</div>
            <div>Date: {new Date(reportData.generated_at).toLocaleDateString()}</div>
            <div>Evaluation Period: Last 30 Days</div>
          </div>
        </div>

        {/* Executive Summary */}
        <div className="space-y-2">
          <h3 className="text-xs font-black uppercase tracking-wider text-purple-800">
            Executive Summary
          </h3>
          <p className="text-xs text-slate-700 leading-relaxed bg-slate-50 p-4 rounded-2xl border border-slate-200 font-medium">
            {reportData.executive_summary}
          </p>
        </div>

        {/* Score & Core Metrics */}
        {(() => {
          const reportHealth = reportData.project?.health_score ?? activeProject.health_score ?? null;
          const isHealthAvailable = reportHealth !== null && reportHealth !== undefined;
          const napScore = reportData.metrics?.nap_consistency_score;
          const isNapAvailable = napScore !== null && napScore !== undefined;

          return (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 items-center">
              <div className="p-6 rounded-2xl bg-purple-50/70 border border-purple-200 text-center space-y-1">
                <span className="text-[10px] font-black uppercase tracking-wider text-purple-900 block">Overall Health Grade</span>
                <span className="text-4xl font-black text-purple-900 block">
                  {isHealthAvailable ? reportHealth : '—'}
                </span>
                <span className="text-xs font-bold text-purple-700">
                  {isHealthAvailable ? 'out of 100' : 'Awaiting Audit'}
                </span>
              </div>

              <div className="sm:col-span-2 grid grid-cols-2 gap-3 text-xs">
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                  <span className="text-slate-500 text-[10px] font-bold uppercase block">Tracked Keywords</span>
                  <span className="text-lg font-black text-slate-900 mt-0.5 block">{reportData.metrics?.total_keywords ?? 0} Terms</span>
                  <span className="text-[11px] text-emerald-700 font-bold">{reportData.metrics?.top_3_keywords ?? 0} in Top 3 Local Pack</span>
                </div>

                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                  <span className="text-slate-500 text-[10px] font-bold uppercase block">Reputation Score</span>
                  <span className="text-lg font-black text-amber-500 mt-0.5 block">
                    {reportData.metrics?.avg_rating !== null && reportData.metrics?.avg_rating !== undefined
                      ? `${reportData.metrics.avg_rating} ★ Rating`
                      : '—'}
                  </span>
                  <span className="text-[11px] text-slate-500 font-medium">{reportData.metrics?.total_reviews ?? 0} Verified Reviews</span>
                </div>

                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                  <span className="text-slate-500 text-[10px] font-bold uppercase block">NAP Consistency</span>
                  <span className="text-lg font-black text-purple-700 mt-0.5 block">
                    {isNapAvailable ? `${napScore}% Uniform` : 'Awaiting Audit'}
                  </span>
                  <span className="text-[11px] text-slate-500 font-medium">Directory Alignment</span>
                </div>

                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                  <span className="text-slate-500 text-[10px] font-bold uppercase block">Optimizations Completed</span>
                  <span className="text-lg font-black text-slate-900 mt-0.5 block">{reportData.metrics?.completed_tasks_count ?? 0} Tasks</span>
                  <span className="text-[11px] font-bold text-slate-600">
                    {(reportData.metrics?.open_issues_count ?? 0) === 0
                      ? 'Zero Critical Blockers'
                      : `${reportData.metrics?.open_issues_count} Open Issues`}
                  </span>
                </div>
              </div>
            </div>
          );
        })()}

        {/* Recommended Action Plan */}
        {reportData.next_month_recommendations && reportData.next_month_recommendations.length > 0 && (
          <div className="space-y-3 pt-4 border-t border-slate-200">
            <h3 className="text-xs font-black uppercase tracking-wider text-purple-800">
              Strategic Objectives for Next Month
            </h3>
            <div className="space-y-2">
              {reportData.next_month_recommendations.map((rec: string, rIdx: number) => (
                <div
                  key={rIdx}
                  className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-800 font-medium flex items-start space-x-2"
                >
                  <CheckCircle className="w-4 h-4 text-purple-600 shrink-0 mt-0.5" />
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

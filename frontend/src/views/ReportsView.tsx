import React, { useState, useEffect } from 'react';
import {
  FileText,
  Printer,
  Sparkles,
  CheckCircle,
  ShieldCheck,
  Building2,
  Calendar,
  MapPin,
  Star,
  BookOpen,
  AlertTriangle,
  Award,
  Layers,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ExternalLink,
  ChevronRight
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const ReportsView: React.FC = () => {
  const { activeProject } = useProject();
  const [reportType, setReportType] = useState<'local_seo' | 'executive'>('local_seo');
  const [reportData, setReportData] = useState<any>(null);
  const [executiveData, setExecutiveData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchReports = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const [localResp, execResp] = await Promise.allSettled([
        api.get(`/reports/${activeProject.id}/local-seo`),
        api.get(`/reports/${activeProject.id}/executive`)
      ]);
      if (localResp.status === 'fulfilled') setReportData(localResp.value.data);
      if (execResp.status === 'fulfilled') setExecutiveData(execResp.value.data);
    } catch (e) {
      console.error('Failed to load reports:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [activeProject?.id]);

  const handleDownloadPDF = async () => {
    if (!activeProject) return;
    try {
      const response = await api.get(`/reports/${activeProject.id}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `SEO_Audit_Report_${activeProject.domain}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (e) {
      console.error('PDF download error:', e);
    }
  };

  const handleDownloadXLSX = async () => {
    if (!activeProject) return;
    try {
      const response = await api.get(`/reports/${activeProject.id}/xlsx`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Master_SEO_Audit_${activeProject.domain}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (e) {
      console.error('XLSX download error:', e);
    }
  };

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

  if (loading || (!reportData && !executiveData)) {
    return (
      <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center space-y-3">
        <Sparkles className="w-8 h-8 mx-auto text-emerald-600 animate-spin" />
        <p className="text-xs font-semibold text-slate-600">Compiling Local SEO intelligence report for {activeProject.name}...</p>
      </div>
    );
  }

  const profile = reportData?.business_profile;
  const audit = reportData?.audit;
  const geo = reportData?.geo_visibility;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <FileText className="w-6 h-6 text-emerald-600" />
            <span>Local SEO Intelligence & Audit Report</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            White-label client deliverable with 20-category local audit breakdown, Geo-Grid visibility, and 90-day action plan.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start">
          {/* Report Type Selector */}
          <div className="flex bg-slate-100 p-1 rounded-xl border border-slate-200">
            <button
              onClick={() => setReportType('local_seo')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                reportType === 'local_seo'
                  ? 'bg-white text-emerald-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Intelligence Audit
            </button>
            <button
              onClick={() => setReportType('executive')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                reportType === 'executive'
                  ? 'bg-white text-emerald-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Executive Summary
            </button>
          </div>

          <button
            onClick={handleDownloadPDF}
            className="flex items-center space-x-1.5 px-3 py-2 bg-white border border-slate-200 hover:border-emerald-300 text-slate-700 hover:text-emerald-700 rounded-xl text-xs font-bold shadow-xs transition-all"
          >
            <FileText className="w-3.5 h-3.5 text-emerald-600" />
            <span>PDF</span>
          </button>

          <button
            onClick={handleDownloadXLSX}
            className="flex items-center space-x-1.5 px-3 py-2 bg-white border border-slate-200 hover:border-emerald-300 text-slate-700 hover:text-emerald-700 rounded-xl text-xs font-bold shadow-xs transition-all"
          >
            <FileText className="w-3.5 h-3.5 text-emerald-600" />
            <span>XLSX</span>
          </button>

          <button
            onClick={handlePrint}
            className="flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-bold shadow-sm hover:bg-emerald-700 transition-all"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Print / Export</span>
          </button>
        </div>
      </div>

      {/* Report Container */}
      {reportType === 'local_seo' && reportData && (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 sm:p-12 space-y-8 print:p-0 print:border-none print:shadow-none shadow-sm">
          {/* Header Banner */}
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6 border-b border-slate-200 pb-8">
            <div className="space-y-1">
              <span className="text-[10px] font-black uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                Official Local SEO Intelligence Audit
              </span>
              <h2 className="text-3xl font-black text-slate-900 mt-2">
                {profile?.business_name || activeProject.name}
              </h2>
              <div className="text-xs text-slate-500 font-mono">
                {profile?.website || activeProject.domain} • {profile?.primary_category || 'Local Business'}
              </div>
              <div className="text-xs text-slate-600 pt-1">
                📍 {profile?.primary_address || 'Address pending'}, {profile?.city || ''} {profile?.state || ''} {profile?.postal_code || ''}
              </div>
            </div>

            <div className="text-left sm:text-right space-y-1 text-xs text-slate-500 bg-slate-50 p-4 rounded-xl border border-slate-200 shrink-0">
              <div className="font-bold text-slate-800">LocalLift SEO Platform</div>
              <div>Report Date: {new Date(reportData.generated_at).toLocaleDateString()}</div>
              <div>Audit Checkpoints: {audit?.total_findings || 0} items</div>
              <div className="pt-1 flex items-center sm:justify-end space-x-1 text-emerald-700 font-bold">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Evidence-Backed Truth Engine</span>
              </div>
            </div>
          </div>

          {/* Top KPI Metrics Strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Local SEO Health</div>
              <div className={`text-3xl font-black mt-1 ${
                audit?.overall_score !== null && audit?.overall_score !== undefined
                  ? audit.overall_score >= 80 ? 'text-emerald-600' : audit.overall_score >= 50 ? 'text-amber-600' : 'text-rose-600'
                  : 'text-slate-400'
              }`}>
                {audit?.overall_score !== null && audit?.overall_score !== undefined ? `${audit.overall_score}/100` : 'N/A'}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">20 Categories Audited</div>
            </div>

            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">5x5 Geo Visibility</div>
              <div className={`text-3xl font-black mt-1 ${
                geo?.local_visibility_pct !== null && geo?.local_visibility_pct !== undefined
                  ? geo.local_visibility_pct >= 60 ? 'text-emerald-600' : 'text-amber-600'
                  : 'text-slate-400'
              }`}>
                {geo?.local_visibility_pct !== null && geo?.local_visibility_pct !== undefined ? `${geo.local_visibility_pct}%` : 'N/A'}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                {geo?.keyword ? `for "${geo.keyword}"` : 'Awaiting Geo scan'}
              </div>
            </div>

            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Tracked Keywords</div>
              <div className="text-3xl font-black text-slate-800 mt-1">
                {reportData.keywords?.length || 0}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                {reportData.keywords?.filter((k: any) => k.current_rank && k.current_rank <= 3).length || 0} in Top 3 Pack
              </div>
            </div>

            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Customer Reviews</div>
              <div className="text-3xl font-black text-slate-800 mt-1">
                {reportData.reputation?.total_reviews || 0}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                {reportData.reputation?.average_rating ? `★ ${reportData.reputation.average_rating} Avg Rating` : 'No rating data'}
              </div>
            </div>
          </div>

          {/* Executive Narrative */}
          <div className="space-y-2 p-5 bg-emerald-50/50 rounded-xl border border-emerald-200/60">
            <h3 className="text-xs font-black text-emerald-900 uppercase tracking-wider flex items-center space-x-1.5">
              <Award className="w-4 h-4 text-emerald-600" />
              <span>Executive Performance Assessment</span>
            </h3>
            <p className="text-xs text-slate-700 leading-relaxed font-medium">
              {reportData.executive_summary}
            </p>
          </div>

          {/* 20-Category Score Overview */}
          {audit?.category_scores && Object.keys(audit.category_scores).length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
                <Layers className="w-4 h-4 text-emerald-600" />
                <span>20-Category Audit Framework Breakdown</span>
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(audit.category_scores).map(([catKey, rawScore]: [string, any]) => {
                  const score: number | null = typeof rawScore === 'object' && rawScore !== null ? (rawScore.score ?? null) : (typeof rawScore === 'number' ? rawScore : null);
                  return (
                    <div key={catKey} className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold text-slate-700 capitalize">
                          {catKey.replace(/_/g, ' ')}
                        </span>
                        <span className={`text-xs font-black ${
                          score === null ? 'text-slate-500' : score >= 80 ? 'text-emerald-600' : score >= 50 ? 'text-amber-600' : 'text-rose-600'
                        }`}>
                          {score !== null ? `${score}%` : '—'}
                        </span>
                      </div>
                      <div className="w-full bg-slate-200 h-1.5 rounded-full mt-2 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            score === null ? 'bg-slate-300' : score >= 80 ? 'bg-emerald-500' : score >= 50 ? 'bg-amber-500' : 'bg-rose-500'
                          }`}
                          style={{ width: `${score !== null ? score : 0}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Priority Findings & Action Items */}
          {reportData.priority_findings && reportData.priority_findings.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>Priority Action Items & Findings</span>
              </h3>
              <div className="space-y-2">
                {reportData.priority_findings.map((f: any) => (
                  <div key={f.id} className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                          f.severity === 'CRITICAL' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800'
                        }`}>
                          {f.severity}
                        </span>
                        <span className="text-xs font-bold text-slate-900">{f.title}</span>
                      </div>
                      <span className="text-[10px] text-slate-400 font-medium capitalize">{f.category_name}</span>
                    </div>
                    {f.evidence && (
                      <p className="text-xs text-slate-600">
                        <span className="font-semibold text-slate-700">Evidence:</span> {f.evidence}
                      </p>
                    )}
                    {f.recommended_action && (
                      <p className="text-xs text-emerald-800 font-medium bg-emerald-50 p-2 rounded-lg border border-emerald-200/50">
                        <span className="font-bold">Recommended Action:</span> {f.recommended_action}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 90-Day Action Roadmap */}
          {reportData.action_plan && (
            <div className="space-y-3">
              <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
                <Calendar className="w-4 h-4 text-purple-600" />
                <span>90-Day Local SEO Implementation Roadmap</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2">
                  <div className="text-xs font-black text-purple-700 uppercase tracking-wider">Month 1</div>
                  <div className="text-xs font-bold text-slate-800">{reportData.action_plan.month_1?.focus}</div>
                  <ul className="space-y-1.5 text-xs text-slate-600 list-disc list-inside">
                    {reportData.action_plan.month_1?.actions?.map((act: string, i: number) => (
                      <li key={i}>{act}</li>
                    ))}
                  </ul>
                </div>

                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2">
                  <div className="text-xs font-black text-purple-700 uppercase tracking-wider">Month 2</div>
                  <div className="text-xs font-bold text-slate-800">{reportData.action_plan.month_2?.focus}</div>
                  <ul className="space-y-1.5 text-xs text-slate-600 list-disc list-inside">
                    {reportData.action_plan.month_2?.actions?.map((act: string, i: number) => (
                      <li key={i}>{act}</li>
                    ))}
                  </ul>
                </div>

                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2">
                  <div className="text-xs font-black text-purple-700 uppercase tracking-wider">Month 3</div>
                  <div className="text-xs font-bold text-slate-800">{reportData.action_plan.month_3?.focus}</div>
                  <ul className="space-y-1.5 text-xs text-slate-600 list-disc list-inside">
                    {reportData.action_plan.month_3?.actions?.map((act: string, i: number) => (
                      <li key={i}>{act}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Provenance & Methodology Footer */}
          <div className="border-t border-slate-200 pt-6 text-[10px] text-slate-400 space-y-1">
            <div className="font-bold text-slate-600">Methodology & Evidence Provenance:</div>
            <div>
              LocalLift calculates metrics strictly from live API queries, verified HTML document inspection, and localized GPS SERP scans. Zero synthetic or hardcoded metrics are utilized in this report.
            </div>
          </div>
        </div>
      )}

      {/* Executive Report Mode */}
      {reportType === 'executive' && executiveData && (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 sm:p-10 space-y-8 print:p-0 print:border-none print:shadow-none shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 border-b border-slate-200 pb-6">
            <div>
              <div className="text-[10px] font-black text-purple-700 uppercase tracking-wider">
                Local SEO Monthly Performance Review
              </div>
              <h2 className="text-2xl font-black text-slate-900 mt-1">{executiveData.project?.name || activeProject.name}</h2>
              <div className="text-xs text-slate-500 font-mono mt-0.5">{executiveData.project?.domain || activeProject.domain}</div>
            </div>

            <div className="text-left sm:text-right text-xs text-slate-500">
              <div className="font-bold text-slate-800">Generated for: {activeProject.name}</div>
              <div>Date: {new Date(executiveData.generated_at).toLocaleDateString()}</div>
              <div>Evaluation Period: Last 30 Days</div>
            </div>
          </div>

          <div className="p-4 bg-emerald-50/50 rounded-xl border border-emerald-200/60">
            <p className="text-xs text-slate-700 leading-relaxed font-medium">{executiveData.executive_summary}</p>
          </div>

          {executiveData.next_month_recommendations && (
            <div className="space-y-3">
              <h3 className="text-xs font-black text-slate-900 uppercase tracking-wider">Recommended Next Actions</h3>
              <div className="space-y-2">
                {executiveData.next_month_recommendations.map((rec: string, idx: number) => (
                  <div key={idx} className="flex items-start space-x-2 text-xs text-slate-700 p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span>{rec}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

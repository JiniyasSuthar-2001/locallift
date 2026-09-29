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
  ChevronRight,
  ChevronDown,
  Search,
  Filter,
  Globe,
  Activity,
  Download,
  Users,
  Eye,
  Crosshair,
  TrendingUp,
  Tag
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

  // Findings UI filters
  const [findingSearch, setFindingSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [expandedSections, setExpandedSections] = useState<{ [key: string]: boolean }>({
    findings: true,
    geogrid: true,
    website: true,
    keywords: true,
    reputation: true,
    citations: true,
    competitors: true,
    schema_nap: true,
    content_gaps: true,
    action_plan: true
  });

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const fetchReports = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const [localResp, execResp] = await Promise.allSettled([
        api.get(`/reports/${activeProject.id}/local-seo/snapshot`),
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
      const response = await api.get(`/reports/${activeProject.id}/local-seo/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      const domainClean = (activeProject.domain || 'business').replace(/[^a-zA-Z0-9.-]/g, '_');
      link.setAttribute('download', `LocalSEO_Intelligence_Audit_${domainClean}_${new Date().toISOString().slice(0, 10)}.pdf`);
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
      const response = await api.get(`/reports/${activeProject.id}/local-seo/xlsx`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      const domainClean = (activeProject.domain || 'business').replace(/[^a-zA-Z0-9.-]/g, '_');
      link.setAttribute('download', `LocalSEO_Intelligence_Audit_${domainClean}_${new Date().toISOString().slice(0, 10)}.xlsx`);
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
  const websiteAudit = reportData?.website_audit;
  const provenance = reportData?.provenance || {};
  const coverage = reportData?.coverage || {};
  const allFindings = audit?.findings || [];

  // Filtered findings
  const filteredFindings = allFindings.filter((f: any) => {
    const matchesCat = selectedCategory === 'all' || f.category_key === selectedCategory;
    const matchesStatus = selectedStatus === 'all' || f.status === selectedStatus;
    const matchesSearch = !findingSearch ||
      f.title?.toLowerCase().includes(findingSearch.toLowerCase()) ||
      f.evidence?.toLowerCase().includes(findingSearch.toLowerCase()) ||
      f.category_name?.toLowerCase().includes(findingSearch.toLowerCase());
    return matchesCat && matchesStatus && matchesSearch;
  });

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-16">
      {/* Header Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <FileText className="w-6 h-6 text-emerald-600" />
            <span>Local SEO Intelligence & Audit Report</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Authoritative run-resolved client deliverable across Central Intelligence Scans and standalone module runs.
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
            className="flex items-center space-x-1.5 px-3 py-2 bg-white border border-slate-200 hover:border-emerald-300 text-slate-700 hover:text-emerald-700 rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-emerald-600" />
            <span>PDF</span>
          </button>

          <button
            onClick={handleDownloadXLSX}
            className="flex items-center space-x-1.5 px-3 py-2 bg-white border border-slate-200 hover:border-emerald-300 text-slate-700 hover:text-emerald-700 rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-emerald-600" />
            <span>XLSX</span>
          </button>

          <button
            onClick={handlePrint}
            className="flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 text-white rounded-xl text-xs font-bold shadow-sm hover:bg-emerald-700 transition-all cursor-pointer"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Print</span>
          </button>
        </div>
      </div>

      {/* Report Snapshot Provenance & Coverage Banner */}
      {reportData && (
        <div className="bg-slate-900 text-white rounded-2xl p-5 shadow-lg border border-slate-800 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-black uppercase tracking-wider text-emerald-400">Authoritative Report Snapshot</span>
            </div>
            <div className="text-[11px] text-slate-400">
              Data Resolved As Of: <strong className="text-slate-200">{new Date(reportData.data_as_of).toLocaleString()}</strong>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-2.5 bg-slate-800/60 rounded-xl border border-slate-700/50">
              <div className="text-[10px] text-slate-400 font-medium">Central Scan Source</div>
              <div className="font-bold text-white mt-0.5">
                {reportData.central_scan?.id ? `Scan #${reportData.central_scan.id} (${reportData.central_scan.status})` : 'Standalone Live'}
              </div>
            </div>

            <div className="p-2.5 bg-slate-800/60 rounded-xl border border-slate-700/50">
              <div className="text-[10px] text-slate-400 font-medium">Standalone Overrides</div>
              <div className="font-bold text-emerald-400 mt-0.5">
                {reportData.overrides_summary?.total_overrides || 0} module(s) updated
              </div>
            </div>

            <div className="p-2.5 bg-slate-800/60 rounded-xl border border-slate-700/50">
              <div className="text-[10px] text-slate-400 font-medium">Audit Checkpoints</div>
              <div className="font-bold text-white mt-0.5">
                {coverage.audit_findings_count || 0} verified findings
              </div>
            </div>

            <div className="p-2.5 bg-slate-800/60 rounded-xl border border-slate-700/50">
              <div className="text-[10px] text-slate-400 font-medium">5x5 Geo-Grid Pins</div>
              <div className="font-bold text-white mt-0.5">
                {coverage.geogrid_points_count || 0} coordinate points
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Intelligence Audit Report */}
      {reportType === 'local_seo' && reportData && (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 sm:p-12 space-y-10 print:p-0 print:border-none print:shadow-none shadow-sm">
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
              <div>Report Date: {new Date(reportData.report_generated_at).toLocaleDateString()}</div>
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
              {reportData.executive_summary?.narrative || reportData.executive_summary}
            </p>
          </div>

          {/* SECTION 1: 20-Category Audit Framework Breakdown */}
          {audit?.category_breakdowns && audit.category_breakdowns.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
                  <Layers className="w-4 h-4 text-emerald-600" />
                  <span>20-Category Audit Framework Breakdown</span>
                </h3>
                <span className="text-[10px] font-bold text-slate-400">
                  Source: {provenance.local_audit?.source_type || 'Local Audit'} #{provenance.local_audit?.source_run_id || 'N/A'}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                {audit.category_breakdowns.map((cb: any) => (
                  <div key={cb.category_key} className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-bold text-slate-700">
                        {cb.category_name}
                      </span>
                      <span className={`text-xs font-black ${
                        cb.score === null ? 'text-slate-500' : cb.score >= 80 ? 'text-emerald-600' : cb.score >= 50 ? 'text-amber-600' : 'text-rose-600'
                      }`}>
                        {cb.score !== null ? `${cb.score}%` : '—'}
                      </span>
                    </div>
                    <div className="w-full bg-slate-200 h-1.5 rounded-full mt-2 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          cb.score === null ? 'bg-slate-300' : cb.score >= 80 ? 'bg-emerald-500' : cb.score >= 50 ? 'bg-amber-500' : 'bg-rose-500'
                        }`}
                        style={{ width: `${cb.score !== null ? cb.score : 0}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1.5">
                      <span>{cb.total_checks} checks</span>
                      <span className="text-emerald-600 font-medium">{cb.passed_checks} passed</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* SECTION 2: Complete Local SEO Audit Findings */}
          <div className="space-y-4">
            <div
              onClick={() => toggleSection('findings')}
              className="flex items-center justify-between border-b border-slate-200 pb-2 cursor-pointer select-none"
            >
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-emerald-600" />
                <h3 className="text-sm font-black text-slate-900">
                  Complete Local SEO Audit Findings ({allFindings.length} total checkpoints)
                </h3>
              </div>
              <div className="flex items-center space-x-2 text-xs font-bold text-slate-500">
                <span>{expandedSections.findings ? 'Collapse' : 'Expand'}</span>
                {expandedSections.findings ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </div>
            </div>

            {expandedSections.findings && (
              <div className="space-y-4">
                {/* Search & Filter Controls */}
                <div className="flex flex-wrap items-center gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <div className="relative flex-1 min-w-[200px]">
                    <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      placeholder="Search findings by title, evidence, or category..."
                      value={findingSearch}
                      onChange={e => setFindingSearch(e.target.value)}
                      className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-emerald-500"
                    />
                  </div>

                  <select
                    value={selectedCategory}
                    onChange={e => setSelectedCategory(e.target.value)}
                    className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium focus:outline-none"
                  >
                    <option value="all">All 20 Categories</option>
                    {(audit?.category_breakdowns || []).map((cb: any) => (
                      <option key={cb.category_key} value={cb.category_key}>{cb.category_name}</option>
                    ))}
                  </select>

                  <select
                    value={selectedStatus}
                    onChange={e => setSelectedStatus(e.target.value)}
                    className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium focus:outline-none"
                  >
                    <option value="all">All Statuses</option>
                    <option value="FAIL">FAIL / Critical</option>
                    <option value="PARTIAL">WARN / Partial</option>
                    <option value="PASS">PASS</option>
                    <option value="NOT_VERIFIED">Not Verified</option>
                  </select>
                </div>

                {/* Findings Table */}
                <div className="border border-slate-200 rounded-xl overflow-hidden">
                  <div className="overflow-x-auto max-h-[500px]">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead className="bg-slate-900 text-white sticky top-0 z-10 text-[11px] font-bold">
                        <tr>
                          <th className="p-3">Category</th>
                          <th className="p-3">Checkpoint</th>
                          <th className="p-3">Status</th>
                          <th className="p-3">Severity</th>
                          <th className="p-3">Evidence & Recommendation</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {filteredFindings.length > 0 ? (
                          filteredFindings.map((f: any) => (
                            <tr key={f.id} className="hover:bg-slate-50/80 transition-colors">
                              <td className="p-3 font-semibold text-slate-800 whitespace-nowrap align-top">
                                {f.category_name}
                              </td>
                              <td className="p-3 font-medium text-slate-900 align-top max-w-[220px]">
                                {f.title}
                              </td>
                              <td className="p-3 align-top whitespace-nowrap">
                                <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                                  f.status === 'PASS'
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : f.status === 'FAIL'
                                    ? 'bg-rose-100 text-rose-800'
                                    : 'bg-amber-100 text-amber-800'
                                }`}>
                                  {f.status}
                                </span>
                              </td>
                              <td className="p-3 align-top text-slate-600 font-bold whitespace-nowrap">
                                {f.severity}
                              </td>
                              <td className="p-3 align-top text-slate-600 space-y-1">
                                {f.evidence && <div><strong>Evidence:</strong> {f.evidence}</div>}
                                {f.recommendation && (
                                  <div className="text-emerald-800 font-medium bg-emerald-50 p-1.5 rounded border border-emerald-200/40">
                                    <strong>Action:</strong> {f.recommendation}
                                  </div>
                                )}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={5} className="p-6 text-center text-slate-400">
                              No findings match the selected filter.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* SECTION 3: 5x5 Geo-Grid Rankings & Competitors */}
          <div className="space-y-4">
            <div
              onClick={() => toggleSection('geogrid')}
              className="flex items-center justify-between border-b border-slate-200 pb-2 cursor-pointer select-none"
            >
              <div className="flex items-center space-x-2">
                <MapPin className="w-4 h-4 text-emerald-600" />
                <h3 className="text-sm font-black text-slate-900">
                  5x5 Geo-Grid Rankings & Matrix Points ({geo?.points?.length || 0} Pins)
                </h3>
              </div>
              <div className="flex items-center space-x-2 text-xs font-bold text-slate-500">
                <span className="text-[10px] text-slate-400 font-normal">
                  Source: {provenance.geo?.source_type} #{provenance.geo?.source_run_id}
                </span>
                {expandedSections.geogrid ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </div>
            </div>

            {expandedSections.geogrid && (
              <div className="space-y-4">
                {/* Geo-Grid Points Table */}
                <div className="border border-slate-200 rounded-xl overflow-hidden max-h-[350px] overflow-y-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead className="bg-slate-900 text-white sticky top-0 z-10 text-[11px] font-bold">
                      <tr>
                        <th className="p-2.5">#</th>
                        <th className="p-2.5">Area Name</th>
                        <th className="p-2.5">Coordinates</th>
                        <th className="p-2.5">Rank</th>
                        <th className="p-2.5">Matched Business</th>
                        <th className="p-2.5">Distance</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {(geo?.points || []).map((pt: any) => (
                        <tr key={pt.id || pt.point_number} className="hover:bg-slate-50">
                          <td className="p-2.5 font-bold text-slate-800">{pt.point_number + 1}</td>
                          <td className="p-2.5 font-medium text-slate-900">{pt.area_name}</td>
                          <td className="p-2.5 text-slate-500 font-mono text-[10px]">
                            {pt.latitude?.toFixed(4)}, {pt.longitude?.toFixed(4)}
                          </td>
                          <td className="p-2.5 font-black">
                            <span className={`px-2 py-0.5 rounded text-[10px] ${
                              pt.rank !== null && pt.rank <= 3
                                ? 'bg-emerald-100 text-emerald-800'
                                : pt.rank !== null && pt.rank <= 10
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-slate-100 text-slate-600'
                            }`}>
                              {pt.rank !== null ? `#${pt.rank}` : '20+'}
                            </span>
                          </td>
                          <td className="p-2.5 text-slate-700">{pt.matched_business || pt.matched_domain || 'Not in Local Pack'}</td>
                          <td className="p-2.5 text-slate-500">{pt.distance_km?.toFixed(1)} km {pt.direction}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Geo-Grid Competitors Table */}
                {geo?.competitors && geo.competitors.length > 0 && (
                  <div className="space-y-2 pt-2">
                    <h4 className="text-xs font-black text-slate-800 uppercase tracking-wider">
                      Geo-Grid Competitor Ranking Pins ({geo.competitors.length} observations)
                    </h4>
                    <div className="border border-slate-200 rounded-xl overflow-hidden max-h-[250px] overflow-y-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead className="bg-slate-100 text-slate-700 sticky top-0 text-[10px] font-bold">
                          <tr>
                            <th className="p-2">Pin Area</th>
                            <th className="p-2">Competitor Name</th>
                            <th className="p-2">Rank</th>
                            <th className="p-2">Domain</th>
                            <th className="p-2">Distance</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {geo.competitors.slice(0, 50).map((gc: any, idx: number) => (
                            <tr key={idx} className="hover:bg-slate-50">
                              <td className="p-2 text-slate-700">{gc.area_name}</td>
                              <td className="p-2 font-bold text-slate-900">{gc.competitor_name}</td>
                              <td className="p-2 font-black text-emerald-700">#{gc.rank}</td>
                              <td className="p-2 text-slate-500">{gc.domain || '—'}</td>
                              <td className="p-2 text-slate-400">{gc.distance_km ? `${gc.distance_km.toFixed(1)} km` : '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* SECTION 4: Technical Website Audit & Pages */}
          <div className="space-y-4">
            <div
              onClick={() => toggleSection('website')}
              className="flex items-center justify-between border-b border-slate-200 pb-2 cursor-pointer select-none"
            >
              <div className="flex items-center space-x-2">
                <Globe className="w-4 h-4 text-emerald-600" />
                <h3 className="text-sm font-black text-slate-900">
                  Technical Website Audit & Analyzed Pages ({websiteAudit?.pages?.length || 0} Pages)
                </h3>
              </div>
              <div className="flex items-center space-x-2 text-xs font-bold text-slate-500">
                <span className="text-[10px] text-slate-400 font-normal">
                  Source: {provenance.website_audit?.source_type} #{provenance.website_audit?.source_run_id}
                </span>
                {expandedSections.website ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </div>
            </div>

            {expandedSections.website && (
              <div className="space-y-4">
                {websiteAudit?.pagespeed && (
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <div className="text-[10px] font-bold text-slate-400 uppercase">Google PageSpeed Insights (Mobile)</div>
                      <div className="text-xl font-black text-emerald-600 mt-0.5">
                        {websiteAudit.pagespeed.performance_score !== null ? `${websiteAudit.pagespeed.performance_score}/100` : 'N/A'}
                      </div>
                    </div>
                    <div className="flex items-center gap-6 text-xs text-slate-600">
                      <div><strong>FCP:</strong> {websiteAudit.pagespeed.fcp || 'N/A'}</div>
                      <div><strong>LCP:</strong> {websiteAudit.pagespeed.lcp || 'N/A'}</div>
                      <div><strong>CLS:</strong> {websiteAudit.pagespeed.cls || 'N/A'}</div>
                    </div>
                  </div>
                )}

                <div className="border border-slate-200 rounded-xl overflow-hidden max-h-[300px] overflow-y-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead className="bg-slate-900 text-white sticky top-0 text-[11px] font-bold">
                      <tr>
                        <th className="p-2.5">URL</th>
                        <th className="p-2.5">HTTP</th>
                        <th className="p-2.5">H1 Heading</th>
                        <th className="p-2.5">Words</th>
                        <th className="p-2.5">Speed</th>
                        <th className="p-2.5">Indexable</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {(websiteAudit?.pages || []).map((p: any) => (
                        <tr key={p.id} className="hover:bg-slate-50">
                          <td className="p-2.5 text-slate-800 font-mono text-[10px] max-w-[250px] truncate">{p.url}</td>
                          <td className="p-2.5 font-bold text-slate-700">{p.status_code}</td>
                          <td className="p-2.5 text-slate-900 font-medium max-w-[200px] truncate">{p.h1 || '—'}</td>
                          <td className="p-2.5 text-slate-600">{p.word_count}</td>
                          <td className="p-2.5 text-slate-500">{p.load_time_ms}ms</td>
                          <td className="p-2.5">
                            <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${p.is_indexable ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>
                              {p.is_indexable ? 'INDEXABLE' : 'NOINDEX'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* SECTION 5: Tracked Keywords & Rankings */}
          <div className="space-y-4">
            <div
              onClick={() => toggleSection('keywords')}
              className="flex items-center justify-between border-b border-slate-200 pb-2 cursor-pointer select-none"
            >
              <div className="flex items-center space-x-2">
                <TrendingUp className="w-4 h-4 text-emerald-600" />
                <h3 className="text-sm font-black text-slate-900">
                  Tracked Local Keywords ({reportData.keywords?.length || 0} Terms)
                </h3>
              </div>
              <div className="flex items-center space-x-2 text-xs font-bold text-slate-500">
                <span className="text-[10px] text-slate-400 font-normal">
                  Source: {provenance.rankings?.source_type} #{provenance.rankings?.source_run_id}
                </span>
                {expandedSections.keywords ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </div>
            </div>

            {expandedSections.keywords && (
              <div className="border border-slate-200 rounded-xl overflow-hidden max-h-[300px] overflow-y-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-900 text-white sticky top-0 text-[11px] font-bold">
                    <tr>
                      <th className="p-2.5">Keyword</th>
                      <th className="p-2.5">Location</th>
                      <th className="p-2.5">Current Rank</th>
                      <th className="p-2.5">Previous</th>
                      <th className="p-2.5">SERP Type</th>
                      <th className="p-2.5">Intent</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {(reportData.keywords || []).map((k: any) => (
                      <tr key={k.id} className="hover:bg-slate-50">
                        <td className="p-2.5 font-bold text-slate-900">{k.keyword}</td>
                        <td className="p-2.5 text-slate-600">{k.target_location || 'Local Area'}</td>
                        <td className="p-2.5 font-black text-emerald-700">
                          {k.current_rank ? `#${k.current_rank}` : 'Unranked'}
                        </td>
                        <td className="p-2.5 text-slate-400">{k.previous_rank ? `#${k.previous_rank}` : '—'}</td>
                        <td className="p-2.5 text-slate-600">{k.serp_type}</td>
                        <td className="p-2.5 text-slate-500">{k.search_intent}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* SECTION 6: Customer Reviews & Citations */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Reviews */}
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
                  <Star className="w-4 h-4 text-amber-500" />
                  <span>Reviews ({reportData.reputation?.reviews?.length || 0})</span>
                </h3>
              </div>
              <div className="border border-slate-200 rounded-xl overflow-hidden max-h-[300px] overflow-y-auto divide-y divide-slate-100">
                {(reportData.reputation?.reviews || []).map((r: any) => (
                  <div key={r.id} className="p-3 hover:bg-slate-50 space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-slate-900">{r.author_name}</span>
                      <span className="text-amber-500 font-black">{'★'.repeat(r.rating || 5)}</span>
                    </div>
                    <p className="text-xs text-slate-600 line-clamp-2">{r.review_text || 'No comment text.'}</p>
                    <div className="text-[10px] text-slate-400 flex items-center justify-between">
                      <span>{r.source}</span>
                      <span>{r.review_date?.slice(0, 10)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Citations */}
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
                  <BookOpen className="w-4 h-4 text-emerald-600" />
                  <span>Citations ({reportData.citations?.listings?.length || 0})</span>
                </h3>
              </div>
              <div className="border border-slate-200 rounded-xl overflow-hidden max-h-[300px] overflow-y-auto divide-y divide-slate-100">
                {(reportData.citations?.listings || []).map((c: any) => (
                  <div key={c.id} className="p-3 hover:bg-slate-50 flex items-center justify-between text-xs">
                    <div>
                      <div className="font-bold text-slate-900">{c.directory_name}</div>
                      <div className="text-[10px] text-slate-400 font-mono truncate max-w-[200px]">{c.listing_url || c.domain}</div>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${
                      c.nap_status === 'consistent' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                    }`}>
                      {c.nap_status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* SECTION 7: 90-Day Action Roadmap */}
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
              <div>Data As Of: {executiveData.data_as_of ? new Date(executiveData.data_as_of).toLocaleDateString() : new Date().toLocaleDateString()}</div>
              <div>Evaluation Period: Authoritative Resolved Snapshot</div>
            </div>
          </div>

          <div className="p-4 bg-emerald-50/50 rounded-xl border border-emerald-200/60">
            <p className="text-xs text-slate-700 leading-relaxed font-medium">{executiveData.executive_summary}</p>
          </div>

          {/* KPI Strip in Executive Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
              <div className="text-[10px] font-bold text-slate-400 uppercase">Health Score</div>
              <div className="text-2xl font-black text-emerald-600 mt-1">{executiveData.project?.health_score || 0}/100</div>
            </div>
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
              <div className="text-[10px] font-bold text-slate-400 uppercase">Geo Visibility</div>
              <div className="text-2xl font-black text-emerald-600 mt-1">{executiveData.metrics?.local_visibility_pct || 0}%</div>
            </div>
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
              <div className="text-[10px] font-bold text-slate-400 uppercase">Keywords in Pack</div>
              <div className="text-2xl font-black text-slate-800 mt-1">{executiveData.metrics?.top_3_keywords || 0}</div>
            </div>
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
              <div className="text-[10px] font-bold text-slate-400 uppercase">Customer Reviews</div>
              <div className="text-2xl font-black text-slate-800 mt-1">{executiveData.metrics?.total_reviews || 0}</div>
            </div>
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

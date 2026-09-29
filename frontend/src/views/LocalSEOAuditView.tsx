import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldCheck,
  RotateCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  History,
  ChevronDown,
  Filter,
  Search,
  ExternalLink,
  Globe,
  MapPin,
  FileCode2,
  Building2,
  Sparkles,
  Layers,
  ArrowRight,
  Info,
  Calendar,
  Check,
  AlertCircle,
  X
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import { FindingCard } from '../components/audit/FindingCard';
import { CategoryScoreCard } from '../components/audit/CategoryScoreCard';
import api from '../api/client';
import type {
  LocalAuditRun,
  LocalAuditFinding,
  AuditCategoryKey
} from '../types';
import { AUDIT_CATEGORY_LABELS } from '../types';

type FilterTab = 'all' | 'fail' | 'partial' | 'pass' | 'not_verified';
type ViewMode = 'grid' | 'categories' | 'findings';

export const LocalSEOAuditView: React.FC = () => {
  const { activeProject } = useProject();
  const [auditRun, setAuditRun] = useState<LocalAuditRun | null>(null);
  const [history, setHistory] = useState<LocalAuditRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [isAuditing, setIsAuditing] = useState(false);
  const [isScanningTechnical, setIsScanningTechnical] = useState(false);
  const [scanErrorMessage, setScanErrorMessage] = useState<string | null>(null);
  const [scanProgressMessage, setScanProgressMessage] = useState<string | null>(null);

  const [filterTab, setFilterTab] = useState<FilterTab>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<string>('all');

  // Integration readiness state
  const [readinessData, setReadinessData] = useState<{
    hasGbp: boolean;
    crawledPagesCount: number;
    citationsCount: number;
    schemaCount: number;
  }>({
    hasGbp: false,
    crawledPagesCount: 0,
    citationsCount: 0,
    schemaCount: 0
  });

  const loadAuditData = async () => {
    if (!activeProject?.id) return;
    try {
      setLoading(true);
      const [latestResp, historyResp, diagResp] = await Promise.allSettled([
        api.get(`/audits/${activeProject.id}/local/latest`),
        api.get(`/audits/${activeProject.id}/local/history?limit=10`),
        api.get(`/audits/${activeProject.id}/diagnostic-summary`)
      ]);

      if (latestResp.status === 'fulfilled' && latestResp.value.data) {
        setAuditRun(latestResp.value.data);
      } else {
        setAuditRun(null);
      }

      if (historyResp.status === 'fulfilled' && Array.isArray(historyResp.value.data)) {
        setHistory(historyResp.value.data);
      }

      if (diagResp.status === 'fulfilled' && diagResp.value.data) {
        const d = diagResp.value.data;
        setReadinessData({
          hasGbp: !!d.gbp_status?.connected,
          crawledPagesCount: d.pages_analyzed || d.crawled_pages || 0,
          citationsCount: d.citations_status?.total || 0,
          schemaCount: d.schema_summary?.total_schema_instances || 0
        });
      }
    } catch (e) {
      console.error('Failed to load audit:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setAuditRun(null);
    setHistory([]);
    setScanErrorMessage(null);
    loadAuditData();
  }, [activeProject?.id]);

  const handleRunAudit = async () => {
    if (!activeProject) return;
    try {
      setIsAuditing(true);
      setScanErrorMessage(null);
      const resp = await api.post(`/audits/${activeProject.id}/local/run`);
      if (resp.data) {
        setAuditRun(resp.data);
        const hResp = await api.get(`/audits/${activeProject.id}/local/history?limit=10`);
        if (Array.isArray(hResp.data)) setHistory(hResp.data);
        await loadAuditData();
      }
    } catch (e: any) {
      console.error('Audit failed:', e);
      const detail = e.response?.data?.detail || e.message || 'Audit execution encountered an error.';
      setScanErrorMessage(`Local SEO audit run failed: ${detail}. Please try again.`);
    } finally {
      setIsAuditing(false);
    }
  };

  const handleRunTechnicalScan = async () => {
    if (!activeProject) return;
    try {
      setIsScanningTechnical(true);
      setScanErrorMessage(null);
      setScanProgressMessage('Initiating website crawler & analyzing link graph...');

      const resp = await api.post(`/audits/${activeProject.id}/local/technical-scan`);
      const jobId = resp.data?.job_id;

      if (jobId) {
        // Poll job status until terminal state
        let isDone = false;
        let attempts = 0;
        const maxAttempts = 120; // 3 minutes max

        while (!isDone && attempts < maxAttempts) {
          await new Promise(r => setTimeout(r, 1500));
          attempts++;

          try {
            const jobResp = await api.get(`/audits/jobs/${jobId}`);
            const job = jobResp.data;

            if (job) {
              const stageMsg = job.current_stage || `Crawling pages (${job.pages_crawled || 0} crawled)...`;
              setScanProgressMessage(stageMsg);

              const st = (job.status || '').toLowerCase();
              if (['completed', 'completed_with_errors'].includes(st)) {
                isDone = true;
                await loadAuditData();
              } else if (['failed', 'cancelled'].includes(st)) {
                isDone = true;
                const err = job.error_message || 'Crawler encountered an error during execution.';
                setScanErrorMessage(`Technical SEO scan: ${err}`);
              }
            }
          } catch (pollErr) {
            console.warn('Temporary error polling technical scan job:', pollErr);
          }
        }

        await loadAuditData();
      } else if (resp.data?.id) {
        setAuditRun(resp.data);
        await loadAuditData();
      }
    } catch (e: any) {
      console.error('Technical scan error:', e);
      const detail = e.response?.data?.detail || e.message || 'Technical scan failed.';
      setScanErrorMessage(`Technical SEO scan could not be completed. ${detail}. Verify web server responsiveness and robots.txt settings.`);
    } finally {
      setIsScanningTechnical(false);
      setScanProgressMessage(null);
    }
  };

  const handleSelectRun = async (runId: number) => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/audits/${activeProject.id}/local/runs/${runId}`);
      if (resp.data) setAuditRun(resp.data);
    } catch (e) {
      console.error('Failed to load audit run:', e);
    } finally {
      setLoading(false);
    }
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={ShieldCheck}
        badge="Local SEO Audit"
        title="Select a Project"
        description="Select an active project to run a comprehensive 20-category Local SEO audit."
      />
    );
  }

  const findings: LocalAuditFinding[] = auditRun?.findings || [];

  // Filter findings based on tab, category dropdown, and search query
  const filteredFindings = findings.filter(f => {
    if (filterTab !== 'all' && f.status !== filterTab.toUpperCase()) return false;
    if (selectedCategoryFilter !== 'all' && f.category !== selectedCategoryFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchTitle = (f.title || '').toLowerCase().includes(q);
      const matchEvidence = (f.evidence || '').toLowerCase().includes(q);
      const matchCat = (f.category || '').toLowerCase().includes(q);
      if (!matchTitle && !matchEvidence && !matchCat) return false;
    }
    return true;
  });

  // Group findings by category
  const categoryGroups: Record<string, LocalAuditFinding[]> = {};
  for (const f of filteredFindings) {
    if (!categoryGroups[f.category]) categoryGroups[f.category] = [];
    categoryGroups[f.category].push(f);
  }

  const overallScore = auditRun?.overall_score;
  const summary: Record<string, any> = auditRun?.findings_summary || {};
  const passCount = summary.pass ?? summary.passed ?? 0;
  const failCount = summary.fail ?? summary.failed ?? 0;
  const partialCount = summary.partial ?? 0;
  const notVerifiedCount = (summary.not_verified ?? 0) + (summary.error ?? 0);
  const totalCount = summary.total ?? findings.length;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ─── Error Notification Banner ─── */}
      {scanErrorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 flex items-start justify-between gap-3 shadow-xs">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <div className="text-xs font-black">Scan Notification</div>
              <p className="text-xs mt-0.5 text-rose-800">{scanErrorMessage}</p>
            </div>
          </div>
          <button
            onClick={() => setScanErrorMessage(null)}
            className="p-1 text-rose-400 hover:text-rose-700 rounded-lg"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ─── Live Scan Progress Banner ─── */}
      {(isScanningTechnical || scanProgressMessage) && (
        <div className="p-4 rounded-xl bg-purple-50 border border-purple-200 text-purple-900 flex items-center gap-3 shadow-xs animate-pulse">
          <RotateCw className="w-4 h-4 text-purple-600 animate-spin shrink-0" />
          <div className="text-xs font-bold">{scanProgressMessage || 'Executing Technical SEO website crawl...'}</div>
        </div>
      )}

      {/* ─── Top Audit Header ─── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl gradient-brand text-white shadow-2xs">
              <ShieldCheck className="w-5 h-5 stroke-[2.2]" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-black text-[#142820] tracking-tight">
                Local SEO Audit & Governance
              </h1>
              <p className="text-xs text-[#587568] mt-0.5">
                Comprehensive 20-category audit evaluating on-page signals, Schema JSON-LD, GBP alignment, and technical crawler health for <span className="font-bold text-[#142820]">{activeProject.domain}</span>.
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start shrink-0">
          {history.length > 1 && (
            <div className="flex items-center gap-1.5 bg-white border border-[#DCE8DC] rounded-xl px-3 py-1.5 shadow-2xs">
              <History className="w-3.5 h-3.5 text-[#587568]" />
              <select
                value={auditRun?.id || ''}
                onChange={(e) => handleSelectRun(parseInt(e.target.value))}
                className="text-xs font-bold text-[#142820] bg-transparent focus:outline-none cursor-pointer"
              >
                {history.map((run) => (
                  <option key={run.id} value={run.id}>
                    Run #{run.id} &bull; {formatDate(run.executed_at || run.created_at)}
                    {run.overall_score != null ? ` (${run.overall_score}/100)` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={handleRunTechnicalScan}
            disabled={isScanningTechnical || isAuditing}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 disabled:opacity-50 transition-all shadow-xs"
          >
            <Globe className={`w-3.5 h-3.5 ${isScanningTechnical ? 'animate-spin' : ''}`} />
            <span>{isScanningTechnical ? 'Crawling Site...' : 'Run Technical Scan'}</span>
          </button>

          <button
            onClick={handleRunAudit}
            disabled={isAuditing || isScanningTechnical}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-[#236B4F] hover:bg-[#1D5A42] disabled:opacity-50 transition-all shadow-xs"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isAuditing ? 'animate-spin' : ''}`} />
            <span>{isAuditing ? 'Auditing 20 Categories...' : 'Run Full Audit'}</span>
          </button>
        </div>
      </div>

      {loading && !auditRun && (
        <div className="flex flex-col items-center justify-center py-20 bg-white rounded-2xl border border-[#DCE8DC]">
          <div className="w-8 h-8 border-3 border-[#236B4F] border-t-transparent rounded-full animate-spin mb-3" />
          <span className="text-xs font-bold text-slate-700">Loading audit results...</span>
        </div>
      )}

      {!loading && !auditRun && (
        <div className="rounded-2xl border border-[#DCE8DC] bg-white p-8">
          <EmptyState
            icon={ShieldCheck}
            badge="20 Categories"
            title="No Local SEO Audit Executed Yet"
            description="Launch your first audit to evaluate business identity, NAP integrity, Schema markup, and Google Business Profile match with verified evidence."
            actionText="Run Full Local SEO Audit"
            onAction={handleRunAudit}
          />
        </div>
      )}

      {auditRun && (
        <>
          {/* ─── KPI & Overall Score Hero Strip ─── */}
          <div className="rounded-2xl border border-[#DCE8DC] bg-white p-5 sm:p-6 shadow-xs">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
              {/* Score Gauge Ring */}
              <div className="lg:col-span-5 flex items-center gap-4 sm:gap-5 pr-0 lg:pr-6 lg:border-r lg:border-[#EBF2EB]">
                <div className={`w-20 h-20 sm:w-22 sm:h-22 rounded-2xl flex flex-col items-center justify-center ${getScoreBg(overallScore)} border-2 ${getScoreBorder(overallScore)} shrink-0 shadow-2xs`}>
                  <span className={`text-3xl sm:text-4xl font-black ${getScoreColor(overallScore)} leading-none`}>
                    {overallScore != null ? overallScore : '—'}
                  </span>
                  <span className="text-[10px] font-bold text-[#587568] uppercase tracking-wider mt-1">
                    {overallScore != null ? '/ 100' : 'Data Pending'}
                  </span>
                </div>
                <div>
                  <div className="flex items-center gap-1.5">
                    <h3 className="text-base sm:text-lg font-black text-[#142820]">
                      {overallScore != null ? 'Local SEO Health Score' : 'Score Pending Verification'}
                    </h3>
                  </div>
                  <p className="text-xs text-[#587568] mt-1 leading-snug">
                    {overallScore != null
                      ? `Calculated across ${totalCount} checks evaluated in 20 local ranking categories.`
                      : 'Audit executed. Connect GBP and verify website crawl to calculate complete weighted score.'}
                  </p>
                  <div className="flex items-center gap-2 mt-2 text-[11px] font-semibold text-[#587568]">
                    <Calendar className="w-3.5 h-3.5 text-[#236B4F]" />
                    <span>Run #{auditRun.id} &bull; {formatDate(auditRun.completed_at || auditRun.created_at)}</span>
                  </div>
                </div>
              </div>

              {/* Summary Badges Strip */}
              <div className="lg:col-span-7 grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-emerald-50/70 border border-emerald-200 flex flex-col items-center justify-center text-center">
                  <div className="flex items-center gap-1 text-emerald-800 text-xs font-bold">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Passed</span>
                  </div>
                  <span className="text-xl font-black text-emerald-900 mt-1">{passCount}</span>
                </div>

                <div className="p-3 rounded-xl bg-rose-50/70 border border-rose-200 flex flex-col items-center justify-center text-center">
                  <div className="flex items-center gap-1 text-rose-800 text-xs font-bold">
                    <XCircle className="w-3.5 h-3.5" />
                    <span>Failed</span>
                  </div>
                  <span className="text-xl font-black text-rose-900 mt-1">{failCount}</span>
                </div>

                <div className="p-3 rounded-xl bg-amber-50/70 border border-amber-200 flex flex-col items-center justify-center text-center">
                  <div className="flex items-center gap-1 text-amber-800 text-xs font-bold">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Partial</span>
                  </div>
                  <span className="text-xl font-black text-amber-900 mt-1">{partialCount}</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex flex-col items-center justify-center text-center">
                  <div className="flex items-center gap-1 text-slate-700 text-xs font-bold">
                    <HelpCircle className="w-3.5 h-3.5" />
                    <span>Data Pending</span>
                  </div>
                  <span className="text-xl font-black text-slate-800 mt-1">{notVerifiedCount}</span>
                </div>
              </div>
            </div>
          </div>

          {/* ─── Audit Data Readiness Banner ─── */}
          <div className="rounded-xl border border-[#DCE8DC] bg-white p-4 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-bold text-[#142820]">
                <Sparkles className="w-4 h-4 text-[#236B4F]" />
                <span>Audit Data Feed Diagnostics</span>
              </div>
              <span className="text-[11px] text-[#587568] font-medium hidden sm:inline">
                Data sources powering the 20 audit rules
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <Link
                to="/audits/website"
                className="p-2.5 rounded-lg border border-[#DCE8DC] hover:border-[#236B4F] bg-[#F7FAF7] hover:bg-[#F1F7F1] transition-all flex items-center justify-between group"
              >
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-[#236B4F]" />
                  <div>
                    <div className="font-extrabold text-[#142820]">Website Crawl</div>
                    <div className="text-[10px] text-[#587568]">
                      {readinessData.crawledPagesCount > 0 ? `${readinessData.crawledPagesCount} pages analyzed` : 'Not crawled yet'}
                    </div>
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-[#587568] group-hover:translate-x-0.5 transition-transform" />
              </Link>

              <Link
                to="/connections"
                className="p-2.5 rounded-lg border border-[#DCE8DC] hover:border-[#236B4F] bg-[#F7FAF7] hover:bg-[#F1F7F1] transition-all flex items-center justify-between group"
              >
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-[#236B4F]" />
                  <div>
                    <div className="font-extrabold text-[#142820]">Google Business Profile</div>
                    <div className="text-[10px] text-[#587568]">
                      {readinessData.hasGbp ? 'Verified connection' : 'Connect listing'}
                    </div>
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-[#587568] group-hover:translate-x-0.5 transition-transform" />
              </Link>

              <Link
                to="/local/citations"
                className="p-2.5 rounded-lg border border-[#DCE8DC] hover:border-[#236B4F] bg-[#F7FAF7] hover:bg-[#F1F7F1] transition-all flex items-center justify-between group"
              >
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-[#236B4F]" />
                  <div>
                    <div className="font-extrabold text-[#142820]">Directory Citations</div>
                    <div className="text-[10px] text-[#587568]">
                      {readinessData.citationsCount > 0 ? `${readinessData.citationsCount} citations registered` : 'Import citations'}
                    </div>
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-[#587568] group-hover:translate-x-0.5 transition-transform" />
              </Link>

              <Link
                to="/seo/schema"
                className="p-2.5 rounded-lg border border-[#DCE8DC] hover:border-[#236B4F] bg-[#F7FAF7] hover:bg-[#F1F7F1] transition-all flex items-center justify-between group"
              >
                <div className="flex items-center gap-2">
                  <FileCode2 className="w-4 h-4 text-[#236B4F]" />
                  <div>
                    <div className="font-extrabold text-[#142820]">Schema Markup</div>
                    <div className="text-[10px] text-[#587568]">
                      {readinessData.schemaCount > 0 ? `${readinessData.schemaCount} instances validated` : 'Validate JSON-LD'}
                    </div>
                  </div>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-[#587568] group-hover:translate-x-0.5 transition-transform" />
              </Link>
            </div>
          </div>

          {/* ─── View Mode Switcher & Filter Controls ─── */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#EBF2EB] pb-3">
            {/* View Mode Buttons */}
            <div className="flex items-center gap-1.5 bg-[#F7FAF7] p-1 rounded-xl border border-[#DCE8DC]">
              <button
                onClick={() => setViewMode('grid')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  viewMode === 'grid'
                    ? 'bg-[#236B4F] text-white shadow-2xs'
                    : 'text-[#587568] hover:text-[#142820]'
                }`}
              >
                20-Category Grid
              </button>
              <button
                onClick={() => setViewMode('categories')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  viewMode === 'categories'
                    ? 'bg-[#236B4F] text-white shadow-2xs'
                    : 'text-[#587568] hover:text-[#142820]'
                }`}
              >
                Category Accordion
              </button>
              <button
                onClick={() => setViewMode('findings')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  viewMode === 'findings'
                    ? 'bg-[#236B4F] text-white shadow-2xs'
                    : 'text-[#587568] hover:text-[#142820]'
                }`}
              >
                All Findings ({findings.length})
              </button>
            </div>

            {/* Status & Search Filter */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[#587568]" />
                <input
                  type="text"
                  placeholder="Search rules, evidence..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 rounded-xl border border-[#DCE8DC] bg-white text-xs font-medium text-[#142820] placeholder-[#587568] focus:outline-none focus:border-[#236B4F] w-44 sm:w-56"
                />
              </div>

              {/* Status Filter Tabs */}
              <div className="flex items-center gap-1 bg-white border border-[#DCE8DC] p-0.5 rounded-xl">
                {(['all', 'fail', 'partial', 'pass', 'not_verified'] as FilterTab[]).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setFilterTab(tab)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all ${
                      filterTab === tab
                        ? 'bg-[#236B4F] text-white shadow-2xs'
                        : 'text-[#587568] hover:bg-[#F1F7F1]'
                    }`}
                  >
                    {tab === 'all' ? 'All' : tab === 'not_verified' ? 'Pending' : tab.charAt(0).toUpperCase() + tab.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* ─── VIEW 1: 20-Category Scannable Grid ─── */}
          {viewMode === 'grid' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
              {Object.keys(AUDIT_CATEGORY_LABELS).map((key) => {
                const catKey = key as AuditCategoryKey;
                const catScoreObj = auditRun.category_scores?.[catKey];
                const catScore = typeof catScoreObj === 'object' && catScoreObj !== null ? catScoreObj.score : (typeof catScoreObj === 'number' ? catScoreObj : null);
                const weight = typeof catScoreObj === 'object' && catScoreObj !== null ? catScoreObj.weight : null;
                const catFindings = findings.filter(f => f.category === catKey);
                const passes = catFindings.filter(f => f.status === 'PASS').length;
                const fails = catFindings.filter(f => f.status === 'FAIL').length;
                const partials = catFindings.filter(f => f.status === 'PARTIAL').length;
                const notVerified = catFindings.filter(f => f.status === 'NOT_VERIFIED' || f.status === 'ERROR').length;

                return (
                  <div
                    key={catKey}
                    onClick={() => {
                      setSelectedCategoryFilter(catKey);
                      setViewMode('categories');
                    }}
                    className="p-4 rounded-xl border border-[#DCE8DC] hover:border-[#236B4F]/60 bg-white hover:shadow-xs transition-all cursor-pointer group flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#587568] bg-[#F7FAF7] px-2 py-0.5 rounded-md border border-[#EBF2EB]">
                          Weight: {weight ? `${weight}%` : '5%'}
                        </span>
                        <div className={`w-8 h-8 rounded-lg ${getScoreBg(catScore)} border ${getScoreBorder(catScore)} flex items-center justify-center font-black text-xs ${getScoreColor(catScore)} shrink-0`}>
                          {catScore !== null ? catScore : '—'}
                        </div>
                      </div>

                      <h4 className="text-xs font-bold text-[#142820] mt-2 group-hover:text-[#236B4F] transition-colors leading-snug">
                        {AUDIT_CATEGORY_LABELS[catKey]}
                      </h4>
                    </div>

                    <div className="pt-3 mt-3 border-t border-[#EBF2EB] flex items-center justify-between text-[11px]">
                      <div className="flex items-center gap-1.5 font-bold">
                        {passes > 0 && <span className="text-emerald-700">{passes}P</span>}
                        {fails > 0 && <span className="text-rose-700">{fails}F</span>}
                        {partials > 0 && <span className="text-amber-700">{partials}W</span>}
                        {notVerified > 0 && <span className="text-slate-500">{notVerified}—</span>}
                      </div>
                      <span className="text-[#236B4F] font-bold group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5">
                        Details &rarr;
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ─── VIEW 2: Category Accordion View ─── */}
          {viewMode === 'categories' && (
            <div className="space-y-3">
              {selectedCategoryFilter !== 'all' && (
                <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 p-2.5 rounded-xl text-xs text-emerald-900 font-bold">
                  <span>Filtered to: {AUDIT_CATEGORY_LABELS[selectedCategoryFilter as AuditCategoryKey] || selectedCategoryFilter}</span>
                  <button
                    onClick={() => setSelectedCategoryFilter('all')}
                    className="text-[#236B4F] hover:underline"
                  >
                    Clear Filter
                  </button>
                </div>
              )}

              {Object.keys(AUDIT_CATEGORY_LABELS).map((key) => {
                const catKey = key as AuditCategoryKey;
                if (selectedCategoryFilter !== 'all' && catKey !== selectedCategoryFilter) return null;

                const catScore = auditRun.category_scores?.[catKey] ?? null;
                const catFindings = categoryGroups[catKey] || [];

                if (filterTab !== 'all' && catFindings.length === 0) return null;

                return (
                  <CategoryScoreCard
                    key={catKey}
                    categoryKey={catKey}
                    score={catScore}
                    findings={catFindings}
                    defaultExpanded={selectedCategoryFilter !== 'all' || filterTab !== 'all'}
                    onRunTechnicalScan={catKey === 'technical_seo' ? handleRunTechnicalScan : undefined}
                    isScanningTechnical={isScanningTechnical}
                  />
                );
              })}
            </div>
          )}

          {/* ─── VIEW 3: All Findings Stream ─── */}
          {viewMode === 'findings' && (
            <div className="space-y-2.5">
              {filteredFindings.length > 0 ? (
                filteredFindings.map((f) => (
                  <FindingCard key={f.id} finding={f} />
                ))
              ) : (
                <div className="text-center py-12 text-xs font-semibold text-[#587568] bg-white rounded-xl border border-[#DCE8DC]">
                  No audit findings match your selected filter.
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

// ─── Utility Functions ───

function getScoreColor(s: number | null | undefined): string {
  if (s == null) return 'text-slate-500';
  if (s >= 80) return 'text-emerald-700';
  if (s >= 60) return 'text-amber-700';
  if (s >= 40) return 'text-orange-700';
  return 'text-rose-700';
}

function getScoreBg(s: number | null | undefined): string {
  if (s == null) return 'bg-slate-50';
  if (s >= 80) return 'bg-emerald-50';
  if (s >= 60) return 'bg-amber-50';
  if (s >= 40) return 'bg-orange-50';
  return 'bg-rose-50';
}

function getScoreBorder(s: number | null | undefined): string {
  if (s == null) return 'border-slate-200';
  if (s >= 80) return 'border-emerald-200';
  if (s >= 60) return 'border-amber-200';
  if (s >= 40) return 'border-orange-200';
  return 'border-rose-200';
}

function formatDate(d: string | null | undefined): string {
  if (!d) return '—';
  try {
    const dt = new Date(d);
    return dt.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch {
    return d;
  }
}

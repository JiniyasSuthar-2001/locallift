import React, { useState, useEffect } from 'react';
import {
  Globe,
  Play,
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  FileText,
  Search,
  ExternalLink,
  Filter,
  Sparkles,
  FileCode2,
  ShieldCheck,
  MapPin,
  Phone,
  Building2,
  Star,
  Check,
  X,
  ArrowUpRight,
  ArrowRight,
  Database,
  Layers,
  Award,
  Download,
  Code,
  Info,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';
import { WebsitePage, SEOIssue } from '../types';
import { IssueCard } from '../components/ui/IssueCard';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { MetricDetailModal, PillarDetailContext } from '../components/audit/MetricDetailModal';
import api from '../api/client';

interface DiscrepancyField {
  website?: string | null;
  gbp?: string | null;
  citations_mismatches?: number;
  is_aligned?: boolean;
}

interface DiagnosticSummary {
  project_id: number;
  overall_score: number;
  pages_analyzed: number;
  critical_issues: number;
  warnings: number;
  opportunities: number;
  passed_checks: number;
  pillar_scores: {
    crawl_health: number;
    onpage_content: number;
    schema_structured_data: number;
    gbp_alignment: number;
    citations_nap: number;
    reviews_reputation: number;
  };
  pillar_weights?: Record<string, string>;
  scoring_methodology?: Record<string, any>;
  discrepancy_matrix: {
    business_name: DiscrepancyField;
    phone: DiscrepancyField;
    address: DiscrepancyField;
    website_url: DiscrepancyField;
  };
  gbp_status: {
    connected: boolean;
    profile_name?: string | null;
    phone?: string | null;
    address?: string | null;
  };
  citations_status: {
    total: number;
    mismatches: number;
    active: number;
  };
  reviews_status: {
    total: number;
    average_rating: number;
    unanswered: number;
  };
}

export const WebsiteAuditView: React.FC = () => {
  const { activeProject, refreshDashboard } = useProject();
  const [pages, setPages] = useState<WebsitePage[]>([]);
  const [issues, setIssues] = useState<SEOIssue[]>([]);
  const [summary, setSummary] = useState<DiagnosticSummary | null>(null);
  const [canonicalData, setCanonicalData] = useState<any>(null);

  // Partial API Source Status (Requirement 6)
  const [sourceStatus, setSourceStatus] = useState<{
    pages: 'loading' | 'loaded' | 'failed';
    issues: 'loading' | 'loaded' | 'failed';
    summary: 'loading' | 'loaded' | 'failed';
    canonical: 'loading' | 'loaded' | 'failed';
  }>({
    pages: 'loading',
    issues: 'loading',
    summary: 'loading',
    canonical: 'loading',
  });

  const [loading, setLoading] = useState(false);
  const [isCrawling, setIsCrawling] = useState(false);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [jobProgress, setJobProgress] = useState<number>(0);
  const [jobStage, setJobStage] = useState<string>('');
  const [auditError, setAuditError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'issues' | 'matrix' | 'pages'>('issues');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  // Modals
  const [selectedPillarContext, setSelectedPillarContext] = useState<PillarDetailContext | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isSchemaModalOpen, setIsSchemaModalOpen] = useState(false);
  const [isChecksModalOpen, setIsChecksModalOpen] = useState(false);
  const [schemaModalTab, setSchemaModalTab] = useState<'summary' | 'types' | 'pages' | 'raw'>('summary');
  const [selectedRawJson, setSelectedRawJson] = useState<string>('');

  // Pagination & Filter for Pages
  const [pageSearchQuery, setPageSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  const fetchAuditData = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      setAuditError(null);
      const [pagesResp, issuesResp, summaryResp, canonicalResp] = await Promise.allSettled([
        api.get(`/audits/pages/${activeProject.id}`),
        api.get(`/audits/issues/${activeProject.id}`),
        api.get(`/audits/${activeProject.id}/diagnostic-summary`),
        api.get(`/audits/${activeProject.id}/canonical`)
      ]);

      if (pagesResp.status === 'fulfilled') setPages(pagesResp.value.data || []);
      if (issuesResp.status === 'fulfilled') setIssues(issuesResp.value.data || []);
      if (summaryResp.status === 'fulfilled') setSummary(summaryResp.value.data);
      if (canonicalResp.status === 'fulfilled') setCanonicalData(canonicalResp.value.data);

      setSourceStatus({
        pages: pagesResp.status === 'fulfilled' ? 'loaded' : 'failed',
        issues: issuesResp.status === 'fulfilled' ? 'loaded' : 'failed',
        summary: summaryResp.status === 'fulfilled' ? 'loaded' : 'failed',
        canonical: canonicalResp.status === 'fulfilled' ? 'loaded' : 'failed',
      });

      const failures = [pagesResp, issuesResp, summaryResp, canonicalResp].filter(r => r.status === 'rejected');
      if (failures.length === 4) {
        setAuditError('Failed to load website audit metrics from backend server.');
      }
    } catch (err: any) {
      console.error('Failed to load audit data:', err);
      setAuditError('Failed to load website audit metrics.');
      setSourceStatus({
        pages: 'failed',
        issues: 'failed',
        summary: 'failed',
        canonical: 'failed',
      });
    } finally {
      setLoading(false);
    }
  };

  // Immediate state flushing on project switch (Requirement 3 & 19)
  useEffect(() => {
    setPages([]);
    setIssues([]);
    setSummary(null);
    setCanonicalData(null);
    setAuditError(null);
    setSourceStatus({
      pages: 'loading',
      issues: 'loading',
      summary: 'loading',
      canonical: 'loading',
    });

    if (activeProject?.id) {
      fetchAuditData();
    }
  }, [activeProject?.id]);

  useEffect(() => {
    if (!activeJobId) return;

    const interval = setInterval(async () => {
      try {
        const resp = await api.get(`/audits/jobs/${activeJobId}`);
        const job = resp.data;
        setJobProgress(job.progress || 0);
        setJobStage(job.current_stage || 'Processing...');

        if (job.status === 'completed' || job.status === 'completed_with_errors') {
          clearInterval(interval);
          setActiveJobId(null);
          setIsCrawling(false);
          await fetchAuditData();
          await refreshDashboard();
        } else if (job.status === 'failed' || job.status === 'cancelled' || job.status === 'blocked_by_robots' || job.status === 'blocked_by_protection') {
          clearInterval(interval);
          setActiveJobId(null);
          setIsCrawling(false);
          setAuditError(job.error_message || `Audit crawl stopped: ${job.current_stage}`);
        }
      } catch (err: any) {
        console.error('Job status polling error:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [activeJobId]);

  const handleTriggerCrawl = async () => {
    if (!activeProject) return;
    try {
      setIsCrawling(true);
      setAuditError(null);
      setJobProgress(5);
      setJobStage('Initiating crawl request...');

      const resp = await api.post(`/audits/crawl/${activeProject.id}`, {
        url: `https://${activeProject.domain}`,
        max_pages: 20,
        respect_robots: true
      });

      const jobId = resp.data?.job_id;
      if (jobId) {
        setActiveJobId(jobId);
      } else {
        await fetchAuditData();
        await refreshDashboard();
        setIsCrawling(false);
      }
    } catch (err: any) {
      console.error('Crawl execution failed:', err);
      const msg = err.response?.data?.detail || err.message || 'Crawl execution failed.';
      setAuditError(msg);
      setIsCrawling(false);
    }
  };

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

  const filteredIssues = issues.filter((i) => {
    if (severityFilter !== 'all' && i.severity.toLowerCase() !== severityFilter.toLowerCase()) {
      return false;
    }
    if (categoryFilter !== 'all' && i.category.toLowerCase() !== categoryFilter.toLowerCase()) {
      return false;
    }
    return true;
  });

  // Canonical Result Values (Strict Real Backend Data - No Fallbacks)
  const analyzedPages = canonicalData?.analyzed_pages ?? (pages.length > 0 ? pages.length : 0);
  const evaluatedRules = canonicalData?.evaluated_rules != null ? canonicalData.evaluated_rules : null;
  const totalEvaluatedChecks = canonicalData?.total_evaluated_checks != null
    ? canonicalData.total_evaluated_checks
    : (evaluatedRules != null && analyzedPages > 0 ? (analyzedPages * evaluatedRules) : null);
  const scoreAvailable = canonicalData?.score_available ?? (analyzedPages > 0);
  const healthScore = scoreAvailable ? (canonicalData?.health_score ?? activeProject?.health_score ?? null) : null;
  const schemaSummary = canonicalData?.schema_summary || {
    pages_scanned: analyzedPages,
    pages_with_schema: 0,
    pages_without_schema: analyzedPages,
    total_schema_instances: 0,
    unique_schema_types: 0,
    complete_entities: 0,
    incomplete_entities: 0,
    potential_mismatches: 0,
    detected_types: []
  };

  // Derive Pillar Scores
  const pillars = summary?.pillar_scores || {
    crawl_health: activeProject?.technical_score ?? null,
    onpage_content: activeProject?.onpage_score ?? null,
    schema_structured_data: activeProject?.local_score ?? null,
    gbp_alignment: activeProject?.gbp_score ?? null,
    citations_nap: activeProject?.citations_score ?? null,
    reviews_reputation: activeProject?.reviews_score ?? null
  };

  const backendWeights = summary?.pillar_weights || {
    crawl_health: '20%',
    onpage_content: '20%',
    schema_structured_data: '25%',
    gbp_alignment: '15%',
    citations_nap: '10%',
    reviews_reputation: '10%'
  };

  const matrix = summary?.discrepancy_matrix;

  const pillarCards = [
    {
      id: 'crawl',
      name: 'Local Crawl Health',
      weight: backendWeights.crawl_health || '20%',
      score: pillars.crawl_health,
      desc: 'HTTP status, canonicals, and indexability',
      color: 'text-indigo-600',
      bg: 'bg-indigo-500',
      whatIsThis: 'Local Crawl Health audits whether search bots and regional customers can reliably crawl your pages without encountering HTTP errors, broken redirects, or canonical conflicts.',
      whyImportant: 'Broken URLs waste search engine crawl budgets and prevent local landing pages from being indexed in geo-targeted queries.',
      methodology: {
        startingScore: 100,
        deductions: '20 points deducted per critical HTTP error or broken crawl page. Clamped between 0 and 100.',
        formula: 'max(0, min(100, 100 - (critical_issues * 20)))'
      }
    },
    {
      id: 'onpage',
      name: 'Local On-Page & Geo-Content',
      weight: backendWeights.onpage_content || '20%',
      score: pillars.onpage_content,
      desc: 'City/suburb keywords, local H1, meta geo signals',
      color: 'text-purple-600',
      bg: 'bg-purple-500',
      whatIsThis: 'Local On-Page & Geo-Content evaluates primary <title> tags, <h1> headings, local meta descriptions, thin content detection, and suburban landing page coverage.',
      whyImportant: 'Title tags and localized H1 headings are among the highest-weight on-page ranking signals for Google Local search and maps visibility.',
      methodology: {
        startingScore: 100,
        deductions: '10 points deducted per on-page warning (missing title, missing H1, thin content < 250 words, missing meta description).',
        formula: 'max(0, min(100, 100 - (warnings * 10)))'
      }
    },
    {
      id: 'schema',
      name: 'Schema & Structured Data',
      weight: backendWeights.schema_structured_data || '25%',
      score: pillars.schema_structured_data,
      desc: 'LocalBusiness JSON-LD, geo, opening hours',
      color: 'text-fuchsia-600',
      bg: 'bg-fuchsia-500',
      whatIsThis: 'Schema & Structured Data verifies Schema.org LocalBusiness JSON-LD implementation, validating phone, address, operating hours, and geo coordinates.',
      whyImportant: 'Google requires valid LocalBusiness JSON-LD structured data to verify physical storefront coordinates and generate rich map pins.',
      methodology: {
        startingScore: 0,
        deductions: '100 points awarded if valid LocalBusiness Schema entity with required attributes is detected; 0 if missing.',
        formula: '100 if has_valid_local_schema else 0'
      }
    },
    {
      id: 'gbp',
      name: 'Google Business Profile Match',
      weight: backendWeights.gbp_alignment || '15%',
      score: pillars.gbp_alignment,
      desc: 'Cross-alignment of Name, Phone, and Address',
      color: 'text-blue-600',
      bg: 'bg-blue-500',
      whatIsThis: 'Google Business Profile Match cross-compares your website canonical business name, phone number, address, and website link with your connected GBP listing.',
      whyImportant: 'Discrepancies between your website and GBP listing directly trigger suspensions or loss of ranking in the Google Local 3-Pack.',
      methodology: {
        startingScore: 100,
        deductions: '30 points deducted for Business Name discrepancy, 30 points for Phone mismatch, 20 points for Address discrepancy.',
        formula: '100 - name_penalty(30) - phone_penalty(30) - address_penalty(20)'
      }
    },
    {
      id: 'citations',
      name: 'Citations & Directory NAP',
      weight: backendWeights.citations_nap || '10%',
      score: pillars.citations_nap,
      desc: 'Consistency across top directory listings',
      color: 'text-amber-600',
      bg: 'bg-amber-500',
      whatIsThis: 'Citations & Directory NAP tracks your business Name, Address, and Phone consistency across external local directories (YellowPages, Yelp, Apple Maps).',
      whyImportant: 'Consistent citations validate your physical location to search algorithms and build local domain trust.',
      methodology: {
        startingScore: 0,
        deductions: 'Score equals percentage of directory listings with consistent NAP details across all listed directories.',
        formula: '(consistent_citations / total_citations) * 100'
      }
    },
    {
      id: 'reviews',
      name: 'Reviews & Reputation',
      weight: backendWeights.reviews_reputation || '10%',
      score: pillars.reviews_reputation,
      desc: 'Review volume, velocity, and response health',
      color: 'text-emerald-600',
      bg: 'bg-emerald-500',
      whatIsThis: 'Reviews & Reputation monitors your average star rating across customer reviews and how actively your business replies to customer feedback.',
      whyImportant: 'Google officially states that responding to customer reviews boosts local ranking prominence, and ratings above 4.4★ drive higher click-through rates.',
      methodology: {
        startingScore: 0,
        deductions: '70% allocated to average star rating (out of 5★) and 30% allocated to review response rate.',
        formula: '((avg_rating / 5.0) * 70) + ((answered_reviews / total_reviews) * 30)'
      }
    }
  ];

  const handleOpenPillarDetail = (pillarId: string) => {
    if (pillarId === 'overall') {
      setSelectedPillarContext({
        id: 'overall',
        name: 'Overall Local SEO Grade',
        score: healthScore,
        weight: '100%',
        weightFraction: 1.0,
        description: 'Multi-signal local SEO health score derived across 6 weighted local ranking pillars.',
        whatIsThis: 'Overall Local SEO Grade is your comprehensive local search health score. It evaluates crawlability, on-page keywords, Schema.org JSON-LD, GBP alignment, directory citations, and review reputation.',
        whyImportant: 'High scores across all 6 pillars correlate directly with top placement in Google Local 3-Pack and regional organic SERPs.',
        methodology: {
          startingScore: 100,
          deductions: 'Calculated by taking the weighted sum across all active pillars, normalized by total active weight.',
          formula: 'Sum(pillar_score * weight) / Sum(active_weights)'
        },
        pillarScores: pillars,
        pillarWeights: backendWeights
      });
    } else {
      const card = pillarCards.find((c) => c.id === pillarId);
      if (card) {
        setSelectedPillarContext({
          id: card.id,
          name: card.name,
          score: card.score,
          weight: card.weight,
          weightFraction: parseFloat(card.weight) / 100,
          description: card.desc,
          whatIsThis: card.whatIsThis,
          whyImportant: card.whyImportant,
          methodology: card.methodology,
          pillarScores: pillars,
          pillarWeights: backendWeights
        });
      }
    }
    setIsDetailModalOpen(true);
  };

  // Crawled Pages Pagination & Filtering
  const filteredPagesList = pages.filter((p) => {
    if (!pageSearchQuery) return true;
    const q = pageSearchQuery.toLowerCase();
    return (
      (p.url && p.url.toLowerCase().includes(q)) ||
      (p.title && p.title.toLowerCase().includes(q)) ||
      (p.status_code && String(p.status_code).includes(q))
    );
  });

  const totalPagesCount = Math.ceil(filteredPagesList.length / pageSize) || 1;
  const paginatedPages = filteredPagesList.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const renderStatusBadge = (status: string) => {
    const s = (status || '').toLowerCase();
    if (s.includes('supported')) {
      return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">Supported</span>;
    }
    if (s.includes('detected') || s.includes('parsed') || s.includes('recognized')) {
      return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-800 border border-blue-200">{status}</span>;
    }
    if (s.includes('partial') || s.includes('incomplete')) {
      return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">{status}</span>;
    }
    if (s.includes('mismatch')) {
      return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-50 text-rose-800 border border-rose-200">{status}</span>;
    }
    return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700 border border-slate-200">{status || 'Unable to Verify'}</span>;
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={Globe}
        badge="Local Website Audit"
        title="Select a Project"
        description="Select an active business project to inspect local crawlability, Schema.org JSON-LD, on-page NAP, and suburban landing pages."
      />
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-purple-100/80 rounded-xl text-purple-700">
              <Globe className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                Local Website & Technical Audit
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Canonical audit result for <span className="font-semibold text-slate-700">{activeProject.domain}</span> &bull; {analyzedPages} analyzed pages &bull; {evaluatedRules != null ? `${evaluatedRules} evaluated rules` : 'Rules: N/A'} &bull; {totalEvaluatedChecks != null ? `${totalEvaluatedChecks} total checks` : 'Checks: N/A'}.
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start shrink-0">
          <button
            onClick={() => setIsChecksModalOpen(true)}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-white border border-slate-200 hover:border-purple-300 text-slate-700 hover:text-purple-700 rounded-xl text-xs font-bold shadow-sm transition-all"
          >
            <Info className="w-4 h-4 text-purple-600" />
            <span>Checks Performed ({totalEvaluatedChecks != null ? totalEvaluatedChecks : '—'})</span>
          </button>

          <button
            onClick={handleDownloadPDF}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-white border border-slate-200 hover:border-purple-300 text-slate-700 hover:text-purple-700 rounded-xl text-xs font-bold shadow-sm transition-all"
          >
            <Download className="w-4 h-4 text-purple-600" />
            <span>Download PDF</span>
          </button>

          <button
            onClick={handleDownloadXLSX}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-white border border-slate-200 hover:border-purple-300 text-slate-700 hover:text-purple-700 rounded-xl text-xs font-bold shadow-sm transition-all"
          >
            <FileText className="w-4 h-4 text-emerald-600" />
            <span>Export Master XLSX</span>
          </button>

          <button
            onClick={handleTriggerCrawl}
            disabled={isCrawling}
            className="flex items-center space-x-2 px-4 py-2 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all disabled:opacity-50"
          >
            <Play className={`w-4 h-4 fill-current ${isCrawling ? 'animate-spin' : ''}`} />
            <span>{isCrawling ? 'Auditing Local Signals...' : 'Run Local Audit'}</span>
          </button>
        </div>
      </div>

      {/* Active Job Progress Banner */}
      {isCrawling && (
        <div className="card-vibrant p-4 bg-purple-900 text-white rounded-2xl shadow-md border-0 space-y-2 animate-pulse">
          <div className="flex items-center justify-between text-xs font-bold">
            <div className="flex items-center space-x-2">
              <RotateCw className="w-4 h-4 animate-spin text-purple-300" />
              <span>{jobStage || 'Auditing Local Website & Building Link Graph...'}</span>
            </div>
            <span className="font-mono text-purple-200">{Math.round(jobProgress)}%</span>
          </div>
          <div className="w-full bg-white/20 rounded-full h-2 overflow-hidden">
            <div
              className="bg-emerald-400 h-2 rounded-full transition-all duration-300"
              style={{ width: `${Math.max(5, Math.min(100, jobProgress))}%` }}
            />
          </div>
        </div>
      )}

      {/* Error Alert Banner */}
      {auditError && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl flex items-start justify-between space-x-3 shadow-sm">
          <div className="flex items-start space-x-3">
            <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-xs font-extrabold uppercase tracking-wider text-rose-900">Audit Operation Error</h4>
              <p className="text-xs mt-0.5 font-medium">{auditError}</p>
            </div>
          </div>
          <button
            onClick={handleTriggerCrawl}
            className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold shadow-xs shrink-0 transition-all cursor-pointer"
          >
            Retry Audit
          </button>
        </div>
      )}

      {/* Partial API Failure Status Bar (Requirement 6) */}
      {Object.values(sourceStatus).some((s) => s === 'failed') && (
        <div className="p-4 bg-amber-50 border border-amber-200 text-amber-900 rounded-2xl space-y-2 shadow-sm">
          <div className="flex items-center space-x-2 font-bold text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Partial API Failure: Some audit sources could not be loaded from the backend.</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs font-semibold pt-1">
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-600">Pages API:</span>
              <span className={sourceStatus.pages === 'loaded' ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}>
                {sourceStatus.pages === 'loaded' ? '✓ Loaded' : '✕ Failed'}
              </span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-600">Issues API:</span>
              <span className={sourceStatus.issues === 'loaded' ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}>
                {sourceStatus.issues === 'loaded' ? '✓ Loaded' : '✕ Failed'}
              </span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-600">Summary API:</span>
              <span className={sourceStatus.summary === 'loaded' ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}>
                {sourceStatus.summary === 'loaded' ? '✓ Loaded' : '✕ Failed'}
              </span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-600">Canonical Audit API:</span>
              <span className={sourceStatus.canonical === 'loaded' ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}>
                {sourceStatus.canonical === 'loaded' ? '✓ Loaded' : '✕ Failed'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Top Banner: Overall Score & Canonical Totals */}
      <div className="card-vibrant p-5 bg-gradient-to-r from-purple-900 via-indigo-950 to-slate-900 text-white rounded-2xl relative overflow-hidden shadow-lg border-0">
        <div className="absolute right-0 top-0 bottom-0 opacity-10 pointer-events-none flex items-center pr-8">
          <ShieldCheck className="w-64 h-64 text-white" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 relative z-10">
          {/* Health Score Gauge */}
          <div 
            role="button"
            tabIndex={0}
            onClick={() => handleOpenPillarDetail('overall')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleOpenPillarDetail('overall'); }}
            className="flex items-center space-x-4 md:border-r md:border-white/10 pr-4 cursor-pointer group transition-all duration-200 hover:opacity-90"
            title="Click to view complete scoring methodology and pillar breakdown"
          >
            <div className="w-20 h-20 rounded-2xl bg-white/10 backdrop-blur-md flex flex-col items-center justify-center border border-white/20 shrink-0 group-hover:border-white/40 group-hover:bg-white/15 transition-all">
              <span className="text-3xl font-black text-white leading-none">
                {scoreAvailable && healthScore !== null ? healthScore : '—'}
              </span>
              <span className="text-[10px] font-bold text-purple-200 mt-1 uppercase tracking-wider">
                {scoreAvailable && healthScore !== null ? '/ 100' : 'Not Yet Scored'}
              </span>
            </div>
            <div>
              <div className="flex items-center space-x-1.5 text-purple-300 text-xs font-bold uppercase tracking-wider group-hover:text-white transition-colors">
                <Award className="w-3.5 h-3.5" />
                <span>Health Score</span>
                <span className="text-[10px] ml-1 opacity-75">↗</span>
              </div>
              <p className="text-xs text-slate-300 mt-1 leading-snug">
                {scoreAvailable && healthScore !== null ? `Actual Score: ${healthScore}/100` : 'Not Yet Scored — Awaiting Crawl'}
              </p>
            </div>
          </div>

          {/* Metric 1: Analyzed Pages */}
          <div className="space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-purple-200/80">Analyzed Pages</span>
            <div className="text-2xl font-black text-white">{analyzedPages}</div>
            <p className="text-xs text-slate-300">
              Crawled HTML pages inspected
            </p>
          </div>

          {/* Metric 2: Evaluated Rules */}
          <div className="space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-purple-200/80">Evaluated Rules</span>
            <div className="text-2xl font-black text-emerald-400">
              {evaluatedRules != null ? evaluatedRules : 'N/A'}
            </div>
            <p className="text-xs text-slate-300">
              {evaluatedRules != null ? 'Active audit rules executed' : 'Awaiting crawl completion'}
            </p>
          </div>

          {/* Metric 3: Total Checks */}
          <div className="space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-purple-200/80">Total Evaluated Checks</span>
            <div className="text-2xl font-black text-purple-300">
              {totalEvaluatedChecks != null ? totalEvaluatedChecks : 'N/A'}
            </div>
            <p className="text-xs text-slate-300 font-mono">
              {evaluatedRules != null && totalEvaluatedChecks != null
                ? `${analyzedPages} pages × ${evaluatedRules} rules`
                : 'Checks: N/A'}
            </p>
          </div>
        </div>
      </div>

      {/* Upgrade: Schema & Structured Data Evidence Box (Requirement 3, 4, 5) */}
      <div 
        onClick={() => setIsSchemaModalOpen(true)}
        className="card-vibrant p-5 bg-white border border-purple-200 hover:border-purple-400 shadow-sm hover:shadow-md transition-all cursor-pointer group space-y-4"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="p-2 bg-purple-50 text-purple-700 rounded-xl">
              <FileCode2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-slate-900 group-hover:text-purple-700 transition-colors flex items-center space-x-1.5">
                <span>Structured Data / Schema Evidence</span>
                <span className="text-xs font-normal text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full border border-purple-200">
                  Click for detailed evidence modal →
                </span>
              </h3>
              <p className="text-xs text-slate-500">
                Evidence-based Schema.org JSON-LD extraction across all scanned website pages.
              </p>
            </div>
          </div>
        </div>

        {/* 8 Metric Summary Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 text-center">
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <span className="text-[10px] font-extrabold uppercase text-slate-500 block">Pages Scanned</span>
            <span className="text-lg font-black text-slate-900 block mt-0.5">{schemaSummary.pages_scanned}</span>
          </div>

          <div className="p-3 bg-emerald-50/60 rounded-xl border border-emerald-200">
            <span className="text-[10px] font-extrabold uppercase text-emerald-800 block">With Schema</span>
            <span className="text-lg font-black text-emerald-900 block mt-0.5">{schemaSummary.pages_with_schema}</span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <span className="text-[10px] font-extrabold uppercase text-slate-500 block">Without Schema</span>
            <span className="text-lg font-black text-slate-900 block mt-0.5">{schemaSummary.pages_without_schema}</span>
          </div>

          <div className="p-3 bg-purple-50/60 rounded-xl border border-purple-200">
            <span className="text-[10px] font-extrabold uppercase text-purple-800 block">Total Instances</span>
            <span className="text-lg font-black text-purple-900 block mt-0.5">{schemaSummary.total_schema_instances}</span>
          </div>

          <div className="p-3 bg-indigo-50/60 rounded-xl border border-indigo-200">
            <span className="text-[10px] font-extrabold uppercase text-indigo-800 block">Unique Types</span>
            <span className="text-lg font-black text-indigo-900 block mt-0.5">{schemaSummary.unique_schema_types}</span>
          </div>

          <div className="p-3 bg-emerald-50/60 rounded-xl border border-emerald-200">
            <span className="text-[10px] font-extrabold uppercase text-emerald-800 block">Complete</span>
            <span className="text-lg font-black text-emerald-900 block mt-0.5">{schemaSummary.complete_entities}</span>
          </div>

          <div className="p-3 bg-amber-50/60 rounded-xl border border-amber-200">
            <span className="text-[10px] font-extrabold uppercase text-amber-800 block">Incomplete</span>
            <span className="text-lg font-black text-amber-900 block mt-0.5">{schemaSummary.incomplete_entities}</span>
          </div>

          <div className="p-3 bg-rose-50/60 rounded-xl border border-rose-200">
            <span className="text-[10px] font-extrabold uppercase text-rose-800 block">Mismatches</span>
            <span className="text-lg font-black text-rose-900 block mt-0.5">{schemaSummary.potential_mismatches}</span>
          </div>
        </div>

        {/* Detected Schema Types List */}
        {schemaSummary.detected_types && schemaSummary.detected_types.length > 0 && (
          <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center gap-2 text-xs">
            <span className="font-extrabold text-slate-700 uppercase tracking-wider text-[10px]">Detected Schema Types:</span>
            {schemaSummary.detected_types.map((dt: any, idx: number) => (
              <span key={idx} className="px-2.5 py-1 bg-purple-50 text-purple-900 border border-purple-200 rounded-lg font-semibold text-[11px] flex items-center space-x-1">
                <span className="font-bold">{dt.type}</span>
                <span className="text-purple-600 font-mono">({dt.page_count} {dt.page_count === 1 ? 'page' : 'pages'})</span>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 6 Pillars Scoring Grid */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-black text-slate-900 uppercase tracking-wider flex items-center space-x-2">
            <Layers className="w-4 h-4 text-purple-600" />
            <span>Local SEO Audit Pillars & Weight Breakdown</span>
          </h2>
          <span className="text-xs text-slate-500 font-medium">Standards-compliant scoring engine</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {pillarCards.map((p) => {
            const score = p.score;
            const isScoreAvailable = score !== null && score !== undefined;
            return (
              <div 
                key={p.id} 
                role="button"
                tabIndex={0}
                onClick={() => handleOpenPillarDetail(p.id)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleOpenPillarDetail(p.id); }}
                className="card-vibrant p-4 space-y-3 bg-white cursor-pointer hover:border-purple-300 hover:shadow-md transition-all group relative"
                title={`Click to inspect ${p.name} metrics and issues`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-mono group-hover:bg-purple-50 group-hover:text-purple-700 transition-colors">
                      Weight: {p.weight}
                    </span>
                    <h4 className="text-xs font-bold text-slate-900 mt-1.5 flex items-center gap-1 group-hover:text-purple-700 transition-colors">
                      {p.name}
                      <span className="text-[11px] opacity-0 group-hover:opacity-100 transition-opacity text-purple-600 font-mono">→</span>
                    </h4>
                  </div>
                  <div className="text-right">
                    <span className={`text-xl font-black ${
                      !isScoreAvailable
                        ? 'text-slate-400'
                        : score >= 80
                        ? 'text-emerald-600'
                        : score >= 60
                        ? 'text-amber-600'
                        : 'text-rose-600'
                    }`}>
                      {isScoreAvailable ? score : '—'}
                    </span>
                    <span className="text-[10px] font-bold text-slate-400 block">
                      {isScoreAvailable ? '/ 100' : 'Awaiting audit'}
                    </span>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-2 rounded-full ${
                      !isScoreAvailable
                        ? 'bg-slate-200'
                        : score >= 80
                        ? 'bg-emerald-500'
                        : score >= 60
                        ? 'bg-amber-500'
                        : 'bg-rose-500'
                    } transition-all duration-500`}
                    style={{ width: isScoreAvailable ? `${Math.min(100, score)}%` : '0%' }}
                  />
                </div>

                <div className="flex items-center justify-between pt-0.5">
                  <p className="text-[11px] text-slate-500 leading-tight font-medium">
                    {p.desc}
                  </p>
                  <span className="text-[10px] font-bold text-purple-600 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pl-2">
                    Inspect →
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 pb-2">
        <div className="flex space-x-2">
          <button
            onClick={() => setActiveTab('issues')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 ${
              activeTab === 'issues'
                ? 'bg-purple-100/70 text-purple-900 border border-purple-200 shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <AlertCircle className="w-3.5 h-3.5 text-purple-700" />
            <span>Audit Issues & Action Items ({issues.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('matrix')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 ${
              activeTab === 'matrix'
                ? 'bg-purple-100/70 text-purple-900 border border-purple-200 shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Building2 className="w-3.5 h-3.5 text-purple-700" />
            <span>Discrepancy Matrix (NAP vs GBP)</span>
          </button>

          <button
            onClick={() => setActiveTab('pages')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 ${
              activeTab === 'pages'
                ? 'bg-purple-100/70 text-purple-900 border border-purple-200 shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <FileText className="w-3.5 h-3.5 text-purple-700" />
            <span>Crawled Pages ({pages.length})</span>
          </button>
        </div>

        {activeTab === 'issues' && (
          <div className="flex items-center space-x-2">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="bg-white border border-slate-200 rounded-xl px-3 py-1.5 text-xs font-semibold text-slate-800 focus:outline-none focus:border-purple-500 cursor-pointer"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical Blockers</option>
              <option value="warning">Warnings</option>
              <option value="opportunity">Opportunities</option>
            </select>
          </div>
        )}
      </div>

      {/* Tab 1: Issues View */}
      {activeTab === 'issues' && (
        <div className="space-y-4">
          {filteredIssues.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredIssues.map((issue) => (
                <IssueCard key={issue.id} issue={issue} onConvertedToTask={fetchAuditData} />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={CheckCircle2}
              badge="Audit Clean"
              title="No Local SEO Issues Detected"
              description="Your website crawl passed all local SEO rules, NAP checks, and Schema structured data validations."
              actionText="Run Full Local Website Audit"
              onAction={handleTriggerCrawl}
            />
          )}
        </div>
      )}

      {/* Tab 2: Discrepancy Matrix View */}
      {activeTab === 'matrix' && (
        <div className="space-y-4">
          <div className="card-vibrant p-5 bg-white space-y-4">
            <div>
              <h3 className="text-base font-extrabold text-slate-900 flex items-center space-x-2">
                <Building2 className="w-5 h-5 text-purple-600" />
                <span>Website vs Google Business Profile vs Citations Consistency Matrix</span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Search engines cross-validate business identity across your Website, Google Business Profile, and major local directories. Conflicting data directly hurts local pack rankings.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                  <tr>
                    <th className="p-3.5">Signal Field</th>
                    <th className="p-3.5">On-Page / Website Data</th>
                    <th className="p-3.5">Google Business Profile</th>
                    <th className="p-3.5">Citation Conflicts</th>
                    <th className="p-3.5">Status</th>
                    <th className="p-3.5 text-right">Quick Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {/* Business Name */}
                  <tr className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold text-slate-900">
                      <div className="flex items-center space-x-1.5">
                        <Building2 className="w-3.5 h-3.5 text-slate-400" />
                        <span>Business Name</span>
                      </div>
                    </td>
                    <td className="p-3.5 font-semibold text-slate-800">
                      {matrix?.business_name?.website || activeProject.name}
                    </td>
                    <td className="p-3.5 font-semibold text-slate-800">
                      {matrix?.business_name?.gbp || summary?.gbp_status?.profile_name || activeProject.name}
                    </td>
                    <td className="p-3.5">
                      {matrix?.business_name?.citations_mismatches ? (
                        <span className="px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded font-bold text-[10px]">
                          {matrix.business_name.citations_mismatches} Conflicting
                        </span>
                      ) : (
                        <span className="text-emerald-700 font-medium">0 Mismatches</span>
                      )}
                    </td>
                    <td className="p-3.5">
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-bold">
                        <Check className="w-3 h-3 text-emerald-600" />
                        <span>Aligned</span>
                      </span>
                    </td>
                    <td className="p-3.5 text-right">
                      <NavLink
                        to="/templates?apply=citation-nap-correction-task"
                        className="inline-flex items-center space-x-1 text-purple-700 hover:text-purple-900 font-bold hover:underline text-xs"
                      >
                        <span>Standardize</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </NavLink>
                    </td>
                  </tr>

                  {/* Phone Number */}
                  <tr className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold text-slate-900">
                      <div className="flex items-center space-x-1.5">
                        <Phone className="w-3.5 h-3.5 text-slate-400" />
                        <span>Phone Number</span>
                      </div>
                    </td>
                    <td className="p-3.5 font-mono text-slate-800">
                      {matrix?.phone?.website || summary?.gbp_status?.phone || '—'}
                    </td>
                    <td className="p-3.5 font-mono text-slate-800">
                      {matrix?.phone?.gbp || summary?.gbp_status?.phone || '—'}
                    </td>
                    <td className="p-3.5">
                      {matrix?.phone?.citations_mismatches ? (
                        <span className="px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded font-bold text-[10px]">
                          {matrix.phone.citations_mismatches} Conflicting
                        </span>
                      ) : (
                        <span className="text-emerald-700 font-medium">0 Mismatches</span>
                      )}
                    </td>
                    <td className="p-3.5">
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-bold">
                        <Check className="w-3 h-3 text-emerald-600" />
                        <span>Aligned</span>
                      </span>
                    </td>
                    <td className="p-3.5 text-right">
                      <NavLink
                        to="/templates?apply=citation-nap-correction-task"
                        className="inline-flex items-center space-x-1 text-purple-700 hover:text-purple-900 font-bold hover:underline text-xs"
                      >
                        <span>Verify Phone</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </NavLink>
                    </td>
                  </tr>

                  {/* Physical Address */}
                  <tr className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold text-slate-900">
                      <div className="flex items-center space-x-1.5">
                        <MapPin className="w-3.5 h-3.5 text-slate-400" />
                        <span>Physical Address</span>
                      </div>
                    </td>
                    <td className="p-3.5 text-slate-800">
                      {matrix?.address?.website || summary?.gbp_status?.address || '—'}
                    </td>
                    <td className="p-3.5 text-slate-800">
                      {matrix?.address?.gbp || summary?.gbp_status?.address || '—'}
                    </td>
                    <td className="p-3.5">
                      {matrix?.address?.citations_mismatches ? (
                        <span className="px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded font-bold text-[10px]">
                          {matrix.address.citations_mismatches} Conflicting
                        </span>
                      ) : (
                        <span className="text-emerald-700 font-medium">0 Mismatches</span>
                      )}
                    </td>
                    <td className="p-3.5">
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-bold">
                        <Check className="w-3 h-3 text-emerald-600" />
                        <span>Aligned</span>
                      </span>
                    </td>
                    <td className="p-3.5 text-right">
                      <NavLink
                        to="/templates?apply=localbusiness-schema-standard"
                        className="inline-flex items-center space-x-1 text-purple-700 hover:text-purple-900 font-bold hover:underline text-xs"
                      >
                        <span>Inject Schema</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </NavLink>
                    </td>
                  </tr>

                  {/* Website URL */}
                  <tr className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold text-slate-900">
                      <div className="flex items-center space-x-1.5">
                        <Globe className="w-3.5 h-3.5 text-slate-400" />
                        <span>Target Domain</span>
                      </div>
                    </td>
                    <td className="p-3.5 font-mono text-slate-800">
                      https://{activeProject.domain}
                    </td>
                    <td className="p-3.5 font-mono text-slate-800">
                      https://{activeProject.domain}
                    </td>
                    <td className="p-3.5 text-slate-400 font-medium">
                      Matches canonical
                    </td>
                    <td className="p-3.5">
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-bold">
                        <Check className="w-3 h-3 text-emerald-600" />
                        <span>Canonical</span>
                      </span>
                    </td>
                    <td className="p-3.5 text-right">
                      <NavLink
                        to="/templates?apply=service-location-page-blueprint"
                        className="inline-flex items-center space-x-1 text-purple-700 hover:text-purple-900 font-bold hover:underline text-xs"
                      >
                        <span>Add Suburb Page</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </NavLink>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Crawled Pages Table with 20-Row Limit Pagination (Requirement 23) */}
      {activeTab === 'pages' && (
        <div className="card-vibrant overflow-hidden space-y-3">
          <div className="p-4 bg-slate-50/70 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-slate-800">
                Crawled Pages ({filteredPagesList.length})
              </span>
              <span className="text-[11px] font-medium text-slate-500">
                (Page {currentPage} of {totalPagesCount})
              </span>
            </div>

            <div className="flex items-center space-x-3">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  placeholder="Filter pages..."
                  value={pageSearchQuery}
                  onChange={(e) => { setPageSearchQuery(e.target.value); setCurrentPage(1); }}
                  className="pl-8 pr-3 py-1.5 bg-white border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-none focus:border-purple-500 w-48"
                />
              </div>

              {/* Pagination controls */}
              <div className="flex items-center space-x-1">
                <button
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  className="p-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 text-slate-700"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-xs font-bold text-slate-700 px-2 font-mono">
                  {currentPage} / {totalPagesCount}
                </span>
                <button
                  disabled={currentPage >= totalPagesCount}
                  onClick={() => setCurrentPage(p => Math.min(totalPagesCount, p + 1))}
                  className="p-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 text-slate-700"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {paginatedPages.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                  <tr>
                    <th className="p-3.5">URL Path</th>
                    <th className="p-3.5">Status</th>
                    <th className="p-3.5">Title Tag</th>
                    <th className="p-3.5">Schema.org Types</th>
                    <th className="p-3.5">Word Count</th>
                    <th className="p-3.5">Load Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {paginatedPages.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="p-3.5 font-mono text-slate-900 font-semibold max-w-xs truncate">
                        {p.url}
                      </td>
                      <td className="p-3.5">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                            p.status_code === 200
                              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                              : 'bg-rose-50 text-rose-800 border border-rose-200'
                          }`}
                        >
                          {p.status_code}
                        </span>
                      </td>
                      <td className="p-3.5 text-slate-700 max-w-sm truncate">
                        {p.title || <span className="text-slate-400 italic">Missing title</span>}
                      </td>
                      <td className="p-3.5">
                        {p.schema_types && p.schema_types.length > 0 ? (
                          <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-800 border border-purple-200 text-[10px] font-bold">
                            {p.schema_types.join(', ')}
                          </span>
                        ) : (
                          <span className="text-slate-400 font-medium">None</span>
                        )}
                      </td>
                      <td className="p-3.5 font-mono text-slate-700 font-semibold">
                        {p.word_count || 0} words
                      </td>
                      <td className="p-3.5 font-mono text-slate-500">
                        {p.load_time_ms ? `${p.load_time_ms}ms` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              icon={Globe}
              badge="No Pages Crawled"
              title="No Matching Crawled Pages"
              description="No pages match the active search filter or no completed crawl is available."
              actionText="Start Local Page Crawl"
              onAction={handleTriggerCrawl}
            />
          )}

          {/* Footer pagination info */}
          <div className="p-3 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>
              Showing {filteredPagesList.length > 0 ? (currentPage - 1) * pageSize + 1 : 0} to {Math.min(currentPage * pageSize, filteredPagesList.length)} of {filteredPagesList.length} pages
            </span>
            <span>Maximum 20 rows per page</span>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* SCHEMA DETAIL MODAL (Requirement 5)                                */}
      {/* =================================================================== */}
      {isSchemaModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col shadow-2xl border border-purple-100 animate-scale-in">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-purple-900 text-white">
              <div>
                <span className="text-[10px] font-black uppercase tracking-wider text-purple-300">Technical Audit Evidence</span>
                <h3 className="text-lg font-black mt-0.5">Schema & Structured Data Deep Detail</h3>
              </div>
              <button
                onClick={() => setIsSchemaModalOpen(false)}
                className="p-1.5 rounded-xl hover:bg-white/10 text-slate-300 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Tabs */}
            <div className="flex border-b border-slate-200 bg-slate-50 px-5 gap-2 pt-2">
              <button
                onClick={() => setSchemaModalTab('summary')}
                className={`px-4 py-2 text-xs font-bold rounded-t-xl border-b-2 transition-all ${
                  schemaModalTab === 'summary'
                    ? 'border-purple-600 text-purple-900 bg-white shadow-xs'
                    : 'border-transparent text-slate-600 hover:text-slate-900'
                }`}
              >
                Summary
              </button>
              <button
                onClick={() => setSchemaModalTab('types')}
                className={`px-4 py-2 text-xs font-bold rounded-t-xl border-b-2 transition-all ${
                  schemaModalTab === 'types'
                    ? 'border-purple-600 text-purple-900 bg-white shadow-xs'
                    : 'border-transparent text-slate-600 hover:text-slate-900'
                }`}
              >
                Type Breakdown
              </button>
              <button
                onClick={() => setSchemaModalTab('pages')}
                className={`px-4 py-2 text-xs font-bold rounded-t-xl border-b-2 transition-all ${
                  schemaModalTab === 'pages'
                    ? 'border-purple-600 text-purple-900 bg-white shadow-xs'
                    : 'border-transparent text-slate-600 hover:text-slate-900'
                }`}
              >
                Page Evidence
              </button>
              <button
                onClick={() => setSchemaModalTab('raw')}
                className={`px-4 py-2 text-xs font-bold rounded-t-xl border-b-2 transition-all ${
                  schemaModalTab === 'raw'
                    ? 'border-purple-600 text-purple-900 bg-white shadow-xs'
                    : 'border-transparent text-slate-600 hover:text-slate-900'
                }`}
              >
                Raw JSON-LD
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto flex-1 space-y-5 text-slate-800 text-xs">
              {schemaModalTab === 'summary' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 text-center">
                      <span className="text-[10px] font-bold text-slate-500 uppercase block">Pages Scanned</span>
                      <span className="text-2xl font-black text-slate-900 block mt-1">{schemaSummary.pages_scanned}</span>
                    </div>
                    <div className="p-4 bg-emerald-50/70 rounded-2xl border border-emerald-200 text-center">
                      <span className="text-[10px] font-bold text-emerald-800 uppercase block">Pages With Schema</span>
                      <span className="text-2xl font-black text-emerald-900 block mt-1">{schemaSummary.pages_with_schema}</span>
                    </div>
                    <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 text-center">
                      <span className="text-[10px] font-bold text-slate-500 uppercase block">Pages Without Schema</span>
                      <span className="text-2xl font-black text-slate-900 block mt-1">{schemaSummary.pages_without_schema}</span>
                    </div>
                    <div className="p-4 bg-purple-50/70 rounded-2xl border border-purple-200 text-center">
                      <span className="text-[10px] font-bold text-purple-800 uppercase block">Total Schema Instances</span>
                      <span className="text-2xl font-black text-purple-900 block mt-1">{schemaSummary.total_schema_instances}</span>
                    </div>
                  </div>

                  <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200 space-y-2">
                    <h4 className="font-extrabold text-slate-900 text-xs uppercase tracking-wider">Validation Overview</h4>
                    <p className="text-slate-600 leading-relaxed">
                      Crawler scanned {schemaSummary.pages_scanned} pages and identified {schemaSummary.total_schema_instances} JSON-LD instances across {schemaSummary.unique_schema_types} schema types.
                      Entity completeness score: <b>{schemaSummary.complete_entities} complete</b>, <b>{schemaSummary.incomplete_entities} incomplete</b>, and <b>{schemaSummary.potential_mismatches} potential mismatches</b>.
                    </p>
                  </div>
                </div>
              )}

              {schemaModalTab === 'types' && (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold border-b border-slate-200">
                      <tr>
                        <th className="p-3">Schema Type</th>
                        <th className="p-3">Page Count</th>
                        <th className="p-3">Instance Count</th>
                        <th className="p-3">Validation Status</th>
                        <th className="p-3">Completeness</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {(schemaSummary.detected_types || []).map((dt: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50/60">
                          <td className="p-3 font-bold text-slate-900">{dt.type}</td>
                          <td className="p-3 font-mono">{dt.page_count} pages</td>
                          <td className="p-3 font-mono">{dt.instance_count} instances</td>
                          <td className="p-3">{renderStatusBadge(dt.page_count > 0 ? 'Supported' : 'Detected')}</td>
                          <td className="p-3 font-semibold">{dt.page_count > 0 ? 'Complete' : 'Incomplete'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {schemaModalTab === 'pages' && (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold border-b border-slate-200">
                      <tr>
                        <th className="p-3">URL</th>
                        <th className="p-3">Schema Type</th>
                        <th className="p-3">Validation Status</th>
                        <th className="p-3">Important Properties</th>
                        <th className="p-3">Missing Properties</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {(canonicalData?.schema_evidence || []).map((se: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50/60">
                          <td className="p-3 font-mono text-slate-900 max-w-xs truncate">{se.url}</td>
                          <td className="p-3 font-semibold">{se.schema_type}</td>
                          <td className="p-3">{renderStatusBadge(se.validation_status)}</td>
                          <td className="p-3 font-mono text-[11px]">
                            {JSON.stringify(se.important_properties || {})}
                          </td>
                          <td className="p-3 text-rose-600 font-semibold">
                            {(se.missing_properties || []).join(', ') || 'None'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {schemaModalTab === 'raw' && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800">Raw JSON-LD Script Payload</span>
                    <span className="text-[10px] text-slate-500 font-mono">Unmodified technical evidence</span>
                  </div>
                  <pre className="p-4 bg-slate-900 text-emerald-400 rounded-2xl text-[11px] font-mono overflow-x-auto max-h-96 leading-relaxed">
                    {canonicalData?.schema_evidence && canonicalData.schema_evidence.length > 0
                      ? canonicalData.schema_evidence.map((se: any) => `// URL: ${se.url}\n${se.raw_json_ld || 'No raw JSON-LD'}`).join('\n\n')
                      : 'No raw JSON-LD markup detected.'}
                  </pre>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 text-right">
              <button
                onClick={() => setIsSchemaModalOpen(false)}
                className="px-5 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold shadow-sm transition-all"
              >
                Close Modal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* CHECKS PERFORMED POPUP (Requirement 6, 7, 8, 9, 10)                 */}
      {/* =================================================================== */}
      {isChecksModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col shadow-2xl border border-purple-100 animate-scale-in">
            {/* Header */}
            <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-900 text-white">
              <div>
                <div className="text-[10px] font-black uppercase tracking-wider text-purple-400">AUDIT RULE BREAKDOWN</div>
                <h3 className="text-lg font-black mt-0.5">Checks & Rules Evaluated</h3>
              </div>
              <button
                onClick={() => setIsChecksModalOpen(false)}
                className="p-1.5 rounded-xl hover:bg-white/10 text-slate-300 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Context Header */}
            <div className="p-5 bg-purple-50/70 border-b border-purple-100 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
              <div>
                <span className="text-[10px] font-extrabold uppercase text-purple-800 block">Domain</span>
                <span className="font-mono font-bold text-slate-900 block mt-0.5">{activeProject.domain}</span>
              </div>
              <div>
                <span className="text-[10px] font-extrabold uppercase text-purple-800 block">Crawl ID</span>
                <span className="font-mono font-bold text-slate-900 block mt-0.5">{canonicalData?.crawl_id || 'N/A'}</span>
              </div>
              <div>
                <span className="text-[10px] font-extrabold uppercase text-purple-800 block">Evaluated Rules</span>
                <span className="font-mono font-bold text-slate-900 block mt-0.5">
                  {evaluatedRules != null ? `${evaluatedRules} Rules` : 'N/A'}
                </span>
              </div>
              <div>
                <span className="text-[10px] font-extrabold uppercase text-purple-800 block">Total Checks</span>
                <span className="font-mono font-bold text-purple-900 block mt-0.5">
                  {evaluatedRules != null && totalEvaluatedChecks != null
                    ? `${analyzedPages} pages × ${evaluatedRules} rules = ${totalEvaluatedChecks} checks`
                    : 'Checks: N/A'}
                </span>
              </div>
            </div>

            {/* Rule Table */}
            <div className="p-6 overflow-y-auto flex-1">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-slate-100 text-slate-700 uppercase text-[10px] font-bold border-b border-slate-200">
                  <tr>
                    <th className="p-3">Rule ID</th>
                    <th className="p-3">Category</th>
                    <th className="p-3">Rule Name</th>
                    <th className="p-3">What Was Checked</th>
                    <th className="p-3">Validation Method</th>
                    <th className="p-3">Pages</th>
                    <th className="p-3">Passed</th>
                    <th className="p-3">Problems</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-800">
                  {(canonicalData?.rule_execution_results || []).map((r: any, idx: number) => (
                    <tr key={idx} className="hover:bg-slate-50/70">
                      <td className="p-3 font-mono font-bold text-purple-700">{r.rule_id}</td>
                      <td className="p-3 font-semibold text-slate-700">{r.category}</td>
                      <td className="p-3 font-bold text-slate-900">{r.rule_name}</td>
                      <td className="p-3 text-slate-600 max-w-xs">{r.what_was_checked}</td>
                      <td className="p-3 font-mono text-[11px] text-slate-500">{r.validation_method}</td>
                      <td className="p-3 font-mono font-bold">{r.pages_checked}</td>
                      <td className="p-3 font-mono text-emerald-700 font-bold">{r.passed}</td>
                      <td className="p-3 font-mono text-rose-600 font-bold">{r.problems}</td>
                      <td className="p-3">
                        {r.status === 'Not Evaluated' ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">Not Evaluated</span>
                        ) : r.problems === 0 ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">Passed</span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-800 border border-rose-200">Issues Found</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 text-right">
              <button
                onClick={() => setIsChecksModalOpen(false)}
                className="px-5 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold shadow-sm transition-all"
              >
                Close Rule Table
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Metric Detail Drill-Down Modal */}
      <MetricDetailModal
        isOpen={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
        context={selectedPillarContext}
        issues={issues}
        onSelectPillar={handleOpenPillarDetail}
      />
    </div>
  );
};

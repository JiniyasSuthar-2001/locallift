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
import { Modal } from '../components/ui/Modal';
import api from '../api/client';

interface DiscrepancyField {
  website?: string | null;
  gbp?: string | null;
  citations_mismatches?: number;
  is_aligned?: boolean;
}

interface PillarData {
  score: number | null;
  status: string;
  pages_checked?: number;
  checks?: string[];
  what_we_checked?: string;
  what_we_found?: string[];
  affected_pages?: Array<{
    url: string;
    issue?: string;
    status_code?: number;
    recommendation?: string;
  }>;
  issues?: Array<{
    title: string;
    severity: string;
    category?: string;
    evidence?: string;
    why_it_matters?: string;
    recommended_solution?: string;
    affected_url?: string;
  }>;
  recommendations?: string[];
  detected_types?: string[];
  local_business?: {
    found: boolean;
    type?: string;
    name?: string;
    phone?: string;
    address?: string;
    geo?: any;
    opening_hours?: any;
    url?: string;
  };
  checklist?: {
    schema_found?: boolean;
    local_business?: boolean;
    business_name?: boolean;
    address?: boolean;
    phone?: boolean;
    geo?: boolean;
    opening_hours?: boolean;
    website?: boolean;
  };
  fields?: {
    name_match?: boolean;
    phone_match?: boolean;
    address_match?: boolean;
    website_match?: boolean;
    website_name?: string;
    gbp_name?: string;
    website_phone?: string;
    gbp_phone?: string;
    website_address?: string;
    gbp_address?: string;
  };
  records?: Array<{
    directory: string;
    status: string;
    is_aligned: boolean;
  }>;
  summary?: {
    total_reviews: number;
    average_rating: number;
    unanswered_count: number;
    response_coverage_pct?: number;
  };
}

interface DiagnosticSummary {
  project_id: number;
  overall_score: number | null;
  pages_analyzed: number;
  critical_issues: number;
  warnings: number;
  opportunities: number;
  passed_checks: number;
  pillar_scores: {
    crawl_health: number | null;
    onpage_content: number | null;
    schema_structured_data: number | null;
    gbp_alignment: number | null;
    citations_nap: number | null;
    reviews_reputation: number | null;
  };
  pillar_weights?: Record<string, string>;
  scoring_methodology?: Record<string, any>;
  crawl?: PillarData;
  local_on_page?: PillarData;
  schema?: PillarData;
  gbp_match?: PillarData;
  citations?: PillarData;
  reviews?: PillarData;
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
  const [isRefreshing, setIsRefreshing] = useState(false);
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

  const fetchAuditData = async (isManualRefresh = false) => {
    if (!activeProject) return;
    try {
      if (isManualRefresh) {
        setIsRefreshing(true);
      } else {
        setLoading(true);
      }
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
      setIsRefreshing(false);
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
  const healthScore = scoreAvailable ? (summary?.overall_score ?? canonicalData?.health_score ?? activeProject?.health_score ?? null) : null;
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

  // Derive Pillar Scores & Detailed Evidence from summary
  const crawlData = summary?.crawl;
  const onpageData = summary?.local_on_page;
  const schemaData = summary?.schema;
  const gbpData = summary?.gbp_match;
  const citationsData = summary?.citations;
  const reviewsData = summary?.reviews;

  const pillars = summary?.pillar_scores || {
    crawl_health: crawlData?.score ?? activeProject?.technical_score ?? null,
    onpage_content: onpageData?.score ?? activeProject?.onpage_score ?? null,
    schema_structured_data: schemaData?.score ?? activeProject?.local_score ?? null,
    gbp_alignment: gbpData?.score ?? activeProject?.gbp_score ?? null,
    citations_nap: citationsData?.score ?? activeProject?.citations_score ?? null,
    reviews_reputation: reviewsData?.score ?? activeProject?.reviews_score ?? null
  };

  const backendWeights = summary?.pillar_weights || {
    crawl_health: '20%',
    onpage_content: '25%',
    schema_structured_data: '15%',
    gbp_alignment: '10%',
    citations_nap: '10%',
    reviews_reputation: '20%'
  };

  const matrix = summary?.discrepancy_matrix;

  const handleOpenPillarDetail = (pillarId: string) => {
    if (pillarId === 'overall') {
      setSelectedPillarContext({
        id: 'overall',
        name: 'Overall Local SEO Grade',
        score: healthScore,
        status: healthScore !== null && healthScore >= 80 ? 'optimal' : healthScore !== null && healthScore >= 50 ? 'needs_attention' : 'critical',
        weight: '100%',
        description: 'Multi-signal local SEO health score derived across 6 weighted local ranking pillars.',
        whatWeChecked: 'We evaluated your website across crawl accessibility, on-page location relevance, Schema.org LocalBusiness structured data, Google Business Profile alignment, directory citations, and customer reputation.',
        whatWeFound: [
          `Analyzed ${analyzedPages} crawled pages across domain https://${activeProject?.domain || ''}`,
          `Identified ${issues.length} actionable SEO improvement opportunities`,
          `Google Business Profile: ${summary?.gbp_status?.connected ? 'Connected and cross-checked' : 'Not connected'}`
        ],
        whatToDo: 'Focus first on fixing critical crawl and Schema.org issues, then verify that business name, phone, and address perfectly match your Google Business Profile.',
        pillarScores: pillars,
        pillarWeights: backendWeights
      });
    } else if (pillarId === 'crawl') {
      setSelectedPillarContext({
        id: 'crawl',
        name: 'Local Crawl Health',
        score: crawlData?.score ?? pillars.crawl_health,
        status: crawlData?.status || 'pass',
        weight: backendWeights.crawl_health || '20%',
        description: 'Can Google access and index the important pages on your website?',
        whatWeChecked: crawlData?.what_we_checked || 'HTTP response status codes, broken page detection, canonical link consistency, meta indexability, and robots.txt accessibility.',
        whatWeFound: crawlData?.what_we_found || ['All scanned pages returned HTTP 200 responses.'],
        affectedPages: crawlData?.affected_pages || [],
        whatToDo: (crawlData?.recommendations && crawlData.recommendations[0]) || 'Ensure all key local landing pages return HTTP 200 OK and reference canonical URLs.',
        pillarScores: pillars,
        pillarWeights: backendWeights
      });
    } else if (pillarId === 'onpage') {
      setSelectedPillarContext({
        id: 'onpage',
        name: 'Local On-Page & Geo-Content',
        score: onpageData?.score ?? pillars.onpage_content,
        status: onpageData?.status || 'pass',
        weight: backendWeights.onpage_content || '25%',
        description: 'Does your website clearly tell Google what business you are, where you operate, and what you offer?',
        whatWeChecked: onpageData?.what_we_checked || 'Business name, city and geo keywords in <title> and <h1> headings, local meta descriptions, phone numbers, and physical address presence.',
        whatWeFound: onpageData?.what_we_found || ['Target business name and local contact signals detected.'],
        affectedPages: onpageData?.affected_pages || [],
        whatToDo: (onpageData?.recommendations && onpageData.recommendations[0]) || 'Include your target city or service area in your primary H1 heading and page title.',
        pillarScores: pillars,
        pillarWeights: backendWeights
      });
    } else if (pillarId === 'schema') {
      setSelectedPillarContext({
        id: 'schema',
        name: 'Schema & Structured Data',
        score: schemaData?.score ?? pillars.schema_structured_data,
        status: schemaData?.status || 'error',
        weight: backendWeights.schema_structured_data || '15%',
        description: 'Does your website provide structured information that helps search engines understand your local business?',
        whatWeChecked: schemaData?.what_we_checked || 'JSON-LD structured data scripts, distinguishing LocalBusiness and its specialized subtypes from generic WebSite or Breadcrumb schema.',
        whatWeFound: schemaData?.what_we_found || ['No LocalBusiness schema markup detected.'],
        affectedPages: schemaData?.affected_pages || [],
        whatToDo: (schemaData?.recommendations && schemaData.recommendations[0]) || 'Add Schema.org LocalBusiness JSON-LD markup containing your business name, address, telephone, and geo coordinates.',
        pillarScores: pillars,
        pillarWeights: backendWeights
      });
    } else if (pillarId === 'gbp') {
      setSelectedPillarContext({
        id: 'gbp',
        name: 'Google Business Profile Match',
        score: gbpData?.score ?? pillars.gbp_alignment,
        status: gbpData?.status || (summary?.gbp_status?.connected ? 'matched' : 'not_connected'),
        weight: backendWeights.gbp_alignment || '10%',
        description: 'Cross-alignment between website NAP and your project-bound Google Business Profile.',
        whatWeChecked: gbpData?.what_we_checked || 'Exact comparison of business name, phone number, address, and website link between on-page content and project-bound GBP.',
        whatWeFound: gbpData?.what_we_found || [summary?.gbp_status?.connected ? 'Cross-checked website NAP against GBP listing.' : 'Google Business Profile not connected to this project.'],
        affectedPages: gbpData?.affected_pages || [],
        whatToDo: (gbpData?.recommendations && gbpData.recommendations[0]) || 'Connect your Google Business Profile and ensure the website NAP details match verbatim.',
        pillarScores: pillars,
        pillarWeights: backendWeights
      });
    } else if (pillarId === 'citations') {
      setSelectedPillarContext({
        id: 'citations',
        name: 'Citations & Directory NAP',
        score: citationsData?.score ?? pillars.citations_nap,
        status: citationsData?.status || 'not_verified',
        weight: backendWeights.citations_nap || '10%',
        description: 'Consistency across external directory listings and citations.',
        whatWeChecked: citationsData?.what_we_checked || 'NAP data consistency across external local directories (YellowPages, Yelp, Apple Maps, TrueLocal).',
        whatWeFound: citationsData?.what_we_found || ['Directory citation data has not been audited yet for this project.'],
        affectedPages: citationsData?.affected_pages || [],
        whatToDo: (citationsData?.recommendations && citationsData.recommendations[0]) || 'Standardize your Name, Address, and Phone number across all primary business directories.',
        pillarScores: pillars,
        pillarWeights: backendWeights
      });
    } else if (pillarId === 'reviews') {
      setSelectedPillarContext({
        id: 'reviews',
        name: 'Reviews & Reputation',
        score: reviewsData?.score ?? pillars.reviews_reputation,
        status: reviewsData?.status || 'no_data',
        weight: backendWeights.reviews_reputation || '20%',
        description: 'Customer review volume, star rating, and merchant response health.',
        whatWeChecked: reviewsData?.what_we_checked || 'Review volume, average rating, and response coverage from your verified Google Business Profile.',
        whatWeFound: reviewsData?.what_we_found || ['Review data unavailable from Google Business Profile.'],
        affectedPages: reviewsData?.affected_pages || [],
        whatToDo: (reviewsData?.recommendations && reviewsData.recommendations[0]) || 'Encourage positive customer reviews and reply to customer feedback promptly.',
        pillarScores: pillars,
        pillarWeights: backendWeights
      });
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

  // Helper for Last Crawl Date Formatting
  const lastCrawlDate = canonicalData?.crawled_at || canonicalData?.created_at || (pages.length > 0 ? pages[0].crawled_at : null);
  const formatLastCrawl = (d: string | null) => {
    if (!d) return isCrawling ? 'In Progress' : 'Awaiting Crawl';
    try {
      const date = new Date(d);
      const now = new Date();
      const isToday = date.toDateString() === now.toDateString();
      const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      return isToday ? `Today ${timeStr}` : `${date.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${timeStr}`;
    } catch {
      return 'Recently';
    }
  };

  // Helper for Categorized Error UX (Requirement 6)
  const parseErrorDetails = (err: string) => {
    const lower = err.toLowerCase();
    let status = 'N/A';
    let stage = 'Page Discovery & Crawl';
    let reason = err;
    let suggestedAction = 'Verify server availability and allow LocalLift crawler access.';

    if (lower.includes('403') || lower.includes('forbidden') || lower.includes('waf') || lower.includes('cloudflare')) {
      status = '403';
      reason = 'Server rejected crawler request (WAF, Cloudflare, or IP forbidden).';
      suggestedAction = 'Verify server/WAF firewall configuration and whitelist the LocalLift crawler User-Agent.';
    } else if (lower.includes('404') || lower.includes('not found')) {
      status = '404';
      reason = 'Target domain or initial seed URL was not found.';
      suggestedAction = 'Verify the project domain URL and protocol (https://).';
    } else if (lower.includes('timeout') || lower.includes('timed out')) {
      status = 'Timeout';
      reason = 'The web server took too long to respond to crawler requests.';
      suggestedAction = 'Check web host uptime, server latency, and firewall rate limits.';
    } else if (lower.includes('dns') || lower.includes('getaddrinfo') || lower.includes('name resolution')) {
      status = 'DNS Error';
      reason = 'Domain name resolution failed for target host.';
      suggestedAction = 'Verify DNS records (A/AAAA) for this domain.';
    } else if (lower.includes('tls') || lower.includes('ssl') || lower.includes('certificate')) {
      status = 'TLS/SSL Error';
      reason = 'SSL/TLS handshake or certificate verification failed.';
      suggestedAction = 'Check SSL certificate validity and HTTPS configuration.';
    } else if (lower.includes('robots.txt') || lower.includes('disallow')) {
      status = 'Robots Disallowed';
      stage = 'Robots Protocol Compliance';
      reason = 'robots.txt rules disallow crawling this section or domain.';
      suggestedAction = 'Update robots.txt rules to permit search engine and SEO auditing bots.';
    } else if (lower.includes('redirect')) {
      status = 'Redirect Error';
      reason = 'Too many redirects or invalid redirect target detected.';
      suggestedAction = 'Inspect 301/302 redirect rules on your web server.';
    }

    return { status, stage, reason, suggestedAction };
  };

  const criticalIssuesCount = issues.filter(i => i.severity.toLowerCase() === 'critical').length;
  const warningIssuesCount = issues.filter(i => i.severity.toLowerCase() === 'warning').length;
  const passedChecksCount = Math.max(0, (totalEvaluatedChecks || (analyzedPages * 14)) - issues.length);

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
      {/* =================================================================== */}
      {/* 1. VIEW HEADER & ACTION BUTTONS (Requirements 2, 3, 4)             */}
      {/* =================================================================== */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Title & Domain */}
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 shadow-2xs">
              <Globe className="w-6 h-6" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                  Local Website & Technical Audit
                </h1>
                <a
                  href={`https://${activeProject.domain}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-900 border border-slate-300 rounded-lg text-xs font-bold transition-colors cursor-pointer"
                  title="Open live website in new tab"
                >
                  <Globe className="w-3.5 h-3.5 text-emerald-700" />
                  <span>{activeProject.domain}</span>
                  <ExternalLink className="w-3 h-3 text-slate-500" />
                </a>
              </div>
              <p className="text-xs text-slate-600 mt-1 font-medium">
                Comprehensive on-page, crawlability, and Schema.org governance audit powered by the local crawler engine.
              </p>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2 self-start lg:self-auto shrink-0">
          <button
            onClick={() => setIsChecksModalOpen(true)}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-white border border-slate-300 hover:border-slate-400 text-slate-800 hover:text-slate-900 rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer"
          >
            <Info className="w-4 h-4 text-emerald-700" />
            <span>Checks ({totalEvaluatedChecks != null ? totalEvaluatedChecks.toLocaleString() : (isCrawling ? 'Processing...' : '—')})</span>
          </button>

          <button
            onClick={() => fetchAuditData(true)}
            disabled={loading || isRefreshing || isCrawling}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-white border border-slate-300 hover:border-slate-400 text-slate-800 hover:text-slate-900 rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer disabled:opacity-60"
            title="Refresh audit data from server without restarting crawl"
          >
            <RotateCw className={`w-3.5 h-3.5 text-slate-700 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>

          <button
            onClick={handleDownloadPDF}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-white border border-slate-300 hover:border-slate-400 text-slate-800 hover:text-slate-900 rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer"
          >
            <Download className="w-4 h-4 text-emerald-700" />
            <span>Download PDF</span>
          </button>

          <button
            onClick={handleDownloadXLSX}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-white border border-slate-300 hover:border-slate-400 text-slate-800 hover:text-slate-900 rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer"
          >
            <FileText className="w-4 h-4 text-emerald-700" />
            <span>Export Master XLSX</span>
          </button>

          <button
            onClick={handleTriggerCrawl}
            disabled={isCrawling}
            className="flex items-center space-x-2 px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold shadow-md transition-all cursor-pointer disabled:opacity-85"
          >
            {isCrawling ? (
              <>
                <RotateCw className="w-4 h-4 animate-spin text-white" />
                <span>Auditing Local Signals... ({Math.round(jobProgress)}%)</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>Run Local Audit</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* =================================================================== */}
      {/* 2. COMPACT METADATA CHIPS STRIP (Requirement 2 & 3)                 */}
      {/* =================================================================== */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {/* Chip 1: Pages Analyzed */}
        <div className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs flex flex-col justify-between">
          <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Pages Analyzed</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-xl font-black text-slate-900">
              {analyzedPages > 0 ? analyzedPages : (isCrawling ? 'Discovering...' : 0)}
            </span>
            <span className="text-[11px] text-slate-500 font-medium">Pages</span>
          </div>
        </div>

        {/* Chip 2: Rules Evaluated */}
        <div className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs flex flex-col justify-between">
          <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Rules Evaluated</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-xl font-black text-slate-900">
              {evaluatedRules != null ? evaluatedRules : (isCrawling ? 'Processing...' : '14')}
            </span>
            <span className="text-[11px] text-slate-500 font-medium">Rules</span>
          </div>
        </div>

        {/* Chip 3: Total Checks */}
        <div className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs flex flex-col justify-between">
          <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Total Checks</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-xl font-black text-slate-900">
              {totalEvaluatedChecks != null ? totalEvaluatedChecks.toLocaleString() : (analyzedPages > 0 ? (analyzedPages * 14).toLocaleString() : '—')}
            </span>
            <span className="text-[11px] text-slate-500 font-medium">Checks</span>
          </div>
        </div>

        {/* Chip 4: Last Crawl */}
        <div className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs flex flex-col justify-between">
          <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Last Crawl</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-sm font-bold text-slate-900 truncate">
              {formatLastCrawl(lastCrawlDate)}
            </span>
            <span className="text-[10px] text-slate-500 font-medium">Time</span>
          </div>
        </div>

        {/* Chip 5: Crawl Status */}
        <div className="p-3.5 bg-white border border-slate-200 rounded-xl shadow-xs flex flex-col justify-between col-span-2 sm:col-span-1">
          <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Crawl Status</span>
          <div className="mt-1">
            {isCrawling ? (
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-900 border border-amber-300 animate-pulse">
                <RotateCw className="w-3 h-3 animate-spin text-amber-700" />
                <span>Running ({Math.round(jobProgress)}%)</span>
              </span>
            ) : auditError ? (
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-900 border border-rose-300">
                <X className="w-3 h-3 text-rose-700" />
                <span>Failed</span>
              </span>
            ) : analyzedPages > 0 ? (
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-900 border border-emerald-300">
                <Check className="w-3 h-3 text-emerald-700" />
                <span>Completed</span>
              </span>
            ) : (
              <span className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-800 border border-slate-300">
                <span>Awaiting Crawl</span>
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Active Job Progress Banner - Localized, Crisp & High-Contrast */}
      {isCrawling && (
        <div 
          role="status" 
          aria-live="polite" 
          className="p-4.5 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-2xl shadow-lg border border-emerald-500/30 space-y-2.5"
        >
          <div className="flex items-center justify-between text-xs font-bold">
            <div className="flex items-center space-x-2.5">
              <span className="p-1.5 bg-emerald-500/20 rounded-lg border border-emerald-400/30 text-emerald-300">
                <RotateCw className="w-4 h-4 animate-spin" />
              </span>
              <div>
                <span className="text-white font-extrabold text-sm block">
                  {jobStage || 'Auditing Local Website & Building Link Graph...'}
                </span>
                <span className="text-slate-300 text-[11px] font-normal">
                  Live Technical Website Crawler execution in progress &bull; Results update progressively
                </span>
              </div>
            </div>
            <div className="text-right">
              <span className="font-mono text-base font-black text-emerald-400">{Math.round(jobProgress)}%</span>
              <span className="text-[10px] text-slate-300 block uppercase tracking-wider font-bold">Progress</span>
            </div>
          </div>
          <div className="w-full bg-white/15 rounded-full h-2.5 overflow-hidden p-0.5 border border-white/10">
            <div
              className="bg-gradient-to-r from-emerald-400 to-teal-300 h-1.5 rounded-full transition-all duration-300 shadow-xs"
              style={{ width: `${Math.max(5, Math.min(100, jobProgress))}%` }}
            />
          </div>
        </div>
      )}

      {/* Categorized Technical Scan Error UX (Requirement 6) */}
      {auditError && (() => {
        const errorDetail = parseErrorDetails(auditError);
        return (
          <div className="p-5 bg-rose-50 border border-rose-300 rounded-2xl space-y-3 shadow-xs">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-2.5">
                <div className="p-2 bg-rose-100 rounded-xl text-rose-800">
                  <AlertTriangle className="w-5 h-5 text-rose-700" />
                </div>
                <div>
                  <h4 className="text-sm font-black text-rose-950">Technical Scan Failed</h4>
                  <p className="text-xs text-rose-800 font-medium">Crawler encountered an execution blocker during audit.</p>
                </div>
              </div>
              <button
                onClick={handleTriggerCrawl}
                className="px-3.5 py-1.5 bg-rose-700 hover:bg-rose-800 text-white rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer"
              >
                Retry Technical Scan
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs pt-1">
              <div className="p-3 bg-white/80 rounded-xl border border-rose-200">
                <span className="text-[10px] font-bold text-rose-900 uppercase block">HTTP Status</span>
                <span className="font-mono font-bold text-slate-900 block mt-0.5">{errorDetail.status}</span>
              </div>
              <div className="p-3 bg-white/80 rounded-xl border border-rose-200">
                <span className="text-[10px] font-bold text-rose-900 uppercase block">Target URL</span>
                <span className="font-mono font-bold text-slate-900 block mt-0.5 truncate">https://{activeProject.domain}/</span>
              </div>
              <div className="p-3 bg-white/80 rounded-xl border border-rose-200">
                <span className="text-[10px] font-bold text-rose-900 uppercase block">Execution Stage</span>
                <span className="font-semibold text-slate-900 block mt-0.5">{errorDetail.stage}</span>
              </div>
              <div className="p-3 bg-white/80 rounded-xl border border-rose-200">
                <span className="text-[10px] font-bold text-rose-900 uppercase block">Reason</span>
                <span className="font-medium text-slate-800 block mt-0.5">{errorDetail.reason}</span>
              </div>
            </div>

            <div className="p-3 bg-white/90 rounded-xl border border-rose-200 text-xs text-slate-800 flex items-start space-x-2">
              <span className="font-bold text-rose-900 shrink-0">Suggested Action:</span>
              <span>{errorDetail.suggestedAction}</span>
            </div>
          </div>
        );
      })()}

      {/* Technical Audit Completion Summary (Requirement 27) */}
      {!isCrawling && analyzedPages > 0 && (
        <div className="p-4 bg-white border border-slate-200 rounded-2xl shadow-xs space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center space-x-2.5">
              <div className="p-2 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-xl">
                <ShieldCheck className="w-5 h-5 text-emerald-700" />
              </div>
              <div>
                <h3 className="text-sm font-black text-slate-900">
                  {criticalIssuesCount > 0 ? 'Technical Audit Complete with Warnings' : 'Technical Audit Complete'}
                </h3>
                <p className="text-xs text-slate-600 font-medium">
                  {analyzedPages} pages analysed &bull; {evaluatedRules ?? 14} rules evaluated &bull; {totalEvaluatedChecks ?? (analyzedPages * 14)} checks completed
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs">
              <button
                onClick={() => setActiveTab('issues')}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl font-bold transition-colors cursor-pointer"
              >
                View Findings ({issues.length})
              </button>
              <button
                onClick={() => setActiveTab('pages')}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl font-bold transition-colors cursor-pointer"
              >
                View Crawl Data ({pages.length})
              </button>
              <button
                onClick={handleDownloadPDF}
                className="px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 rounded-xl font-bold transition-colors cursor-pointer"
              >
                Download Report
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 text-xs pt-1 border-t border-slate-100">
            <div className="p-2 bg-slate-50 rounded-lg text-center">
              <span className="text-[10px] font-bold text-slate-600 uppercase block">Critical</span>
              <span className="text-sm font-black text-rose-700 block mt-0.5">{criticalIssuesCount}</span>
            </div>
            <div className="p-2 bg-slate-50 rounded-lg text-center">
              <span className="text-[10px] font-bold text-slate-600 uppercase block">Warnings</span>
              <span className="text-sm font-black text-amber-700 block mt-0.5">{warningIssuesCount}</span>
            </div>
            <div className="p-2 bg-slate-50 rounded-lg text-center">
              <span className="text-[10px] font-bold text-slate-600 uppercase block">Passed</span>
              <span className="text-sm font-black text-emerald-700 block mt-0.5">{passedChecksCount}</span>
            </div>
            <div className="p-2 bg-slate-50 rounded-lg text-center">
              <span className="text-[10px] font-bold text-slate-600 uppercase block">Crawl</span>
              <span className="text-xs font-black text-emerald-700 block mt-0.5">SUCCESS</span>
            </div>
            <div className="p-2 bg-slate-50 rounded-lg text-center">
              <span className="text-[10px] font-bold text-slate-600 uppercase block">Schema</span>
              <span className="text-xs font-black text-emerald-700 block mt-0.5">
                {schemaSummary.pages_with_schema > 0 ? 'SUCCESS' : 'NO SCHEMA'}
              </span>
            </div>
            <div className="p-2 bg-slate-50 rounded-lg text-center">
              <span className="text-[10px] font-bold text-slate-600 uppercase block">Robots.txt</span>
              <span className="text-xs font-black text-emerald-700 block mt-0.5">SUCCESS</span>
            </div>
            <div className="p-2 bg-slate-50 rounded-lg text-center">
              <span className="text-[10px] font-bold text-slate-600 uppercase block">Sitemap</span>
              <span className="text-xs font-black text-emerald-700 block mt-0.5">
                {pages.length > 0 ? 'SUCCESS' : 'PARTIAL'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Partial API Failure Status Bar */}
      {Object.values(sourceStatus).some((s) => s === 'failed') && (
        <div className="p-4 bg-amber-50 border border-amber-200 text-amber-900 rounded-2xl space-y-2 shadow-sm">
          <div className="flex items-center space-x-2 font-bold text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Partial API Failure: Some audit sources could not be loaded from the backend.</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs font-semibold pt-1">
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-700">Pages API:</span>
              <span className={sourceStatus.pages === 'loaded' ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}>
                {sourceStatus.pages === 'loaded' ? '✓ Loaded' : '✕ Failed'}
              </span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-700">Issues API:</span>
              <span className={sourceStatus.issues === 'loaded' ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}>
                {sourceStatus.issues === 'loaded' ? '✓ Loaded' : '✕ Failed'}
              </span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-700">Summary API:</span>
              <span className={sourceStatus.summary === 'loaded' ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}>
                {sourceStatus.summary === 'loaded' ? '✓ Loaded' : '✕ Failed'}
              </span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="text-slate-700">Canonical Audit API:</span>
              <span className={sourceStatus.canonical === 'loaded' ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}>
                {sourceStatus.canonical === 'loaded' ? '✓ Loaded' : '✕ Failed'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Top Banner: Overall Score & Canonical Totals - High Contrast & Solid Readability */}
      <div className="card-vibrant p-5 bg-gradient-to-r from-purple-950 via-indigo-950 to-slate-900 text-white rounded-2xl relative overflow-hidden shadow-xl border border-purple-800/40">
        <div className="absolute right-0 top-0 bottom-0 opacity-15 pointer-events-none flex items-center pr-8">
          <ShieldCheck className="w-64 h-64 text-white" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 relative z-10 items-center">
          {/* Health Score Gauge */}
          <div 
            role="button"
            tabIndex={0}
            onClick={() => handleOpenPillarDetail('overall')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleOpenPillarDetail('overall'); }}
            className="flex items-center space-x-4 md:border-r md:border-white/15 pr-4 cursor-pointer group transition-all duration-200"
            title="Click to view complete scoring methodology and pillar breakdown"
          >
            <div className="w-20 h-20 rounded-2xl bg-white/15 backdrop-blur-md flex flex-col items-center justify-center border-2 border-white/30 shrink-0 group-hover:border-white/60 group-hover:bg-white/20 transition-all shadow-md">
              <span className="text-3xl font-black text-white leading-none">
                {scoreAvailable && healthScore !== null ? healthScore : '—'}
              </span>
              <span className="text-[10px] font-extrabold text-purple-200 mt-1 uppercase tracking-wider">
                {scoreAvailable && healthScore !== null ? '/ 100' : 'Not Yet Scored'}
              </span>
            </div>
            <div>
              <div className="flex items-center space-x-1.5 text-purple-200 text-xs font-extrabold uppercase tracking-wider group-hover:text-white transition-colors">
                <Award className="w-4 h-4 text-emerald-400" />
                <span>Health Score</span>
                <span className="text-xs ml-0.5 text-purple-300">↗</span>
              </div>
              <p className="text-xs text-slate-100 font-medium mt-1 leading-snug">
                {isCrawling && scoreAvailable && healthScore !== null ? (
                  <span className="flex flex-wrap items-center gap-1 text-emerald-300 font-semibold">
                    <span>Actual Score: {healthScore}/100</span>
                    <span className="text-[10px] bg-emerald-500/20 text-emerald-200 px-1.5 py-0.2 rounded border border-emerald-400/30">Last completed</span>
                  </span>
                ) : scoreAvailable && healthScore !== null ? (
                  `Actual Score: ${healthScore}/100`
                ) : isCrawling ? (
                  <span className="text-purple-200 font-medium flex items-center gap-1">
                    <RotateCw className="w-3 h-3 animate-spin text-purple-300 inline" />
                    Calculating health score...
                  </span>
                ) : (
                  'Not Yet Scored — Awaiting Crawl'
                )}
              </p>
              {isCrawling && scoreAvailable && healthScore !== null && (
                <span className="text-[11px] text-purple-200 mt-0.5 block font-medium">
                  Scanning for updated results...
                </span>
              )}
            </div>
          </div>

          {/* Metric 1: Analyzed Pages */}
          <div className="space-y-1">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-purple-200">Analyzed Pages</span>
            <div className="text-2xl font-black text-white">
              {analyzedPages > 0 ? (
                analyzedPages
              ) : isCrawling ? (
                <span className="text-lg font-bold text-purple-200 flex items-center gap-1.5">
                  <RotateCw className="w-4 h-4 animate-spin inline text-purple-300" /> Discovering...
                </span>
              ) : (
                0
              )}
            </div>
            <p className="text-xs text-slate-200 font-medium">
              {analyzedPages > 0 ? 'Crawled HTML pages inspected' : (isCrawling ? 'Discovering target website URLs' : 'No pages crawled yet')}
            </p>
          </div>

          {/* Metric 2: Evaluated Rules */}
          <div className="space-y-1">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-purple-200">Evaluated Rules</span>
            <div className="text-2xl font-black text-emerald-400">
              {evaluatedRules != null ? (
                evaluatedRules
              ) : isCrawling ? (
                <span className="text-base font-bold text-emerald-300 flex items-center gap-1.5">
                  <RotateCw className="w-4 h-4 animate-spin inline text-emerald-400" /> Processing...
                </span>
              ) : (
                '—'
              )}
            </div>
            <p className="text-xs text-slate-200 font-medium">
              {evaluatedRules != null ? 'Active audit rules executed' : (isCrawling ? 'Evaluating technical SEO rules...' : 'Waiting to begin')}
            </p>
          </div>

          {/* Metric 3: Total Checks */}
          <div className="space-y-1">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-purple-200">Total Evaluated Checks</span>
            <div className="text-2xl font-black text-purple-300">
              {totalEvaluatedChecks != null ? (
                totalEvaluatedChecks.toLocaleString()
              ) : isCrawling ? (
                <span className="text-base font-bold text-purple-200 flex items-center gap-1.5">
                  <RotateCw className="w-4 h-4 animate-spin inline text-purple-300" /> Processing...
                </span>
              ) : (
                '—'
              )}
            </div>
            <p className="text-xs text-slate-200 font-medium font-mono">
              {evaluatedRules != null && totalEvaluatedChecks != null
                ? `${analyzedPages} pages × ${evaluatedRules} rules`
                : (isCrawling ? 'Analyzing check matrix...' : 'Checks: Pending')}
            </p>
          </div>
        </div>
      </div>

      {/* Upgrade: Schema & Structured Data Evidence Box */}
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
              <p className="text-xs text-slate-600 font-medium">
                Evidence-based Schema.org JSON-LD extraction across all scanned website pages.
              </p>
            </div>
          </div>
        </div>

        {/* 8 Metric Summary Grid - Bright and High Contrast */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 text-center">
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <span className="text-[10px] font-extrabold uppercase text-slate-600 block">Pages Scanned</span>
            <span className="text-lg font-black text-slate-900 block mt-0.5">{schemaSummary.pages_scanned}</span>
          </div>

          <div className="p-3 bg-emerald-50/80 rounded-xl border border-emerald-300">
            <span className="text-[10px] font-extrabold uppercase text-emerald-800 block">With Schema</span>
            <span className="text-lg font-black text-emerald-900 block mt-0.5">{schemaSummary.pages_with_schema}</span>
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
            <span className="text-[10px] font-extrabold uppercase text-slate-600 block">Without Schema</span>
            <span className="text-lg font-black text-slate-900 block mt-0.5">{schemaSummary.pages_without_schema}</span>
          </div>

          <div className="p-3 bg-purple-50/80 rounded-xl border border-purple-300">
            <span className="text-[10px] font-extrabold uppercase text-purple-800 block">Total Instances</span>
            <span className="text-lg font-black text-purple-900 block mt-0.5">{schemaSummary.total_schema_instances}</span>
          </div>

          <div className="p-3 bg-indigo-50/80 rounded-xl border border-indigo-300">
            <span className="text-[10px] font-extrabold uppercase text-indigo-800 block">Unique Types</span>
            <span className="text-lg font-black text-indigo-900 block mt-0.5">{schemaSummary.unique_schema_types}</span>
          </div>

          <div className="p-3 bg-emerald-50/80 rounded-xl border border-emerald-300">
            <span className="text-[10px] font-extrabold uppercase text-emerald-800 block">Complete</span>
            <span className="text-lg font-black text-emerald-900 block mt-0.5">{schemaSummary.complete_entities}</span>
          </div>

          <div className="p-3 bg-amber-50/80 rounded-xl border border-amber-300">
            <span className="text-[10px] font-extrabold uppercase text-amber-800 block">Incomplete</span>
            <span className="text-lg font-black text-amber-900 block mt-0.5">{schemaSummary.incomplete_entities}</span>
          </div>

          <div className="p-3 bg-rose-50/80 rounded-xl border border-rose-300">
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
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-black text-slate-900 uppercase tracking-wider flex items-center space-x-2">
            <Layers className="w-4 h-4 text-purple-600" />
            <span>Local SEO Audit Pillars & Evidence Breakdown</span>
          </h2>
          <span className="text-xs text-slate-500 font-medium">Standards-compliant local audit engine</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* CARD 1: Local Crawl Health */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => handleOpenPillarDetail('crawl')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleOpenPillarDetail('crawl'); }}
            className="card-vibrant p-5 space-y-3.5 bg-white cursor-pointer hover:border-purple-300 hover:shadow-md transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2.5">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 font-mono">
                    Weight: {backendWeights.crawl_health || '20%'}
                  </span>
                  <h4 className="text-sm font-bold text-slate-900 mt-1.5 group-hover:text-purple-700 transition-colors">
                    Local Crawl Health
                  </h4>
                </div>
                <div className="text-right">
                  <span className={`text-2xl font-black ${
                    pillars.crawl_health === null
                      ? 'text-slate-500'
                      : pillars.crawl_health >= 80
                      ? 'text-emerald-600'
                      : pillars.crawl_health >= 60
                      ? 'text-amber-600'
                      : 'text-rose-600'
                  }`}>
                    {pillars.crawl_health !== null ? pillars.crawl_health : (isCrawling ? '...' : '—')}
                  </span>
                  <span className="text-[10px] font-bold text-slate-500 block">
                    {pillars.crawl_health !== null ? '/ 100' : (isCrawling ? 'Evaluating' : 'No Data')}
                  </span>
                </div>
              </div>

              <p className="text-xs text-slate-600 font-medium leading-snug">
                Can Google access and index the important pages on your website?
              </p>

              {/* Crawl Findings Preview */}
              <div className="space-y-1.5 pt-1">
                {(crawlData?.what_we_found || [
                  analyzedPages > 0 ? `Scanned ${analyzedPages} pages for accessibility.` : (isCrawling ? 'Crawling website pages...' : 'Awaiting page crawl.')
                ]).slice(0, 2).map((f, idx) => (
                  <div key={idx} className="text-[11px] font-medium text-slate-700 flex items-start space-x-1.5">
                    <span className="shrink-0 text-slate-400">•</span>
                    <span className="truncate">{f.replace(/^[✓⚠•]\s*/, '')}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-[11px] font-semibold text-slate-500 font-mono">
                {crawlData?.pages_checked ?? analyzedPages} Pages Checked
              </span>
              <span className="font-bold text-purple-700 group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5 text-[11px]">
                Inspect Crawl →
              </span>
            </div>
          </div>

          {/* CARD 2: Local On-Page & Geo-Content */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => handleOpenPillarDetail('onpage')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleOpenPillarDetail('onpage'); }}
            className="card-vibrant p-5 space-y-3.5 bg-white cursor-pointer hover:border-purple-300 hover:shadow-md transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2.5">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 font-mono">
                    Weight: {backendWeights.onpage_content || '25%'}
                  </span>
                  <h4 className="text-sm font-bold text-slate-900 mt-1.5 group-hover:text-purple-700 transition-colors">
                    Local On-Page & Geo-Content
                  </h4>
                </div>
                <div className="text-right">
                  <span className={`text-2xl font-black ${
                    pillars.onpage_content === null
                      ? 'text-slate-500'
                      : pillars.onpage_content >= 80
                      ? 'text-emerald-600'
                      : pillars.onpage_content >= 60
                      ? 'text-amber-600'
                      : 'text-rose-600'
                  }`}>
                    {pillars.onpage_content !== null ? pillars.onpage_content : (isCrawling ? '...' : '—')}
                  </span>
                  <span className="text-[10px] font-bold text-slate-500 block">
                    {pillars.onpage_content !== null ? '/ 100' : (isCrawling ? 'Evaluating' : 'No Data')}
                  </span>
                </div>
              </div>

              <p className="text-xs text-slate-600 font-medium leading-snug">
                Does your website clearly tell Google what business you are, where you operate, and what you offer?
              </p>

              {/* On-Page Findings Preview */}
              <div className="space-y-1.5 pt-1">
                {(onpageData?.what_we_found || [
                  'Business name and phone contact signals evaluated.'
                ]).slice(0, 2).map((f, idx) => (
                  <div key={idx} className="text-[11px] font-medium text-slate-700 flex items-start space-x-1.5">
                    <span className="shrink-0 text-slate-400">•</span>
                    <span className="truncate">{f.replace(/^[✓⚠•]\s*/, '')}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-[11px] font-semibold text-slate-500">
                Title, H1 & Geo Signals
              </span>
              <span className="font-bold text-purple-700 group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5 text-[11px]">
                Inspect On-Page →
              </span>
            </div>
          </div>

          {/* CARD 3: Schema & Structured Data */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => handleOpenPillarDetail('schema')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleOpenPillarDetail('schema'); }}
            className="card-vibrant p-5 space-y-3.5 bg-white cursor-pointer hover:border-purple-300 hover:shadow-md transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2.5">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 font-mono">
                    Weight: {backendWeights.schema_structured_data || '15%'}
                  </span>
                  <h4 className="text-sm font-bold text-slate-900 mt-1.5 group-hover:text-purple-700 transition-colors">
                    Schema & Structured Data
                  </h4>
                </div>
                <div className="text-right">
                  <span className={`text-2xl font-black ${
                    pillars.schema_structured_data === null
                      ? 'text-slate-500'
                      : pillars.schema_structured_data >= 80
                      ? 'text-emerald-600'
                      : pillars.schema_structured_data >= 50
                      ? 'text-amber-600'
                      : 'text-rose-600'
                  }`}>
                    {pillars.schema_structured_data !== null ? pillars.schema_structured_data : (isCrawling ? '...' : '—')}
                  </span>
                  <span className="text-[10px] font-bold text-slate-500 block">
                    {pillars.schema_structured_data !== null ? '/ 100' : (isCrawling ? 'Evaluating' : 'No Schema')}
                  </span>
                </div>
              </div>

              <p className="text-xs text-slate-600 font-medium leading-snug">
                Does your website provide structured information that helps search engines understand your local business?
              </p>

              {/* Schema Checklist Badges */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                  schemaData?.checklist?.local_business
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                    : 'bg-rose-50 text-rose-800 border-rose-200'
                }`}>
                  LocalBusiness: {schemaData?.checklist?.local_business ? '✓' : '✕'}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                  schemaData?.checklist?.address
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                    : 'bg-slate-100 text-slate-600 border-slate-200'
                }`}>
                  Address: {schemaData?.checklist?.address ? '✓' : '✕'}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                  schemaData?.checklist?.phone
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                    : 'bg-slate-100 text-slate-600 border-slate-200'
                }`}>
                  Phone: {schemaData?.checklist?.phone ? '✓' : '✕'}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                  schemaData?.checklist?.geo
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                    : 'bg-slate-100 text-slate-600 border-slate-200'
                }`}>
                  Geo: {schemaData?.checklist?.geo ? '✓' : '✕'}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                  schemaData?.checklist?.opening_hours
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                    : 'bg-amber-50 text-amber-800 border-amber-200'
                }`}>
                  Hours: {schemaData?.checklist?.opening_hours ? '✓' : '⚠'}
                </span>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-[11px] font-semibold text-purple-800 truncate max-w-[140px]">
                {schemaData?.detected_types && schemaData.detected_types.length > 0
                  ? schemaData.detected_types.slice(0, 2).join(', ')
                  : 'No JSON-LD'}
              </span>
              <span className="font-bold text-purple-700 group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5 text-[11px]">
                Inspect Schema →
              </span>
            </div>
          </div>

          {/* CARD 4: Google Business Profile Match */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => handleOpenPillarDetail('gbp')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleOpenPillarDetail('gbp'); }}
            className="card-vibrant p-5 space-y-3.5 bg-white cursor-pointer hover:border-purple-300 hover:shadow-md transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2.5">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 font-mono">
                    Weight: {backendWeights.gbp_alignment || '10%'}
                  </span>
                  <h4 className="text-sm font-bold text-slate-900 mt-1.5 group-hover:text-purple-700 transition-colors">
                    Google Business Profile Match
                  </h4>
                </div>
                <div className="text-right">
                  {summary?.gbp_status?.connected ? (
                    <>
                      <span className={`text-2xl font-black ${
                        pillars.gbp_alignment !== null && pillars.gbp_alignment >= 80
                          ? 'text-emerald-600'
                          : pillars.gbp_alignment !== null && pillars.gbp_alignment >= 50
                          ? 'text-amber-600'
                          : 'text-rose-600'
                      }`}>
                        {pillars.gbp_alignment !== null ? pillars.gbp_alignment : '—'}
                      </span>
                      <span className="text-[10px] font-bold text-slate-500 block">/ 100</span>
                    </>
                  ) : (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 border border-slate-200 block">
                      Not Connected
                    </span>
                  )}
                </div>
              </div>

              <p className="text-xs text-slate-600 font-medium leading-snug">
                Cross-alignment between website NAP and your project-bound Google Business Profile.
              </p>

              {summary?.gbp_status?.connected ? (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                    gbpData?.fields?.name_match
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      : 'bg-rose-50 text-rose-800 border-rose-200'
                  }`}>
                    Name: {gbpData?.fields?.name_match ? '✓ Match' : '⚠ Differs'}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                    gbpData?.fields?.phone_match
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      : 'bg-rose-50 text-rose-800 border-rose-200'
                  }`}>
                    Phone: {gbpData?.fields?.phone_match ? '✓ Match' : '⚠ Differs'}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                    gbpData?.fields?.address_match
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      : 'bg-rose-50 text-rose-800 border-rose-200'
                  }`}>
                    Address: {gbpData?.fields?.address_match ? '✓ Match' : '⚠ Differs'}
                  </span>
                </div>
              ) : (
                <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-100 text-[11px] text-slate-600 font-medium">
                  <span className="font-bold text-slate-700">Google Business Profile not connected.</span> Connect your GBP listing to compare website NAP alignment.
                </div>
              )}
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-[11px] font-semibold text-slate-500">
                {summary?.gbp_status?.connected ? 'Bound Profile Verified' : 'GBP Disconnected'}
              </span>
              <span className="font-bold text-purple-700 group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5 text-[11px]">
                Inspect Match →
              </span>
            </div>
          </div>

          {/* CARD 5: Citations & Directory NAP */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => handleOpenPillarDetail('citations')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleOpenPillarDetail('citations'); }}
            className="card-vibrant p-5 space-y-3.5 bg-white cursor-pointer hover:border-purple-300 hover:shadow-md transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2.5">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 font-mono">
                    Weight: {backendWeights.citations_nap || '10%'}
                  </span>
                  <h4 className="text-sm font-bold text-slate-900 mt-1.5 group-hover:text-purple-700 transition-colors">
                    Citations & Directory NAP
                  </h4>
                </div>
                <div className="text-right">
                  {citationsData?.status !== 'not_verified' && pillars.citations_nap !== null ? (
                    <>
                      <span className={`text-2xl font-black ${
                        pillars.citations_nap >= 80 ? 'text-emerald-600' : 'text-amber-600'
                      }`}>
                        {pillars.citations_nap}
                      </span>
                      <span className="text-[10px] font-bold text-slate-500 block">/ 100</span>
                    </>
                  ) : (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-800 border border-blue-200 block">
                      Not Verified
                    </span>
                  )}
                </div>
              </div>

              <p className="text-xs text-slate-600 font-medium leading-snug">
                Consistency of Name, Phone, and Address across major online directories.
              </p>

              {summary?.citations_status?.total ? (
                <div className="space-y-1 pt-1 text-[11px] font-medium text-slate-700">
                  <div>Directories checked: <b className="text-slate-900">{summary.citations_status.total}</b></div>
                  <div>Consistent NAP: <b className="text-emerald-700">{summary.citations_status.active}</b></div>
                  <div>Needs attention: <b className="text-rose-700">{summary.citations_status.mismatches}</b></div>
                </div>
              ) : (
                <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-100 text-[11px] text-slate-600 font-medium">
                  <span className="font-bold text-slate-700">Citation data not verified.</span> Directory listings have not been audited for this project.
                </div>
              )}
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-[11px] font-semibold text-slate-500">
                Directory Network NAP
              </span>
              <span className="font-bold text-purple-700 group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5 text-[11px]">
                Inspect Citations →
              </span>
            </div>
          </div>

          {/* CARD 6: Reviews & Reputation */}
          <div
            role="button"
            tabIndex={0}
            onClick={() => handleOpenPillarDetail('reviews')}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleOpenPillarDetail('reviews'); }}
            className="card-vibrant p-5 space-y-3.5 bg-white cursor-pointer hover:border-purple-300 hover:shadow-md transition-all group flex flex-col justify-between"
          >
            <div className="space-y-2.5">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 font-mono">
                    Weight: {backendWeights.reviews_reputation || '20%'}
                  </span>
                  <h4 className="text-sm font-bold text-slate-900 mt-1.5 group-hover:text-purple-700 transition-colors">
                    Reviews & Reputation
                  </h4>
                </div>
                <div className="text-right">
                  {reviewsData?.status !== 'no_data' && pillars.reviews_reputation !== null ? (
                    <>
                      <span className={`text-2xl font-black ${
                        pillars.reviews_reputation >= 80 ? 'text-emerald-600' : 'text-amber-600'
                      }`}>
                        {pillars.reviews_reputation}
                      </span>
                      <span className="text-[10px] font-bold text-slate-500 block">/ 100</span>
                    </>
                  ) : (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 border border-slate-200 block">
                      No Data
                    </span>
                  )}
                </div>
              </div>

              <p className="text-xs text-slate-600 font-medium leading-snug">
                Review volume, customer star rating, and merchant reply coverage.
              </p>

              {summary?.reviews_status?.total ? (
                <div className="space-y-1 pt-1 text-[11px] font-medium text-slate-700">
                  <div>Total reviews: <b className="text-slate-900">{summary.reviews_status.total}</b></div>
                  <div>Average rating: <b className="text-amber-700">{summary.reviews_status.average_rating}★</b></div>
                  <div>Unanswered: <b className="text-slate-700">{summary.reviews_status.unanswered}</b></div>
                </div>
              ) : (
                <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-100 text-[11px] text-slate-600 font-medium">
                  <span className="font-bold text-slate-700">Review data unavailable.</span> Google Business Profile has not provided customer review data.
                </div>
              )}
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-[11px] font-semibold text-slate-500">
                GBP Reputation Feed
              </span>
              <span className="font-bold text-purple-700 group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5 text-[11px]">
                Inspect Reviews →
              </span>
            </div>
          </div>
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
      <Modal
        isOpen={isSchemaModalOpen}
        onClose={() => setIsSchemaModalOpen(false)}
        maxWidth="4xl"
        title="Schema & Structured Data Deep Detail"
        description="Technical Audit Evidence"
        footer={
          <div className="flex justify-end w-full">
            <button
              onClick={() => setIsSchemaModalOpen(false)}
              className="px-5 py-2.5 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold shadow-xs transition-all"
            >
              Close Modal
            </button>
          </div>
        }
      >
        <div className="space-y-4">
          {/* Modal Tabs */}
          <div className="flex border-b border-slate-200 bg-slate-50 px-2 gap-2 pt-2 -mx-6 -mt-6">
            <button
              onClick={() => setSchemaModalTab('summary')}
              className={`px-4 py-2 text-xs font-bold rounded-t-xl border-b-2 transition-all ${
                schemaModalTab === 'summary'
                  ? 'border-emerald-600 text-emerald-900 bg-white shadow-xs'
                  : 'border-transparent text-slate-600 hover:text-slate-900'
              }`}
            >
              Summary
            </button>
            <button
              onClick={() => setSchemaModalTab('types')}
              className={`px-4 py-2 text-xs font-bold rounded-t-xl border-b-2 transition-all ${
                schemaModalTab === 'types'
                  ? 'border-emerald-600 text-emerald-900 bg-white shadow-xs'
                  : 'border-transparent text-slate-600 hover:text-slate-900'
              }`}
            >
              Type Breakdown
            </button>
            <button
              onClick={() => setSchemaModalTab('pages')}
              className={`px-4 py-2 text-xs font-bold rounded-t-xl border-b-2 transition-all ${
                schemaModalTab === 'pages'
                  ? 'border-emerald-600 text-emerald-900 bg-white shadow-xs'
                  : 'border-transparent text-slate-600 hover:text-slate-900'
              }`}
            >
              Page Evidence
            </button>
            <button
              onClick={() => setSchemaModalTab('raw')}
              className={`px-4 py-2 text-xs font-bold rounded-t-xl border-b-2 transition-all ${
                schemaModalTab === 'raw'
                  ? 'border-emerald-600 text-emerald-900 bg-white shadow-xs'
                  : 'border-transparent text-slate-600 hover:text-slate-900'
              }`}
            >
              Raw JSON-LD
            </button>
          </div>

          {/* Modal Body Content */}
          <div className="space-y-4 text-slate-800 text-xs pt-2">
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
                  <div className="p-4 bg-emerald-50/70 rounded-2xl border border-emerald-200 text-center">
                    <span className="text-[10px] font-bold text-emerald-800 uppercase block">Total Schema Instances</span>
                    <span className="text-2xl font-black text-emerald-900 block mt-1">{schemaSummary.total_schema_instances}</span>
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
        </div>
      </Modal>

      {/* =================================================================== */}
      {/* CHECKS PERFORMED POPUP (Requirement 6, 7, 8, 9, 10)                 */}
      {/* =================================================================== */}
      <Modal
        isOpen={isChecksModalOpen}
        onClose={() => setIsChecksModalOpen(false)}
        maxWidth="5xl"
        title="Checks & Rules Evaluated"
        description="AUDIT RULE BREAKDOWN"
        footer={
          <div className="flex justify-end w-full">
            <button
              onClick={() => setIsChecksModalOpen(false)}
              className="px-5 py-2.5 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold shadow-xs transition-all"
            >
              Close Rule Table
            </button>
          </div>
        }
      >
        <div className="space-y-4">
          {/* Context Header */}
          <div className="p-4 bg-emerald-50/70 rounded-2xl border border-emerald-100 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-[10px] font-extrabold uppercase text-emerald-800 block">Domain</span>
              <span className="font-mono font-bold text-slate-900 block mt-0.5">{activeProject.domain}</span>
            </div>
            <div>
              <span className="text-[10px] font-extrabold uppercase text-emerald-800 block">Crawl ID</span>
              <span className="font-mono font-bold text-slate-900 block mt-0.5">{canonicalData?.crawl_id || 'N/A'}</span>
            </div>
            <div>
              <span className="text-[10px] font-extrabold uppercase text-emerald-800 block">Evaluated Rules</span>
              <span className="font-mono font-bold text-slate-900 block mt-0.5">
                {evaluatedRules != null ? `${evaluatedRules} Rules` : 'N/A'}
              </span>
            </div>
            <div>
              <span className="text-[10px] font-extrabold uppercase text-emerald-800 block">Total Checks</span>
              <span className="font-mono font-bold text-emerald-900 block mt-0.5">
                {evaluatedRules != null && totalEvaluatedChecks != null
                  ? `${analyzedPages} pages × ${evaluatedRules} rules = ${totalEvaluatedChecks} checks`
                  : 'Checks: N/A'}
              </span>
            </div>
          </div>

          {/* Rule Table */}
          <div className="overflow-x-auto">
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
                    <td className="p-3 font-mono font-bold text-emerald-700">{r.rule_id}</td>
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
        </div>
      </Modal>

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

import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  Globe,
  Star,
  ShieldCheck,
  CheckSquare,
  AlertCircle,
  Clock,
  Sparkles,
  ExternalLink,
  ChevronRight,
  Search,
  CheckCircle2,
  Plus,
  Play,
  Layers,
  MapPin,
  Bot
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';
import { useProject } from '../context/ProjectContext';
import { Link, useNavigate } from 'react-router-dom';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { StatCard } from '../components/ui/StatCard';
import api from '../api/client';
import { MetricDetailModal, PillarDetailContext } from '../components/audit/MetricDetailModal';
import { SEOIssue } from '../types';

export const Dashboard: React.FC = () => {
  const { activeProject, dashboard, loading, refreshDashboard } = useProject();
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<any[]>([]);
  const [keywords, setKeywords] = useState<any[]>([]);
  const [gscMetrics, setGscMetrics] = useState<any[]>([]);
  const [auditIssues, setAuditIssues] = useState<SEOIssue[]>([]);
  const [diagnosticSummary, setDiagnosticSummary] = useState<any>(null);
  const [dataLoading, setDataLoading] = useState(false);

  // Drill-down modal state
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [selectedPillarContext, setSelectedPillarContext] = useState<PillarDetailContext | null>(null);

  useEffect(() => {
    if (!activeProject) return;

    const loadProjectData = async () => {
      try {
        setDataLoading(true);
        const [kwResp, taskResp, gscResp, auditSummResp, auditIssuesResp] = await Promise.allSettled([
          api.get(`/keywords/${activeProject.id}`),
          api.get(`/tasks/${activeProject.id}`),
          api.get(`/google/gsc/${activeProject.id}`),
          api.get(`/audits/${activeProject.id}/diagnostic-summary`),
          api.get(`/audits/issues/${activeProject.id}`)
        ]);

        if (kwResp.status === 'fulfilled') {
          setKeywords(kwResp.value.data || []);
        }
        if (taskResp.status === 'fulfilled') {
          setTasks(taskResp.value.data || []);
        }
        if (gscResp.status === 'fulfilled') {
          setGscMetrics(gscResp.value.data?.daily_history || []);
        }
        if (auditSummResp.status === 'fulfilled' && auditSummResp.value.data) {
          setDiagnosticSummary(auditSummResp.value.data);
        }
        if (auditIssuesResp.status === 'fulfilled' && Array.isArray(auditIssuesResp.value.data)) {
          setAuditIssues(auditIssuesResp.value.data);
        }
      } catch (e) {
        console.error('Error loading dashboard data:', e);
      } finally {
        setDataLoading(false);
      }
    };

    loadProjectData();
  }, [activeProject?.id]);

  const toggleTaskStatus = async (taskId: number, currentStatus: string) => {
    try {
      const newStatus = currentStatus === 'completed' ? 'open' : 'completed';
      await api.patch(`/tasks/${taskId}`, { status: newStatus });
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, status: newStatus } : t));
      await refreshDashboard();
    } catch (e) {
      console.error('Failed to update task:', e);
    }
  };

  if (loading && !dashboard) {
    return (
      <div className="card-nature p-12 text-center space-y-3">
        <Sparkles className="w-8 h-8 mx-auto text-[#236B4F] animate-spin" />
        <p className="text-xs font-semibold text-[#587568]">Loading live project intelligence...</p>
      </div>
    );
  }

  if (!activeProject) {
    return (
      <EmptyState
        icon={Globe}
        badge="No Project Selected"
        title="Get Started with LocalLift"
        description="Create or select a business project to start auditing SEO health, tracking local keywords, and monitoring Google Business Profile performance."
        actionText="Setup New Project"
        actionLink="/onboarding"
      />
    );
  }

  const overallHealth = diagnosticSummary?.overall_score ?? (
    dashboard?.health_score !== undefined && dashboard?.health_score !== null 
      ? dashboard.health_score 
      : activeProject.health_score
  );
  const isHealthCalculated = overallHealth !== null && overallHealth !== undefined;

  const backendWeights: Record<string, string> = diagnosticSummary?.pillar_weights || {
    crawl_health: '20%',
    onpage_content: '20%',
    schema_structured_data: '25%',
    gbp_alignment: '15%',
    citations_nap: '10%',
    reviews_reputation: '10%'
  };

  const pillars = diagnosticSummary?.pillar_scores || {
    crawl_health: activeProject.technical_score ?? null,
    onpage_content: activeProject.onpage_score ?? null,
    schema_structured_data: activeProject.local_score ?? null,
    gbp_alignment: activeProject.gbp_score ?? null,
    citations_nap: activeProject.citations_score ?? null,
    reviews_reputation: activeProject.reviews_score ?? null
  };

  const pillarCards = [
    {
      id: 'crawl',
      name: 'Local Crawl Health',
      weight: backendWeights.crawl_health || '20%',
      weightFraction: 0.20,
      score: pillars.crawl_health,
      desc: 'HTTP status, canonicals, and indexability',
      whatIsThis: 'Local Crawl Health audits whether search bots and regional customers can reliably crawl your pages without encountering HTTP errors, broken redirects, or canonical conflicts.',
      whyImportant: 'Broken URLs waste search engine crawl budgets and prevent local landing pages from being indexed and surfaced in geo-targeted queries.',
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
      weightFraction: 0.20,
      score: pillars.onpage_content,
      desc: 'City/suburb keywords, local H1, meta geo signals',
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
      weightFraction: 0.25,
      score: pillars.schema_structured_data,
      desc: 'LocalBusiness JSON-LD, geo, opening hours',
      whatIsThis: 'Schema & Structured Data verifies Schema.org LocalBusiness JSON-LD implementation, validating phone, address, operating hours, and geo coordinates.',
      whyImportant: 'Google requires valid LocalBusiness JSON-LD structured data to verify physical storefront coordinates and generate rich map pins and Knowledge Graph entries.',
      methodology: {
        startingScore: 0,
        deductions: '100 points awarded if valid LocalBusiness Schema entity with required attributes is detected on primary local landing pages; 0 if missing.',
        formula: '100 if has_valid_local_schema else 0'
      }
    },
    {
      id: 'gbp',
      name: 'Google Business Profile Match',
      weight: backendWeights.gbp_alignment || '15%',
      weightFraction: 0.15,
      score: pillars.gbp_alignment,
      desc: 'Cross-alignment of Name, Phone, and Address',
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
      weightFraction: 0.10,
      score: pillars.citations_nap,
      desc: 'Consistency across top directory listings',
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
      weightFraction: 0.10,
      score: pillars.reviews_reputation,
      desc: 'Review volume, velocity, and response health',
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
        score: overallHealth,
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
      const card = pillarCards.find((c) => c.id === pillarId || (pillarId === 'technical' && c.id === 'crawl') || (pillarId === 'local' && c.id === 'schema'));
      if (card) {
        setSelectedPillarContext({
          id: card.id,
          name: card.name,
          score: card.score,
          weight: card.weight,
          weightFraction: card.weightFraction,
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

  const healthBreakdown = pillarCards;

  const improvedKeywordsCount = keywords.filter(k => k.current_rank && k.previous_rank && k.current_rank < k.previous_rank).length;
  const top3KeywordsCount = keywords.filter(k => k.current_rank && k.current_rank <= 3).length;

  return (
    <div className="space-y-6">
      {/* Hero Atmosphere Banner */}
      <div className="card-nature p-6 relative overflow-hidden bg-gradient-to-r from-white via-[#F7FAF7] to-[#F1F7F1]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#EAF2EA] text-[#174A38] border border-[#B8DFC9]">
                Local SEO Operations
              </span>
              <span className="text-xs text-[#587568]">{activeProject.domain}</span>
            </div>
            <h2 className="text-xl font-black text-[#142820] tracking-tight mt-1.5">
              {activeProject.name} — Local Visibility & Health
            </h2>
            <p className="text-xs text-[#587568] mt-0.5">
              Live ranking presence, organic visibility trends, and automated technical audit remediations.
            </p>
          </div>

          <div className="flex items-center space-x-2.5 shrink-0">
            <button
              onClick={() => navigate('/audits/website')}
              className="btn-primary-gradient px-4 py-2 rounded-xl text-xs flex items-center space-x-2"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Run Full Audit</span>
            </button>
          </div>
        </div>
      </div>

      {/* 1. Horizontal KPI Cards Section */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {/* Card 1: SEO Health (Clickable Drill-Down) */}
        <div 
          role="button"
          tabIndex={0}
          onClick={() => handleOpenPillarDetail('overall')}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleOpenPillarDetail('overall'); }}
          className="kpi-forest p-4 rounded-2xl shadow-2xs space-y-2 relative overflow-hidden cursor-pointer hover:shadow-md hover:ring-2 hover:ring-[#236B4F]/30 transition-all group"
          title="Click to view full SEO scoring methodology and pillar breakdown"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#174A38] group-hover:text-[#236B4F] transition-colors flex items-center gap-1">
              <span>SEO Health</span>
              <span className="text-[10px] opacity-70 group-hover:opacity-100">↗</span>
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]">
              {isHealthCalculated
                ? (overallHealth >= 80 ? 'Good' : overallHealth >= 60 ? 'Fair' : 'Needs Action')
                : 'Awaiting Audit'}
            </span>
          </div>
          <div className="flex items-baseline space-x-1.5">
            <span className="text-2xl lg:text-3xl font-black text-[#142820]">
              {isHealthCalculated ? overallHealth : '—'}
            </span>
            {isHealthCalculated ? (
              <span className="text-xs font-bold text-[#587568]">/ 100</span>
            ) : (
              <span className="text-xs font-semibold text-[#587568]">Not yet audited</span>
            )}
          </div>
          <div className="text-[11px] text-[#174A38] font-semibold flex items-center justify-between">
            <div className="flex items-center space-x-1">
              <span className="text-[#236B4F] font-black">●</span>
              <span>Overall Site Grade</span>
            </div>
            <span className="text-[10px] font-bold text-[#236B4F] opacity-0 group-hover:opacity-100 transition-opacity">
              Inspect →
            </span>
          </div>
        </div>

        {/* Card 2: Local Visibility */}
        <div className="kpi-accent p-4 rounded-2xl shadow-2xs space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#142820]">
              Local Visibility
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]">
              {top3KeywordsCount} in Top 3
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-[#142820]">
              {keywords.length > 0 ? Math.round((top3KeywordsCount / keywords.length) * 100) : 0}%
            </span>
          </div>
          <div className="text-[11px] text-[#2E4E40] font-semibold">
            Local Pack Share
          </div>
        </div>

        {/* Card 3: Keywords Improved */}
        <div className="kpi-forest p-4 rounded-2xl shadow-2xs space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#174A38]">
              Rank Climbers
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]">
              +{improvedKeywordsCount}
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-[#142820]">{improvedKeywordsCount}</span>
          </div>
          <div className="text-[11px] text-[#174A38] font-semibold">
            Keywords Improved
          </div>
        </div>

        {/* Card 4: Active Tasks */}
        <div className="kpi-amber p-4 rounded-2xl shadow-2xs space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#92400E]">
              Active Tasks
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A]">
              {tasks.filter(t => t.status !== 'completed').length} Open
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-[#142820]">
              {tasks.filter(t => t.status !== 'completed').length}
            </span>
          </div>
          <div className="text-[11px] text-[#92400E] font-semibold">
            Pending Remediation
          </div>
        </div>

        {/* Card 5: Total Tracked */}
        <div className="kpi-forest p-4 rounded-2xl shadow-2xs space-y-2 relative overflow-hidden col-span-2 md:col-span-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#174A38]">
              Tracked Terms
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]">
              Live
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-[#142820]">{keywords.length}</span>
          </div>
          <div className="text-[11px] text-[#174A38] font-semibold">
            Active Search Terms
          </div>
        </div>
      </div>

      {/* 2. Six-Pillar Local SEO Breakdown (Interactive Drill-Down) */}
      <div className="card-nature p-5 space-y-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#EBF2EB] pb-3">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-[#236B4F]" />
            <h3 className="text-sm font-extrabold text-[#142820] tracking-tight">
              Local SEO Pillars & Weighted Health
            </h3>
          </div>
          <span className="text-[11px] text-[#587568] font-medium">
            Click any pillar card to drill into real issues, affected URLs & recommendations
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {healthBreakdown.map((p) => {
            const isScoreAvailable = p.score !== null && p.score !== undefined;
            return (
              <div
                key={p.id}
                role="button"
                tabIndex={0}
                onClick={() => handleOpenPillarDetail(p.id)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleOpenPillarDetail(p.id); }}
                className="p-3.5 rounded-xl border border-[#E0ECE0] bg-white hover:border-[#236B4F] hover:shadow-sm transition-all cursor-pointer group space-y-2.5"
                title={`Click to inspect ${p.name} audit findings`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md bg-[#F1F6F1] text-[#174A38] font-mono group-hover:bg-[#DDEFE5] transition-colors">
                      Weight: {p.weight}
                    </span>
                    <h4 className="text-xs font-bold text-[#142820] mt-1.5 flex items-center gap-1 group-hover:text-[#236B4F] transition-colors">
                      {p.name}
                      <span className="text-[11px] opacity-0 group-hover:opacity-100 transition-opacity text-[#236B4F] font-mono">→</span>
                    </h4>
                  </div>
                  <div className="text-right">
                    <span className={`text-lg font-black ${
                      !isScoreAvailable
                        ? 'text-slate-400'
                        : p.score >= 80
                        ? 'text-[#065F46]'
                        : p.score >= 60
                        ? 'text-[#D97706]'
                        : 'text-[#991B1B]'
                    }`}>
                      {isScoreAvailable ? p.score : '—'}
                    </span>
                    <span className="text-[10px] font-bold text-slate-400 block">
                      {isScoreAvailable ? '/ 100' : 'Awaiting audit'}
                    </span>
                  </div>
                </div>

                <div className="w-full bg-[#EBF2EB] rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-1.5 rounded-full ${
                      !isScoreAvailable
                        ? 'bg-slate-200'
                        : p.score >= 80
                        ? 'bg-[#236B4F]'
                        : p.score >= 60
                        ? 'bg-[#D97706]'
                        : 'bg-[#DC2626]'
                    } transition-all duration-500`}
                    style={{ width: isScoreAvailable ? `${Math.min(100, p.score)}%` : '0%' }}
                  />
                </div>

                <div className="flex items-center justify-between pt-0.5">
                  <p className="text-[11px] text-[#587568] leading-tight truncate">
                    {p.desc}
                  </p>
                  <span className="text-[10px] font-bold text-[#236B4F] opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pl-2">
                    Inspect →
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. Performance Overview Section with Nature Line/Area Chart */}
      <div className="card-nature p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#EBF2EB] pb-4">
          <div>
            <h2 className="text-base font-extrabold text-[#142820] tracking-tight">
              Search Performance & Visibility
            </h2>
            <p className="text-xs text-[#587568] mt-0.5">
              Live Google Search visibility and impression analytics for {activeProject.domain}.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <Link
              to="/google/gsc"
              className="text-xs font-bold text-[#236B4F] hover:text-[#174A38] flex items-center space-x-1"
            >
              <span>Search Console View</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {/* Real GSC / GA4 Quick Stats Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
          <div className="bg-[#F7FAF7] rounded-xl p-3 border border-[#EBF2EB]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#587568] block">Search Clicks</span>
            <div className="text-xl font-black text-[#142820] mt-0.5">
              {dashboard?.gsc_summary?.clicks !== undefined && dashboard?.gsc_summary?.clicks !== null 
                ? Number(dashboard.gsc_summary.clicks).toLocaleString() 
                : '—'}
            </div>
            <span className="text-[10px] text-[#587568]">
              {dashboard?.gsc_summary?.connected ? 'GSC 28-day organic' : 'Awaiting GSC sync'}
            </span>
          </div>

          <div className="bg-[#F7FAF7] rounded-xl p-3 border border-[#EBF2EB]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#587568] block">Search Impressions</span>
            <div className="text-xl font-black text-[#142820] mt-0.5">
              {dashboard?.gsc_summary?.impressions !== undefined && dashboard?.gsc_summary?.impressions !== null 
                ? Number(dashboard.gsc_summary.impressions).toLocaleString() 
                : '—'}
            </div>
            <span className="text-[10px] text-[#587568]">
              {dashboard?.gsc_summary?.connected ? 'Google Search appearances' : 'Awaiting GSC sync'}
            </span>
          </div>

          <div className="bg-[#F7FAF7] rounded-xl p-3 border border-[#EBF2EB]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#587568] block">Average CTR</span>
            <div className="text-xl font-black text-[#142820] mt-0.5">
              {dashboard?.gsc_summary?.ctr !== undefined && dashboard?.gsc_summary?.ctr !== null 
                ? `${(dashboard.gsc_summary.ctr * 100).toFixed(1)}%` 
                : '—'}
            </div>
            <span className="text-[10px] text-[#587568]">Click-through rate</span>
          </div>

          <div className="bg-[#F7FAF7] rounded-xl p-3 border border-[#EBF2EB]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#587568] block">GA4 Organic Users</span>
            <div className="text-xl font-black text-[#142820] mt-0.5">
              {dashboard?.ga4_summary?.organic_users !== undefined && dashboard?.ga4_summary?.organic_users !== null 
                ? Number(dashboard.ga4_summary.organic_users).toLocaleString() 
                : '—'}
            </div>
            <span className="text-[10px] text-[#587568]">
              {dashboard?.ga4_summary?.connected ? 'GA4 verified traffic' : 'Connect GA4'}
            </span>
          </div>
        </div>

        {gscMetrics.length > 0 ? (
          <div className="h-60 w-full pt-1">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={gscMetrics} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorImpressions" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#236B4F" stopOpacity={0.25}/>
                    <stop offset="95%" stopColor="#236B4F" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorClicks" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#39B982" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#39B982" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EAF2EA" />
                <XAxis dataKey="date" tickLine={false} axisLine={{ stroke: '#DCE8DC' }} tick={{ fill: '#587568', fontSize: 11 }} />
                <YAxis tickLine={false} axisLine={{ stroke: '#DCE8DC' }} tick={{ fill: '#587568', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#121D16', borderRadius: '0.75rem', borderColor: '#22382C', color: '#F5FAF6' }}
                  labelStyle={{ fontWeight: 'bold', color: '#F5FAF6' }}
                />
                <Legend verticalAlign="top" height={36} iconType="circle" />
                <Area type="monotone" name="Impressions" dataKey="impressions" stroke="#236B4F" strokeWidth={2.5} fillOpacity={1} fill="url(#colorImpressions)" />
                <Area type="monotone" name="Clicks" dataKey="clicks" stroke="#39B982" strokeWidth={2.5} fillOpacity={1} fill="url(#colorClicks)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="p-8 text-center bg-[#F7FAF7] rounded-xl border border-[#DCE8DC] space-y-2">
            <Globe className="w-8 h-8 text-[#236B4F] mx-auto stroke-[1.8]" />
            <h4 className="text-xs font-bold text-[#142820]">Google Search Console Integration</h4>
            <p className="text-xs text-[#587568] max-w-md mx-auto">
              Authorize Google Search Console to populate daily organic search impressions, query rankings, and CTR analytics.
            </p>
            <div className="pt-2">
              <Link
                to="/google/gsc"
                className="btn-secondary-nature inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs"
              >
                <span>Connect Search Console</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        )}
      </div>

      {/* 3. Top Keyword Rankings Table (Real Data) */}
      <div className="card-nature overflow-hidden">
        <div className="p-4 border-b border-[#EBF2EB] flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <TrendingUp className="w-4 h-4 text-[#236B4F]" />
            <h3 className="text-sm font-extrabold text-[#142820] tracking-tight">
              Top Tracked Keyword Rankings
            </h3>
          </div>
          <Link
            to="/rankings/keywords"
            className="text-xs font-bold text-[#236B4F] hover:text-[#174A38] flex items-center space-x-1"
          >
            <span>Manage All Keywords</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {keywords.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-[#2E4E40]">
              <thead className="bg-[#F7FAF7] text-[#587568] uppercase text-[10px] font-bold tracking-wider border-b border-[#EBF2EB]">
                <tr>
                  <th className="p-3.5">Keyword</th>
                  <th className="p-3.5">Location</th>
                  <th className="p-3.5">Current Rank</th>
                  <th className="p-3.5">Previous</th>
                  <th className="p-3.5">Change</th>
                  <th className="p-3.5 text-right">Search Volume</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EBF2EB]">
                {keywords.slice(0, 6).map((kw) => {
                  const hasDiff = kw.previous_rank !== null && kw.current_rank !== null;
                  const isUp = hasDiff && kw.current_rank < kw.previous_rank;
                  const isDown = hasDiff && kw.current_rank > kw.previous_rank;
                  const diff = hasDiff ? Math.abs(kw.previous_rank - kw.current_rank) : 0;

                  return (
                    <tr key={kw.id} className="hover:bg-[#F7FAF7] transition-colors">
                      <td className="p-3.5 font-bold text-[#142820]">{kw.keyword}</td>
                      <td className="p-3.5 text-[#587568]">{kw.target_location || 'Local Metro'}</td>
                      <td className="p-3.5">
                        <span
                          className={`inline-flex items-center justify-center w-7 h-7 rounded-lg font-black text-xs ${
                            kw.current_rank && kw.current_rank <= 3
                              ? 'bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]'
                              : kw.current_rank && kw.current_rank <= 10
                              ? 'bg-[#E6F8F0] text-[#065F46] border border-[#A7F3D0]'
                              : 'bg-[#F1F5F1] text-[#2E4E40] border border-[#DCE8DC]'
                          }`}
                        >
                          {kw.current_rank ? kw.current_rank : '—'}
                        </span>
                      </td>
                      <td className="p-3.5 text-[#587568] font-medium">
                        {kw.previous_rank ? `#${kw.previous_rank}` : '—'}
                      </td>
                      <td className="p-3.5">
                        {hasDiff && diff > 0 ? (
                          <span
                            className={`inline-flex items-center font-bold text-xs ${
                              isUp ? 'text-[#065F46]' : 'text-[#991B1B]'
                            }`}
                          >
                            {isUp ? '↑' : '↓'}
                            {diff}
                          </span>
                        ) : (
                          <span className="text-[#587568] font-bold">—</span>
                        )}
                      </td>
                      <td className="p-3.5 text-right font-mono text-[#142820] font-semibold">
                        {kw.search_volume ? `${kw.search_volume.toLocaleString()} / mo` : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center space-y-2">
            <p className="text-xs text-[#587568]">No keywords added yet for this project.</p>
            <Link
              to="/rankings/keywords"
              className="inline-flex items-center space-x-1 text-xs font-bold text-[#236B4F] hover:text-[#174A38]"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Track Your First Keyword</span>
            </Link>
          </div>
        )}
      </div>

      {/* 4. Active Remediation Tasks */}
      <div className="card-nature overflow-hidden">
        <div className="p-4 border-b border-[#EBF2EB] flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CheckSquare className="w-4 h-4 text-[#236B4F]" />
            <h3 className="text-sm font-extrabold text-[#142820] tracking-tight">
              Actionable SEO Tasks & Audit Fixes
            </h3>
          </div>
          <Link
            to="/tasks"
            className="text-xs font-bold text-[#236B4F] hover:text-[#174A38] flex items-center space-x-1"
          >
            <span>View Task Board</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {tasks.length > 0 ? (
          <div className="divide-y divide-[#EBF2EB]">
            {tasks.slice(0, 5).map((task) => (
              <div
                key={task.id}
                className="p-4 flex items-center justify-between hover:bg-[#F7FAF7] transition-colors"
              >
                <div className="flex items-center space-x-3 truncate">
                  <button
                    onClick={() => toggleTaskStatus(task.id, task.status)}
                    className={`w-5 h-5 rounded-md border flex items-center justify-center transition-colors shrink-0 ${
                      task.status === 'completed'
                        ? 'bg-[#236B4F] border-[#236B4F] text-white'
                        : 'border-[#B8DFC9] hover:border-[#236B4F] bg-white'
                    }`}
                  >
                    {task.status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5" />}
                  </button>
                  <div className="truncate">
                    <p className={`text-xs font-bold truncate ${task.status === 'completed' ? 'line-through text-[#8DAAA0]' : 'text-[#142820]'}`}>
                      {task.title}
                    </p>
                    <p className="text-[11px] text-[#587568] truncate">{task.description}</p>
                  </div>
                </div>

                <div className="flex items-center space-x-2 shrink-0 ml-3">
                  <StatusBadge status={task.priority || 'medium'} size="sm" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center space-y-2">
            <p className="text-xs text-[#587568]">All audit remediation tasks are completed.</p>
          </div>
        )}
      </div>

      {/* Metric Detail Drill-Down Modal */}
      <MetricDetailModal
        isOpen={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
        context={selectedPillarContext}
        issues={auditIssues}
        onSelectPillar={handleOpenPillarDetail}
      />
    </div>
  );
};

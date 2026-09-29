import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  LayoutGrid,
  TrendingUp,
  MapPin,
  Globe,
  Star,
  BookOpen,
  CheckSquare,
  Activity,
  AlertTriangle,
  RotateCw,
  Plus,
  ArrowRight,
  ExternalLink,
  ShieldCheck,
  Zap,
  BarChart3,
  Calendar,
  Filter,
  CheckCircle2,
  Clock,
  Search,
  Sparkles,
  Layers,
  Building2,
  ChevronRight,
  ArrowUpRight,
  Flame,
  Info
} from 'lucide-react';
import api from '../api/client';
import { useProject } from '../context/ProjectContext';
import { useAuth } from '../context/AuthContext';
import { Project } from '../types';

interface ProjectSummaryItem {
  id: number;
  name: string;
  domain: string;
  primary_category: string;
  country: string | null;
  status: string;
  is_archived: boolean;
  health_score: number | null;
  keyword_count: number;
  review_count: number;
  rating_avg: number | null;
  citation_count: number;
  open_issues_count: number;
  open_tasks_count: number;
  completed_tasks_count: number;
  last_scan_date: string | null;
  last_scan_status: string;
  last_scan_type: string | null;
}

export interface SERPProviderUsage {
  connected: boolean;
  provider: string | null;
  provider_name: string | null;
  plan_name: string | null;
  usage_model: string | null;
  used: number | null;
  limit: number | null;
  remaining: number | null;
  balance: number | null;
  currency: string | null;
  unit: string | null;
  percentage_used: number | null;
  renewal_date: string | null;
  last_synced_at: string | null;
  usage_available: boolean;
  locallift_requests_used: number;
}

interface UserDashboardOverview {
  summary: {
    total_projects: number;
    total_websites: number;
    tracked_keywords: number;
    active_scan_jobs: number;
    completed_scans: number;
    open_tasks: number;
    total_reviews: number;
    citation_records: number;
    geogrid_scans: number;
  };
  projects: ProjectSummaryItem[];
  usage: {
    serp_provider?: SERPProviderUsage;
    serp_used: number;
    ai_tokens_used: number;
    ai_tokens_limit: number;
    keywords_used: number;
    keywords_limit: number;
    geogrid_used: number;
    geogrid_limit: number;
  };
  recent_activity: {
    id: string;
    project_id: number;
    project_name: string;
    type: string;
    job_type: string;
    title: string;
    status: string;
    timestamp: string | null;
    details: string;
  }[];
  alerts: {
    id: string;
    severity: 'warning' | 'info' | 'error';
    project_id?: number;
    project_name?: string;
    title: string;
    message: string;
    timestamp: string | null;
  }[];
}

interface AnalyticsData {
  date_range: string;
  project_filter: number | null;
  timeline: {
    date: string;
    label: string;
    scans_completed: number;
    keywords_scanned: number;
    reviews_synced: number;
    citations_found: number;
    tasks_completed: number;
    serp_queries: number;
    ai_tokens: number;
  }[];
  project_comparison: {
    project_id: number;
    project_name: string;
    domain: string;
    category: string;
    health_score: number;
    keywords_count: number;
    scans_count: number;
    citations_count: number;
    reviews_count: number;
    relative_activity_score: number;
  }[];
  ranking_distribution: {
    top3: number;
    top10: number;
    top20: number;
    below20: number;
    unranked: number;
  };
}

export const UserCentralDashboardView: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { projects: contextProjects, setActiveProject } = useProject();

  const [loading, setLoading] = useState(true);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);
  const [overview, setOverview] = useState<UserDashboardOverview | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [dateRange, setDateRange] = useState<'today' | '7d' | '30d' | '90d'>('30d');
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'comparison' | 'activity' | 'usage'>('overview');
  const [searchProjectQuery, setSearchProjectQuery] = useState('');
  const [isSyncing, setIsSyncing] = useState(false);
  const [isRefreshingSerp, setIsRefreshingSerp] = useState(false);

  const handleRefreshSerp = async () => {
    try {
      setIsRefreshingSerp(true);
      const resp = await api.post('/serp/refresh-usage');
      if (resp.data && overview) {
        const u = resp.data.usage_info || {};
        const a = resp.data.account_info || {};
        setOverview({
          ...overview,
          usage: {
            ...overview.usage,
            serp_provider: {
              connected: Boolean(resp.data.has_key && resp.data.connection_status === 'connected'),
              provider: resp.data.provider,
              provider_name: resp.data.provider_name,
              plan_name: a.plan_name || null,
              usage_model: u.model || null,
              used: u.used ?? null,
              limit: u.limit ?? null,
              remaining: u.remaining ?? null,
              balance: u.balance ?? null,
              currency: u.currency ?? 'USD',
              unit: u.unit ?? 'searches',
              percentage_used: u.percentage_used ?? null,
              renewal_date: a.renewal_date || null,
              last_synced_at: resp.data.last_synced_at || new Date().toISOString(),
              usage_available: u.model !== 'unavailable' && u.model !== 'not_configured',
              locallift_requests_used: overview.usage.serp_used
            }
          }
        });
      }
    } catch (err) {
      console.error('Failed to refresh SERP usage:', err);
    } finally {
      setIsRefreshingSerp(false);
    }
  };

  // Fetch Overview Data
  const fetchOverview = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get('/dashboard/overview');
      setOverview(res.data);
    } catch (err: any) {
      console.error('Failed to load user central dashboard overview:', err);
      setError('Unable to load aggregated dashboard data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Fetch Analytics Data
  const fetchAnalytics = async () => {
    try {
      setAnalyticsLoading(true);
      const params: any = { date_range: dateRange };
      if (selectedProjectId) {
        params.project_id = selectedProjectId;
      }
      const res = await api.get('/dashboard/analytics', { params });
      setAnalytics(res.data);
    } catch (err: any) {
      console.error('Failed to load analytics data:', err);
    } finally {
      setAnalyticsLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [dateRange, selectedProjectId]);

  const handleRefresh = async () => {
    setIsSyncing(true);
    await Promise.all([fetchOverview(), fetchAnalytics()]);
    setTimeout(() => setIsSyncing(false), 500);
  };

  const handleOpenProjectDashboard = (projectItem: ProjectSummaryItem) => {
    // Find matching project in context
    const fullProj = contextProjects.find((p) => p.id === projectItem.id) || ({
      id: projectItem.id,
      name: projectItem.name,
      domain: projectItem.domain,
      primary_category: projectItem.primary_category,
      country: projectItem.country,
      status: projectItem.status,
      is_archived: projectItem.is_archived,
      health_score: projectItem.health_score,
      locations: [],
      additional_categories: []
    } as unknown as Project);

    setActiveProject(fullProj);
    navigate('/');
  };

  const filteredProjects = useMemo(() => {
    if (!overview?.projects) return [];
    if (!searchProjectQuery.trim()) return overview.projects;
    const q = searchProjectQuery.toLowerCase();
    return overview.projects.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.domain.toLowerCase().includes(q) ||
        p.primary_category.toLowerCase().includes(q)
    );
  }, [overview?.projects, searchProjectQuery]);

  // Max value for comparative activity bars
  const maxActivityScore = useMemo(() => {
    if (!analytics?.project_comparison || analytics.project_comparison.length === 0) return 100;
    return Math.max(...analytics.project_comparison.map((p) => p.relative_activity_score), 10);
  }, [analytics?.project_comparison]);

  // Max value for timeline chart
  const maxTimelineScans = useMemo(() => {
    if (!analytics?.timeline || analytics.timeline.length === 0) return 10;
    return Math.max(...analytics.timeline.map((t) => t.scans_completed + t.tasks_completed), 5);
  }, [analytics?.timeline]);

  if (loading && !overview) {
    return (
      <div className="flex items-center justify-center py-28">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-4 border-[#236B4F] border-t-transparent rounded-full animate-spin mx-auto shadow-md shadow-[#236B4F]/20" />
          <div className="space-y-1">
            <h3 className="text-sm font-black text-[#142820] tracking-tight uppercase">Central Command</h3>
            <p className="text-xs text-[#587568]">Aggregating authorized project intelligence...</p>
          </div>
        </div>
      </div>
    );
  }

  const summary = overview?.summary || {
    total_projects: 0,
    total_websites: 0,
    tracked_keywords: 0,
    active_scan_jobs: 0,
    completed_scans: 0,
    open_tasks: 0,
    total_reviews: 0,
    citation_records: 0,
    geogrid_scans: 0
  };

  const usage = overview?.usage || {
    serp_provider: {
      connected: false,
      provider: null,
      provider_name: null,
      plan_name: null,
      usage_model: null,
      used: null,
      limit: null,
      remaining: null,
      balance: null,
      currency: null,
      unit: null,
      percentage_used: null,
      renewal_date: null,
      last_synced_at: null,
      usage_available: false,
      locallift_requests_used: 0
    },
    serp_used: 0,
    ai_tokens_used: 0,
    ai_tokens_limit: 100000,
    keywords_used: 0,
    keywords_limit: 200,
    geogrid_used: 0,
    geogrid_limit: 1000
  };
  const serpProvider = usage.serp_provider;

  return (
    <div className="space-y-7 pb-12 animate-in fade-in duration-200">
      {/* 1. Header Banner */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-gradient-to-r from-[#174A38] via-[#236B4F] to-[#1C5840] rounded-3xl p-6 md:p-8 text-white shadow-xl shadow-[#236B4F]/10 relative overflow-hidden">
        {/* Subtle Decorative Background Shapes */}
        <div className="absolute -right-10 -bottom-10 w-60 h-60 bg-white/5 rounded-full blur-2xl pointer-events-none" />
        <div className="absolute top-0 right-1/4 w-32 h-32 bg-emerald-400/10 rounded-full blur-xl pointer-events-none" />

        <div className="space-y-2 z-10">
          <div className="flex items-center gap-2.5">
            <span className="px-3 py-1 text-[11px] font-black uppercase tracking-wider rounded-lg bg-white/15 text-emerald-200 border border-white/20 backdrop-blur-md">
              Central Hub
            </span>
            <span className="text-xs text-emerald-100/80 font-medium">
              Multi-Project Intelligence & Telemetry
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-black tracking-tight text-white">
            All My Projects Command Center
          </h1>
          <p className="text-xs md:text-sm text-emerald-100/90 max-w-2xl leading-relaxed">
            Consolidated overview across all your authorized organizations, locations, keyword rankings, and automation scans.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center flex-wrap gap-2.5 z-10 self-start lg:self-center">
          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            disabled={isSyncing}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/20 border border-white/20 text-xs font-bold text-white transition-all backdrop-blur-md"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
            <span>Sync Telemetry</span>
          </button>

          {/* Add Project CTA */}
          <button
            onClick={() => navigate('/onboarding')}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white text-[#174A38] hover:bg-emerald-50 text-xs font-black transition-all shadow-md shadow-black/10"
          >
            <Plus className="w-4 h-4 text-[#236B4F]" />
            <span>Add Project</span>
          </button>
        </div>
      </div>

      {/* 2. Customer Alerts (if any) */}
      {overview?.alerts && overview.alerts.length > 0 && (
        <div className="space-y-2">
          {overview.alerts.map((alert) => (
            <div
              key={alert.id}
              className={`p-4 rounded-2xl border flex items-start gap-3 text-xs transition-all ${
                alert.severity === 'warning'
                  ? 'bg-amber-50/80 border-amber-200 text-amber-900'
                  : alert.severity === 'error'
                  ? 'bg-rose-50/80 border-rose-200 text-rose-900'
                  : 'bg-emerald-50/80 border-emerald-200 text-emerald-900'
              }`}
            >
              <AlertTriangle
                className={`w-4 h-4 shrink-0 mt-0.5 ${
                  alert.severity === 'warning'
                    ? 'text-amber-600'
                    : alert.severity === 'error'
                    ? 'text-rose-600'
                    : 'text-emerald-600'
                }`}
              />
              <div className="flex-1 min-w-0">
                <div className="font-black text-xs">{alert.title}</div>
                <div className="text-[11px] opacity-90 mt-0.5 leading-normal">{alert.message}</div>
              </div>
              {alert.project_id && (
                <button
                  onClick={() => {
                    const p = overview.projects.find((proj) => proj.id === alert.project_id);
                    if (p) handleOpenProjectDashboard(p);
                  }}
                  className="px-2.5 py-1 rounded-lg bg-white/80 border border-current text-[10px] font-bold shrink-0 hover:bg-white transition-colors"
                >
                  View Project
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 3. Global KPI Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
        {/* Total Projects */}
        <div className="p-4 rounded-2xl bg-white border border-[#DCE8DC] shadow-xs space-y-2 hover:border-[#B8DFC9] transition-all">
          <div className="flex items-center justify-between text-[#587568]">
            <span className="text-[11px] font-bold uppercase tracking-wider">Projects</span>
            <Building2 className="w-4 h-4 text-[#236B4F]" />
          </div>
          <div className="text-2xl font-black text-[#142820] tracking-tight">{summary.total_projects}</div>
          <div className="text-[10px] text-[#587568] font-medium flex items-center gap-1">
            <Globe className="w-3 h-3 text-[#2FA878]" />
            <span>{summary.total_websites} Websites</span>
          </div>
        </div>

        {/* Tracked Keywords */}
        <div className="p-4 rounded-2xl bg-white border border-[#DCE8DC] shadow-xs space-y-2 hover:border-[#B8DFC9] transition-all">
          <div className="flex items-center justify-between text-[#587568]">
            <span className="text-[11px] font-bold uppercase tracking-wider">Keywords</span>
            <TrendingUp className="w-4 h-4 text-[#236B4F]" />
          </div>
          <div className="text-2xl font-black text-[#142820] tracking-tight">{summary.tracked_keywords}</div>
          <div className="text-[10px] text-[#587568] font-medium">
            Across {summary.total_projects} active projects
          </div>
        </div>

        {/* Active Scan Jobs */}
        <div className="p-4 rounded-2xl bg-white border border-[#DCE8DC] shadow-xs space-y-2 hover:border-[#B8DFC9] transition-all">
          <div className="flex items-center justify-between text-[#587568]">
            <span className="text-[11px] font-bold uppercase tracking-wider">Active Scans</span>
            <Activity className={`w-4 h-4 ${summary.active_scan_jobs > 0 ? 'text-purple-600 animate-spin' : 'text-[#587568]'}`} />
          </div>
          <div className="text-2xl font-black text-[#142820] tracking-tight">{summary.active_scan_jobs}</div>
          <div className="text-[10px] text-[#587568] font-medium">
            {summary.completed_scans} completed scans
          </div>
        </div>

        {/* Geo-Grid Scans */}
        <div className="p-4 rounded-2xl bg-white border border-[#DCE8DC] shadow-xs space-y-2 hover:border-[#B8DFC9] transition-all">
          <div className="flex items-center justify-between text-[#587568]">
            <span className="text-[11px] font-bold uppercase tracking-wider">Geo-Grid</span>
            <MapPin className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-black text-[#142820] tracking-tight">{summary.geogrid_scans}</div>
          <div className="text-[10px] text-[#587568] font-medium">Local grid heatmaps</div>
        </div>

        {/* Citations & NAP */}
        <div className="p-4 rounded-2xl bg-white border border-[#DCE8DC] shadow-xs space-y-2 hover:border-[#B8DFC9] transition-all">
          <div className="flex items-center justify-between text-[#587568]">
            <span className="text-[11px] font-bold uppercase tracking-wider">Citations</span>
            <BookOpen className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-2xl font-black text-[#142820] tracking-tight">{summary.citation_records}</div>
          <div className="text-[10px] text-[#587568] font-medium">Directories verified</div>
        </div>

        {/* Reviews Tracked */}
        <div className="p-4 rounded-2xl bg-white border border-[#DCE8DC] shadow-xs space-y-2 hover:border-[#B8DFC9] transition-all">
          <div className="flex items-center justify-between text-[#587568]">
            <span className="text-[11px] font-bold uppercase tracking-wider">Reviews</span>
            <Star className="w-4 h-4 text-amber-500 fill-amber-500/30" />
          </div>
          <div className="text-2xl font-black text-[#142820] tracking-tight">{summary.total_reviews}</div>
          <div className="text-[10px] text-[#587568] font-medium">{summary.open_tasks} open tasks</div>
        </div>
      </div>

      {/* 4. Customer Resource Capacity & Usage Bars */}
      <div className="bg-white rounded-3xl border border-[#DCE8DC] p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#236B4F]" />
            <h3 className="text-sm font-black text-[#142820] uppercase tracking-wider">
              Account Resource Capacity
            </h3>
          </div>
          <span className="text-[11px] font-semibold text-[#587568]">
            Current plan allocation & consumption
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-1">
          {/* SERP Provider Usage */}
          <div className="p-3.5 rounded-2xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-2 relative group hover:border-[#B8DFC9] transition-all">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="font-bold text-[#142820] truncate">SERP Provider Usage</span>
                {serpProvider?.connected && (
                  <button
                    onClick={handleRefreshSerp}
                    disabled={isRefreshingSerp}
                    title="Refresh external SERP provider usage"
                    className="p-1 rounded-md hover:bg-[#EAF2EA] text-[#587568] hover:text-[#236B4F] transition-colors"
                  >
                    <RotateCw className={`w-3 h-3 ${isRefreshingSerp ? 'animate-spin text-[#236B4F]' : ''}`} />
                  </button>
                )}
              </div>

              {serpProvider?.connected ? (
                <span className="text-[10px] font-extrabold px-1.5 py-0.5 rounded-md bg-[#EAF2EA] text-[#236B4F] truncate max-w-[120px]">
                  {serpProvider.provider_name || 'Connected'}
                </span>
              ) : (
                <Link
                  to="/settings"
                  className="text-[10px] font-bold text-rose-600 hover:underline"
                >
                  Connect
                </Link>
              )}
            </div>

            {/* Dynamic Usage Presentation based on Provider Billing Model */}
            {!serpProvider?.connected ? (
              <div className="space-y-1.5 py-1">
                <div className="text-xs font-bold text-slate-500">Not Connected</div>
                <div className="text-[10px] text-[#587568] leading-tight">
                  <Link to="/settings" className="text-[#236B4F] font-bold hover:underline">
                    Configure your SERP provider
                  </Link>{' '}
                  in Settings to enable rank tracking.
                </div>
              </div>
            ) : serpProvider.usage_model === 'monthly_search_quota' && serpProvider.limit ? (
              <>
                <div className="flex items-baseline justify-between text-xs">
                  <span className="text-[10px] font-bold text-[#587568] truncate">
                    {serpProvider.plan_name || 'Search Quota'}
                  </span>
                  <span className="font-black text-[#236B4F]">
                    {serpProvider.used?.toLocaleString() ?? 0} / {serpProvider.limit.toLocaleString()}
                  </span>
                </div>
                <div className="w-full bg-[#EAF2EA] h-2 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      (serpProvider.percentage_used || 0) >= 90 ? 'bg-rose-600' : 'bg-[#236B4F]'
                    }`}
                    style={{ width: `${Math.min(100, serpProvider.percentage_used || 0)}%` }}
                  />
                </div>
                <div className="text-[10px] text-[#587568] flex justify-between">
                  <span>{serpProvider.remaining?.toLocaleString() ?? 0} remaining</span>
                  <span>{serpProvider.percentage_used || 0}% used</span>
                </div>
              </>
            ) : serpProvider.usage_model === 'account_balance' && serpProvider.balance !== null ? (
              <div className="space-y-1 py-0.5">
                <div className="text-base font-black text-emerald-700">
                  ${serpProvider.balance.toFixed(2)} <span className="text-[10px] font-bold text-[#587568]">{serpProvider.currency || 'USD'}</span>
                </div>
                <div className="text-[10px] text-[#587568]">
                  Account Balance • Usage billed per query
                </div>
              </div>
            ) : serpProvider.usage_model === 'credits' ? (
              <div className="space-y-1.5 py-0.5">
                <div className="flex items-baseline justify-between text-xs">
                  <span className="text-[10px] font-bold text-[#587568]">Credits Balance</span>
                  <span className="font-black text-emerald-700">
                    {serpProvider.remaining?.toLocaleString() ?? serpProvider.used?.toLocaleString() ?? 0}
                  </span>
                </div>
                <div className="text-[10px] text-[#587568]">
                  {serpProvider.used?.toLocaleString() || 0} credits used this period
                </div>
              </div>
            ) : (
              <div className="space-y-1 py-0.5">
                <div className="text-xs font-bold text-[#142820]">
                  {serpProvider.provider_name} Active
                </div>
                <div className="text-[10px] text-[#587568]">
                  Self-hosted / unmetered SERP requests
                </div>
              </div>
            )}

            <div className="text-[9px] text-[#587568] pt-1 border-t border-[#EAF2EA] flex items-center justify-between">
              <span>LocalLift: {usage.serp_used.toLocaleString()} queries</span>
              <span>{serpProvider?.last_synced_at ? `Synced` : 'Live'}</span>
            </div>
          </div>

          {/* AI Tokens */}
          <div className="p-3.5 rounded-2xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-[#142820]">AI Tokens</span>
              <span className="font-black text-purple-700">
                {usage.ai_tokens_used.toLocaleString()} tokens
              </span>
            </div>
            <div className="w-full bg-[#EAF2EA] h-2 rounded-full overflow-hidden">
              <div
                className="bg-purple-600 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, (usage.ai_tokens_used / (usage.ai_tokens_limit || 1)) * 100)}%` }}
              />
            </div>
            <div className="text-[10px] text-[#587568] flex justify-between">
              <span>Diagnostics & Content AI</span>
              <span>{Math.round((usage.ai_tokens_used / (usage.ai_tokens_limit || 1)) * 100)}%</span>
            </div>
          </div>

          {/* Keyword Tracking */}
          <div className="p-3.5 rounded-2xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-[#142820]">Keywords Capacity</span>
              <span className="font-black text-blue-700">
                {usage.keywords_used} / {usage.keywords_limit}
              </span>
            </div>
            <div className="w-full bg-[#EAF2EA] h-2 rounded-full overflow-hidden">
              <div
                className="bg-blue-600 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, (usage.keywords_used / (usage.keywords_limit || 1)) * 100)}%` }}
              />
            </div>
            <div className="text-[10px] text-[#587568] flex justify-between">
              <span>Active tracked keywords</span>
              <span>{Math.round((usage.keywords_used / (usage.keywords_limit || 1)) * 100)}%</span>
            </div>
          </div>

          {/* Geo-Grid Points */}
          <div className="p-3.5 rounded-2xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-[#142820]">Geo-Grid Scans</span>
              <span className="font-black text-emerald-700">
                {usage.geogrid_used} / {usage.geogrid_limit}
              </span>
            </div>
            <div className="w-full bg-[#EAF2EA] h-2 rounded-full overflow-hidden">
              <div
                className="bg-emerald-600 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, (usage.geogrid_used / (usage.geogrid_limit || 1)) * 100)}%` }}
              />
            </div>
            <div className="text-[10px] text-[#587568] flex justify-between">
              <span>5x5 & 7x7 grid searches</span>
              <span>{Math.round((usage.geogrid_used / (usage.geogrid_limit || 1)) * 100)}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* 5. Filter & View Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3.5 rounded-2xl border border-[#DCE8DC] shadow-xs">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          {[
            { id: 'overview', label: 'Projects Overview', icon: Building2 },
            { id: 'comparison', label: 'Project Comparison', icon: BarChart3 },
            { id: 'activity', label: 'Recent Activity', icon: Activity },
            { id: 'usage', label: 'Resource Telemetry', icon: Zap }
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all shrink-0 ${
                  isActive
                    ? 'bg-[#236B4F] text-white shadow-xs'
                    : 'text-[#587568] hover:text-[#142820] hover:bg-[#F1F7F1]'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Global Filters: Date Range + Project Filter */}
        <div className="flex items-center gap-2 self-end sm:self-auto">
          {/* Project Filter */}
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] text-xs font-semibold text-[#142820]">
            <Filter className="w-3.5 h-3.5 text-[#587568]" />
            <select
              value={selectedProjectId || ''}
              onChange={(e) => setSelectedProjectId(e.target.value ? Number(e.target.value) : null)}
              className="bg-transparent border-none text-xs font-bold text-[#142820] focus:ring-0 cursor-pointer p-0 pr-1 outline-none"
            >
              <option value="">All Authorized Projects</option>
              {overview?.projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* Date Range Selector */}
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] text-xs font-semibold text-[#142820]">
            <Calendar className="w-3.5 h-3.5 text-[#587568]" />
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value as any)}
              className="bg-transparent border-none text-xs font-bold text-[#142820] focus:ring-0 cursor-pointer p-0 pr-1 outline-none"
            >
              <option value="today">Today</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="90d">Last 90 Days</option>
            </select>
          </div>
        </div>
      </div>

      {/* 6. TAB CONTENT */}

      {/* TAB 1: Projects Overview Cards & Table */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Projects Table Card */}
          <div className="bg-white rounded-3xl border border-[#DCE8DC] shadow-xs overflow-hidden">
            {/* Table Header Controls */}
            <div className="p-5 border-b border-[#EBF2EB] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-black text-[#142820] uppercase tracking-wider">
                  My Authorized Projects ({filteredProjects.length})
                </h3>
                <p className="text-xs text-[#587568] mt-0.5">
                  Click any project to switch to its dedicated Single Project Dashboard
                </p>
              </div>

              {/* Search input */}
              <div className="relative max-w-xs w-full">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[#587568]" />
                <input
                  type="text"
                  placeholder="Filter projects by name or domain..."
                  value={searchProjectQuery}
                  onChange={(e) => setSearchProjectQuery(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] text-xs text-[#142820] placeholder-slate-400 focus:outline-none focus:border-[#236B4F]"
                />
              </div>
            </div>

            {/* Table / List */}
            {filteredProjects.length === 0 ? (
              <div className="p-12 text-center space-y-3">
                <Building2 className="w-10 h-10 text-slate-300 mx-auto" />
                <p className="text-xs text-slate-500 font-semibold">No projects match your filter.</p>
              </div>
            ) : (
              <div className="divide-y divide-[#EBF2EB] overflow-x-auto">
                {filteredProjects.map((proj) => {
                  const hasHealth = proj.health_score !== null && proj.health_score !== undefined;
                  const score = proj.health_score || 0;
                  const scoreColor =
                    score >= 80 ? 'text-emerald-700 bg-emerald-50 border-emerald-200' :
                    score >= 60 ? 'text-amber-700 bg-amber-50 border-amber-200' :
                    'text-rose-700 bg-rose-50 border-rose-200';

                  return (
                    <div
                      key={proj.id}
                      className="p-5 hover:bg-[#F7FAF7] transition-all flex flex-col lg:flex-row lg:items-center justify-between gap-4 group"
                    >
                      {/* Left: Project identity */}
                      <div className="flex items-start gap-3.5 min-w-0 flex-1">
                        <div className="w-10 h-10 rounded-2xl bg-[#EAF2EA] border border-[#B8DFC9] flex items-center justify-center shrink-0 text-[#236B4F] font-black text-sm group-hover:scale-105 transition-transform shadow-2xs">
                          {proj.name.charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h4 className="font-black text-sm text-[#142820] truncate">{proj.name}</h4>
                            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#F1F7F1] text-[#2E4E40] border border-[#DCE8DC]">
                              {proj.primary_category}
                            </span>
                            {proj.country && (
                              <span className="text-[10px] text-[#587568] font-medium">
                                ({proj.country})
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-[#587568] font-medium flex items-center gap-2 mt-0.5">
                            <span className="text-[#236B4F] font-semibold">{proj.domain}</span>
                            <span>•</span>
                            <span>
                              Last scan: {proj.last_scan_date ? new Date(proj.last_scan_date).toLocaleDateString() : 'No scan yet'}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Middle: Metrics Pills */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-4 shrink-0">
                        {/* Health Score */}
                        <div className="p-2 rounded-xl bg-white border border-[#DCE8DC] text-center min-w-[85px]">
                          <div className="text-[10px] text-[#587568] font-bold uppercase">SEO Health</div>
                          <div className={`text-xs font-black mt-0.5 px-2 py-0.5 rounded-lg border inline-block ${hasHealth ? scoreColor : 'text-slate-400 bg-slate-50 border-slate-200'}`}>
                            {hasHealth ? `${score}%` : 'Not scanned'}
                          </div>
                        </div>

                        {/* Keywords */}
                        <div className="p-2 rounded-xl bg-white border border-[#DCE8DC] text-center min-w-[85px]">
                          <div className="text-[10px] text-[#587568] font-bold uppercase">Keywords</div>
                          <div className="text-xs font-black text-[#142820] mt-0.5">
                            {proj.keyword_count > 0 ? `${proj.keyword_count} tracked` : '0'}
                          </div>
                        </div>

                        {/* Citations & Reviews */}
                        <div className="p-2 rounded-xl bg-white border border-[#DCE8DC] text-center min-w-[85px]">
                          <div className="text-[10px] text-[#587568] font-bold uppercase">Citations</div>
                          <div className="text-xs font-black text-[#142820] mt-0.5">
                            {proj.citation_count} directories
                          </div>
                        </div>

                        {/* Open Tasks */}
                        <div className="p-2 rounded-xl bg-white border border-[#DCE8DC] text-center min-w-[85px]">
                          <div className="text-[10px] text-[#587568] font-bold uppercase">Open Issues</div>
                          <div className="text-xs font-black text-[#142820] mt-0.5">
                            {proj.open_issues_count} items
                          </div>
                        </div>
                      </div>

                      {/* Right: Open Dashboard CTA */}
                      <div className="shrink-0 flex items-center justify-end">
                        <button
                          onClick={() => handleOpenProjectDashboard(proj)}
                          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#EAF2EA] hover:bg-[#236B4F] text-[#174A38] hover:text-white border border-[#B8DFC9] hover:border-transparent text-xs font-bold transition-all shadow-xs group-hover:bg-[#236B4F] group-hover:text-white"
                        >
                          <span>Open Dashboard</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Multi-Project Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Chart 1: Project Activity Comparison */}
            <div className="bg-white rounded-3xl border border-[#DCE8DC] p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-black text-[#142820] uppercase tracking-wider">
                    Project Activity Comparison
                  </h3>
                  <p className="text-xs text-[#587568] mt-0.5">
                    Comparative telemetry score across your authorized projects
                  </p>
                </div>
                <BarChart3 className="w-4 h-4 text-[#236B4F]" />
              </div>

              {analyticsLoading ? (
                <div className="py-12 text-center text-xs text-[#587568]">Loading activity comparison...</div>
              ) : !analytics?.project_comparison || analytics.project_comparison.length === 0 ? (
                <div className="py-12 text-center text-xs text-[#587568]">No project comparison data.</div>
              ) : (
                <div className="space-y-3 pt-2">
                  {analytics.project_comparison.map((item) => {
                    const pct = Math.round((item.relative_activity_score / maxActivityScore) * 100);
                    return (
                      <div key={item.project_id} className="space-y-1.5">
                        <div className="flex items-center justify-between text-xs">
                          <div className="font-bold text-[#142820] truncate max-w-[200px]">
                            {item.project_name}
                          </div>
                          <div className="flex items-center gap-3 text-[11px] text-[#587568]">
                            <span>{item.keywords_count} keywords</span>
                            <span>•</span>
                            <span className="font-semibold text-[#236B4F]">{item.scans_count} scans</span>
                          </div>
                        </div>
                        <div className="w-full bg-[#EAF2EA] h-3 rounded-full overflow-hidden">
                          <div
                            className="bg-gradient-to-r from-[#236B4F] to-[#2FA878] h-full rounded-full transition-all duration-500"
                            style={{ width: `${Math.max(8, pct)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Chart 2: Keyword Ranking Distribution */}
            <div className="bg-white rounded-3xl border border-[#DCE8DC] p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-black text-[#142820] uppercase tracking-wider">
                    Keyword Ranking Distribution
                  </h3>
                  <p className="text-xs text-[#587568] mt-0.5">
                    SERP rank distribution across all tracked keywords in your projects
                  </p>
                </div>
                <TrendingUp className="w-4 h-4 text-[#236B4F]" />
              </div>

              {analyticsLoading ? (
                <div className="py-12 text-center text-xs text-[#587568]">Loading ranking distribution...</div>
              ) : (
                <div className="space-y-4 pt-2">
                  {/* Visual segment breakdown */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 rounded-2xl bg-emerald-50 border border-emerald-200 text-center">
                      <div className="text-[10px] font-black uppercase text-emerald-800">Top 3 Ranks</div>
                      <div className="text-xl font-black text-emerald-900 mt-0.5">
                        {analytics?.ranking_distribution.top3 || 0}
                      </div>
                    </div>
                    <div className="p-3 rounded-2xl bg-blue-50 border border-blue-200 text-center">
                      <div className="text-[10px] font-black uppercase text-blue-800">Top 10 Ranks</div>
                      <div className="text-xl font-black text-blue-900 mt-0.5">
                        {analytics?.ranking_distribution.top10 || 0}
                      </div>
                    </div>
                    <div className="p-3 rounded-2xl bg-amber-50 border border-amber-200 text-center">
                      <div className="text-[10px] font-black uppercase text-amber-800">Top 20 Ranks</div>
                      <div className="text-xl font-black text-amber-900 mt-0.5">
                        {analytics?.ranking_distribution.top20 || 0}
                      </div>
                    </div>
                    <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200 text-center">
                      <div className="text-[10px] font-black uppercase text-slate-700">Beyond 20</div>
                      <div className="text-xl font-black text-slate-800 mt-0.5">
                        {analytics?.ranking_distribution.below20 || 0}
                      </div>
                    </div>
                  </div>

                  {/* Summary note */}
                  <div className="p-3.5 rounded-2xl bg-[#F7FAF7] border border-[#DCE8DC] text-xs text-[#587568] flex items-center gap-2.5">
                    <Info className="w-4 h-4 text-[#236B4F] shrink-0" />
                    <span>
                      Total <strong>{summary.tracked_keywords}</strong> keywords monitored in live SERP scans across your active projects.
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: Project Comparison Matrix */}
      {activeTab === 'comparison' && (
        <div className="bg-white rounded-3xl border border-[#DCE8DC] p-6 shadow-xs space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-black text-[#142820] uppercase tracking-wider">
                Multi-Project Comparative Matrix
              </h3>
              <p className="text-xs text-[#587568] mt-0.5">
                Measurable performance metrics across all your customer projects
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#DCE8DC] text-[#587568] text-[10px] font-extrabold uppercase tracking-wider bg-[#F7FAF7]">
                  <th className="p-3.5 rounded-l-xl">Project Name</th>
                  <th className="p-3.5">Category</th>
                  <th className="p-3.5">Health Score</th>
                  <th className="p-3.5">Keywords</th>
                  <th className="p-3.5">Reviews</th>
                  <th className="p-3.5">Citations</th>
                  <th className="p-3.5">Open Issues</th>
                  <th className="p-3.5">Last Scan</th>
                  <th className="p-3.5 rounded-r-xl text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EBF2EB]">
                {overview?.projects.map((p) => (
                  <tr key={p.id} className="hover:bg-[#F7FAF7] transition-colors">
                    <td className="p-3.5">
                      <div className="font-bold text-[#142820]">{p.name}</div>
                      <div className="text-[10px] text-[#587568]">{p.domain}</div>
                    </td>
                    <td className="p-3.5 font-medium text-[#2E4E40]">{p.primary_category}</td>
                    <td className="p-3.5">
                      {p.health_score !== null ? (
                        <span className="px-2 py-0.5 rounded-md font-bold text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200">
                          {p.health_score}%
                        </span>
                      ) : (
                        <span className="text-[10px] text-slate-400">No score</span>
                      )}
                    </td>
                    <td className="p-3.5 font-bold text-[#142820]">{p.keyword_count}</td>
                    <td className="p-3.5">
                      <span className="font-bold text-[#142820]">{p.review_count}</span>
                      {p.rating_avg && <span className="text-[#587568] ml-1">({p.rating_avg}★)</span>}
                    </td>
                    <td className="p-3.5 font-bold text-[#142820]">{p.citation_count}</td>
                    <td className="p-3.5 font-bold text-amber-700">{p.open_issues_count}</td>
                    <td className="p-3.5 text-[#587568]">
                      {p.last_scan_date ? new Date(p.last_scan_date).toLocaleDateString() : '—'}
                    </td>
                    <td className="p-3.5 text-right">
                      <button
                        onClick={() => handleOpenProjectDashboard(p)}
                        className="px-3 py-1.5 rounded-xl bg-[#EAF2EA] hover:bg-[#236B4F] text-[#174A38] hover:text-white text-xs font-bold transition-colors"
                      >
                        Switch To Project
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: Recent Activity Stream */}
      {activeTab === 'activity' && (
        <div className="bg-white rounded-3xl border border-[#DCE8DC] p-6 shadow-xs space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-black text-[#142820] uppercase tracking-wider">
                Authorized Projects Activity Stream
              </h3>
              <p className="text-xs text-[#587568] mt-0.5">
                Real-time chronological events strictly from your organization&apos;s projects
              </p>
            </div>
          </div>

          {!overview?.recent_activity || overview.recent_activity.length === 0 ? (
            <div className="py-12 text-center text-xs text-[#587568]">No recent activity recorded yet.</div>
          ) : (
            <div className="space-y-3">
              {overview.recent_activity.map((act) => (
                <div
                  key={act.id}
                  className="p-3.5 rounded-2xl bg-[#F7FAF7] border border-[#DCE8DC] hover:border-[#B8DFC9] transition-all flex items-center justify-between gap-4 text-xs"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-xl bg-[#EAF2EA] text-[#236B4F] flex items-center justify-center shrink-0 font-bold">
                      {act.type === 'scan_job' ? <Activity className="w-4 h-4" /> : <CheckSquare className="w-4 h-4" />}
                    </div>
                    <div className="min-w-0">
                      <div className="font-bold text-[#142820] truncate">{act.title}</div>
                      <div className="text-[10px] text-[#587568]">{act.details}</div>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#EAF2EA] text-[#174A38]">
                      {act.status}
                    </span>
                    <div className="text-[9px] text-slate-400 mt-0.5">
                      {act.timestamp ? new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 4: Resource Telemetry */}
      {activeTab === 'usage' && (
        <div className="bg-white rounded-3xl border border-[#DCE8DC] p-6 shadow-xs space-y-6">
          <div>
            <h3 className="text-sm font-black text-[#142820] uppercase tracking-wider">
              Resource Telemetry & Quota Accounting
            </h3>
            <p className="text-xs text-[#587568] mt-0.5">
              Live consumption tracking across SERP providers, AI tokens, and scanner points
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-5 rounded-2xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-4">
              <h4 className="text-xs font-black text-[#142820] uppercase">SERP Queries Breakdown</h4>
              <div className="text-3xl font-black text-[#236B4F]">
                {usage.serp_used.toLocaleString()} <span className="text-xs text-[#587568] font-medium">queries consumed</span>
              </div>
              <p className="text-xs text-[#587568] leading-relaxed">
                Aggregates keyword rank scans, competitor checks, and geo-grid search points executed across your {summary.total_projects} projects.
              </p>
            </div>

            <div className="p-5 rounded-2xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-4">
              <h4 className="text-xs font-black text-[#142820] uppercase">AI Diagnostics & Tokens</h4>
              <div className="text-3xl font-black text-purple-700">
                {usage.ai_tokens_used.toLocaleString()} <span className="text-xs text-[#587568] font-medium">tokens used</span>
              </div>
              <p className="text-xs text-[#587568] leading-relaxed">
                Tokens consumed during AI assistant diagnostics, review response generations, and landing page content gap recommendations.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

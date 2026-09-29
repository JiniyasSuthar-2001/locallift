import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid
} from 'recharts';
import {
  TrendingUp,
  Activity,
  Layers,
  Search,
  Cpu,
  ShieldAlert,
  AlertTriangle,
  Calendar,
  Download,
  Filter,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Info,
  ExternalLink,
  ChevronRight,
  Users,
  Globe
} from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../../api/client';

interface AnalyticsSectionProps {
  customers?: any[];
}

export const MasterPlaceAnalyticsSection: React.FC<AnalyticsSectionProps> = ({ customers = [] }) => {
  const [range, setRange] = useState<string>('30d');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [customerId, setCustomerId] = useState<string>('');
  const [providerFilter, setProviderFilter] = useState<string>('');
  const [jobTypeFilter, setJobTypeFilter] = useState<string>('');

  const [activeTab, setActiveTab] = useState<'growth' | 'scans' | 'providers' | 'tenants' | 'reliability'>('growth');
  const [tenantMetric, setTenantMetric] = useState<'serp_requests' | 'ai_tokens' | 'google_requests' | 'scan_jobs' | 'total_cost_usd'>('serp_requests');

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = async (isManual = false) => {
    if (isManual) setRefreshing(true);
    else setLoading(true);

    try {
      const params: any = { range };
      if (range === 'custom' && startDate && endDate) {
        params.start_date = startDate;
        params.end_date = endDate;
      }
      if (customerId) params.customer_id = customerId;
      if (providerFilter) params.provider = providerFilter;
      if (jobTypeFilter) params.job_type = jobTypeFilter;

      const res = await api.get('/masterplace/analytics/overview', { params });
      setData(res.data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to load MasterPlace analytics:', err);
      setError('Unable to load analytics data from backend.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, [range, customerId, providerFilter, jobTypeFilter]);

  const handleExportCSV = (metric: string) => {
    const params = new URLSearchParams({
      metric,
      range,
      ...(customerId ? { customer_id: customerId } : {})
    });
    window.open(`/api/v1/masterplace/analytics/export?${params.toString()}`, '_blank');
  };

  const ts = data?.time_series || {};
  const kpis = data?.kpis || {};

  // Custom Chart Tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-900/95 border border-slate-700/80 p-3 rounded-xl shadow-2xl backdrop-blur-md text-xs space-y-1.5 min-w-[160px]">
          <div className="font-bold text-slate-300 border-b border-slate-800 pb-1">{label}</div>
          {payload.map((entry: any, index: number) => (
            <div key={`item-${index}`} className="flex items-center justify-between gap-4">
              <span className="flex items-center gap-1.5" style={{ color: entry.color }}>
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
                <span className="text-slate-400 capitalize">{entry.name.replace(/_/g, ' ')}:</span>
              </span>
              <span className="font-bold text-white">
                {typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  const renderEmptyState = (title: string, desc: string) => (
    <div className="flex flex-col items-center justify-center h-64 text-center p-6 bg-slate-950/40 rounded-2xl border border-dashed border-slate-800">
      <Info className="w-8 h-8 text-slate-600 mb-2" />
      <div className="text-xs font-bold text-slate-300">{title}</div>
      <p className="text-[11px] text-slate-500 max-w-sm mt-1">{desc}</p>
    </div>
  );

  return (
    <div className="space-y-6 pt-4">
      {/* ─── Header & Filter Bar ─── */}
      <div className="p-5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-purple-400" />
              <h2 className="text-base font-black tracking-tight text-white uppercase">Platform Analytics & Growth Telemetry</h2>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Historical performance, cross-tenant resource consumption, and provider health derived from database records.
            </p>
          </div>

          {/* Quick Date Range Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            {[
              { id: 'today', label: 'Today' },
              { id: '7d', label: '7 Days' },
              { id: '30d', label: '30 Days' },
              { id: '90d', label: '90 Days' },
              { id: 'custom', label: 'Custom' }
            ].map((btn) => (
              <button
                key={btn.id}
                onClick={() => setRange(btn.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  range === btn.id
                    ? 'bg-purple-600 text-white shadow-md shadow-purple-600/30'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-750 border border-slate-700/60'
                }`}
              >
                {btn.label}
              </button>
            ))}

            <button
              onClick={() => fetchAnalytics(true)}
              disabled={refreshing}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700/60 transition-all"
              title="Refresh Analytics"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Dimension Filters */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-slate-800/80 text-xs">
          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Filter Customer</label>
            <select
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-purple-500"
            >
              <option value="">All Customers (Platform-Wide)</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} {c.status === 'suspended' ? '(Suspended)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Filter Provider</label>
            <select
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value)}
              className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-purple-500"
            >
              <option value="">All Providers</option>
              <option value="serpapi">SerpApi</option>
              <option value="openserp">OpenSERP</option>
              <option value="gemini">Gemini AI</option>
              <option value="openai">OpenAI</option>
              <option value="google_places">Google Places API</option>
            </select>
          </div>

          <div>
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">Scan Job Type</label>
            <select
              value={jobTypeFilter}
              onChange={(e) => setJobTypeFilter(e.target.value)}
              className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-purple-500"
            >
              <option value="">All Scan Types</option>
              <option value="keyword_rank">Keyword Rank Tracker</option>
              <option value="geo_grid">Geo-Grid Scanner</option>
              <option value="website_audit">Technical SEO Audit</option>
              <option value="local_audit">Local SEO Audit</option>
            </select>
          </div>

          {range === 'custom' && (
            <div className="flex items-center gap-2">
              <div className="flex-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">From</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full px-2 py-1 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-xs"
                />
              </div>
              <div className="flex-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">To</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full px-2 py-1 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-xs"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ─── Period KPI Snapshot Cards with Delta ─── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>Period Scans</span>
            <Activity className="w-3.5 h-3.5 text-purple-400" />
          </div>
          <div className="text-xl font-black text-white">{kpis.total_scans?.toLocaleString() || 0}</div>
          <div className="text-[10px] flex items-center gap-1 font-semibold">
            {kpis.scans_growth_pct != null ? (
              <span className={kpis.scans_growth_pct >= 0 ? 'text-emerald-400 flex items-center' : 'text-rose-400 flex items-center'}>
                {kpis.scans_growth_pct >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                {Math.abs(kpis.scans_growth_pct)}% vs prior period
              </span>
            ) : (
              <span className="text-slate-500">Baseline period</span>
            )}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>SERP Requests</span>
            <Search className="w-3.5 h-3.5 text-blue-400" />
          </div>
          <div className="text-xl font-black text-white">{kpis.total_serp_requests?.toLocaleString() || 0}</div>
          <div className="text-[10px] flex items-center gap-1 font-semibold">
            {kpis.serp_growth_pct != null ? (
              <span className={kpis.serp_growth_pct >= 0 ? 'text-emerald-400 flex items-center' : 'text-rose-400 flex items-center'}>
                {kpis.serp_growth_pct >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                {Math.abs(kpis.serp_growth_pct)}% vs prior
              </span>
            ) : (
              <span className="text-slate-500">Tracked SERP calls</span>
            )}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>AI Tokens Used</span>
            <Cpu className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div className="text-xl font-black text-white">{kpis.total_ai_tokens?.toLocaleString() || 0}</div>
          <div className="text-[10px] flex items-center gap-1 font-semibold">
            {kpis.ai_growth_pct != null ? (
              <span className={kpis.ai_growth_pct >= 0 ? 'text-emerald-400 flex items-center' : 'text-rose-400 flex items-center'}>
                {kpis.ai_growth_pct >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                {Math.abs(kpis.ai_growth_pct)}% vs prior
              </span>
            ) : (
              <span className="text-slate-500">Token telemetry</span>
            )}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>Google API Calls</span>
            <Layers className="w-3.5 h-3.5 text-amber-400" />
          </div>
          <div className="text-xl font-black text-white">{kpis.total_google_requests?.toLocaleString() || 0}</div>
          <div className="text-[10px] text-slate-400 font-medium truncate">
            GBP, GSC, Places tracked
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-1">
          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <span>Platform Errors</span>
            <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
          </div>
          <div className={`text-xl font-black ${kpis.total_errors > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
            {kpis.total_errors?.toLocaleString() || 0}
          </div>
          <div className="text-[10px] text-slate-400 font-medium">
            API, provider & scan errors
          </div>
        </div>
      </div>

      {/* ─── Analytics Category Navigation Tabs ─── */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2 overflow-x-auto text-xs font-bold">
        {[
          { id: 'growth', label: 'Platform & Customer Growth', icon: TrendingUp },
          { id: 'scans', label: 'Scan Activity & Reliability', icon: Activity },
          { id: 'providers', label: 'Google, SERP & AI Providers', icon: Layers },
          { id: 'tenants', label: 'Top Resource Consumers', icon: Users },
          { id: 'reliability', label: 'System Errors & Queue Health', icon: ShieldAlert }
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl transition-all whitespace-nowrap ${
                isActive
                  ? 'bg-purple-950/60 text-purple-300 border border-purple-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Loading state indicator */}
      {loading && !data && (
        <div className="flex items-center justify-center h-80">
          <div className="text-center space-y-2">
            <div className="w-8 h-8 border-3 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-slate-400 font-medium">Compiling platform analytics...</p>
          </div>
        </div>
      )}

      {/* ─── TAB 1: PLATFORM & CUSTOMER GROWTH ─── */}
      {!loading && activeTab === 'growth' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Customer Growth */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black text-white tracking-tight">Customer Growth Over Time</h3>
                <p className="text-[11px] text-slate-400">New customer signups, active tenants, and suspended accounts</p>
              </div>
              <button
                onClick={() => handleExportCSV('customer_growth')}
                className="flex items-center gap-1 text-[11px] font-semibold text-purple-400 hover:text-purple-300 transition-colors"
                title="Export CSV"
              >
                <Download className="w-3 h-3" />
                CSV
              </button>
            </div>

            {ts.customer_growth && ts.customer_growth.length > 0 ? (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={ts.customer_growth}>
                    <defs>
                      <linearGradient id="activeCustGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="label" stroke="#64748b" fontSize={10} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                    <Area type="monotone" dataKey="active_customers" name="Active Customers" stroke="#8b5cf6" fillOpacity={1} fill="url(#activeCustGrad)" strokeWidth={2} />
                    <Line type="monotone" dataKey="new_customers" name="New Customers" stroke="#10b981" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="suspended_customers" name="Suspended" stroke="#ef4444" strokeWidth={1.5} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              renderEmptyState('No customer historical data', 'No customer growth records found for the selected time range.')
            )}

            <div className="flex justify-end pt-2 border-t border-slate-800/80">
              <Link to="/masterplace/customers" className="text-xs font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1">
                View Customers Directory <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
          </div>

          {/* Project & Website Growth */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black text-white tracking-tight">Project & Website Growth</h3>
                <p className="text-[11px] text-slate-400">Total client projects and tracked domains</p>
              </div>
              <button
                onClick={() => handleExportCSV('project_growth')}
                className="flex items-center gap-1 text-[11px] font-semibold text-purple-400 hover:text-purple-300 transition-colors"
                title="Export CSV"
              >
                <Download className="w-3 h-3" />
                CSV
              </button>
            </div>

            {ts.project_website_growth && ts.project_website_growth.length > 0 ? (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={ts.project_website_growth}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="label" stroke="#64748b" fontSize={10} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                    <Line type="monotone" dataKey="total_projects" name="Total Projects" stroke="#3b82f6" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="total_websites" name="Total Websites" stroke="#06b6d4" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="new_projects" name="New Projects" stroke="#a855f7" strokeWidth={1.5} dot={false} strokeDasharray="4 4" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              renderEmptyState('No project records', 'Project growth records will appear here as new projects are registered.')
            )}

            <div className="flex justify-end pt-2 border-t border-slate-800/80">
              <Link to="/masterplace/websites" className="text-xs font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1">
                View Monitored Websites <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 2: SCAN ACTIVITY & HEALTH ─── */}
      {!loading && activeTab === 'scans' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Scan Activity Breakdown */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black text-white tracking-tight">Scan Activity Breakdown</h3>
                <p className="text-[11px] text-slate-400">Scans by engine (Keyword Tracker, Geo-Grid, Audits)</p>
              </div>
              <button
                onClick={() => handleExportCSV('scan_activity')}
                className="flex items-center gap-1 text-[11px] font-semibold text-purple-400 hover:text-purple-300 transition-colors"
                title="Export CSV"
              >
                <Download className="w-3 h-3" />
                CSV
              </button>
            </div>

            {ts.scan_activity && ts.scan_activity.some((r: any) => r.total_scans > 0) ? (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ts.scan_activity}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="label" stroke="#64748b" fontSize={10} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                    <Bar dataKey="keyword_scan" name="Keyword Rank" stackId="a" fill="#8b5cf6" />
                    <Bar dataKey="geo_grid" name="Geo-Grid" stackId="a" fill="#3b82f6" />
                    <Bar dataKey="website_audit" name="Website Audit" stackId="a" fill="#10b981" />
                    <Bar dataKey="local_audit" name="Local Audit" stackId="a" fill="#f59e0b" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              renderEmptyState('No scan jobs in range', 'No scan jobs have been executed during this period.')
            )}

            <div className="flex justify-end pt-2 border-t border-slate-800/80">
              <Link to="/masterplace/jobs" className="text-xs font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1">
                Open Scan Jobs Monitor <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
          </div>

          {/* Scan Reliability & Success Rate */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black text-white tracking-tight">Scan Reliability & Health</h3>
                <p className="text-[11px] text-slate-400">Completed vs Failed vs Timed out jobs</p>
              </div>
              <button
                onClick={() => handleExportCSV('scan_health')}
                className="flex items-center gap-1 text-[11px] font-semibold text-purple-400 hover:text-purple-300 transition-colors"
                title="Export CSV"
              >
                <Download className="w-3 h-3" />
                CSV
              </button>
            </div>

            {ts.scan_health && ts.scan_health.some((r: any) => (r.completed + r.failed + r.timed_out) > 0) ? (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={ts.scan_health}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="label" stroke="#64748b" fontSize={10} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                    <Line type="monotone" dataKey="completed" name="Completed" stroke="#10b981" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="failed" name="Failed" stroke="#ef4444" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="timed_out" name="Timed Out" stroke="#f59e0b" strokeWidth={1.5} dot={false} strokeDasharray="3 3" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              renderEmptyState('Insufficient scan health data', 'Scan reliability metrics will appear here as scan jobs execute.')
            )}

            <div className="flex justify-end pt-2 border-t border-slate-800/80">
              <Link to="/masterplace/jobs" className="text-xs font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1">
                View Failed & Timed Out Jobs <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 3: PROVIDER & RESOURCE USAGE ─── */}
      {!loading && activeTab === 'providers' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Google API Usage & Errors */}
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-black text-white tracking-tight">Tracked Google API Requests</h3>
                  <p className="text-[11px] text-slate-400">Google Business Profile, Search Console & Places calls</p>
                </div>
                <button
                  onClick={() => handleExportCSV('google_api')}
                  className="flex items-center gap-1 text-[11px] font-semibold text-purple-400 hover:text-purple-300 transition-colors"
                >
                  <Download className="w-3 h-3" />
                  CSV
                </button>
              </div>

              {ts.google_api_usage && ts.google_api_usage.some((r: any) => r.total_requests > 0) ? (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={ts.google_api_usage}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="label" stroke="#64748b" fontSize={10} tickLine={false} />
                      <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                      <Bar dataKey="gbp_requests" name="GBP API" stackId="g" fill="#3b82f6" />
                      <Bar dataKey="gsc_requests" name="Search Console" stackId="g" fill="#10b981" />
                      <Bar dataKey="places_requests" name="Places API" stackId="g" fill="#f59e0b" />
                      <Bar dataKey="errors" name="Errors" fill="#ef4444" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                renderEmptyState('No tracked Google API requests', 'No Google API calls tracked in the selected time range.')
              )}

              <div className="flex justify-end pt-2 border-t border-slate-800/80">
                <Link to="/masterplace/google" className="text-xs font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1">
                  Google API Integrations <ChevronRight className="w-3 h-3" />
                </Link>
              </div>
            </div>

            {/* SERP Provider Requests */}
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-black text-white tracking-tight">SERP Provider Traffic</h3>
                  <p className="text-[11px] text-slate-400">Tracked SERP search queries across SerpApi & OpenSERP</p>
                </div>
                <button
                  onClick={() => handleExportCSV('serp_usage')}
                  className="flex items-center gap-1 text-[11px] font-semibold text-purple-400 hover:text-purple-300 transition-colors"
                >
                  <Download className="w-3 h-3" />
                  CSV
                </button>
              </div>

              {ts.serp_usage && ts.serp_usage.some((r: any) => r.total_requests > 0) ? (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={ts.serp_usage}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="label" stroke="#64748b" fontSize={10} tickLine={false} />
                      <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                      <Bar dataKey="serpapi_requests" name="SerpApi" stackId="s" fill="#8b5cf6" />
                      <Bar dataKey="openserp_requests" name="OpenSERP" stackId="s" fill="#06b6d4" />
                      <Bar dataKey="failed" name="Failed Queries" fill="#ef4444" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                renderEmptyState('No SERP queries recorded', 'SERP traffic data will be charted here as keyword and Geo-Grid scans execute.')
              )}

              <div className="flex justify-end pt-2 border-t border-slate-800/80">
                <Link to="/masterplace/serp" className="text-xs font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1">
                  SERP Quotas & Balance <ChevronRight className="w-3 h-3" />
                </Link>
              </div>
            </div>
          </div>

          {/* AI Token Usage & Cost */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-black text-white tracking-tight">AI Token Consumption</h3>
                  <p className="text-[11px] text-slate-400">Input vs Output token volume across AI tasks</p>
                </div>
                <button
                  onClick={() => handleExportCSV('ai_token_usage')}
                  className="flex items-center gap-1 text-[11px] font-semibold text-purple-400 hover:text-purple-300 transition-colors"
                >
                  <Download className="w-3 h-3" />
                  CSV
                </button>
              </div>

              {ts.ai_token_usage && ts.ai_token_usage.some((r: any) => r.total_tokens > 0) ? (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={ts.ai_token_usage}>
                      <defs>
                        <linearGradient id="aiTokenGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="label" stroke="#64748b" fontSize={10} tickLine={false} />
                      <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                      <Tooltip content={<CustomTooltip />} />
                      <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                      <Area type="monotone" dataKey="total_tokens" name="Total Tokens" stroke="#10b981" fillOpacity={1} fill="url(#aiTokenGrad)" strokeWidth={2} />
                      <Line type="monotone" dataKey="input_tokens" name="Input Tokens" stroke="#3b82f6" strokeWidth={1.5} dot={false} />
                      <Line type="monotone" dataKey="output_tokens" name="Output Tokens" stroke="#a855f7" strokeWidth={1.5} dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                renderEmptyState('No AI telemetry recorded', 'AI token consumption data will populate as AI diagnostic and generation features run.')
              )}

              <div className="flex justify-end pt-2 border-t border-slate-800/80">
                <Link to="/masterplace/ai" className="text-xs font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1">
                  AI Governance & Kill Switch <ChevronRight className="w-3 h-3" />
                </Link>
              </div>
            </div>

            {/* AI Provider Breakdown Table */}
            <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
              <h3 className="text-sm font-black text-white tracking-tight">AI Provider Distribution</h3>
              <p className="text-[11px] text-slate-400">Breakdown of requests, total tokens, and estimated compute cost</p>

              {data?.ai_provider_comparison && data.ai_provider_comparison.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        <th className="pb-2">Provider</th>
                        <th className="pb-2 text-right">Requests</th>
                        <th className="pb-2 text-right">Tokens</th>
                        <th className="pb-2 text-right">Errors</th>
                        <th className="pb-2 text-right">Est. Cost</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-medium">
                      {data.ai_provider_comparison.map((p: any) => (
                        <tr key={p.provider} className="hover:bg-slate-850/50">
                          <td className="py-2.5 font-bold text-white uppercase">{p.provider}</td>
                          <td className="py-2.5 text-right text-slate-300">{p.requests.toLocaleString()}</td>
                          <td className="py-2.5 text-right text-emerald-400 font-mono">{p.total_tokens.toLocaleString()}</td>
                          <td className="py-2.5 text-right text-red-400">{p.errors}</td>
                          <td className="py-2.5 text-right text-slate-200 font-mono">${p.estimated_cost_usd}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                renderEmptyState('No provider comparison data', 'AI provider metrics will appear here as requests occur.')
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 4: RESOURCE-CONSUMING TENANTS ─── */}
      {!loading && activeTab === 'tenants' && (
        <div className="space-y-6">
          {/* Top Customers Horizontal Bar / Inspector */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-black text-white tracking-tight">Top Customers by Resource Consumption</h3>
                <p className="text-[11px] text-slate-400">Objective ranking based on measurable provider units and tokens</p>
              </div>

              {/* Metric Selector */}
              <div className="flex items-center gap-2 text-xs">
                <span className="text-[10px] font-bold uppercase text-slate-400">Sort Metric:</span>
                <select
                  value={tenantMetric}
                  onChange={(e) => setTenantMetric(e.target.value as any)}
                  className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-purple-500"
                >
                  <option value="serp_requests">SERP Requests</option>
                  <option value="ai_tokens">AI Tokens</option>
                  <option value="google_requests">Google API Calls</option>
                  <option value="scan_jobs">Scan Jobs</option>
                  <option value="total_cost_usd">Estimated Cost ($)</option>
                </select>

                <button
                  onClick={() => handleExportCSV('top_customers')}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-750 text-slate-300 font-semibold transition-colors"
                >
                  <Download className="w-3 h-3" />
                  CSV
                </button>
              </div>
            </div>

            {data?.top_customers_usage && data.top_customers_usage.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      <th className="pb-2">Customer / Org</th>
                      <th className="pb-2">Status</th>
                      <th className="pb-2 text-right">SERP Calls</th>
                      <th className="pb-2 text-right">AI Tokens</th>
                      <th className="pb-2 text-right">Google Calls</th>
                      <th className="pb-2 text-right">Scan Jobs</th>
                      <th className="pb-2 text-right">Est. Cost</th>
                      <th className="pb-2 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-medium">
                    {data.top_customers_usage.map((c: any) => (
                      <tr key={c.id} className="hover:bg-slate-850/50">
                        <td className="py-3 font-bold text-white">{c.name}</td>
                        <td className="py-3">
                          <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold uppercase ${
                            c.status === 'active'
                              ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-500/30'
                              : 'bg-red-950/60 text-red-400 border border-red-500/30'
                          }`}>
                            {c.status}
                          </span>
                        </td>
                        <td className="py-3 text-right text-blue-400 font-mono">{c.serp_requests.toLocaleString()}</td>
                        <td className="py-3 text-right text-emerald-400 font-mono">{c.ai_tokens.toLocaleString()}</td>
                        <td className="py-3 text-right text-amber-400 font-mono">{c.google_requests.toLocaleString()}</td>
                        <td className="py-3 text-right text-purple-400 font-mono">{c.scan_jobs.toLocaleString()}</td>
                        <td className="py-3 text-right text-slate-200 font-mono">${c.total_cost_usd}</td>
                        <td className="py-3 text-right">
                          <Link
                            to={`/masterplace/customers?search=${encodeURIComponent(c.name)}`}
                            className="inline-flex items-center gap-1 text-[11px] font-bold text-purple-400 hover:text-purple-300"
                          >
                            Inspect <ExternalLink className="w-3 h-3" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              renderEmptyState('No customer resource usage', 'Tenant usage telemetry will appear here once scans and API calls execute.')
            )}
          </div>

          {/* Top Websites */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black text-white tracking-tight">Top Websites by Activity</h3>
                <p className="text-[11px] text-slate-400">Highest volume domains across all client projects</p>
              </div>
              <button
                onClick={() => handleExportCSV('top_websites')}
                className="flex items-center gap-1 text-[11px] font-semibold text-purple-400 hover:text-purple-300 transition-colors"
              >
                <Download className="w-3 h-3" />
                CSV
              </button>
            </div>

            {data?.top_websites_usage && data.top_websites_usage.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      <th className="pb-2">Domain</th>
                      <th className="pb-2">Project</th>
                      <th className="pb-2">Customer Org</th>
                      <th className="pb-2 text-right">SERP Requests</th>
                      <th className="pb-2 text-right">AI Tokens</th>
                      <th className="pb-2 text-right">Google Calls</th>
                      <th className="pb-2 text-right">Scan Jobs</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-medium">
                    {data.top_websites_usage.map((w: any) => (
                      <tr key={w.id} className="hover:bg-slate-850/50">
                        <td className="py-2.5 font-bold text-white font-mono">{w.domain}</td>
                        <td className="py-2.5 text-slate-300">{w.project_name}</td>
                        <td className="py-2.5 text-slate-400">{w.org_name}</td>
                        <td className="py-2.5 text-right text-blue-400 font-mono">{w.serp_requests}</td>
                        <td className="py-2.5 text-right text-emerald-400 font-mono">{w.ai_tokens.toLocaleString()}</td>
                        <td className="py-2.5 text-right text-amber-400 font-mono">{w.google_requests}</td>
                        <td className="py-2.5 text-right text-purple-400 font-mono">{w.scan_jobs}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              renderEmptyState('No website activity records', 'Website activity records will populate with scan execution.')
            )}
          </div>
        </div>
      )}

      {/* ─── TAB 5: SYSTEM ERRORS & QUEUE HEALTH ─── */}
      {!loading && activeTab === 'reliability' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Platform Error Trend */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-black text-white tracking-tight">Platform Error Trend</h3>
                <p className="text-[11px] text-slate-400">API failures, scan faults, and provider timeouts</p>
              </div>
              <button
                onClick={() => handleExportCSV('platform_errors')}
                className="flex items-center gap-1 text-[11px] font-semibold text-purple-400 hover:text-purple-300 transition-colors"
              >
                <Download className="w-3 h-3" />
                CSV
              </button>
            </div>

            {ts.platform_error_trend && ts.platform_error_trend.some((r: any) => r.total_errors > 0) ? (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={ts.platform_error_trend}>
                    <defs>
                      <linearGradient id="errGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="label" stroke="#64748b" fontSize={10} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                    <Area type="monotone" dataKey="total_errors" name="Total Errors" stroke="#ef4444" fillOpacity={1} fill="url(#errGrad)" strokeWidth={2} />
                    <Line type="monotone" dataKey="api_errors" name="API Errors" stroke="#f59e0b" strokeWidth={1.5} dot={false} />
                    <Line type="monotone" dataKey="scan_failures" name="Scan Failures" stroke="#a855f7" strokeWidth={1.5} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              renderEmptyState('Zero platform errors', 'No system or provider errors logged in this time range. The platform is operating nominally.')
            )}

            <div className="flex justify-end pt-2 border-t border-slate-800/80">
              <Link to="/masterplace/alerts" className="text-xs font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1">
                View All System Alerts <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
          </div>

          {/* Alert Distribution Over Time */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
            <h3 className="text-sm font-black text-white tracking-tight">Security & Operational Alerts</h3>
            <p className="text-[11px] text-slate-400">Critical vs Warning vs Informational incident logs</p>

            {ts.alert_trend && ts.alert_trend.some((r: any) => r.total > 0) ? (
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={ts.alert_trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="label" stroke="#64748b" fontSize={10} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                    <Bar dataKey="critical" name="Critical" fill="#ef4444" stackId="alt" />
                    <Bar dataKey="warning" name="Warning" fill="#f59e0b" stackId="alt" />
                    <Bar dataKey="info" name="Informational" fill="#3b82f6" stackId="alt" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              renderEmptyState('No incident alerts logged', 'Platform incident alerts will appear here when administrative or security events occur.')
            )}

            <div className="flex justify-end pt-2 border-t border-slate-800/80">
              <Link to="/masterplace/audit" className="text-xs font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1">
                View Audit Log Stream <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

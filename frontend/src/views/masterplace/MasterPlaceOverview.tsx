import React, { useState, useEffect } from 'react';
import {
  Users,
  Globe,
  FolderGit2,
  Activity,
  AlertOctagon,
  AlertTriangle,
  Server,
  Database,
  Cpu,
  RefreshCw,
  XCircle,
  ExternalLink,
  CheckCircle2,
  Layers,
  Search
} from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../../api/client';
import { MasterPlaceAnalyticsSection } from '../../components/masterplace/MasterPlaceAnalyticsSection';

export const MasterPlaceOverview: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchOverview = async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      const res = await api.get('/masterplace/overview');
      setData(res.data);
      setError(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load MasterPlace overview telemetry');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchOverview();
    const interval = setInterval(() => fetchOverview(), 30000); // 30s live poll
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Loading Platform Telemetry...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-2xl bg-red-950/40 border border-red-500/30 text-red-300">
        <div className="flex items-center gap-2 font-bold text-sm">
          <AlertOctagon className="w-4 h-4 text-red-400" />
          <span>Telemetry Error</span>
        </div>
        <p className="text-xs mt-1 text-red-200/80">{error}</p>
        <button
          onClick={() => fetchOverview(true)}
          className="mt-4 px-4 py-1.5 rounded-lg bg-red-600/30 hover:bg-red-600/50 border border-red-500/40 text-xs font-semibold text-white transition-colors"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const kpis = data?.kpis || {};
  const health = data?.system_health || {};
  const activities = data?.activities || [];
  const alerts = data?.alerts || [];

  return (
    <div className="space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Platform Owner Command Center</h1>
          <p className="text-xs text-slate-400 mt-0.5">Authoritative real-time control plane across all LocalLift tenants, providers, and scan jobs.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-slate-400">
            Updated: {data?.updated_at ? new Date(data.updated_at).toLocaleTimeString() : 'Just now'}
          </span>
          <button
            onClick={() => fetchOverview(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Top-Level KPI Cards (Part 4) */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
        {/* Customers */}
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[10px] font-black uppercase tracking-wider">Customers</span>
            <Users className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-black text-white">{kpis.total_customers ?? 0}</div>
          <div className="text-[10px] text-slate-400 font-medium flex items-center justify-between">
            <span className="text-emerald-400 font-semibold">{kpis.active_customers ?? 0} Active</span>
            <span className="text-red-400 font-semibold">{kpis.suspended_customers ?? 0} Suspended</span>
          </div>
        </div>

        {/* Websites */}
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[10px] font-black uppercase tracking-wider">Websites</span>
            <Globe className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-black text-white">{kpis.total_websites ?? 0}</div>
          <div className="text-[10px] text-slate-400 font-medium">All tenant sites</div>
        </div>

        {/* Projects */}
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[10px] font-black uppercase tracking-wider">Projects</span>
            <FolderGit2 className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-black text-white">{kpis.total_projects ?? 0}</div>
          <div className="text-[10px] text-slate-400 font-medium">Client SEO containers</div>
        </div>

        {/* Active Jobs */}
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[10px] font-black uppercase tracking-wider">Active Jobs</span>
            <Activity className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-black text-amber-300">{kpis.active_jobs ?? 0}</div>
          <div className="text-[10px] text-slate-400 font-medium">Queued or running</div>
        </div>

        {/* Failed Today */}
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[10px] font-black uppercase tracking-wider">Failed Today</span>
            <AlertOctagon className="w-4 h-4 text-rose-400" />
          </div>
          <div className={`text-2xl font-black ${kpis.failed_today > 0 ? 'text-rose-400' : 'text-slate-200'}`}>
            {kpis.failed_today ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 font-medium">Scan cancellations/fails</div>
        </div>

        {/* API Errors */}
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[10px] font-black uppercase tracking-wider">API Errors</span>
            <AlertTriangle className="w-4 h-4 text-orange-400" />
          </div>
          <div className={`text-2xl font-black ${kpis.api_errors_today > 0 ? 'text-orange-400' : 'text-slate-200'}`}>
            {kpis.api_errors_today ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 font-medium">External providers today</div>
        </div>

        {/* System Health */}
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[10px] font-black uppercase tracking-wider">DB Latency</span>
            <Database className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-black text-emerald-400">{kpis.db_latency_ms ?? 0}<span className="text-xs ml-0.5 font-normal text-slate-400">ms</span></div>
          <div className="text-[10px] text-emerald-400/90 font-medium">DB Connection Active</div>
        </div>
      </div>

      {/* Platform Health Matrix & Alerts (Part 23, 25, 45) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* System Health Matrix */}
        <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-black uppercase tracking-wider text-slate-400">Platform Subsystems Health</h2>
            <Link to="/masterplace/health" className="text-[11px] font-bold text-purple-400 hover:text-purple-300">
              Details →
            </Link>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
              <div>
                <div className="text-[11px] font-semibold text-slate-400">Backend API</div>
                <div className="text-xs font-bold text-emerald-400 mt-0.5">Healthy ({health.backend?.latency_ms || 12}ms)</div>
              </div>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>

            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
              <div>
                <div className="text-[11px] font-semibold text-slate-400">Database Engine</div>
                <div className="text-xs font-bold text-emerald-400 mt-0.5">Healthy ({kpis.db_latency_ms || 0}ms)</div>
              </div>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>

            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
              <div>
                <div className="text-[11px] font-semibold text-slate-400">Scan Workers</div>
                <div className="text-xs font-bold text-emerald-400 mt-0.5">{health.workers?.status || 'HEALTHY'}</div>
              </div>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>

            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
              <div>
                <div className="text-[11px] font-semibold text-slate-400">AI Subsystem</div>
                <div className={`text-xs font-bold mt-0.5 ${kpis.global_ai_enabled ? 'text-emerald-400' : 'text-red-400'}`}>
                  {kpis.global_ai_enabled ? 'Enabled' : 'Kill Switch Active'}
                </div>
              </div>
              {kpis.global_ai_enabled ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <AlertOctagon className="w-4 h-4 text-red-400" />
              )}
            </div>
          </div>

          <div className="pt-2 text-[11px] text-slate-400 border-t border-slate-800/80 flex items-center justify-between">
            <span>Primary SERP Provider: <strong className="text-slate-200">SerpApi</strong></span>
            <span>Fallback: <strong className="text-slate-200">OpenSERP</strong></span>
          </div>
        </div>

        {/* Platform Alerts Center */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-xs font-black uppercase tracking-wider text-slate-400">Platform Alerts</h2>
              <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-slate-800 text-slate-300">
                {alerts.length} Active
              </span>
            </div>
            <Link to="/masterplace/alerts" className="text-[11px] font-bold text-purple-400 hover:text-purple-300">
              View All Alerts →
            </Link>
          </div>

          <div className="space-y-2.5 max-h-48 overflow-y-auto pr-1">
            {alerts.length === 0 ? (
              <div className="p-4 rounded-xl bg-slate-950 text-center text-xs text-slate-500">
                No active warnings or alerts. All platform subsystems within normal operating bounds.
              </div>
            ) : (
              alerts.map((alt: any) => {
                const isCrit = alt.severity === 'CRITICAL';
                const isWarn = alt.severity === 'WARNING';
                return (
                  <div
                    key={alt.id}
                    className={`p-3 rounded-xl border flex items-start gap-3 ${
                      isCrit
                        ? 'bg-red-950/40 border-red-500/40 text-red-200'
                        : isWarn
                        ? 'bg-amber-950/40 border-amber-500/40 text-amber-200'
                        : 'bg-slate-950 border-slate-800 text-slate-300'
                    }`}
                  >
                    {isCrit ? (
                      <AlertOctagon className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                    ) : isWarn ? (
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold">{alt.title}</span>
                        <span className="text-[10px] opacity-70">
                          {new Date(alt.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-[11px] mt-0.5 opacity-80 leading-relaxed">{alt.message}</p>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* ─── DEDICATED PLATFORM ANALYTICS LAYER (Charts, Graphs & Time-Series) ─── */}
      <MasterPlaceAnalyticsSection customers={data?.customers || []} />

      {/* Live Platform Activity Stream (Part 5) */}
      <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-black text-white tracking-tight">Recent Platform Activity</h2>
            <p className="text-xs text-slate-400 mt-0.5">Authoritative trace of scan jobs, AI consumption, Google integrations, and audit events across all tenants.</p>
          </div>
          <Link to="/masterplace/audit" className="text-xs font-bold text-purple-400 hover:text-purple-300">
            Audit Log →
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-bold uppercase text-[10px] tracking-wider">
                <th className="py-2.5 px-3">Timestamp</th>
                <th className="py-2.5 px-3">Tenant / Project</th>
                <th className="py-2.5 px-3">Event / Operation</th>
                <th className="py-2.5 px-3">Source / Provider</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {activities.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    No recent activity recorded in telemetry log.
                  </td>
                </tr>
              ) : (
                activities.map((act: any) => (
                  <tr key={act.id} className="hover:bg-slate-850/50 transition-colors">
                    <td className="py-3 px-3 text-slate-400 whitespace-nowrap">
                      {new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td className="py-3 px-3">
                      <div className="font-bold text-white">{act.customer}</div>
                      <div className="text-[10px] text-slate-400">{act.project}</div>
                    </td>
                    <td className="py-3 px-3 text-slate-200">{act.event}</td>
                    <td className="py-3 px-3 text-purple-300 font-semibold">{act.source}</td>
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-0.5 text-[10px] font-bold rounded-md uppercase tracking-wider ${
                          act.status === 'COMPLETED' || act.status === 'SUCCESS' || act.status === 'success'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : act.status === 'RUNNING' || act.status === 'QUEUED'
                            ? 'bg-amber-500/20 text-amber-300'
                            : 'bg-red-500/20 text-red-300'
                        }`}
                      >
                        {act.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-400 truncate max-w-xs">{act.details}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

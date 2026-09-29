import React, { useState, useEffect } from 'react';
import {
  Search,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  ArrowRight,
  TrendingUp,
  Sliders
} from 'lucide-react';
import api from '../../api/client';

export const MasterPlaceSERP: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchSERP = async () => {
    setLoading(true);
    try {
      const res = await api.get('/masterplace/serp');
      setData(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSERP();
  }, []);

  const providers = data?.providers || [];
  const routing = data?.routing || {};

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">SERP Providers Center</h1>
          <p className="text-xs text-slate-400 mt-0.5">Authoritative telemetry across all configured search ranking data providers, routing modes, and failure budgets.</p>
        </div>
        <button
          onClick={fetchSERP}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Provider Routing Banner (Part 15) */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-purple-950/40 via-indigo-950/40 to-slate-900 border border-purple-500/30 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-purple-400" />
            <h2 className="text-xs font-black uppercase tracking-wider text-purple-300">Active SERP Provider Routing Engine</h2>
          </div>
          <span className="px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wider rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
            {routing.status || 'OPERATIONAL'}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-6 pt-2 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-medium">Primary Provider:</span>
            <span className="px-3 py-1 rounded-lg bg-slate-900 border border-slate-700 text-white font-bold capitalize">
              {routing.primary || 'serpapi'}
            </span>
          </div>
          <ArrowRight className="w-4 h-4 text-slate-600 hidden sm:block" />
          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-medium">Fallback Provider:</span>
            <span className="px-3 py-1 rounded-lg bg-slate-900 border border-slate-700 text-purple-300 font-bold capitalize">
              {routing.fallback || 'openserp'}
            </span>
          </div>
          <div className="ml-auto text-[11px] text-slate-400">
            Mode: <strong className="text-white capitalize">{routing.mode?.replace('_', ' ') || 'Automatic Fallback'}</strong>
          </div>
        </div>
      </div>

      {/* Provider Telemetry Cards (Part 14) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {providers.map((p: any) => {
          const isHealthy = p.health === 'HEALTHY';
          return (
            <div key={p.provider} className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-white">{p.display_name}</h3>
                  <div className="text-[11px] text-slate-500 font-mono">provider_key: {p.provider}</div>
                </div>
                <span
                  className={`px-2.5 py-1 text-[10px] font-bold rounded-md uppercase tracking-wider ${
                    isHealthy
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : 'bg-amber-500/20 text-amber-300'
                  }`}
                >
                  {p.health}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-[10px] text-slate-400 font-semibold uppercase">Requests Today</div>
                  <div className="text-lg font-black text-white mt-1">{p.requests_today}</div>
                  <div className="text-[10px] text-slate-500">{p.units_today} search units</div>
                </div>
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-[10px] text-slate-400 font-semibold uppercase">Requests (Month)</div>
                  <div className="text-lg font-black text-white mt-1">{p.requests_this_month}</div>
                  <div className="text-[10px] text-slate-500">Est. ${p.cost_this_month}</div>
                </div>
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-[10px] text-slate-400 font-semibold uppercase">Success Rate</div>
                  <div className="text-lg font-black text-emerald-400 mt-1">{p.success_rate}%</div>
                  <div className="text-[10px] text-slate-500">{p.failed_this_month} failures</div>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                <span>Avg Latency: <strong className="text-slate-200">{p.average_response_time}</strong></span>
                <span>Telemetry: <strong className="text-emerald-400">Authoritative Database</strong></span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

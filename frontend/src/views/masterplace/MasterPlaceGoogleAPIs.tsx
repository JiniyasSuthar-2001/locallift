import React, { useState, useEffect } from 'react';
import {
  Layers,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  ShieldCheck,
  RefreshCw,
  Search,
  Key
} from 'lucide-react';
import api from '../../api/client';

export const MasterPlaceGoogleAPIs: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchGoogle = async () => {
    setLoading(true);
    try {
      const res = await api.get('/masterplace/google');
      setData(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGoogle();
  }, []);

  const services = data?.services || [];
  const connections = data?.connections || [];
  const recentErrors = data?.recent_errors || [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Google APIs Control Center</h1>
          <p className="text-xs text-slate-400 mt-0.5">Authoritative monitoring for all platform Google integrations: GBP, Search Console, GA4, Ads, and Places API.</p>
        </div>
        <button
          onClick={fetchGoogle}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Service Cards (Part 10, 11) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {services.map((s: any) => {
          const isHealthy = s.status === 'HEALTHY';
          return (
            <div key={s.service} className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">
                  {s.service.replace('_', ' ')}
                </span>
                <span
                  className={`px-2 py-0.5 text-[9px] font-bold rounded-md uppercase tracking-wider ${
                    isHealthy
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : 'bg-amber-500/20 text-amber-300'
                  }`}
                >
                  {s.status}
                </span>
              </div>

              <div>
                <div className="text-xl font-black text-white">{s.requests_today}</div>
                <div className="text-[10px] text-slate-400">Requests Today</div>
              </div>

              <div className="pt-2 border-t border-slate-800/80 text-[10px] text-slate-400 space-y-1">
                <div className="flex justify-between">
                  <span>Accounts Linked:</span>
                  <span className="text-white font-semibold">{s.connected_accounts}</span>
                </div>
                <div className="flex justify-between">
                  <span>Errors / Expired:</span>
                  <span className={s.error_accounts > 0 ? 'text-rose-400 font-bold' : 'text-slate-300'}>
                    {s.error_accounts}
                  </span>
                </div>
                <div className="text-[9px] text-purple-400/80 mt-1 font-medium">{s.quota_metric}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Connection & Credential Status Table (Part 12, 34 - Operational Metadata ONLY, No Secrets!) */}
      <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-black text-white tracking-tight">Connected Accounts & OAuth Health</h2>
            <p className="text-xs text-slate-400 mt-0.5">Authoritative token expiration and sync telemetry. Raw access tokens, client secrets, and refresh keys are strictly redacted.</p>
          </div>
          <span className="text-xs font-semibold text-slate-400">{connections.length} Accounts</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-bold uppercase text-[10px] tracking-wider">
                <th className="py-2.5 px-3">Service</th>
                <th className="py-2.5 px-3">Organization</th>
                <th className="py-2.5 px-3">Account Email</th>
                <th className="py-2.5 px-3">Credential State</th>
                <th className="py-2.5 px-3">Token Status</th>
                <th className="py-2.5 px-3">Last Sync</th>
                <th className="py-2.5 px-3">Sync Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    Loading Google connections...
                  </td>
                </tr>
              ) : connections.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    No active Google connections configured in database.
                  </td>
                </tr>
              ) : (
                connections.map((c: any) => (
                  <tr key={c.id} className="hover:bg-slate-850/50 transition-colors">
                    <td className="py-3 px-3 font-bold text-white capitalize">{c.service.replace('_', ' ')}</td>
                    <td className="py-3 px-3 text-slate-300">{c.organization_name}</td>
                    <td className="py-3 px-3 text-purple-300 font-medium">{c.account_email}</td>
                    <td className="py-3 px-3">
                      <span className="flex items-center gap-1.5 text-[11px] text-emerald-400 font-semibold">
                        <Key className="w-3.5 h-3.5" />
                        Configured ✓
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-0.5 text-[10px] font-bold rounded-md uppercase tracking-wider ${
                          c.status === 'connected'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : 'bg-red-500/20 text-red-300'
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-400 whitespace-nowrap">
                      {c.last_sync_at ? new Date(c.last_sync_at).toLocaleString() : 'Never'}
                    </td>
                    <td className="py-3 px-3 text-rose-400 truncate max-w-xs">{c.sync_error || 'None'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Google API Error Center (Part 13) */}
      <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4">
        <div>
          <h2 className="text-sm font-black text-white tracking-tight">Google API Error Center</h2>
          <p className="text-xs text-slate-400 mt-0.5">Isolated log of Google API synchronization, authentication, and permission failures.</p>
        </div>

        <div className="space-y-2">
          {recentErrors.length === 0 ? (
            <div className="p-4 rounded-xl bg-slate-950 text-xs text-slate-500 text-center">
              No recent Google API errors recorded.
            </div>
          ) : (
            recentErrors.map((err: any) => (
              <div key={err.id} className="p-3 rounded-xl bg-slate-950 border border-red-500/30 flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-white capitalize">{err.service.replace('_', ' ')}</span>
                    <span className="text-[11px] text-slate-400">({err.account_email})</span>
                  </div>
                  <p className="text-[11px] text-red-300 mt-1">{err.error}</p>
                </div>
                <span className="text-[10px] text-slate-500 whitespace-nowrap">
                  {err.timestamp ? new Date(err.timestamp).toLocaleTimeString() : ''}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

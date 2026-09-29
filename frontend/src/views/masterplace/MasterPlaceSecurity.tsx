import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  Lock,
  AlertTriangle,
  RefreshCw,
  UserX
} from 'lucide-react';
import api from '../../api/client';

export const MasterPlaceSecurity: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchSecurity = async () => {
    setLoading(true);
    try {
      const res = await api.get('/masterplace/overview');
      setData(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSecurity();
  }, []);

  const kpis = data?.kpis || {};

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Platform Security Center</h1>
          <p className="text-xs text-slate-400 mt-0.5">Real-time surveillance of credential integrity, unauthorized access attempts, and tenant boundaries.</p>
        </div>
        <button
          onClick={fetchSecurity}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Security Telemetry Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">Suspended Customers</span>
            <UserX className="w-4 h-4 text-red-400" />
          </div>
          <div className="text-2xl font-black text-white">{kpis.suspended_customers || 0}</div>
          <p className="text-[11px] text-slate-400">Suspended organizations blocked from initiating billable scans.</p>
        </div>

        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">Credential Secret Protection</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-black text-emerald-400">100% Enforced</div>
          <p className="text-[11px] text-slate-400">Raw OAuth secrets, API keys, and auth hashes are redacted across all APIs.</p>
        </div>

        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">MasterPlace Guard</span>
            <Lock className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-black text-purple-300">Backend Verified</div>
          <p className="text-[11px] text-slate-400">All /masterplace/* routes require verified platform operator roles.</p>
        </div>
      </div>

      {/* Security Policies */}
      <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4">
        <h2 className="text-sm font-black text-white tracking-tight">Active Platform Defense Policies</h2>
        <div className="space-y-3 text-xs">
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-start gap-3">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-bold text-white">Strict Tenant Isolation</div>
              <div className="text-slate-400 text-[11px] mt-0.5">
                Every customer dashboard request validates organization and project ownership via SQL joins. Cross-tenant leakage is architecturally prohibited.
              </div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-start gap-3">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-bold text-white">Rate-Limiting on Authentication</div>
              <div className="text-slate-400 text-[11px] mt-0.5">
                Auth endpoints (/auth/login, /auth/register) enforce per-IP and per-account cooldowns to defeat brute force attacks.
              </div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-start gap-3">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-bold text-white">Emergency Kill Switch Guard</div>
              <div className="text-slate-400 text-[11px] mt-0.5">
                The global AI kill switch disables inference instantly across all API entrypoints with mandatory operator audit confirmation.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

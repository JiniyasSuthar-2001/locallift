import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Power,
  AlertOctagon,
  CheckCircle2,
  RefreshCw,
  Coins,
  Flame,
  Layers,
  Users
} from 'lucide-react';
import api from '../../api/client';

export const MasterPlaceAI: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [togglingKillSwitch, setTogglingKillSwitch] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [killReason, setKillReason] = useState('');

  const fetchAI = async () => {
    setLoading(true);
    try {
      const res = await api.get('/masterplace/ai');
      setData(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAI();
  }, []);

  const handleToggleKillSwitch = async () => {
    if (!data) return;
    const targetState = !data.global_ai_enabled;

    setTogglingKillSwitch(true);
    try {
      await api.post('/masterplace/ai/kill-switch', {
        enabled: targetState,
        reason: killReason || `Platform operator manual toggle from MasterPlace AI Center`
      });
      setShowConfirmModal(false);
      setKillReason('');
      await fetchAI();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to toggle Global AI Kill Switch');
    } finally {
      setTogglingKillSwitch(false);
    }
  };

  const metrics = data?.metrics || {};
  const providers = data?.providers || [];
  const features = data?.features || [];
  const topConsumers = data?.top_consumers || [];
  const globalEnabled = data?.global_ai_enabled;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">AI Provider Control Center</h1>
          <p className="text-xs text-slate-400 mt-0.5">Authoritative token consumption telemetry, multi-provider operations, and emergency Global Kill Switch.</p>
        </div>
        <button
          onClick={fetchAI}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Global AI Kill Switch Protected Banner (Part 19) */}
      <div
        className={`p-6 rounded-2xl border flex flex-col md:flex-row md:items-center justify-between gap-6 transition-all ${
          globalEnabled
            ? 'bg-slate-900/90 border-slate-800'
            : 'bg-red-950/40 border-red-500/50 shadow-2xl shadow-red-500/10'
        }`}
      >
        <div className="space-y-1 max-w-xl">
          <div className="flex items-center gap-2">
            <Power className={`w-5 h-5 ${globalEnabled ? 'text-emerald-400' : 'text-red-400 animate-pulse'}`} />
            <h2 className="text-sm font-black uppercase tracking-wider text-white">
              GLOBAL AI KILL SWITCH: {globalEnabled ? (
                <span className="text-emerald-400 font-black">ENABLED (NORMAL OPERATIONS)</span>
              ) : (
                <span className="text-red-400 font-black">ACTIVE (ALL AI DISABLED)</span>
              )}
            </h2>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            In emergencies (uncontrolled runaway costs, upstream provider compromise, or outages), this switch halts all AI generation across the entire platform. Backend-enforced on all customer endpoints.
          </p>
        </div>

        <button
          onClick={() => setShowConfirmModal(true)}
          className={`px-5 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider shadow-lg transition-all ${
            globalEnabled
              ? 'bg-red-600 hover:bg-red-500 text-white shadow-red-600/30'
              : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/30'
          }`}
        >
          {globalEnabled ? 'Engage Global Kill Switch' : 'Deactivate Kill Switch & Resume'}
        </button>
      </div>

      {/* Platform Token Metrics (Part 17) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-2">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">Total Tokens</span>
          <div className="text-2xl font-black text-white">{metrics.total_tokens?.toLocaleString() || 0}</div>
          <div className="text-[10px] text-slate-500">All historical tenant usage</div>
        </div>
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-2">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">Tokens Today</span>
          <div className="text-2xl font-black text-purple-300">{metrics.today_tokens?.toLocaleString() || 0}</div>
          <div className="text-[10px] text-slate-500">{metrics.today_requests || 0} generation calls</div>
        </div>
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-2">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">Input / Output Ratio</span>
          <div className="text-base font-bold text-slate-200 mt-1">
            {metrics.input_tokens?.toLocaleString() || 0} in / {metrics.output_tokens?.toLocaleString() || 0} out
          </div>
          <div className="text-[10px] text-slate-500">Prompt vs Completion</div>
        </div>
        <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-2">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">Estimated Cost</span>
          <div className="text-2xl font-black text-emerald-400">${metrics.estimated_cost || '0.00'}</div>
          <div className="text-[10px] text-slate-500">Today: ${metrics.today_cost || '0.00'}</div>
        </div>
      </div>

      {/* Provider Matrix & Features */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Providers */}
        <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4">
          <h2 className="text-xs font-black uppercase tracking-wider text-slate-400">Configured AI Providers</h2>
          <div className="space-y-3">
            {providers.length === 0 ? (
              <div className="p-4 rounded-xl bg-slate-950 text-xs text-slate-500 text-center">
                No AI provider logs recorded in system.
              </div>
            ) : (
              providers.map((p: any) => (
                <div key={p.provider} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                  <div>
                    <div className="font-bold text-xs text-white uppercase">{p.provider}</div>
                    <div className="text-[11px] text-slate-400">{p.requests} calls · {p.total_tokens.toLocaleString()} tokens</div>
                  </div>
                  <div className="text-right">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${p.status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'}`}>
                      {p.status}
                    </span>
                    <div className="text-[10px] text-slate-500 mt-1">Est. ${p.estimated_cost}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Feature Breakdown */}
        <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4">
          <h2 className="text-xs font-black uppercase tracking-wider text-slate-400">Usage By AI Feature</h2>
          <div className="space-y-3">
            {features.length === 0 ? (
              <div className="p-4 rounded-xl bg-slate-950 text-xs text-slate-500 text-center">
                No feature consumption recorded.
              </div>
            ) : (
              features.map((f: any) => (
                <div key={f.feature} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs">
                  <div>
                    <div className="font-bold text-white capitalize">{f.feature.replace('_', ' ')}</div>
                    <div className="text-[10px] text-slate-400">{f.requests} requests generated</div>
                  </div>
                  <div className="font-mono text-purple-300 font-bold">{f.total_tokens.toLocaleString()} tokens</div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Top AI Consumers Ranking (Part 17) */}
      <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4">
        <div>
          <h2 className="text-sm font-black text-white tracking-tight">Top AI Token Consumers (Tenants)</h2>
          <p className="text-xs text-slate-400 mt-0.5">Who is consuming platform AI tokens? Ranked by measurable token volume.</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-bold uppercase text-[10px] tracking-wider">
                <th className="py-2.5 px-3">Organization</th>
                <th className="py-2.5 px-3">Requests</th>
                <th className="py-2.5 px-3">Tokens Consumed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {topConsumers.length === 0 ? (
                <tr>
                  <td colSpan={3} className="py-6 text-center text-slate-500">
                    No token usage recorded for any organization.
                  </td>
                </tr>
              ) : (
                topConsumers.map((c: any) => (
                  <tr key={c.organization_id} className="hover:bg-slate-850/50 transition-colors">
                    <td className="py-3 px-3">
                      <div className="font-bold text-white">{c.organization_name}</div>
                      <div className="text-[10px] text-slate-500">Org ID #{c.organization_id}</div>
                    </td>
                    <td className="py-3 px-3 text-slate-300">{c.requests}</td>
                    <td className="py-3 px-3 text-purple-300 font-bold font-mono">{c.total_tokens.toLocaleString()}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Confirmation Modal for Kill Switch */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-red-500/40 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-red-400">
              <AlertOctagon className="w-6 h-6" />
              <h3 className="text-base font-black text-white">Confirm Global AI Status Change</h3>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              You are about to {globalEnabled ? 'SUSPEND' : 'RESUME'} all AI operations across every tenant in the platform. This action is recorded in the platform audit log.
            </p>
            <div>
              <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                Reason / Ticket Reference:
              </label>
              <input
                type="text"
                placeholder="e.g. Upstream latency surge or maintenance"
                value={killReason}
                onChange={(e) => setKillReason(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-red-500"
              />
            </div>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setShowConfirmModal(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white"
              >
                Cancel
              </button>
              <button
                disabled={togglingKillSwitch}
                onClick={handleToggleKillSwitch}
                className={`px-4 py-2 rounded-xl text-xs font-black text-white uppercase tracking-wider ${
                  globalEnabled ? 'bg-red-600 hover:bg-red-500' : 'bg-emerald-600 hover:bg-emerald-500'
                }`}
              >
                {togglingKillSwitch ? 'Updating...' : 'Confirm Action'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

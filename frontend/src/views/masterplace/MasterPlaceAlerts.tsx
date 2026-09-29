import React, { useState, useEffect } from 'react';
import {
  Bell,
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  RefreshCw
} from 'lucide-react';
import api from '../../api/client';

export const MasterPlaceAlerts: React.FC = () => {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const res = await api.get('/masterplace/overview');
      setAlerts(res.data.alerts || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Platform Alert Center</h1>
          <p className="text-xs text-slate-400 mt-0.5">Automated telemetry alerts generated strictly from measurable platform conditions and failure budgets.</p>
        </div>
        <button
          onClick={fetchAlerts}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Alerts List */}
      <div className="space-y-3">
        {loading ? (
          <div className="py-12 text-center text-xs text-slate-500">Evaluating platform health conditions...</div>
        ) : alerts.length === 0 ? (
          <div className="p-8 rounded-2xl bg-slate-900/60 border border-slate-800 text-center space-y-2">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
            <h3 className="text-sm font-bold text-white">All Platform Systems Normal</h3>
            <p className="text-xs text-slate-400">Zero active alerts. No quota warnings or provider failures detected.</p>
          </div>
        ) : (
          alerts.map((alt) => {
            const isCrit = alt.severity === 'CRITICAL';
            const isWarn = alt.severity === 'WARNING';
            return (
              <div
                key={alt.id}
                className={`p-4 rounded-2xl border flex items-start gap-4 ${
                  isCrit
                    ? 'bg-red-950/40 border-red-500/40 text-red-200'
                    : isWarn
                    ? 'bg-amber-950/40 border-amber-500/40 text-amber-200'
                    : 'bg-slate-900/80 border-slate-800 text-slate-300'
                }`}
              >
                {isCrit ? (
                  <AlertOctagon className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                ) : isWarn ? (
                  <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                ) : (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-sm font-bold text-white">{alt.title}</span>
                    <span className="text-[10px] uppercase font-black px-2 py-0.5 rounded bg-slate-950/80 border border-slate-800">
                      {alt.severity}
                    </span>
                  </div>
                  <p className="text-xs mt-1 opacity-80 leading-relaxed">{alt.message}</p>
                  <div className="text-[10px] opacity-60 mt-2">
                    Detected: {new Date(alt.timestamp).toLocaleString()}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

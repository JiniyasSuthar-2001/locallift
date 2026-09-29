import React, { useState, useEffect } from 'react';
import {
  Settings,
  Save,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Sliders,
  ShieldAlert
} from 'lucide-react';
import api from '../../api/client';

export const MasterPlaceSettings: React.FC = () => {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const res = await api.get('/masterplace/settings');
      setSettings(res.data.settings || {});
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleUpdate = async (key: string, value: string) => {
    setSavingKey(key);
    try {
      await api.post('/masterplace/settings', {
        key,
        value,
        reason: 'Platform operator updated via MasterPlace settings'
      });
      setSettings((prev) => ({ ...prev, [key]: value }));
      setFeedback(`Setting "${key}" updated successfully.`);
      setTimeout(() => setFeedback(null), 3000);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to update setting');
    } finally {
      setSavingKey(null);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Platform Settings & Configuration</h1>
          <p className="text-xs text-slate-400 mt-0.5">Authoritative control parameters for routing, default timeouts, and systemic guards.</p>
        </div>
        <button
          onClick={fetchSettings}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {feedback && (
        <div className="p-3 rounded-xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {/* Settings Grid */}
      <div className="space-y-6">
        {/* SERP Provider Configuration */}
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
          <h2 className="text-xs font-black uppercase tracking-wider text-slate-400">SERP Provider Routing</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-white">Primary SERP Provider</label>
              <select
                value={settings.serp_primary_provider || 'serpapi'}
                onChange={(e) => handleUpdate('serp_primary_provider', e.target.value)}
                disabled={savingKey === 'serp_primary_provider'}
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-purple-500"
              >
                <option value="serpapi">SerpApi (Google Engine)</option>
                <option value="openserp">OpenSERP Direct</option>
              </select>
              <p className="text-[11px] text-slate-500">First-line provider for keyword ranking and Geo-Grid scans.</p>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-white">Fallback SERP Provider</label>
              <select
                value={settings.serp_fallback_provider || 'openserp'}
                onChange={(e) => handleUpdate('serp_fallback_provider', e.target.value)}
                disabled={savingKey === 'serp_fallback_provider'}
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-purple-500"
              >
                <option value="openserp">OpenSERP Direct</option>
                <option value="serpapi">SerpApi (Google Engine)</option>
              </select>
              <p className="text-[11px] text-slate-500">Engaged automatically if primary encounters repeated 429s or timeouts.</p>
            </div>
          </div>
        </div>

        {/* Scan Timeouts */}
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
          <h2 className="text-xs font-black uppercase tracking-wider text-slate-400">Worker Execution Limits</h2>
          <div className="max-w-md space-y-1.5">
            <label className="text-xs font-bold text-white">Default Scan Timeout (Seconds)</label>
            <div className="flex gap-2">
              <input
                type="number"
                value={settings.default_scan_timeout_seconds || '300'}
                onChange={(e) => setSettings({ ...settings, default_scan_timeout_seconds: e.target.value })}
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-purple-500"
              />
              <button
                onClick={() => handleUpdate('default_scan_timeout_seconds', settings.default_scan_timeout_seconds)}
                disabled={savingKey === 'default_scan_timeout_seconds'}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-bold text-white"
              >
                Save
              </button>
            </div>
            <p className="text-[11px] text-slate-500">Maximum execution window before background worker flags expired scan.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

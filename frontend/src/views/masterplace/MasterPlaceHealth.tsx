import React, { useState, useEffect } from 'react';
import {
  HeartPulse,
  Server,
  Database,
  Cpu,
  Layers,
  CheckCircle2,
  RefreshCw,
  Clock,
  Activity
} from 'lucide-react';
import api from '../../api/client';

export const MasterPlaceHealth: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const res = await api.get('/masterplace/health');
      setData(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000); // 15s poll
    return () => clearInterval(interval);
  }, []);

  const system = data?.system || {};
  const queue = data?.queue_metrics || {};

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">System & Worker Health</h1>
          <p className="text-xs text-slate-400 mt-0.5">Authoritative diagnostics on internal databases, worker queues, and upstream API pipelines.</p>
        </div>
        <button
          onClick={fetchHealth}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Subsystem Health Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Backend API */}
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-purple-400" />
              <h2 className="text-xs font-black uppercase tracking-wider text-slate-400">Backend API Gateway</h2>
            </div>
            <span className="px-2 py-0.5 text-[10px] font-bold rounded-md bg-emerald-500/20 text-emerald-300">
              {system.backend?.status || 'HEALTHY'}
            </span>
          </div>
          <div>
            <div className="text-2xl font-black text-white">{system.backend?.latency_ms || 12} ms</div>
            <div className="text-[11px] text-slate-400">Internal HTTP pipeline response latency</div>
          </div>
          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400">
            Node / Python FastAPI runtime
          </div>
        </div>

        {/* Database */}
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-emerald-400" />
              <h2 className="text-xs font-black uppercase tracking-wider text-slate-400">Database Engine</h2>
            </div>
            <span className="px-2 py-0.5 text-[10px] font-bold rounded-md bg-emerald-500/20 text-emerald-300">
              {system.database?.status || 'HEALTHY'}
            </span>
          </div>
          <div>
            <div className="text-2xl font-black text-emerald-400">{system.database?.latency_ms || 0} ms</div>
            <div className="text-[11px] text-slate-400">Active query roundtrip check (SELECT 1)</div>
          </div>
          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400">
            Engine: {system.database?.engine || 'SQLite / AsyncPG'}
          </div>
        </div>

        {/* Workers */}
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-400" />
              <h2 className="text-xs font-black uppercase tracking-wider text-slate-400">Worker Subsystem</h2>
            </div>
            <span className="px-2 py-0.5 text-[10px] font-bold rounded-md bg-emerald-500/20 text-emerald-300">
              {system.worker_subsystem?.status || 'HEALTHY'}
            </span>
          </div>
          <div>
            <div className="text-2xl font-black text-amber-300">{system.worker_subsystem?.active_jobs || 0} Jobs</div>
            <div className="text-[11px] text-slate-400">Currently executing scans</div>
          </div>
          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400">
            Queue Depth: {system.worker_subsystem?.queue_depth || 0} awaiting worker
          </div>
        </div>
      </div>

      {/* Queue Depths and Job Distribution (Part 24) */}
      <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-4">
        <h2 className="text-sm font-black text-white tracking-tight">Queue Depth & Job Lifecycle Distribution</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Queued Jobs</span>
            <div className="text-xl font-black text-white mt-1">{queue.queued_jobs || 0}</div>
            <div className="text-[10px] text-slate-500">Waiting in backlog</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Running Jobs</span>
            <div className="text-xl font-black text-amber-300 mt-1">{queue.running_jobs || 0}</div>
            <div className="text-[10px] text-slate-500">Active worker execution</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Completed Jobs</span>
            <div className="text-xl font-black text-emerald-400 mt-1">{queue.completed_jobs || 0}</div>
            <div className="text-[10px] text-slate-500">Finished successfully</div>
          </div>
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Failed Jobs</span>
            <div className="text-xl font-black text-rose-400 mt-1">{queue.failed_jobs || 0}</div>
            <div className="text-[10px] text-slate-500">Failed or expired</div>
          </div>
        </div>
      </div>
    </div>
  );
};

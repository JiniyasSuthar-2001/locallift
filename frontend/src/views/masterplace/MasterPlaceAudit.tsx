import React, { useState, useEffect } from 'react';
import {
  FileText,
  Search,
  Filter,
  RefreshCw,
  ShieldCheck,
  CheckCircle2
} from 'lucide-react';
import api from '../../api/client';

export const MasterPlaceAudit: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchAudit = async () => {
    setLoading(true);
    try {
      const res = await api.get('/masterplace/audit', {
        params: {
          page,
          page_size: 30,
          action: actionFilter || undefined
        }
      });
      setLogs(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAudit();
  }, [page, actionFilter]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Platform Audit Log</h1>
          <p className="text-xs text-slate-400 mt-0.5">Immutable record of administrative actions, customer suspensions, AI kill switch events, and security adjustments.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-slate-400">Total Entries: <strong className="text-white">{total}</strong></span>
          <button
            onClick={fetchAudit}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3">
        <Filter className="w-3.5 h-3.5 text-slate-400" />
        <span className="text-xs text-slate-400 font-medium">Filter Action:</span>
        <select
          value={actionFilter}
          onChange={(e) => {
            setActionFilter(e.target.value);
            setPage(1);
          }}
          className="px-3 py-1.5 text-xs rounded-xl bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500"
        >
          <option value="">All Actions</option>
          <option value="CUSTOMER_STATUS_CHANGED">Customer Status Changed</option>
          <option value="GLOBAL_AI_KILL_SWITCH">Global AI Kill Switch</option>
          <option value="JOB_CANCELLED">Job Cancelled</option>
          <option value="SETTING_UPDATED">Setting Updated</option>
        </select>
      </div>

      {/* Audit Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-bold uppercase text-[10px] tracking-wider bg-slate-950/50">
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Actor</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Target Type</th>
                <th className="py-3 px-4">Details</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">IP Address</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    Loading audit trail...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    No audit records found.
                  </td>
                </tr>
              ) : (
                logs.map((l) => (
                  <tr key={l.id} className="hover:bg-slate-850/50 transition-colors">
                    <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                      {new Date(l.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-bold text-white">{l.actor_email}</td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-purple-300 font-semibold">{l.action}</span>
                    </td>
                    <td className="py-3 px-4 text-slate-300 capitalize">{l.target_type || 'System'}</td>
                    <td className="py-3 px-4 text-slate-400 truncate max-w-sm">{l.details}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 text-[9px] font-bold rounded uppercase tracking-wider bg-emerald-500/20 text-emerald-300">
                        {l.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500 font-mono text-[10px]">{l.ip_address || 'Internal'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 30 && (
          <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <div>Showing page {page} of {Math.ceil(total / 30)}</div>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="px-3 py-1 rounded-lg bg-slate-800 disabled:opacity-40 hover:bg-slate-700 text-white font-semibold"
              >
                Previous
              </button>
              <button
                disabled={page >= Math.ceil(total / 30)}
                onClick={() => setPage(page + 1)}
                className="px-3 py-1 rounded-lg bg-slate-800 disabled:opacity-40 hover:bg-slate-700 text-white font-semibold"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

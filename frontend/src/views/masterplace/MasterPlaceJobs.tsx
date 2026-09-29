import React, { useState, useEffect } from 'react';
import {
  Activity,
  Filter,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  RefreshCw,
  StopCircle,
  AlertOctagon,
  ChevronRight,
  X
} from 'lucide-react';
import api from '../../api/client';

export const MasterPlaceJobs: React.FC = () => {
  const [jobs, setJobs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<any>(null);
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const res = await api.get('/masterplace/jobs', {
        params: {
          page,
          page_size: 25,
          status_filter: statusFilter || undefined,
          job_type: typeFilter || undefined
        }
      });
      setJobs(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, [page, statusFilter, typeFilter]);

  const handleCancelJob = async (jobId: number) => {
    if (!window.confirm(`Are you sure you want to cancel Job #${jobId}?`)) return;

    setCancellingId(jobId);
    try {
      await api.post(`/masterplace/jobs/${jobId}/cancel`);
      await fetchJobs();
      if (selectedJob?.id === jobId) {
        setSelectedJob((prev: any) => ({ ...prev, status: 'CANCEL_REQUESTED' }));
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to cancel job');
    } finally {
      setCancellingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Scan Jobs Center</h1>
          <p className="text-xs text-slate-400 mt-0.5">Authoritative platform registry of all asynchronous background operations, worker execution states, and cancellations.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-slate-400">Total: <strong className="text-white">{total}</strong></span>
          <button
            onClick={() => fetchJobs()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Filter className="w-3.5 h-3.5" />
          <span>Filter Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 text-xs rounded-xl bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500"
          >
            <option value="">All Statuses</option>
            <option value="RUNNING">Running</option>
            <option value="QUEUED">Queued</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
            <option value="CANCEL_REQUESTED">Cancel Requested</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span>Job Type:</span>
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 text-xs rounded-xl bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500"
          >
            <option value="">All Types</option>
            <option value="keyword_rank">Keyword Rank</option>
            <option value="geo_grid">Geo-Grid</option>
            <option value="citation_discovery">Citation Discovery</option>
            <option value="website_audit">Website Audit</option>
            <option value="intelligence_scan">Intelligence Scan</option>
          </select>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-bold uppercase text-[10px] tracking-wider bg-slate-950/50">
                <th className="py-3 px-4">Job ID / Type</th>
                <th className="py-3 px-4">Customer Org</th>
                <th className="py-3 px-4">Project</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Progress</th>
                <th className="py-3 px-4">Items (Processed)</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-4">Provider</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {loading ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500">
                    Loading platform scan jobs...
                  </td>
                </tr>
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500">
                    No scan jobs found matching current filters.
                  </td>
                </tr>
              ) : (
                jobs.map((j) => {
                  const isRunning = j.status === 'RUNNING' || j.status === 'QUEUED';
                  return (
                    <tr
                      key={j.id}
                      onClick={() => setSelectedJob(j)}
                      className="hover:bg-slate-850/50 cursor-pointer transition-colors"
                    >
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-white flex items-center gap-1.5">
                          <span>Job #{j.id}</span>
                          <span className="text-purple-400 capitalize">({j.job_type.replace('_', ' ')})</span>
                        </div>
                        <div className="text-[10px] text-slate-500 truncate max-w-xs">{j.current_stage}</div>
                      </td>
                      <td className="py-3.5 px-4 text-slate-200">{j.organization_name}</td>
                      <td className="py-3.5 px-4 text-slate-300">{j.project_name}</td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`px-2 py-0.5 text-[10px] font-bold rounded-md uppercase tracking-wider ${
                            j.status === 'COMPLETED'
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : j.status === 'RUNNING'
                              ? 'bg-amber-500/20 text-amber-300 animate-pulse'
                              : j.status === 'CANCEL_REQUESTED'
                              ? 'bg-orange-500/20 text-orange-300'
                              : j.status === 'CANCELLED'
                              ? 'bg-slate-700/50 text-slate-400'
                              : 'bg-red-500/20 text-red-300'
                          }`}
                        >
                          {j.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="w-20 bg-slate-800 h-2 rounded-full overflow-hidden">
                          <div
                            className="bg-purple-500 h-full rounded-full transition-all"
                            style={{ width: `${Math.min(100, Math.max(0, j.progress_pct || 0))}%` }}
                          />
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5">{Math.round(j.progress_pct || 0)}%</div>
                      </td>
                      <td className="py-3.5 px-4 text-slate-300 font-mono">
                        {j.processed_items} / {j.total_items}
                      </td>
                      <td className="py-3.5 px-4 text-slate-400">
                        {j.duration_seconds !== null ? `${j.duration_seconds}s` : 'In progress'}
                      </td>
                      <td className="py-3.5 px-4 text-slate-300 capitalize">{j.provider || 'Local worker'}</td>
                      <td className="py-3.5 px-4 text-right">
                        {isRunning && (
                          <button
                            disabled={cancellingId === j.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCancelJob(j.id);
                            }}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-600/20 hover:bg-red-600/40 border border-red-500/30 text-red-300 text-[11px] font-semibold transition-colors"
                          >
                            <StopCircle className="w-3.5 h-3.5" />
                            {cancellingId === j.id ? 'Cancelling...' : 'Cancel'}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 25 && (
          <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <div>Showing page {page} of {Math.ceil(total / 25)}</div>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="px-3 py-1 rounded-lg bg-slate-800 disabled:opacity-40 hover:bg-slate-700 text-white font-semibold"
              >
                Previous
              </button>
              <button
                disabled={page >= Math.ceil(total / 25)}
                onClick={() => setPage(page + 1)}
                className="px-3 py-1 rounded-lg bg-slate-800 disabled:opacity-40 hover:bg-slate-700 text-white font-semibold"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Job Details Modal (Part 21) */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">Job #{selectedJob.id} Details</h3>
                <div className="text-xs text-slate-400 capitalize">{selectedJob.job_type.replace('_', ' ')} Scan</div>
              </div>
              <button
                onClick={() => setSelectedJob(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-slate-400 block text-[10px] uppercase font-bold">Status</span>
                <span className="font-bold text-white">{selectedJob.status}</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-slate-400 block text-[10px] uppercase font-bold">Provider</span>
                <span className="font-bold text-white capitalize">{selectedJob.provider || 'Internal Worker'}</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-slate-400 block text-[10px] uppercase font-bold">Items</span>
                <span className="font-bold text-white">{selectedJob.processed_items} / {selectedJob.total_items} items</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                <span className="text-slate-400 block text-[10px] uppercase font-bold">Duration</span>
                <span className="font-bold text-white">{selectedJob.duration_seconds !== null ? `${selectedJob.duration_seconds}s` : 'Running'}</span>
              </div>
            </div>

            {selectedJob.error_message && (
              <div className="p-3 rounded-xl bg-red-950/40 border border-red-500/30 text-xs">
                <span className="font-bold text-red-300 block mb-1">Execution Error:</span>
                <span className="text-red-200/90">{selectedJob.error_message}</span>
              </div>
            )}

            <div className="flex justify-end gap-3 pt-3">
              {(selectedJob.status === 'RUNNING' || selectedJob.status === 'QUEUED') && (
                <button
                  onClick={() => handleCancelJob(selectedJob.id)}
                  className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-xs font-bold text-white"
                >
                  Cancel Job
                </button>
              )}
              <button
                onClick={() => setSelectedJob(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

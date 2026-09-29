import React, { useState, useEffect } from 'react';
import {
  Users,
  Search,
  Filter,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ExternalLink,
  ChevronRight,
  ShieldAlert,
  ShieldCheck,
  FolderGit2,
  Globe,
  Cpu,
  RefreshCw,
  X
} from 'lucide-react';
import api from '../../api/client';

export const MasterPlaceCustomers: React.FC = () => {
  const [customers, setCustomers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  // Customer 360 Modal State
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null);
  const [customer360, setCustomer360] = useState<any>(null);
  const [loading360, setLoading360] = useState(false);
  const [statusUpdating, setStatusUpdating] = useState(false);

  const fetchCustomers = async () => {
    setLoading(true);
    try {
      const res = await api.get('/masterplace/customers', {
        params: {
          page,
          page_size: 20,
          search: search || undefined,
          status_filter: statusFilter || undefined
        }
      });
      setCustomers(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, [page, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchCustomers();
  };

  const openCustomer360 = async (id: number) => {
    setSelectedCustomerId(id);
    setLoading360(true);
    try {
      const res = await api.get(`/masterplace/customers/${id}`);
      setCustomer360(res.data);
    } catch (err) {
      console.error(err);
      setCustomer360(null);
    } finally {
      setLoading360(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!selectedCustomerId) return;
    const confirmMsg = `Are you sure you want to change this customer's status to ${newStatus.toUpperCase()}?`;
    if (!window.confirm(confirmMsg)) return;

    setStatusUpdating(true);
    try {
      await api.post(`/masterplace/customers/${selectedCustomerId}/status`, {
        status: newStatus,
        reason: `Operator action from Customer 360 view`
      });
      // Refresh 360 and list
      await openCustomer360(selectedCustomerId);
      fetchCustomers();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to update customer status');
    } finally {
      setStatusUpdating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Platform Customers</h1>
          <p className="text-xs text-slate-400 mt-0.5">Authoritative registry of all customer organizations, memberships, usage, and operational standing.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-slate-400">Total: <strong className="text-white">{total}</strong></span>
          <button
            onClick={() => fetchCustomers()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-72">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by customer name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs rounded-xl bg-slate-900 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
          />
        </form>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Filter className="w-3.5 h-3.5" />
            <span>Status:</span>
          </div>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 text-xs rounded-xl bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500"
          >
            <option value="">All Statuses</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
            <option value="trial">Trial</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      {/* Customers Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-bold uppercase text-[10px] tracking-wider bg-slate-950/50">
                <th className="py-3 px-4">Customer / Org</th>
                <th className="py-3 px-4">Owner Email</th>
                <th className="py-3 px-4">Plan</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Projects</th>
                <th className="py-3 px-4">Websites</th>
                <th className="py-3 px-4">SERP Usage</th>
                <th className="py-3 px-4">AI Tokens</th>
                <th className="py-3 px-4">Health</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {loading ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-slate-500">
                    Loading platform customers...
                  </td>
                </tr>
              ) : customers.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-slate-500">
                    No customers found matching current filters.
                  </td>
                </tr>
              ) : (
                customers.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => openCustomer360(c.id)}
                    className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                  >
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-white flex items-center gap-1.5">
                        <span>{c.name}</span>
                        <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
                      </div>
                      <div className="text-[10px] text-slate-500">ID #{c.id} · {c.slug}</div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-300">{c.email}</td>
                    <td className="py-3.5 px-4 text-purple-300 uppercase font-semibold text-[10px]">{c.plan}</td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`px-2 py-0.5 text-[10px] font-bold rounded-md uppercase tracking-wider ${
                          c.status === 'active'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : c.status === 'suspended'
                            ? 'bg-red-500/20 text-red-300'
                            : 'bg-amber-500/20 text-amber-300'
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-200">{c.projects_count}</td>
                    <td className="py-3.5 px-4 text-slate-200">{c.websites_count}</td>
                    <td className="py-3.5 px-4 text-slate-300">{c.serp_usage.toLocaleString()}</td>
                    <td className="py-3.5 px-4 text-slate-300">{c.ai_tokens.toLocaleString()}</td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`text-[11px] font-semibold ${
                          c.health === 'Healthy'
                            ? 'text-emerald-400'
                            : c.health === 'Warning'
                            ? 'text-amber-400'
                            : 'text-rose-400'
                        }`}
                      >
                        {c.health}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openCustomer360(c.id);
                        }}
                        className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-purple-300 font-semibold text-[11px] transition-colors"
                      >
                        360 View
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 20 && (
          <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <div>Showing page {page} of {Math.ceil(total / 20)}</div>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="px-3 py-1 rounded-lg bg-slate-800 disabled:opacity-40 hover:bg-slate-700 text-white font-semibold"
              >
                Previous
              </button>
              <button
                disabled={page >= Math.ceil(total / 20)}
                onClick={() => setPage(page + 1)}
                className="px-3 py-1 rounded-lg bg-slate-800 disabled:opacity-40 hover:bg-slate-700 text-white font-semibold"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Customer 360 Drawer / Modal (Part 7, 29) */}
      {selectedCustomerId && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex justify-end">
          <div className="w-full max-w-2xl bg-slate-900 border-l border-slate-800 h-full overflow-y-auto p-6 space-y-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-purple-600/20 border border-purple-500/30 flex items-center justify-center text-purple-300 font-bold">
                  {customer360?.customer?.name?.charAt(0) || 'C'}
                </div>
                <div>
                  <h2 className="text-base font-black text-white">{customer360?.customer?.name || 'Customer 360'}</h2>
                  <div className="text-xs text-slate-400">ID #{selectedCustomerId} · Plan: {customer360?.customer?.plan}</div>
                </div>
              </div>
              <button
                onClick={() => setSelectedCustomerId(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {loading360 ? (
              <div className="py-20 text-center text-xs text-slate-400">Loading Customer 360 telemetry...</div>
            ) : !customer360 ? (
              <div className="py-20 text-center text-xs text-red-400">Failed to load customer details.</div>
            ) : (
              <div className="space-y-6">
                {/* Status & Suspension Controls (Part 29) */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">Account Standing</span>
                      <div className="text-sm font-bold text-white capitalize mt-0.5">Status: {customer360.customer.status}</div>
                    </div>
                    <div>
                      {customer360.customer.status === 'suspended' ? (
                        <button
                          disabled={statusUpdating}
                          onClick={() => handleStatusChange('active')}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/30 hover:bg-emerald-600/50 border border-emerald-500/40 text-emerald-300 text-xs font-bold transition-colors"
                        >
                          <ShieldCheck className="w-4 h-4" />
                          Reactivate Customer
                        </button>
                      ) : (
                        <button
                          disabled={statusUpdating}
                          onClick={() => handleStatusChange('suspended')}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600/30 hover:bg-red-600/50 border border-red-500/40 text-red-300 text-xs font-bold transition-colors"
                        >
                          <ShieldAlert className="w-4 h-4" />
                          Suspend Customer
                        </button>
                      )}
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    Suspension prevents the organization and its users from running new scans, consuming billable SERP credits, or initiating AI jobs.
                  </p>
                </div>

                {/* Resource Accounting */}
                <div>
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 mb-3">Resource Consumption & Telemetry</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-semibold uppercase">SERP Requests</div>
                      <div className="text-base font-bold text-white mt-1">{customer360.usage.serp_requests.toLocaleString()}</div>
                      <div className="text-[10px] text-slate-500">Cost: ${customer360.usage.serp_estimated_cost}</div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-semibold uppercase">AI Tokens</div>
                      <div className="text-base font-bold text-white mt-1">{customer360.usage.ai_total_tokens.toLocaleString()}</div>
                      <div className="text-[10px] text-slate-500">Cost: ${customer360.usage.ai_estimated_cost}</div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-semibold uppercase">Google API Calls</div>
                      <div className="text-base font-bold text-white mt-1">{customer360.usage.google_requests.toLocaleString()}</div>
                      <div className="text-[10px] text-slate-500">Tracked local calls</div>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 font-semibold uppercase">AI Credits Balance</div>
                      <div className="text-base font-bold text-purple-300 mt-1">{customer360.ai_wallet?.credits_balance || 0}</div>
                      <div className="text-[10px] text-slate-500">Daily limit: {customer360.ai_wallet?.daily_limit}</div>
                    </div>
                  </div>
                </div>

                {/* Projects & Websites */}
                <div>
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 mb-3">Projects ({customer360.projects?.length || 0})</h3>
                  <div className="space-y-2">
                    {customer360.projects?.length === 0 ? (
                      <div className="p-3 rounded-xl bg-slate-950 text-xs text-slate-500">No projects connected.</div>
                    ) : (
                      customer360.projects.map((p: any) => (
                        <div key={p.id} className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                          <div>
                            <div className="font-bold text-xs text-white">{p.name}</div>
                            <div className="text-[11px] text-purple-400">{p.domain}</div>
                          </div>
                          <div className="text-right">
                            <span className="text-[10px] px-2 py-0.5 rounded font-semibold bg-slate-800 text-slate-300">{p.status}</span>
                            <div className="text-[10px] text-slate-500 mt-0.5">Health: {p.health_score || 'N/A'}</div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Memberships */}
                <div>
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 mb-3">Members ({customer360.members?.length || 0})</h3>
                  <div className="space-y-2">
                    {customer360.members?.map((m: any) => (
                      <div key={m.id} className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs">
                        <div>
                          <div className="font-bold text-white">{m.full_name || m.email}</div>
                          <div className="text-[10px] text-slate-400">{m.email}</div>
                        </div>
                        <span className="text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider bg-purple-500/20 text-purple-300">
                          {m.role}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

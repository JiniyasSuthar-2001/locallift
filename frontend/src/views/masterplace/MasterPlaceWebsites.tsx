import React, { useState, useEffect } from 'react';
import {
  Globe,
  Search,
  Filter,
  ArrowUpDown,
  ExternalLink,
  Layers,
  RefreshCw
} from 'lucide-react';
import api from '../../api/client';

export const MasterPlaceWebsites: React.FC = () => {
  const [websites, setWebsites] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('pages_crawled');
  const [loading, setLoading] = useState(true);

  const fetchWebsites = async () => {
    setLoading(true);
    try {
      const res = await api.get('/masterplace/websites', {
        params: {
          page,
          page_size: 25,
          search: search || undefined,
          sort_by: sortBy
        }
      });
      setWebsites(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWebsites();
  }, [page, sortBy]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchWebsites();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">Platform Websites Master View</h1>
          <p className="text-xs text-slate-400 mt-0.5">Global inventory of every customer website connected to LocalLift and their crawl resource footprint.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-slate-400">Total Connected: <strong className="text-white">{total}</strong></span>
          <button
            onClick={() => fetchWebsites()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700/80 hover:bg-slate-800 text-xs font-semibold text-slate-200 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Search and Sort controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search by URL, project, or customer..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs rounded-xl bg-slate-900 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
          />
        </form>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <ArrowUpDown className="w-3.5 h-3.5" />
            <span>Sort by:</span>
          </div>
          <select
            value={sortBy}
            onChange={(e) => {
              setSortBy(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 text-xs rounded-xl bg-slate-900 border border-slate-800 text-white focus:outline-none focus:border-purple-500"
          >
            <option value="pages_crawled">Most Pages Crawled</option>
            <option value="recent">Recently Connected</option>
          </select>
        </div>
      </div>

      {/* Websites Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-bold uppercase text-[10px] tracking-wider bg-slate-950/50">
                <th className="py-3 px-4">Website URL</th>
                <th className="py-3 px-4">Customer Organization</th>
                <th className="py-3 px-4">Project</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Pages Crawled</th>
                <th className="py-3 px-4">Scans Count</th>
                <th className="py-3 px-4">SERP Usage</th>
                <th className="py-3 px-4">Last Crawled</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    Loading platform websites...
                  </td>
                </tr>
              ) : websites.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500">
                    No websites found matching query.
                  </td>
                </tr>
              ) : (
                websites.map((w) => (
                  <tr key={w.id} className="hover:bg-slate-850/50 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-bold text-white flex items-center gap-1.5">
                        <Globe className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                        <span className="truncate max-w-xs">{w.url}</span>
                      </div>
                      <div className="text-[10px] text-slate-500">Website ID #{w.id}</div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-slate-200 font-semibold">{w.organization_name}</div>
                      <div className="text-[10px] text-slate-500">Org #{w.organization_id}</div>
                    </td>
                    <td className="py-3 px-4 text-purple-300 font-semibold">{w.project_name}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 text-[10px] font-bold rounded-md uppercase tracking-wider bg-emerald-500/20 text-emerald-300">
                        {w.status || 'READY'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-white font-bold">{w.pages_crawled.toLocaleString()}</td>
                    <td className="py-3 px-4 text-slate-300">{w.scans_count}</td>
                    <td className="py-3 px-4 text-slate-300">{w.serp_usage.toLocaleString()}</td>
                    <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                      {w.last_crawled_at ? new Date(w.last_crawled_at).toLocaleDateString() : 'Never'}
                    </td>
                  </tr>
                ))
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
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { LineChart, Search, Filter, ArrowUpRight, TrendingUp, Globe, Smartphone, Laptop } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const GSCView: React.FC = () => {
  const { activeProject } = useProject();
  const [gscData, setGscData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState('Last 28 Days');

  const fetchGSC = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/google/gsc/${activeProject.id}`);
      setGscData(resp.data);
    } catch (e) {
      console.error('Failed to load GSC data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGSC();
  }, [activeProject?.id]);

  if (!activeProject) {
    return (
      <EmptyState
        icon={LineChart}
        badge="Search Console"
        title="Select a Project"
        description="Select a business project to view Google Search Console organic impressions, clicks, and queries."
      />
    );
  }

  const queries = gscData?.top_queries || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <LineChart className="w-6 h-6 text-purple-600" />
            <span>Google Search Console Insights</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Track organic clicks, search queries, click-through rates, and average SERP positions for {activeProject.domain}.
          </p>
        </div>

        <div className="flex items-center space-x-2 self-start">
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="bg-white border border-slate-200 text-xs font-bold text-slate-800 rounded-xl px-3 py-1.5 focus:outline-none focus:border-purple-500 cursor-pointer"
          >
            <option>Last 7 Days</option>
            <option>Last 28 Days</option>
            <option>Last 3 Months</option>
            <option>Last 12 Months</option>
          </select>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Total Organic Clicks</div>
          <div className="text-2xl font-black text-slate-900 mt-1">
            {gscData?.connected ? (gscData?.total_clicks ?? 0) : '—'}
          </div>
          <div className="text-[11px] text-purple-700 font-bold">
            {gscData?.connected ? 'Organic visits' : 'Not Connected'}
          </div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Total Impressions</div>
          <div className="text-2xl font-black text-slate-900 mt-1">
            {gscData?.connected && gscData?.total_impressions !== undefined ? gscData.total_impressions.toLocaleString() : '—'}
          </div>
          <div className="text-[11px] text-emerald-700 font-bold">
            {gscData?.connected ? 'Search appearances' : 'Not Connected'}
          </div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Average CTR</div>
          <div className="text-2xl font-black text-purple-700 mt-1">
            {gscData?.connected && gscData?.average_ctr !== undefined ? `${gscData.average_ctr}%` : '—'}
          </div>
          <div className="text-[11px] text-slate-500 font-medium">
            {gscData?.connected ? 'Click-through rate' : 'Not Connected'}
          </div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Average Position</div>
          <div className="text-2xl font-black text-slate-900 mt-1">
            {gscData?.connected && gscData?.average_position ? `#${gscData.average_position}` : '—'}
          </div>
          <div className="text-[11px] text-slate-500 font-medium">
            {gscData?.connected ? 'Google SERP Rank' : 'Not Connected'}
          </div>
        </div>
      </div>

      {/* Top Search Queries Table */}
      <div className="card-vibrant overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-900">
            Top Performing Local Search Queries
          </h3>
          <span className="text-xs text-slate-500 font-bold">{queries.length} Queries</span>
        </div>

        {queries.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                <tr>
                  <th className="p-3.5">Top Queries</th>
                  <th className="p-3.5">Clicks</th>
                  <th className="p-3.5">Impressions</th>
                  <th className="p-3.5">CTR</th>
                  <th className="p-3.5">Average Position</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {queries.map((q: any, idx: number) => (
                  <tr key={idx} className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold text-slate-900">{q.query}</td>
                    <td className="p-3.5 font-black text-purple-700">{q.clicks}</td>
                    <td className="p-3.5 text-slate-600">{q.impressions.toLocaleString()}</td>
                    <td className="p-3.5 text-slate-800 font-semibold">{q.ctr}</td>
                    <td className="p-3.5 font-black text-slate-900">#{q.position}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={LineChart}
            badge="Search Queries"
            title="No Search Console Queries"
            description="Authorize Google Search Console to import organic keywords, clicks, and ranking positions."
          />
        )}
      </div>
    </div>
  );
};

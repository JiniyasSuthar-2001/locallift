import React, { useState, useEffect } from 'react';
import { LineChart, Search, Filter, ArrowUpRight, TrendingUp, Globe, Smartphone, Laptop, RefreshCw, CheckCircle2, AlertCircle, Link2, ExternalLink } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const GSCView: React.FC = () => {
  const { activeProject } = useProject();
  const [gscData, setGscData] = useState<any>(null);
  const [availableProps, setAvailableProps] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [mapping, setMapping] = useState(false);
  const [dateRange, setDateRange] = useState('Last 28 Days');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchGSC = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      setErrorMsg(null);
      const [gscResp, propsResp] = await Promise.allSettled([
        api.get(`/google/gsc/${activeProject.id}`),
        api.get(`/connections/gsc/properties/${activeProject.id}`)
      ]);

      if (gscResp.status === 'fulfilled') {
        setGscData(gscResp.value.data);
      }
      if (propsResp.status === 'fulfilled') {
        setAvailableProps(propsResp.value.data || []);
      }
    } catch (e: any) {
      console.error('Failed to load GSC data:', e);
      setErrorMsg('Failed to communicate with Google Search Console service.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGSC();
  }, [activeProject?.id]);

  const handleSyncNow = async () => {
    if (!activeProject) return;
    try {
      setSyncing(true);
      setErrorMsg(null);
      setSuccessMsg(null);
      const resp = await api.post(`/google/gsc/${activeProject.id}/sync`);
      setSuccessMsg(`Search Console synchronized successfully (${resp.data?.synced_records ?? 0} daily records).`);
      await fetchGSC();
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Failed to sync Search Console data.';
      setErrorMsg(msg);
    } finally {
      setSyncing(false);
    }
  };

  const handleSelectProperty = async (propId: number) => {
    if (!activeProject) return;
    try {
      setMapping(true);
      setErrorMsg(null);
      await api.post('/connections/gsc/map-property', {
        project_id: activeProject.id,
        property_id: propId
      });
      setSuccessMsg('Search Console property mapped and synchronized successfully.');
      await fetchGSC();
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Failed to map Search Console property.';
      setErrorMsg(msg);
    } finally {
      setMapping(false);
    }
  };

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
  const repState = gscData?.reporting_state || 'not_connected';
  const isReportingActive = repState === 'reporting_active' && gscData?.total_clicks !== null;

  return (
    <div className="space-y-6">
      {/* Header */}
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

        <div className="flex items-center space-x-2.5 self-start">
          <button
            onClick={handleSyncNow}
            disabled={syncing || !gscData?.connected}
            className="px-3.5 py-2 bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5 disabled:opacity-50"
            title="Fetch latest verified search analytics directly from Google"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span>{syncing ? 'Syncing...' : 'Sync Now'}</span>
          </button>

          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="bg-white border border-slate-200 text-xs font-bold text-slate-800 rounded-xl px-3 py-2 focus:outline-none focus:border-purple-500 cursor-pointer"
          >
            <option>Last 7 Days</option>
            <option>Last 28 Days</option>
            <option>Last 3 Months</option>
            <option>Last 12 Months</option>
          </select>
        </div>
      </div>

      {/* Connection & Property Status Bar */}
      <div className="card-vibrant p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white border border-slate-200 rounded-2xl">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold text-slate-500">Connection Status:</span>
            {repState === 'reporting_active' ? (
              <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200">
                <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                <span>Reporting Active</span>
              </span>
            ) : repState === 'waiting_for_data' ? (
              <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black bg-blue-100 text-blue-800 border border-blue-200">
                <RefreshCw className="w-3 h-3 text-blue-600 animate-spin" />
                <span>Connected • Waiting for Data</span>
              </span>
            ) : repState === 'property_not_mapped' ? (
              <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black bg-amber-100 text-amber-800 border border-amber-200">
                <AlertCircle className="w-3 h-3 text-amber-600" />
                <span>Connected • Property Not Selected</span>
              </span>
            ) : repState === 'needs_reconnection' ? (
              <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black bg-rose-100 text-rose-800 border border-rose-200">
                <AlertCircle className="w-3 h-3 text-rose-600" />
                <span>Token Expired • Needs Reconnection</span>
              </span>
            ) : repState === 'sync_failed' ? (
              <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black bg-rose-100 text-rose-800 border border-rose-200">
                <AlertCircle className="w-3 h-3 text-rose-600" />
                <span>Sync Failed</span>
              </span>
            ) : (
              <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black bg-slate-100 text-slate-600 border border-slate-200">
                <span>Not Connected</span>
              </span>
            )}
          </div>

          {gscData?.mapped_property && (
            <div className="flex items-center space-x-1.5 text-xs text-slate-700 bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200">
              <span className="text-slate-400 font-medium">Mapped Property:</span>
              <span className="font-mono font-bold text-slate-900 truncate max-w-xs">{gscData.mapped_property}</span>
            </div>
          )}
        </div>

        {/* Property Selector */}
        {availableProps.length > 0 && (
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold text-slate-500 whitespace-nowrap">Switch Property:</span>
            <select
              disabled={mapping}
              value={availableProps.find(p => p.project_id === activeProject.id)?.id || ''}
              onChange={(e) => handleSelectProperty(Number(e.target.value))}
              className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-xs font-bold text-slate-800 focus:outline-none focus:border-purple-500 cursor-pointer max-w-xs truncate"
            >
              <option value="" disabled>Select Search Console Site</option>
              {availableProps.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.site_url} {p.project_id === activeProject.id ? '✓ (Active)' : ''}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-2.5 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span className="flex-1">{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-400 hover:text-rose-600 font-bold">Dismiss</button>
        </div>
      )}
      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center space-x-2.5 text-xs text-emerald-800">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span className="flex-1">{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700 font-bold">Dismiss</button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Total Organic Clicks</div>
          <div className="text-2xl font-black text-slate-900 mt-1">
            {isReportingActive ? gscData.total_clicks.toLocaleString() : '—'}
          </div>
          <div className="text-[11px] text-purple-700 font-bold">
            {isReportingActive ? 'Organic visits' : (gscData?.connected ? 'No data available yet' : 'Not Connected')}
          </div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Total Impressions</div>
          <div className="text-2xl font-black text-slate-900 mt-1">
            {isReportingActive ? gscData.total_impressions.toLocaleString() : '—'}
          </div>
          <div className="text-[11px] text-emerald-700 font-bold">
            {isReportingActive ? 'Search appearances' : (gscData?.connected ? 'No data available yet' : 'Not Connected')}
          </div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Average CTR</div>
          <div className="text-2xl font-black text-purple-700 mt-1">
            {isReportingActive && gscData.average_ctr !== null ? `${gscData.average_ctr}%` : '—'}
          </div>
          <div className="text-[11px] text-slate-500 font-medium">
            {isReportingActive ? 'Click-through rate' : (gscData?.connected ? 'No data available yet' : 'Not Connected')}
          </div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Average Position</div>
          <div className="text-2xl font-black text-slate-900 mt-1">
            {isReportingActive && gscData.average_position !== null ? `#${gscData.average_position}` : '—'}
          </div>
          <div className="text-[11px] text-slate-500 font-medium">
            {isReportingActive ? 'Google SERP Rank' : (gscData?.connected ? 'No data available yet' : 'Not Connected')}
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
            title={
              repState === 'waiting_for_data'
                ? 'Awaiting Search Console Data'
                : repState === 'property_not_mapped'
                ? 'Select a Search Console Site'
                : repState === 'needs_reconnection'
                ? 'Google Authorization Expired'
                : 'No Search Console Queries'
            }
            description={
              repState === 'waiting_for_data'
                ? 'Google Search Console is authorized and mapped. Search Analytics queries will populate once Google finishes indexing traffic for this domain.'
                : repState === 'property_not_mapped'
                ? 'Select a verified Search Console property from the dropdown above to map organic keywords and clicks to this project.'
                : repState === 'needs_reconnection'
                ? 'Your Google OAuth authorization token has expired or was revoked. Reconnect Google in Settings to resume syncing.'
                : 'Authorize Google Search Console in Connections to import organic keywords, clicks, and ranking positions.'
            }
          />
        )}
      </div>
    </div>
  );
};

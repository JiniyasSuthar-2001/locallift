import React, { useState, useEffect } from 'react';
import { Activity, Users, MousePointerClick, TrendingUp, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const GA4View: React.FC = () => {
  const { activeProject } = useProject();
  const [ga4Data, setGa4Data] = useState<any>(null);
  const [availableProps, setAvailableProps] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [mapping, setMapping] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchGA4 = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      setErrorMsg(null);
      const [ga4Resp, propsResp] = await Promise.allSettled([
        api.get(`/google/ga4/${activeProject.id}`),
        api.get(`/connections/ga4/properties/${activeProject.id}`)
      ]);

      if (ga4Resp.status === 'fulfilled') {
        setGa4Data(ga4Resp.value.data);
      }
      if (propsResp.status === 'fulfilled') {
        setAvailableProps(propsResp.value.data || []);
      }
    } catch (e: any) {
      console.error('Failed to load GA4 data:', e);
      setErrorMsg('Failed to communicate with Google Analytics 4 service.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGA4();
  }, [activeProject?.id]);

  const handleSyncNow = async () => {
    if (!activeProject) return;
    try {
      setSyncing(true);
      setErrorMsg(null);
      setSuccessMsg(null);
      const resp = await api.post(`/google/ga4/${activeProject.id}/sync`);
      setSuccessMsg(`Google Analytics 4 synchronized successfully (${resp.data?.synced_records ?? 0} daily records).`);
      await fetchGA4();
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Failed to sync GA4 data.';
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
      await api.post('/connections/ga4/map-property', {
        project_id: activeProject.id,
        property_id: propId
      });
      setSuccessMsg('GA4 property mapped and synchronized successfully.');
      await fetchGA4();
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || 'Failed to map GA4 property.';
      setErrorMsg(msg);
    } finally {
      setMapping(false);
    }
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={Activity}
        badge="Analytics"
        title="Select a Project"
        description="Select a business project to view Google Analytics 4 organic traffic, conversions, and landing page sessions."
      />
    );
  }

  const landingPages = ga4Data?.landing_pages || [];
  const repState = ga4Data?.reporting_state || 'not_connected';
  const isReportingActive = repState === 'reporting_active' && ga4Data?.total_users !== null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <Activity className="w-6 h-6 text-purple-600" />
            <span>Google Analytics 4 Engagement</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Track organic user sessions, engagement rates, phone calls, and local landing page conversions for {activeProject.domain}.
          </p>
        </div>

        <div className="flex items-center space-x-2.5 self-start">
          <button
            onClick={handleSyncNow}
            disabled={syncing || !ga4Data?.connected}
            className="px-3.5 py-2 bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5 disabled:opacity-50"
            title="Fetch latest verified reporting data directly from GA4 Data API"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span>{syncing ? 'Syncing...' : 'Sync Now'}</span>
          </button>
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

          {ga4Data?.mapped_property && (
            <div className="flex items-center space-x-1.5 text-xs text-slate-700 bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200">
              <span className="text-slate-400 font-medium">Mapped Property:</span>
              <span className="font-mono font-bold text-slate-900 truncate max-w-xs">{ga4Data.mapped_property}</span>
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
              <option value="" disabled>Select GA4 Property</option>
              {availableProps.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.property_name || p.property_id} {p.project_id === activeProject.id ? '✓ (Active)' : ''}
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
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Organic Users</div>
          <div className="text-2xl font-black text-slate-900 mt-1">
            {isReportingActive && (ga4Data.organic_users ?? ga4Data.total_users) !== null
              ? (ga4Data.organic_users ?? ga4Data.total_users).toLocaleString()
              : '—'}
          </div>
          <div className="text-[11px] text-purple-700 font-bold">
            {isReportingActive ? 'Search visitors' : (ga4Data?.connected ? 'No data available yet' : 'Not Connected')}
          </div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Total Sessions</div>
          <div className="text-2xl font-black text-slate-900 mt-1">
            {isReportingActive && (ga4Data.sessions ?? ga4Data.total_sessions) !== null
              ? (ga4Data.sessions ?? ga4Data.total_sessions).toLocaleString()
              : '—'}
          </div>
          <div className="text-[11px] text-slate-500 font-medium">
            {isReportingActive ? 'Browse sessions' : (ga4Data?.connected ? 'No data available yet' : 'Not Connected')}
          </div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Engagement Rate</div>
          <div className="text-2xl font-black text-emerald-700 mt-1">
            {isReportingActive && ga4Data.engagement_rate !== null ? `${ga4Data.engagement_rate}%` : '—'}
          </div>
          <div className="text-[11px] text-slate-500 font-medium">
            {isReportingActive ? 'Active interactions' : (ga4Data?.connected ? 'No data available yet' : 'Not Connected')}
          </div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Local Conversions</div>
          <div className="text-2xl font-black text-purple-700 mt-1">
            {isReportingActive && (ga4Data.conversions ?? ga4Data.total_conversions) !== null
              ? (ga4Data.conversions ?? ga4Data.total_conversions).toLocaleString()
              : '—'}
          </div>
          <div className="text-[11px] text-purple-900 font-bold">
            {isReportingActive ? 'Calls & Quote requests' : (ga4Data?.connected ? 'No data available yet' : 'Not Connected')}
          </div>
        </div>
      </div>

      {/* Landing Pages Table */}
      <div className="card-vibrant overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-900">
            Top Landing Pages by Organic Engagement
          </h3>
          <span className="text-xs text-slate-500 font-bold">{landingPages.length} Pages</span>
        </div>

        {landingPages.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                <tr>
                  <th className="p-3.5">Landing Page URL</th>
                  <th className="p-3.5">Organic Sessions</th>
                  <th className="p-3.5">Engagement Rate</th>
                  <th className="p-3.5">Conversions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {landingPages.map((lp: any, idx: number) => (
                  <tr key={idx} className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold font-mono text-slate-900">{lp.path}</td>
                    <td className="p-3.5 font-black text-purple-700">{lp.sessions}</td>
                    <td className="p-3.5 text-slate-700 font-semibold">{lp.engagement_rate}%</td>
                    <td className="p-3.5 font-black text-emerald-700">{lp.conversions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={Activity}
            badge="GA4 Landing Pages"
            title={ga4Data?.connected ? "No Data Available Yet" : "No GA4 Landing Pages"}
            description={
              ga4Data?.connected
                ? "Your Google Analytics 4 property is connected. Click 'Sync Now' above to pull the latest organic landing page engagement data."
                : "Connect Google Analytics 4 property to track localized landing page session analytics and conversions."
            }
          />
        )}
      </div>
    </div>
  );
};

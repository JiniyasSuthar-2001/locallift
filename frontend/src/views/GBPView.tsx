import React, { useState, useEffect } from 'react';
import {
  Store,
  RotateCw,
  CheckCircle2,
  Clock,
  History,
  Phone,
  Globe,
  MapPin,
  ExternalLink,
  ShieldCheck,
  Sparkles,
  Link,
  Unlink,
  AlertCircle
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { GoogleBusinessProfile, GBPChange } from '../types';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const GBPView: React.FC = () => {
  const { activeProject, refreshDashboard } = useProject();
  const [gbp, setGbp] = useState<GoogleBusinessProfile | null>(null);
  const [changes, setChanges] = useState<GBPChange[]>([]);
  const [loading, setLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [isConfigured, setIsConfigured] = useState<boolean>(true);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);

  const fetchGBPData = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const [gbpResp, changesResp, statusResp, authResp] = await Promise.allSettled([
        api.get(`/gbp/${activeProject.id}`),
        api.get(`/gbp/${activeProject.id}/changes`),
        api.get(`/gbp/${activeProject.id}/status`),
        api.get(`/gbp/${activeProject.id}/auth-url`)
      ]);

      if (gbpResp.status === 'fulfilled') setGbp(gbpResp.value.data);
      if (changesResp.status === 'fulfilled') setChanges(changesResp.value.data || []);
      if (authResp.status === 'fulfilled') {
        setAuthUrl(authResp.value.data?.auth_url);
        setIsConfigured(authResp.value.data?.is_configured);
      }
    } catch (e) {
      console.error('Failed to load GBP data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGBPData();
  }, [activeProject?.id]);

  const handleSync = async () => {
    if (!activeProject) return;
    try {
      setIsSyncing(true);
      setSyncFeedback(null);
      const res = await api.post(`/gbp/${activeProject.id}/sync`);
      setSyncFeedback(`Sync complete: ${res.data.profiles_synced} profile(s) synced, ${res.data.changes_detected} change(s) detected.`);
      await fetchGBPData();
      await refreshDashboard();
    } catch (e: any) {
      console.error('GBP Sync failed:', e);
      setSyncFeedback(e.response?.data?.detail || 'Sync failed. Please ensure Google Account is connected.');
    } finally {
      setIsSyncing(false);
      setTimeout(() => setSyncFeedback(null), 6000);
    }
  };

  const handleConnectGoogle = () => {
    if (authUrl) {
      window.location.href = authUrl;
    } else {
      alert('Google OAuth credentials not configured in settings. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.');
    }
  };

  const handleDisconnect = async () => {
    if (!activeProject) return;
    if (!confirm('Are you sure you want to disconnect Google Business Profile?')) return;
    try {
      await api.post(`/gbp/${activeProject.id}/disconnect`);
      setGbp(null);
      setChanges([]);
      await fetchGBPData();
      await refreshDashboard();
    } catch (e) {
      console.error('Disconnect failed:', e);
    }
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={Store}
        badge="Google Business Profile"
        title="Select a Project"
        description="Select an active project to view Google Business Profile health, impressions, and automated change history."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <Store className="w-6 h-6 text-purple-600" />
            <span>Google Business Profile Hub</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Monitor Google profile completeness, customer search discovery, call volume, and automated change history.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {gbp ? (
            <>
              <button
                onClick={handleDisconnect}
                className="flex items-center space-x-1.5 px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-rose-50 hover:text-rose-700 text-slate-600 text-xs font-bold transition-all"
              >
                <Unlink className="w-3.5 h-3.5" />
                <span>Disconnect</span>
              </button>

              <button
                onClick={handleSync}
                disabled={isSyncing}
                className="flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all disabled:opacity-50"
              >
                <RotateCw className={`w-4 h-4 ${isSyncing ? 'animate-spin' : ''}`} />
                <span>{isSyncing ? 'Syncing Live GBP...' : 'Sync Live Profile'}</span>
              </button>
            </>
          ) : (
            <button
              onClick={handleConnectGoogle}
              className="flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all"
            >
              <Link className="w-4 h-4" />
              <span>Connect Google Account</span>
            </button>
          )}
        </div>
      </div>

      {syncFeedback && (
        <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl flex items-center space-x-2 text-xs text-purple-900 font-semibold">
          <CheckCircle2 className="w-4 h-4 text-purple-600 shrink-0" />
          <span>{syncFeedback}</span>
        </div>
      )}

      {gbp ? (
        <div className="space-y-6">
          {/* Top Profile Summary Card */}
          <div className="card-vibrant p-6 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-4">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-purple-50 text-purple-800 border border-purple-200">
                    {gbp.primary_category || 'Local Business'}
                  </span>
                  <span className="text-xs font-bold text-emerald-700 flex items-center space-x-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Verified Profile</span>
                  </span>
                  {gbp.last_synced_at && (
                    <span className="text-[10px] text-slate-400 font-mono">
                      Last Synced: {new Date(gbp.last_synced_at).toLocaleDateString()} {new Date(gbp.last_synced_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
                <h2 className="text-xl font-black text-slate-900">{gbp.business_name}</h2>
                <div className="text-xs text-slate-600 flex items-center space-x-4">
                  <span>{gbp.address}</span>
                  {gbp.phone && <span>• {gbp.phone}</span>}
                </div>
              </div>

              <div className="bg-purple-50/80 border border-purple-200 p-4 rounded-2xl flex items-center space-x-4">
                <div>
                  <span className="text-[10px] font-bold uppercase text-purple-900 block">Completeness Score</span>
                  <span className="text-2xl font-black text-purple-900">{gbp.completeness_score}%</span>
                </div>
                <div className="w-10 h-10 rounded-xl gradient-brand flex items-center justify-center text-white font-bold">
                  <ShieldCheck className="w-6 h-6 stroke-[2]" />
                </div>
              </div>
            </div>

            {/* Performance KPI Tiles */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-[10px] font-bold uppercase text-slate-500 block">Search Views</span>
                <span className="text-xl font-black text-slate-900 mt-0.5 block">
                  {gbp.search_impressions.toLocaleString()}
                </span>
                <span className="text-[11px] text-emerald-700 font-semibold">Discovery queries</span>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-[10px] font-bold uppercase text-slate-500 block">Maps Views</span>
                <span className="text-xl font-black text-slate-900 mt-0.5 block">
                  {gbp.maps_impressions.toLocaleString()}
                </span>
                <span className="text-[11px] text-emerald-700 font-semibold">Local pack views</span>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-[10px] font-bold uppercase text-slate-500 block">Phone Calls</span>
                <span className="text-xl font-black text-slate-900 mt-0.5 block">{gbp.call_clicks}</span>
                <span className="text-[11px] text-purple-700 font-semibold">Direct inquiries</span>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-[10px] font-bold uppercase text-slate-500 block">Website Clicks</span>
                <span className="text-xl font-black text-slate-900 mt-0.5 block">{gbp.website_clicks}</span>
                <span className="text-[11px] text-blue-700 font-semibold">Landing page visits</span>
              </div>
            </div>
          </div>

          {/* Change Monitoring Log */}
          <div className="card-vibrant p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <History className="w-4 h-4 text-purple-600" />
                <h3 className="text-sm font-extrabold text-slate-900 tracking-tight">
                  Automated GBP Change Monitor
                </h3>
              </div>
              <span className="text-xs text-slate-500 font-medium">Tracking category, hours, and attributes</span>
            </div>

            {changes.length > 0 ? (
              <div className="divide-y divide-slate-100">
                {changes.map((c) => (
                  <div key={c.id} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                    <div className="space-y-0.5">
                      <span className="font-bold text-slate-900">{c.field_name}: </span>
                      <span className="text-slate-500 line-through mr-2">{c.old_value || 'None'}</span>
                      <span className="font-bold text-emerald-700">→ {c.new_value}</span>
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      {new Date(c.detected_at).toLocaleDateString()}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 text-center text-xs text-slate-500">
                No unauthorized changes detected on this Google Business Profile.
              </div>
            )}
          </div>
        </div>
      ) : (
        <EmptyState
          icon={Store}
          badge={isConfigured ? 'OAuth Ready' : 'Setup Required'}
          title="Google Business Profile Not Connected"
          description={
            isConfigured
              ? 'Connect your Google Business Profile via OAuth to automatically sync customer impressions, reviews, and track unauthorized profile edits.'
              : 'Google OAuth API credentials are not set. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to your .env file to enable live GBP synchronization.'
          }
          actionText={isConfigured ? 'Connect with Google' : undefined}
          onAction={isConfigured ? handleConnectGoogle : undefined}
        />
      )}
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import {
  Link2,
  CheckCircle2,
  AlertCircle,
  RotateCw,
  Trash2,
  ExternalLink,
  Plus,
  Building2,
  Store,
  Layers,
  Search,
  BarChart3,
  Globe,
  MapPin,
  HelpCircle,
  Lock,
  ArrowRight,
  ShieldCheck,
  Radio,
  Eye,
  RefreshCw,
  FolderPlus
} from 'lucide-react';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import { getErrorMessage } from '../utils/error';
import {
  GoogleConnectionSummary,
  DiscoveredResourcesResponse,
  PublicBusinessListingItem,
  DiscoveredGBPLocation
} from '../types';

export const ConnectionsView: React.FC = () => {
  const { user } = useAuth();
  const { activeProject, refreshProjects } = useProject();

  const [loading, setLoading] = useState<boolean>(true);
  const [syncing, setSyncing] = useState<boolean>(false);
  const [importing, setImporting] = useState<boolean>(false);
  const [connectionStatus, setConnectionStatus] = useState<GoogleConnectionSummary | null>(null);
  const [discoveredResources, setDiscoveredResources] = useState<DiscoveredResourcesResponse | null>(null);
  const [publicListings, setPublicListings] = useState<PublicBusinessListingItem[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modals & form state
  const [showMapsModal, setShowMapsModal] = useState<boolean>(false);
  const [showImportModal, setShowImportModal] = useState<boolean>(false);
  const [mapsUrl, setMapsUrl] = useState<string>('');
  const [mapsName, setMapsName] = useState<string>('');
  const [mapsCategory, setMapsCategory] = useState<string>('');
  const [submittingMaps, setSubmittingMaps] = useState<boolean>(false);
  const [disconnectConfirm, setDisconnectConfirm] = useState<boolean>(false);

  // Selected GBP locations for import
  const [selectedLocations, setSelectedLocations] = useState<Record<string, boolean>>({});

  const fetchConnectionData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [statusRes, publicRes] = await Promise.all([
        api.get<GoogleConnectionSummary>('/connections/status'),
        api.get<PublicBusinessListingItem[]>('/connections/public-maps')
      ]);
      setConnectionStatus(statusRes.data);
      setPublicListings(publicRes.data);

      const isConn = statusRes.data.connected || (statusRes.data as any).is_connected || statusRes.data.status === 'connected';
      if (isConn) {
        try {
          // Fetch discovered resources
          const discRes = await api.post<DiscoveredResourcesResponse>('/connections/google/discover');
          setDiscoveredResources(discRes.data);

          // Pre-select all un-imported locations
          const initialSelected: Record<string, boolean> = {};
          (discRes.data.gbp_locations || []).forEach((loc) => {
            if (!loc.already_imported) {
              initialSelected[loc.location_id] = true;
            }
          });
          setSelectedLocations(initialSelected);
        } catch (discErr) {
          console.warn('Google discovery error:', discErr);
        }
      }
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to load connection settings.'));
    } finally {
      setLoading(false);
    }
  };


  useEffect(() => {
    fetchConnectionData();
  }, []);

  const handleStartGoogleOAuth = async () => {
    try {
      const res = await api.get<{ auth_url: string; state: string }>('/connections/google/auth-url');
      if (res.data.auth_url) {
        window.location.href = res.data.auth_url;
      }
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to initiate Google OAuth.'));
    }
  };

  const handleSyncNow = async () => {
    setSyncing(true);
    setErrorMsg(null);
    try {
      await api.post('/connections/google/sync');
      setSuccessMsg('Google resources synchronized successfully.');
      await fetchConnectionData();
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Sync failed.'));
    } finally {
      setSyncing(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await api.post('/connections/google/disconnect');
      setDisconnectConfirm(false);
      setSuccessMsg('Google account disconnected safely. Historical data preserved.');
      setDiscoveredResources(null);
      await fetchConnectionData();
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Disconnect failed.'));
    }
  };

  const handleImportResources = async () => {
    if (!discoveredResources) return;
    setImporting(true);
    setErrorMsg(null);
    try {
      const selectedLocList = discoveredResources.gbp_locations.filter(
        (l) => selectedLocations[l.location_id]
      );

      const res = await api.post<{ created_projects_count: number; updated_projects_count: number; message: string }>(
        '/connections/google/import-resources',
        {
          locations: selectedLocList,
          auto_create_projects: true
        }
      );

      setSuccessMsg(res.data.message);
      setShowImportModal(false);
      await refreshProjects();
      await fetchConnectionData();
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Import failed.'));
    } finally {
      setImporting(false);
    }
  };

  const handleAddPublicMaps = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mapsUrl.trim()) return;
    setSubmittingMaps(true);
    setErrorMsg(null);
    try {
      const res = await api.post<PublicBusinessListingItem>(
        '/connections/public-maps/import',
        {
          maps_url: mapsUrl.trim(),
          business_name: mapsName.trim() || undefined,
          target_category: mapsCategory.trim() || undefined
        }
      );

      const name = res.data?.name || 'Business';
      setSuccessMsg(`Public business "${name}" added for monitoring.`);
      setShowMapsModal(false);
      setMapsUrl('');
      setMapsName('');
      setMapsCategory('');
      const updatedListings = await api.get<PublicBusinessListingItem[]>('/connections/public-maps');
      setPublicListings(updatedListings.data);
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to import Google Maps listing.'));
    } finally {
      setSubmittingMaps(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="flex items-center space-x-3 text-slate-500 text-xs">
          <RotateCw className="w-4 h-4 animate-spin text-purple-600" />
          <span>Loading connections and authorized Google services...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div>
        <h2 className="text-xl font-black text-slate-900 flex items-center space-x-2">
          <Link2 className="w-5 h-5 text-purple-600" />
          <span>External Integrations & Connections</span>
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Connect your official Google account to automatically discover and synchronize Google Business Profile locations, Google Ads, Search Console, and Analytics.
        </p>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-2.5 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span className="flex-1">{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-400 hover:text-rose-600 text-xs font-bold">
            Dismiss
          </button>
        </div>
      )}
      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center space-x-2.5 text-xs text-emerald-800">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span className="flex-1">{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700 text-xs font-bold">
            Dismiss
          </button>
        </div>
      )}

      {/* Master Google Connection Card */}
      <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl shadow-sm bg-white space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-5">
          <div className="flex items-center space-x-3.5">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-purple-500/20">
              <Store className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-base font-black text-slate-900">Google Central Hub</h3>
                {connectionStatus?.connected ? (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                    <span>Connected</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-black bg-slate-100 text-slate-600 border border-slate-200">
                    <span>Not Connected</span>
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                {connectionStatus?.connected
                  ? `Authorized as: ${connectionStatus.google_email || 'Authenticated User'}`
                  : 'Connect your Google account using secure OAuth 2.0 to access Google APIs.'}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {connectionStatus?.connected ? (
              <>
                <button
                  onClick={handleSyncNow}
                  disabled={syncing}
                  className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
                  <span>{syncing ? 'Syncing...' : 'Sync Now'}</span>
                </button>
                <button
                  onClick={() => setShowImportModal(true)}
                  className="px-3.5 py-2 bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5"
                >
                  <FolderPlus className="w-3.5 h-3.5 text-purple-600" />
                  <span>Import Resources</span>
                </button>
                <button
                  onClick={() => setDisconnectConfirm(true)}
                  className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-all"
                  title="Disconnect Google Account"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            ) : (
              <button
                onClick={handleStartGoogleOAuth}
                className="px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all flex items-center space-x-2"
              >
                <ExternalLink className="w-4 h-4" />
                <span>Connect Google Account</span>
              </button>
            )}
          </div>
        </div>

        {/* Multi-Service Sub-Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* GBP Card */}
          <div className="p-4 rounded-xl border border-slate-100 bg-slate-50/60 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Store className="w-4 h-4 text-purple-600" />
                <span className="text-xs font-black text-slate-800">Business Profile</span>
              </div>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                connectionStatus?.has_gbp || (connectionStatus?.counts?.gbp_locations ?? (connectionStatus as any)?.gbp_locations_count ?? 0) > 0 ? 'bg-purple-100 text-purple-800' : 'bg-slate-200 text-slate-600'
              }`}>
                {connectionStatus?.counts?.gbp_locations ?? (connectionStatus as any)?.gbp_locations_count ?? 0} Locations
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              Google Maps profiles, reviews, search impressions & insights.
            </p>
          </div>

          {/* Google Ads Card */}
          <div className="p-4 rounded-xl border border-slate-100 bg-slate-50/60 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Layers className="w-4 h-4 text-blue-600" />
                <span className="text-xs font-black text-slate-800">Google Ads</span>
              </div>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                connectionStatus?.has_ads || (connectionStatus?.counts?.ads_accounts ?? (connectionStatus as any)?.ads_accounts_count ?? 0) > 0 ? 'bg-blue-100 text-blue-800' : 'bg-slate-200 text-slate-600'
              }`}>
                {connectionStatus?.counts?.ads_accounts ?? (connectionStatus as any)?.ads_accounts_count ?? 0} Accounts
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              Local ad campaigns, ad spend, and conversion telemetry.
            </p>
          </div>

          {/* Search Console Card */}
          <div className="p-4 rounded-xl border border-slate-100 bg-slate-50/60 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Search className="w-4 h-4 text-emerald-600" />
                <span className="text-xs font-black text-slate-800">Search Console</span>
              </div>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                connectionStatus?.has_gsc || (connectionStatus?.counts?.gsc_properties ?? (connectionStatus as any)?.search_console_properties_count ?? 0) > 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'
              }`}>
                {connectionStatus?.counts?.gsc_properties ?? (connectionStatus as any)?.search_console_properties_count ?? 0} Sites
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              Organic search performance, queries, clicks and CTR data.
            </p>
          </div>

          {/* Google Analytics Card */}
          <div className="p-4 rounded-xl border border-slate-100 bg-slate-50/60 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <BarChart3 className="w-4 h-4 text-amber-600" />
                <span className="text-xs font-black text-slate-800">Analytics 4</span>
              </div>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                connectionStatus?.has_ga4 || (connectionStatus?.counts?.ga4_properties ?? (connectionStatus as any)?.analytics_properties_count ?? 0) > 0 ? 'bg-amber-100 text-amber-800' : 'bg-slate-200 text-slate-600'
              }`}>
                {connectionStatus?.counts?.ga4_properties ?? (connectionStatus as any)?.analytics_properties_count ?? 0} Streams
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              Website engagement, traffic sources, and conversion analytics.
            </p>
          </div>
        </div>


        {/* Disconnect Confirmation Alert */}
        {disconnectConfirm && (
          <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl space-y-3">
            <div className="flex items-start space-x-3">
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-black text-rose-900">Confirm Google Disconnect</h4>
                <p className="text-xs text-rose-700 mt-0.5">
                  Disconnecting will revoke LocalLift's access tokens and pause automated synchronizations. All historical project data, audit logs, and ranking history in LocalLift will remain safely intact.
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={handleDisconnect}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition-all"
              >
                Yes, Disconnect Google
              </button>
              <button
                onClick={() => setDisconnectConfirm(false)}
                className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50 transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Discovered GBP Locations Table (when connected) */}
      {discoveredResources && discoveredResources.gbp_locations.length > 0 && (
        <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl shadow-sm bg-white space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
                <Store className="w-4 h-4 text-purple-600" />
                <span>Discovered Google Business Profiles ({discoveredResources.gbp_locations.length})</span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Verified locations available from your connected Google account.
              </p>
            </div>
            <button
              onClick={() => setShowImportModal(true)}
              className="px-4 py-2 btn-vibrant-primary text-xs font-bold rounded-xl shadow-sm flex items-center space-x-1.5"
            >
              <FolderPlus className="w-3.5 h-3.5" />
              <span>Import Selected to LocalLift</span>
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-y border-slate-200 text-slate-600 font-bold">
                <tr>
                  <th className="py-2.5 px-3">Location Name</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Address</th>
                  <th className="py-2.5 px-3">Website</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {discoveredResources.gbp_locations.map((loc) => (
                  <tr key={loc.location_id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-2.5 px-3 font-bold text-slate-900">
                      <div className="flex items-center space-x-2">
                        <span>{loc.location_name}</span>
                        {loc.maps_uri && (
                          <a
                            href={loc.maps_uri}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-slate-400 hover:text-purple-600"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-slate-600">{loc.category || 'Local Business'}</td>
                    <td className="py-2.5 px-3 text-slate-600">{loc.address || `${loc.city || ''}, ${loc.state || ''}`}</td>
                    <td className="py-2.5 px-3">
                      {loc.website_url ? (
                        <a
                          href={loc.website_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-purple-600 hover:underline flex items-center space-x-1"
                        >
                          <Globe className="w-3 h-3 text-slate-400" />
                          <span className="truncate max-w-[140px]">{loc.website_url.replace(/^https?:\/\//, '')}</span>
                        </a>
                      ) : (
                        <span className="text-slate-400 italic">No website found</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      {loc.already_imported ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          <span>Imported</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800">
                          Available to Import
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Public Google Maps Monitoring Section */}
      <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl shadow-sm bg-white space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Eye className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-black text-slate-900">Public Google Maps Monitoring</h3>
                <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
                  Non-Owned Businesses
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Track competitors or un-owned client listings using legitimate public Maps links. Owner controls (replying, editing profile) are strictly restricted.
              </p>
            </div>
          </div>

          <button
            onClick={() => setShowMapsModal(true)}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 shrink-0"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Business from Maps</span>
          </button>
        </div>

        {/* Public Listings Table */}
        {publicListings.length === 0 ? (
          <div className="text-center py-6 border border-dashed border-slate-200 rounded-xl bg-slate-50/50 space-y-2">
            <MapPin className="w-6 h-6 text-slate-400 mx-auto" />
            <div className="text-xs font-bold text-slate-700">No Public Listings Being Monitored</div>
            <p className="text-[11px] text-slate-400 max-w-sm mx-auto">
              Add competitor businesses or prospective client listings via Google Maps link to monitor their public rankings, review count, and NAP integrity.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-y border-slate-200 text-slate-600 font-bold">
                <tr>
                  <th className="py-2.5 px-3">Monitored Business</th>
                  <th className="py-2.5 px-3">Mode</th>
                  <th className="py-2.5 px-3">Category / Address</th>
                  <th className="py-2.5 px-3">Public Rating</th>
                  <th className="py-2.5 px-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {publicListings.map((pub) => (
                  <tr key={pub.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-2.5 px-3 font-bold text-slate-900">
                      <div className="flex items-center space-x-2">
                        <span>{pub.name}</span>
                        {pub.maps_url && (
                          <a
                            href={pub.maps_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-slate-400 hover:text-blue-600"
                            title="Open in Google Maps"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
                        <Lock className="w-2.5 h-2.5 text-blue-500" />
                        <span>Public Monitoring</span>
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-600">
                      <div className="font-semibold text-slate-800">{pub.primary_category || 'Local Business'}</div>
                      <div className="text-[11px] text-slate-400 truncate max-w-xs">{pub.formatted_address || 'Address unlisted'}</div>
                    </td>
                    <td className="py-2.5 px-3 text-slate-700 font-medium">
                      {(() => {
                        if (pub.rating != null && pub.review_count != null) {
                          return <span>{pub.rating} ★ ({pub.review_count} {pub.review_count === 1 ? 'review' : 'reviews'})</span>;
                        }
                        if (pub.rating != null) {
                          return <span>{pub.rating} ★ (Unknown reviews)</span>;
                        }
                        if (pub.review_count != null) {
                          return <span>{pub.review_count} {pub.review_count === 1 ? 'review' : 'reviews'} (Rating unknown)</span>;
                        }
                        return <span className="text-slate-400 italic">Unknown / Pending crawl</span>;
                      })()}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="text-[10px] text-slate-400 italic">Owner actions disabled</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* MODAL: Import Discovered Resources */}
      {showImportModal && discoveredResources && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-black text-slate-900 flex items-center space-x-2">
                <FolderPlus className="w-5 h-5 text-purple-600" />
                <span>Import Google Business Profiles</span>
              </h3>
              <button
                onClick={() => setShowImportModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Select which discovered Google Business Profiles you want to automatically import as LocalLift projects and websites.
            </p>

            <div className="max-h-60 overflow-y-auto space-y-2 border border-slate-100 rounded-xl p-2 bg-slate-50/50">
              {discoveredResources.gbp_locations.map((loc) => (
                <label
                  key={loc.location_id}
                  className="flex items-start space-x-3 p-2.5 rounded-lg bg-white border border-slate-200/80 hover:border-purple-300 cursor-pointer transition-all"
                >
                  <input
                    type="checkbox"
                    checked={!!selectedLocations[loc.location_id]}
                    onChange={(e) =>
                      setSelectedLocations({
                        ...selectedLocations,
                        [loc.location_id]: e.target.checked
                      })
                    }
                    className="mt-0.5 rounded border-slate-300 text-purple-600 focus:ring-purple-500"
                  />
                  <div className="flex-1 text-xs">
                    <div className="font-bold text-slate-900">{loc.location_name}</div>
                    <div className="text-[11px] text-slate-500">
                      {loc.address || `${loc.city || ''}, ${loc.state || ''}`} • {loc.website_url || 'No website'}
                    </div>
                  </div>
                </label>
              ))}
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                onClick={() => setShowImportModal(false)}
                className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleImportResources}
                disabled={importing}
                className="px-5 py-2 btn-vibrant-primary text-xs font-bold rounded-xl shadow-md transition-all flex items-center space-x-1.5"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>{importing ? 'Importing...' : 'Import Selected'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Add Business from Google Maps (Public Monitoring) */}
      {showMapsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-black text-slate-900 flex items-center space-x-2">
                <MapPin className="w-5 h-5 text-blue-600" />
                <span>Add Business from Google Maps</span>
              </h3>
              <button
                onClick={() => setShowMapsModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddPublicMaps} className="space-y-3.5 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  Google Maps URL <span className="text-rose-500">*</span>
                </label>
                <input
                  type="url"
                  required
                  value={mapsUrl}
                  onChange={(e) => setMapsUrl(e.target.value)}
                  placeholder="https://www.google.com/maps/place/..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
                <p className="text-[10px] text-slate-400 mt-1">
                  Paste the public Google Maps share link, place link, or CID URL.
                </p>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  Business Name (Optional override)
                </label>
                <input
                  type="text"
                  value={mapsName}
                  onChange={(e) => setMapsName(e.target.value)}
                  placeholder="Leave blank to auto-detect from URL"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  Industry / Category (Optional)
                </label>
                <input
                  type="text"
                  value={mapsCategory}
                  onChange={(e) => setMapsCategory(e.target.value)}
                  placeholder="e.g. Dental Clinic, Plumbing"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl text-[11px] text-blue-800 space-y-1">
                <div className="font-bold flex items-center space-x-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
                  <span>Public Monitoring Mode</span>
                </div>
                <p>
                  No owner credentials required. LocalLift imports public ranking, review signals, and NAP records without violating Google access permissions.
                </p>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowMapsModal(false)}
                  className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingMaps}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-md transition-all flex items-center space-x-1.5"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>{submittingMaps ? 'Importing...' : 'Add Business'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

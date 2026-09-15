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
  SingleServiceStatus,
  DiscoveredResourcesResponse,
  PublicBusinessListingItem
} from '../types';
import { normalizeExternalUrl } from '../utils/url';

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

  // Per-service specific error messages
  const [serviceErrors, setServiceErrors] = useState<Record<string, string | null>>({
    business_profile: null,
    google_ads: null,
    search_console: null,
    analytics: null
  });

  // Modal & action state
  const [showMapsModal, setShowMapsModal] = useState<boolean>(false);
  const [showImportModal, setShowImportModal] = useState<boolean>(false);
  const [mapsUrl, setMapsUrl] = useState<string>('');
  const [mapsName, setMapsName] = useState<string>('');
  const [mapsCategory, setMapsCategory] = useState<string>('');
  const [submittingMaps, setSubmittingMaps] = useState<boolean>(false);
  const [disconnectingService, setDisconnectingService] = useState<string | null>(null);

  // Selected GBP locations for import
  const [selectedLocations, setSelectedLocations] = useState<Record<string, boolean>>({});

  // Property mapping state for active project
  const [activeGscProperty, setActiveGscProperty] = useState<string | null>(null);
  const [activeGa4Property, setActiveGa4Property] = useState<{ property_id: string; display_name: string } | null>(null);
  const [mappingGsc, setMappingGsc] = useState<boolean>(false);
  const [mappingGa4, setMappingGa4] = useState<boolean>(false);
  const [selectedGscUrl, setSelectedGscUrl] = useState<string>('');
  const [selectedGa4PropId, setSelectedGa4PropId] = useState<string>('');

  useEffect(() => {
    if (!activeProject) return;
    const fetchMappedProperties = async () => {
      try {
        const [gscRes, ga4Res] = await Promise.allSettled([
          api.get(`/google/gsc/${activeProject.id}`),
          api.get(`/google/ga4/${activeProject.id}`)
        ]);
        if (gscRes.status === 'fulfilled' && gscRes.value.data?.mapped_property) {
          setActiveGscProperty(gscRes.value.data.mapped_property.site_url);
        }
        if (ga4Res.status === 'fulfilled' && ga4Res.value.data?.mapped_property) {
          setActiveGa4Property({
            property_id: ga4Res.value.data.mapped_property.property_id,
            display_name: ga4Res.value.data.mapped_property.display_name || ga4Res.value.data.mapped_property.property_id
          });
        }
      } catch (e) {
        console.warn('Could not load project mapped properties:', e);
      }
    };
    fetchMappedProperties();
  }, [activeProject?.id]);

  const handleMapGscProperty = async (siteUrl: string) => {
    if (!activeProject || !siteUrl) return;
    setMappingGsc(true);
    setErrorMsg(null);
    try {
      await api.post('/connections/gsc/map-property', {
        project_id: activeProject.id,
        site_url: siteUrl
      });
      setActiveGscProperty(siteUrl);
      setSuccessMsg(`Mapped Search Console property "${siteUrl}" to ${activeProject.name}.`);
    } catch (e: any) {
      setErrorMsg(getErrorMessage(e, 'Failed to map Search Console property.'));
    } finally {
      setMappingGsc(false);
    }
  };

  const handleMapGa4Property = async (propId: string) => {
    if (!activeProject || !propId) return;
    const propObj = discoveredResources?.ga4_properties?.find(p => p.property_id === propId);
    setMappingGa4(true);
    setErrorMsg(null);
    try {
      await api.post('/connections/ga4/map-property', {
        project_id: activeProject.id,
        property_id: propId,
        display_name: propObj?.property_name || propId
      });
      setActiveGa4Property({
        property_id: propId,
        display_name: propObj?.property_name || propId
      });
      setSuccessMsg(`Mapped Google Analytics 4 property "${propObj?.property_name || propId}" to ${activeProject.name}.`);
    } catch (e: any) {
      setErrorMsg(getErrorMessage(e, 'Failed to map Google Analytics 4 property.'));
    } finally {
      setMappingGa4(false);
    }
  };

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

      const anyConn =
        statusRes.data.business_profile?.connected ||
        statusRes.data.google_ads?.connected ||
        statusRes.data.search_console?.connected ||
        statusRes.data.analytics?.connected ||
        statusRes.data.connected ||
        statusRes.data.is_connected;

      if (anyConn) {
        try {
          const discRes = await api.post<DiscoveredResourcesResponse>('/connections/google/discover');
          setDiscoveredResources(discRes.data);

          const initialSelected: Record<string, boolean> = {};
          (discRes.data.gbp_locations || []).forEach((loc) => {
            if (!loc.already_imported) {
              initialSelected[loc.location_id] = true;
            }
          });
          setSelectedLocations(initialSelected);
        } catch (discErr) {
          console.warn('Google discovery notice:', discErr);
        }
      }
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to load Google connection settings.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const googleService = params.get('google_service') || params.get('service');
    const googleStatus = params.get('status') || params.get('google');
    const msg = params.get('message');

    if (googleService && googleStatus === 'success') {
      const formattedName =
        googleService === 'business_profile'
          ? 'Google Business Profile'
          : googleService === 'google_ads'
          ? 'Google Ads'
          : googleService === 'search_console'
          ? 'Google Search Console'
          : googleService === 'analytics'
          ? 'Google Analytics 4'
          : 'Google Service';
      setSuccessMsg(`${formattedName} connected successfully.`);
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (googleStatus === 'success') {
      setSuccessMsg('Google Service connected successfully.');
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (googleStatus === 'error') {
      const targetService = googleService || 'general';
      const decodedErr = msg ? decodeURIComponent(msg) : 'Authorization failed or was cancelled.';
      if (googleService && serviceErrors.hasOwnProperty(googleService)) {
        setServiceErrors((prev) => ({ ...prev, [googleService]: decodedErr }));
      } else {
        setErrorMsg(decodedErr);
      }
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    fetchConnectionData();
  }, []);

  const handleStartOAuthForService = async (serviceKey: string) => {
    setServiceErrors((prev) => ({ ...prev, [serviceKey]: null }));
    setErrorMsg(null);
    try {
      const res = await api.get<{ auth_url: string; service: string }>(
        `/connections/google/${serviceKey}/auth-url`
      );
      if (res.data.auth_url) {
        window.location.href = res.data.auth_url;
      }
    } catch (err: any) {
      const errTxt = getErrorMessage(err, `Failed to initiate OAuth for ${serviceKey}.`);
      setServiceErrors((prev) => ({ ...prev, [serviceKey]: errTxt }));
    }
  };

  const handleDisconnectService = async (serviceKey: string) => {
    setServiceErrors((prev) => ({ ...prev, [serviceKey]: null }));
    setErrorMsg(null);
    try {
      await api.post(`/connections/google/${serviceKey}/disconnect`);
      setDisconnectingService(null);
      
      const formattedName =
        serviceKey === 'business_profile'
          ? 'Google Business Profile'
          : serviceKey === 'google_ads'
          ? 'Google Ads'
          : serviceKey === 'search_console'
          ? 'Google Search Console'
          : 'Google Analytics 4';

      setSuccessMsg(`${formattedName} disconnected successfully.`);
      await fetchConnectionData();
    } catch (err: any) {
      const errTxt = getErrorMessage(err, `Failed to disconnect ${serviceKey}.`);
      setServiceErrors((prev) => ({ ...prev, [serviceKey]: errTxt }));
    }
  };

  const handleSyncNow = async () => {
    setSyncing(true);
    setErrorMsg(null);
    try {
      await api.post('/connections/google/sync');
      setSuccessMsg('Connected Google services synchronized successfully.');
      await fetchConnectionData();
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Synchronization failed.'));
    } finally {
      setSyncing(false);
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

      const res = await api.post<{ created_projects_count: number; message: string }>(
        '/connections/google/import-resources',
        {
          selected_gbp_locations: selectedLocList,
          create_new_projects: true
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
          <span>Loading independent Google service connections...</span>
        </div>
      </div>
    );
  }

  // Individual service status references
  const bpStatus: SingleServiceStatus = connectionStatus?.business_profile || {
    connected: false,
    status: 'disconnected'
  };
  const adsStatus: SingleServiceStatus = connectionStatus?.google_ads || {
    connected: false,
    status: 'disconnected'
  };
  const gscStatus: SingleServiceStatus = connectionStatus?.search_console || {
    connected: false,
    status: 'disconnected'
  };
  const ga4Status: SingleServiceStatus = connectionStatus?.analytics || {
    connected: false,
    status: 'disconnected'
  };

  const anyConnected =
    bpStatus.connected || adsStatus.connected || gscStatus.connected || ga4Status.connected;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-black text-slate-900 flex items-center space-x-2">
            <Link2 className="w-5 h-5 text-purple-600" />
            <span>Google Services</span>
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Connect only the Google services your organization uses. Each service is authorized independently.
          </p>
        </div>
        {anyConnected && (
          <div className="flex items-center space-x-2">
            <button
              onClick={handleSyncNow}
              disabled={syncing}
              className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
              <span>{syncing ? 'Syncing...' : 'Sync All Connected Services'}</span>
            </button>
            {discoveredResources && discoveredResources.gbp_locations.length > 0 && (
              <button
                onClick={() => setShowImportModal(true)}
                className="px-3.5 py-2 bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5"
              >
                <FolderPlus className="w-3.5 h-3.5 text-purple-600" />
                <span>Import Resources</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Global Notifications */}
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

      {/* 4 INDEPENDENT GOOGLE SERVICE CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* CARD 1 — GOOGLE BUSINESS PROFILE */}
        <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl shadow-sm bg-white flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
                  <Store className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-black text-slate-900">Google Business Profile</h3>
                </div>
              </div>
              {bpStatus.connected ? (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  <span>Connected</span>
                </span>
              ) : (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-black bg-slate-100 text-slate-600 border border-slate-200">
                  <span>Not Connected</span>
                </span>
              )}
            </div>

            <p className="text-xs text-slate-500 leading-relaxed">
              Manage locations, reviews, search visibility, and Business Profile insights.
            </p>

            {bpStatus.connected && bpStatus.google_email && (
              <div className="p-2.5 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-600 flex items-center space-x-1.5">
                <span className="text-slate-400 font-medium">Connected account:</span>
                <span className="font-bold text-slate-800">{bpStatus.google_email}</span>
              </div>
            )}

            {serviceErrors.business_profile && (
              <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-start space-x-2">
                <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0 mt-0.5" />
                <div className="flex-1">{serviceErrors.business_profile}</div>
              </div>
            )}
          </div>

          <div className="pt-2 border-t border-slate-100 flex items-center justify-end space-x-2">
            {bpStatus.connected ? (
              <>
                <button
                  onClick={() => handleStartOAuthForService('business_profile')}
                  className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-all flex items-center space-x-1"
                >
                  <RotateCw className="w-3.5 h-3.5 text-slate-500" />
                  <span>Reconnect</span>
                </button>
                <button
                  onClick={() => setDisconnectingService('business_profile')}
                  className="px-3.5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold rounded-xl transition-all flex items-center space-x-1"
                >
                  <Trash2 className="w-3.5 h-3.5 text-rose-600" />
                  <span>Disconnect</span>
                </button>
              </>
            ) : (
              <button
                onClick={() => handleStartOAuthForService('business_profile')}
                className="w-full sm:w-auto px-4 py-2.5 btn-vibrant-primary text-xs font-bold rounded-xl shadow-sm transition-all flex items-center justify-center space-x-2"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Connect Business Profile</span>
              </button>
            )}
          </div>
        </div>

        {/* CARD 2 — GOOGLE ADS */}
        <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl shadow-sm bg-white flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-black text-slate-900">Google Ads</h3>
                </div>
              </div>
              {adsStatus.connected ? (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  <span>Connected</span>
                </span>
              ) : (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-black bg-slate-100 text-slate-600 border border-slate-200">
                  <span>Not Connected</span>
                </span>
              )}
            </div>

            <p className="text-xs text-slate-500 leading-relaxed">
              Access campaigns, advertising spend, conversions, and account telemetry.
            </p>

            {adsStatus.connected && adsStatus.google_email && (
              <div className="p-2.5 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-600 flex items-center space-x-1.5">
                <span className="text-slate-400 font-medium">Connected account:</span>
                <span className="font-bold text-slate-800">{adsStatus.google_email}</span>
              </div>
            )}

            {serviceErrors.google_ads && (
              <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-start space-x-2">
                <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0 mt-0.5" />
                <div className="flex-1">{serviceErrors.google_ads}</div>
              </div>
            )}
          </div>

          <div className="pt-2 border-t border-slate-100 flex items-center justify-end space-x-2">
            {adsStatus.connected ? (
              <>
                <button
                  onClick={() => handleStartOAuthForService('google_ads')}
                  className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-all flex items-center space-x-1"
                >
                  <RotateCw className="w-3.5 h-3.5 text-slate-500" />
                  <span>Reconnect</span>
                </button>
                <button
                  onClick={() => setDisconnectingService('google_ads')}
                  className="px-3.5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold rounded-xl transition-all flex items-center space-x-1"
                >
                  <Trash2 className="w-3.5 h-3.5 text-rose-600" />
                  <span>Disconnect</span>
                </button>
              </>
            ) : (
              <button
                onClick={() => handleStartOAuthForService('google_ads')}
                className="w-full sm:w-auto px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-sm transition-all flex items-center justify-center space-x-2"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Connect Google Ads</span>
              </button>
            )}
          </div>
        </div>

        {/* CARD 3 — GOOGLE SEARCH CONSOLE */}
        <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl shadow-sm bg-white flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
                  <Search className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-black text-slate-900">Google Search Console</h3>
                </div>
              </div>
              {gscStatus.connected ? (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  <span>Connected</span>
                </span>
              ) : (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-black bg-slate-100 text-slate-600 border border-slate-200">
                  <span>Not Connected</span>
                </span>
              )}
            </div>

            <p className="text-xs text-slate-500 leading-relaxed">
              Access search queries, clicks, impressions, CTR, and organic search performance.
            </p>

            {gscStatus.connected && gscStatus.google_email && (
              <div className="p-2.5 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-600 flex items-center space-x-1.5">
                <span className="text-slate-400 font-medium">Connected account:</span>
                <span className="font-bold text-slate-800">{gscStatus.google_email}</span>
              </div>
            )}

            {gscStatus.connected && (
              <div className="space-y-2 pt-2 border-t border-slate-100">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-700">Active Project Property:</span>
                  {activeGscProperty ? (
                    <span className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-mono font-bold truncate max-w-[200px]" title={activeGscProperty}>
                      {activeGscProperty}
                    </span>
                  ) : (
                    <span className="text-xs text-amber-600 font-medium">No property mapped</span>
                  )}
                </div>

                {discoveredResources && (discoveredResources.gsc_properties?.length || 0) > 0 && (
                  <div className="flex items-center gap-2 pt-1">
                    <select
                      value={selectedGscUrl || activeGscProperty || ''}
                      onChange={(e) => setSelectedGscUrl(e.target.value)}
                      className="text-xs border border-slate-200 rounded-lg p-1.5 flex-1 bg-white text-slate-800 truncate"
                    >
                      <option value="">-- Select discovered property --</option>
                      {discoveredResources.gsc_properties.map((p) => (
                        <option key={p.site_url} value={p.site_url}>
                          {p.site_url}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => handleMapGscProperty(selectedGscUrl)}
                      disabled={mappingGsc || !selectedGscUrl || selectedGscUrl === activeGscProperty}
                      className="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold whitespace-nowrap"
                    >
                      {mappingGsc ? 'Mapping...' : 'Map to Project'}
                    </button>
                  </div>
                )}
              </div>
            )}

            {serviceErrors.search_console && (
              <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-start space-x-2">
                <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0 mt-0.5" />
                <div className="flex-1">{serviceErrors.search_console}</div>
              </div>
            )}
          </div>

          <div className="pt-2 border-t border-slate-100 flex items-center justify-end space-x-2">
            {gscStatus.connected ? (
              <>
                <button
                  onClick={() => handleStartOAuthForService('search_console')}
                  className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-all flex items-center space-x-1"
                >
                  <RotateCw className="w-3.5 h-3.5 text-slate-500" />
                  <span>Reconnect</span>
                </button>
                <button
                  onClick={() => setDisconnectingService('search_console')}
                  className="px-3.5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold rounded-xl transition-all flex items-center space-x-1"
                >
                  <Trash2 className="w-3.5 h-3.5 text-rose-600" />
                  <span>Disconnect</span>
                </button>
              </>
            ) : (
              <button
                onClick={() => handleStartOAuthForService('search_console')}
                className="w-full sm:w-auto px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-sm transition-all flex items-center justify-center space-x-2"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Connect Search Console</span>
              </button>
            )}
          </div>
        </div>

        {/* CARD 4 — GOOGLE ANALYTICS 4 */}
        <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl shadow-sm bg-white flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
                  <BarChart3 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-black text-slate-900">Google Analytics 4</h3>
                </div>
              </div>
              {ga4Status.connected ? (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-black bg-emerald-100 text-emerald-800 border border-emerald-200">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  <span>Connected</span>
                </span>
              ) : (
                <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[10px] font-black bg-slate-100 text-slate-600 border border-slate-200">
                  <span>Not Connected</span>
                </span>
              )}
            </div>

            <p className="text-xs text-slate-500 leading-relaxed">
              Access website traffic, users, engagement, acquisition, and analytics properties.
            </p>

            {ga4Status.connected && ga4Status.google_email && (
              <div className="p-2.5 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-600 flex items-center space-x-1.5">
                <span className="text-slate-400 font-medium">Connected account:</span>
                <span className="font-bold text-slate-800">{ga4Status.google_email}</span>
              </div>
            )}

            {ga4Status.connected && (
              <div className="space-y-2 pt-2 border-t border-slate-100">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-700">Active Project Property:</span>
                  {activeGa4Property ? (
                    <span className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-mono font-bold truncate max-w-[200px]" title={activeGa4Property.display_name}>
                      {activeGa4Property.display_name}
                    </span>
                  ) : (
                    <span className="text-xs text-amber-600 font-medium">No property mapped</span>
                  )}
                </div>

                {discoveredResources && (discoveredResources.ga4_properties?.length || 0) > 0 && (
                  <div className="flex items-center gap-2 pt-1">
                    <select
                      value={selectedGa4PropId || activeGa4Property?.property_id || ''}
                      onChange={(e) => setSelectedGa4PropId(e.target.value)}
                      className="text-xs border border-slate-200 rounded-lg p-1.5 flex-1 bg-white text-slate-800 truncate"
                    >
                      <option value="">-- Select discovered GA4 property --</option>
                      {discoveredResources.ga4_properties.map((p) => (
                        <option key={p.property_id} value={p.property_id}>
                          {p.property_name || p.property_id}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => handleMapGa4Property(selectedGa4PropId)}
                      disabled={mappingGa4 || !selectedGa4PropId || selectedGa4PropId === activeGa4Property?.property_id}
                      className="px-2.5 py-1.5 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold whitespace-nowrap"
                    >
                      {mappingGa4 ? 'Mapping...' : 'Map to Project'}
                    </button>
                  </div>
                )}
              </div>
            )}

            {serviceErrors.analytics && (
              <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-start space-x-2">
                <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0 mt-0.5" />
                <div className="flex-1">{serviceErrors.analytics}</div>
              </div>
            )}
          </div>

          <div className="pt-2 border-t border-slate-100 flex items-center justify-end space-x-2">
            {ga4Status.connected ? (
              <>
                <button
                  onClick={() => handleStartOAuthForService('analytics')}
                  className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-all flex items-center space-x-1"
                >
                  <RotateCw className="w-3.5 h-3.5 text-slate-500" />
                  <span>Reconnect</span>
                </button>
                <button
                  onClick={() => setDisconnectingService('analytics')}
                  className="px-3.5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-bold rounded-xl transition-all flex items-center space-x-1"
                >
                  <Trash2 className="w-3.5 h-3.5 text-rose-600" />
                  <span>Disconnect</span>
                </button>
              </>
            ) : (
              <button
                onClick={() => handleStartOAuthForService('analytics')}
                className="w-full sm:w-auto px-4 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-xl shadow-sm transition-all flex items-center justify-center space-x-2"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Connect Analytics</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Disconnect Confirmation Alert Modal */}
      {disconnectingService && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl space-y-3">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-xs font-black text-rose-900">
                Confirm Disconnecting {
                  disconnectingService === 'business_profile'
                    ? 'Google Business Profile'
                    : disconnectingService === 'google_ads'
                    ? 'Google Ads'
                    : disconnectingService === 'search_console'
                    ? 'Google Search Console'
                    : 'Google Analytics 4'
                }
              </h4>
              <p className="text-xs text-rose-700 mt-0.5">
                Disconnecting this service will revoke LocalLift's access tokens for only this service. Other connected Google services will remain active and unaffected.
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleDisconnectService(disconnectingService)}
              className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition-all"
            >
              Confirm Disconnect
            </button>
            <button
              onClick={() => setDisconnectingService(null)}
              className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50 transition-all"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Discovered GBP Locations Table (when Business Profile connected) */}
      {discoveredResources && discoveredResources.gbp_locations.length > 0 && (
        <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl shadow-sm bg-white space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
                <Store className="w-4 h-4 text-purple-600" />
                <span>Discovered Google Business Profiles ({discoveredResources.gbp_locations.length})</span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Verified locations available from your connected Google Business Profile account.
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
                        {loc.maps_uri && normalizeExternalUrl(loc.maps_uri) && (
                          <a
                            href={normalizeExternalUrl(loc.maps_uri)!}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-slate-400 hover:text-purple-600"
                            aria-label="View on Google Maps"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-slate-600">{loc.category || 'Local Business'}</td>
                    <td className="py-2.5 px-3 text-slate-600">{loc.address || `${loc.city || ''}, ${loc.state || ''}`}</td>
                    <td className="py-2.5 px-3">
                      {loc.website_url && normalizeExternalUrl(loc.website_url) ? (
                        <a
                          href={normalizeExternalUrl(loc.website_url)!}
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

      {/* Discovered Search Console Properties Table */}
      {discoveredResources && (discoveredResources.gsc_properties?.length || 0) > 0 && (
        <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl shadow-sm bg-white space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
                <Search className="w-4 h-4 text-emerald-600" />
                <span>Discovered Search Console Properties ({discoveredResources.gsc_properties.length})</span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Verified Search Console web properties available to map directly to your LocalLift projects.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-y border-slate-200 text-slate-600 font-bold">
                <tr>
                  <th className="py-2.5 px-3">Site URL</th>
                  <th className="py-2.5 px-3">Permission Level</th>
                  <th className="py-2.5 px-3">Active Mapping</th>
                  <th className="py-2.5 px-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {discoveredResources.gsc_properties.map((p) => {
                  const isMappedToActive = activeGscProperty === p.site_url;
                  return (
                    <tr key={p.site_url} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-2.5 px-3 font-bold font-mono text-slate-900 truncate max-w-sm">
                        {p.site_url}
                      </td>
                      <td className="py-2.5 px-3 text-slate-600 uppercase font-mono text-[10px]">
                        {p.permission_level || 'siteOwner'}
                      </td>
                      <td className="py-2.5 px-3">
                        {isMappedToActive ? (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            <span>Active Project ({activeProject?.name})</span>
                          </span>
                        ) : p.project_id ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600">
                            Mapped to Project #{p.project_id}
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Unmapped</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        <button
                          onClick={() => handleMapGscProperty(p.site_url)}
                          disabled={mappingGsc || isMappedToActive || !activeProject}
                          className="px-3 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-lg text-xs font-bold disabled:opacity-40"
                        >
                          {isMappedToActive ? 'Mapped' : 'Map to Current Project'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Discovered GA4 Properties Table */}
      {discoveredResources && (discoveredResources.ga4_properties?.length || 0) > 0 && (
        <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl shadow-sm bg-white space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
                <BarChart3 className="w-4 h-4 text-amber-600" />
                <span>Discovered Google Analytics 4 Properties ({discoveredResources.ga4_properties.length})</span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Google Analytics 4 reporting properties available for organic conversion and visitor tracking.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-y border-slate-200 text-slate-600 font-bold">
                <tr>
                  <th className="py-2.5 px-3">Property Name</th>
                  <th className="py-2.5 px-3">Property ID</th>
                  <th className="py-2.5 px-3">Active Mapping</th>
                  <th className="py-2.5 px-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {discoveredResources.ga4_properties.map((p) => {
                  const isMappedToActive = activeGa4Property?.property_id === p.property_id;
                  return (
                    <tr key={p.property_id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-2.5 px-3 font-bold text-slate-900">
                        {p.property_name || `Property ${p.property_id}`}
                      </td>
                      <td className="py-2.5 px-3 text-slate-600 font-mono text-[11px]">
                        {p.property_id}
                      </td>
                      <td className="py-2.5 px-3">
                        {isMappedToActive ? (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            <span>Active Project ({activeProject?.name})</span>
                          </span>
                        ) : p.project_id ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600">
                            Mapped to Project #{p.project_id}
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Unmapped</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        <button
                          onClick={() => handleMapGa4Property(p.property_id)}
                          disabled={mappingGa4 || isMappedToActive || !activeProject}
                          className="px-3 py-1 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 rounded-lg text-xs font-bold disabled:opacity-40"
                        >
                          {isMappedToActive ? 'Mapped' : 'Map to Current Project'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

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
                        {pub.maps_url && normalizeExternalUrl(pub.maps_url) && (
                          <a
                            href={normalizeExternalUrl(pub.maps_url)!}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-slate-400 hover:text-blue-600"
                            aria-label="Open in Google Maps"
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

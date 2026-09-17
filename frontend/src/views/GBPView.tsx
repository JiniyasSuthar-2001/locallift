import React, { useState, useEffect } from 'react';
import {
  Store,
  RotateCw,
  CheckCircle2,
  Phone,
  Globe,
  MapPin,
  ExternalLink,
  ShieldCheck,
  Link,
  Unlink,
  AlertCircle,
  Eye,
  Info,
  Search,
  Key
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';
import { getErrorMessage } from '../utils/error';

interface PublicProfileData {
  source: string;
  lookup_status: string;
  lookup_error: string | null;
  place_id: string | null;
  business_name: string | null;
  formatted_address: string | null;
  address_components: any[] | null;
  phone: string | null;
  website_url: string | null;
  category: string | null;
  business_status: string | null;
  rating: number | null;
  review_count: number | null;
  opening_hours: any | null;
  latitude: number | null;
  longitude: number | null;
  maps_url: string | null;
  checked_at: string | null;
  completeness_score: number | null;
  completeness_label: string;
}

interface OwnerProfileData {
  is_connected: boolean;
  status: string;
  account_email: string | null;
  last_synced_at: string | null;
  profile: {
    business_name: string | null;
    primary_category: string | null;
    address: string | null;
    phone: string | null;
    website_url: string | null;
    search_impressions: number | null;
    maps_impressions: number | null;
    call_clicks: number | null;
    website_clicks: number | null;
  } | null;
}

export const GBPView: React.FC = () => {
  const { activeProject, refreshDashboard } = useProject();

  // System A: Public Profile State
  const [publicProfile, setPublicProfile] = useState<PublicProfileData | null>(null);
  const [searchName, setSearchName] = useState('');
  const [searchLocation, setSearchLocation] = useState('');
  const [mapsUrlInput, setMapsUrlInput] = useState('');
  const [isSearchingPublic, setIsSearchingPublic] = useState(false);
  const [publicLookupError, setPublicLookupError] = useState<string | null>(null);

  // System B: Owner Profile State
  const [ownerData, setOwnerData] = useState<OwnerProfileData | null>(null);
  const [isSyncingOwner, setIsSyncingOwner] = useState(false);
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [isOAuthConfigured, setIsOAuthConfigured] = useState<boolean>(true);
  const [ownerFeedback, setOwnerFeedback] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);

  const fetchAllData = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const [pubRes, ownerRes, authRes] = await Promise.allSettled([
        api.get(`/gbp/${activeProject.id}/public-profile`),
        api.get(`/gbp/${activeProject.id}/owner-profile`),
        api.get(`/gbp/${activeProject.id}/auth-url`)
      ]);

      if (pubRes.status === 'fulfilled') {
        setPublicProfile(pubRes.value.data);
      }
      if (ownerRes.status === 'fulfilled') {
        setOwnerData(ownerRes.value.data);
      }
      if (authRes.status === 'fulfilled') {
        setAuthUrl(authRes.value.data?.auth_url);
        setIsOAuthConfigured(authRes.value.data?.is_configured);
      }
    } catch (e) {
      console.error('Failed to load GBP profiles:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeProject) {
      setSearchName(activeProject.name || '');
      setSearchLocation(activeProject.country || '');
    }
    fetchAllData();
  }, [activeProject?.id]);

  const handlePublicSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject) return;
    if (!searchName.trim() && !searchLocation.trim()) return;

    setIsSearchingPublic(true);
    setPublicLookupError(null);
    try {
      const resp = await api.post(`/gbp/${activeProject.id}/public-lookup`, {
        business_name: searchName.trim(),
        location: searchLocation.trim()
      });
      setPublicProfile(resp.data);
      if (resp.data.lookup_status !== 'found') {
        setPublicLookupError(resp.data.lookup_error || `Lookup status: ${resp.data.lookup_status}`);
      }
    } catch (err: any) {
      setPublicLookupError(getErrorMessage(err, 'Public Google Places lookup failed.'));
    } finally {
      setIsSearchingPublic(false);
    }
  };

  const handleMapsUrlImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !mapsUrlInput.trim()) return;

    setIsSearchingPublic(true);
    setPublicLookupError(null);
    try {
      const resp = await api.post(`/gbp/${activeProject.id}/public-lookup`, {
        maps_url: mapsUrlInput.trim()
      });
      setPublicProfile(resp.data);
      if (resp.data.lookup_status !== 'found') {
        setPublicLookupError(resp.data.lookup_error || `URL resolution status: ${resp.data.lookup_status}`);
      } else {
        setMapsUrlInput('');
      }
    } catch (err: any) {
      setPublicLookupError(getErrorMessage(err, 'Failed to import Google Maps URL.'));
    } finally {
      setIsSearchingPublic(false);
    }
  };

  const handleConnectGoogle = () => {
    if (authUrl) {
      window.location.href = authUrl;
    } else {
      setOwnerFeedback('Google OAuth credentials are not configured in settings. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your backend environment configuration.');
    }
  };

  const handleSyncOwnerData = async () => {
    if (!activeProject) return;
    try {
      setIsSyncingOwner(true);
      setOwnerFeedback(null);
      const res = await api.post(`/gbp/${activeProject.id}/sync`);
      setOwnerFeedback(`Sync complete: ${res.data.profiles_synced} profile(s) synced.`);
      await fetchAllData();
      await refreshDashboard();
    } catch (e: any) {
      setOwnerFeedback(getErrorMessage(e, 'GBP sync failed. Please ensure Google Account is connected.'));
    } finally {
      setIsSyncingOwner(false);
      setTimeout(() => setOwnerFeedback(null), 6000);
    }
  };

  const handleDisconnectOwner = async () => {
    if (!activeProject) return;
    if (!confirm('Are you sure you want to disconnect Google Business Profile owner connection? Public profile information above will remain available.')) return;
    try {
      await api.post(`/gbp/${activeProject.id}/disconnect`);
      setOwnerData(null);
      await fetchAllData();
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
        description="Select an active project to view Google Business Profile public data and owner-authorized performance metrics."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div>
        <h1 className="text-2xl font-black text-[#142820] tracking-tight flex items-center space-x-2.5">
          <Store className="w-6 h-6 text-[#236B4F]" />
          <span>Google Business Profile</span>
        </h1>
        <p className="text-xs text-[#587568] mt-1">
          Public Google business information can be checked without connecting Google.
        </p>
      </div>

      {/* ========================================================================= */}
      {/* SYSTEM A: PUBLIC GOOGLE PROFILE CARD (NO OAUTH REQUIRED)                   */}
      {/* ========================================================================= */}
      <div className="card-nature p-6 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#EBF2EB] pb-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-[#EAF2EA] text-[#142820] border border-[#B8DFC9]">
                Public Google Profile
              </span>
              <span className="text-xs font-semibold text-[#587568] flex items-center space-x-1">
                <Eye className="w-3.5 h-3.5 text-[#236B4F]" />
                <span>No Google connection required</span>
              </span>
            </div>
            <h2 className="text-lg font-black text-[#142820] mt-1">
              Public Business Information (Google Places API)
            </h2>
          </div>

          {/* Completeness Score Badge (Measured strictly from retrieved fields, or "Not measured") */}
          <div className="bg-[#F7FAF7] border border-[#DCE8DC] p-3.5 rounded-2xl flex items-center space-x-3 shrink-0">
            <div>
              <span className="text-[10px] font-bold uppercase text-[#587568] block">Public Completeness</span>
              <span className="text-xl font-black text-[#142820]">
                {publicProfile?.completeness_score !== null && publicProfile?.completeness_score !== undefined
                  ? `${publicProfile.completeness_score}%`
                  : 'Not measured'}
              </span>
              <span className="text-[9px] text-[#587568] block mt-0.5">
                {publicProfile?.completeness_label || 'Not measured'}
              </span>
            </div>
            <div className="w-9 h-9 rounded-xl bg-[#EAF2EA] border border-[#B8DFC9] flex items-center justify-center text-[#236B4F] font-bold">
              <ShieldCheck className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Search & Import Input Forms */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          {/* Form 1: Search by Name & Location */}
          <form onSubmit={handlePublicSearch} className="p-4 bg-[#F7FAF7] border border-[#DCE8DC] rounded-xl space-y-3">
            <h4 className="text-xs font-bold text-[#142820] uppercase tracking-wider flex items-center space-x-1.5">
              <Search className="w-3.5 h-3.5 text-[#236B4F]" />
              <span>Find by Name & Location</span>
            </h4>
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Business Name (e.g. Acme Plumbing)"
                value={searchName}
                onChange={(e) => setSearchName(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-[#B8DFC9] bg-white text-[#142820] focus:ring-2 focus:ring-[#236B4F] focus:outline-none"
              />
              <input
                type="text"
                placeholder="Location (e.g. Sydney, NSW)"
                value={searchLocation}
                onChange={(e) => setSearchLocation(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-[#B8DFC9] bg-white text-[#142820] focus:ring-2 focus:ring-[#236B4F] focus:outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={isSearchingPublic || (!searchName.trim() && !searchLocation.trim())}
              className="w-full btn-primary-nature py-2 rounded-xl text-xs font-bold flex items-center justify-center space-x-2"
            >
              <Search className={`w-3.5 h-3.5 ${isSearchingPublic ? 'animate-spin' : ''}`} />
              <span>{isSearchingPublic ? 'Searching Google...' : 'Find Google Business Profile'}</span>
            </button>
          </form>

          {/* Form 2: Import by Google Maps URL */}
          <form onSubmit={handleMapsUrlImport} className="p-4 bg-[#F7FAF7] border border-[#DCE8DC] rounded-xl space-y-3">
            <h4 className="text-xs font-bold text-[#142820] uppercase tracking-wider flex items-center space-x-1.5">
              <Globe className="w-3.5 h-3.5 text-[#236B4F]" />
              <span>Import by Google Maps URL</span>
            </h4>
            <div className="space-y-2">
              <input
                type="url"
                placeholder="https://maps.google.com/?cid=... or https://maps.app.goo.gl/..."
                value={mapsUrlInput}
                onChange={(e) => setMapsUrlInput(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-[#B8DFC9] bg-white text-[#142820] focus:ring-2 focus:ring-[#236B4F] focus:outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={isSearchingPublic || !mapsUrlInput.trim()}
              className="w-full btn-secondary-nature py-2 rounded-xl text-xs font-bold flex items-center justify-center space-x-2"
            >
              <Globe className={`w-3.5 h-3.5 text-[#236B4F] ${isSearchingPublic ? 'animate-spin' : ''}`} />
              <span>{isSearchingPublic ? 'Resolving Link...' : 'Import Public Profile'}</span>
            </button>
          </form>
        </div>

        {/* Lookup Error Feedback */}
        {publicLookupError && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center space-x-2 font-medium">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{publicLookupError}</span>
          </div>
        )}

        {/* Display Actual Retrieved Google Public Profile */}
        {publicProfile && publicProfile.lookup_status === 'found' ? (
          <div className="p-5 bg-white border border-[#B8DFC9] rounded-2xl space-y-4 shadow-xs">
            <div className="flex items-center justify-between border-b border-[#EBF2EB] pb-3">
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span className="text-xs font-bold text-[#142820]">Public Google Profile Found</span>
              </div>
              <span className="text-[10px] text-[#587568] font-mono">
                Source: Google Places API • Last checked: {publicProfile.checked_at ? new Date(publicProfile.checked_at).toLocaleString() : 'Just now'}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Business Name</span>
                <span className="font-extrabold text-[#142820]">{publicProfile.business_name || 'Not available'}</span>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Category</span>
                <span className="font-semibold text-[#142820]">{publicProfile.category || 'Not available'}</span>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Business Status</span>
                <span className="font-semibold text-emerald-700">{publicProfile.business_status || 'Not available'}</span>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Formatted Address</span>
                <span className="font-medium text-[#142820]">{publicProfile.formatted_address || 'Not available'}</span>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Phone Number</span>
                <span className="font-medium text-[#142820]">{publicProfile.phone || 'Not available'}</span>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Website URL</span>
                {publicProfile.website_url ? (
                  <a href={publicProfile.website_url} target="_blank" rel="noopener noreferrer" className="font-medium text-[#236B4F] hover:underline flex items-center space-x-1 truncate">
                    <span className="truncate">{publicProfile.website_url}</span>
                    <ExternalLink className="w-3 h-3 shrink-0 inline" />
                  </a>
                ) : (
                  <span className="font-medium text-[#587568]">Not available</span>
                )}
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Google Rating</span>
                <span className="font-extrabold text-[#142820]">
                  {publicProfile.rating !== null ? `⭐ ${publicProfile.rating} / 5.0` : 'Not available'}
                </span>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Review Count</span>
                <span className="font-extrabold text-[#142820]">
                  {publicProfile.review_count !== null ? `${publicProfile.review_count} reviews` : 'Not available'}
                </span>
              </div>

              <div>
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Place ID</span>
                <span className="font-mono text-[11px] text-[#587568] truncate block">{publicProfile.place_id || 'Not available'}</span>
              </div>

              {publicProfile.latitude !== null && publicProfile.longitude !== null && (
                <div>
                  <span className="text-[10px] font-bold uppercase text-[#587568] block">GPS Coordinates</span>
                  <span className="font-mono text-[11px] text-[#587568]">
                    {publicProfile.latitude}, {publicProfile.longitude}
                  </span>
                </div>
              )}

              {publicProfile.maps_url && (
                <div className="sm:col-span-2">
                  <span className="text-[10px] font-bold uppercase text-[#587568] block">Google Maps Link</span>
                  <a href={publicProfile.maps_url} target="_blank" rel="noopener noreferrer" className="font-medium text-[#236B4F] hover:underline flex items-center space-x-1 truncate">
                    <span className="truncate">{publicProfile.maps_url}</span>
                    <ExternalLink className="w-3 h-3 shrink-0 inline" />
                  </a>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] text-center text-xs text-[#587568]">
            No public Google Place profile resolved yet. Enter a business name/location or paste a Google Maps link above to import genuine Google Places data.
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* SYSTEM B: GOOGLE BUSINESS PROFILE OWNER CONNECTION CARD (REQUIRES OAUTH)   */}
      {/* ========================================================================= */}
      <div className="card-nature p-6 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#EBF2EB] pb-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
                ownerData?.is_connected
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : 'bg-slate-100 text-slate-700 border-slate-200'
              }`}>
                {ownerData?.is_connected ? 'Connected' : 'Not Connected'}
              </span>
              <span className="text-xs font-semibold text-[#587568]">
                OAuth required for owner-authorized performance metrics & review responses
              </span>
            </div>
            <h2 className="text-lg font-black text-[#142820] mt-1">
              Google Business Profile Owner Connection
            </h2>
            {!ownerData?.is_connected && (
              <p className="text-xs text-[#587568] mt-0.5">
                Public Google information is still available above. Connect Google OAuth below to authorize access to private search impressions, call clicks, and owner actions.
              </p>
            )}
          </div>

          <div className="flex items-center space-x-3 shrink-0">
            {ownerData?.is_connected ? (
              <>
                <button
                  type="button"
                  onClick={handleSyncOwnerData}
                  disabled={isSyncingOwner}
                  className="btn-primary-nature px-4 py-2 rounded-xl text-xs font-bold flex items-center space-x-2 shadow-xs"
                >
                  <RotateCw className={`w-3.5 h-3.5 ${isSyncingOwner ? 'animate-spin' : ''}`} />
                  <span>{isSyncingOwner ? 'Syncing...' : 'Sync GBP'}</span>
                </button>

                <button
                  type="button"
                  onClick={handleDisconnectOwner}
                  className="px-3.5 py-2 rounded-xl border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 text-xs font-bold flex items-center space-x-1.5 transition-all"
                >
                  <Unlink className="w-3.5 h-3.5" />
                  <span>Disconnect</span>
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={handleConnectGoogle}
                className="btn-primary-nature px-5 py-2.5 rounded-xl text-xs font-bold shadow-xs flex items-center space-x-2"
              >
                <Link className="w-4 h-4" />
                <span>Connect Google Business Profile</span>
              </button>
            )}
          </div>
        </div>

        {ownerFeedback && (
          <div className="p-3 bg-[#F1F7F1] border border-[#B8DFC9] rounded-xl text-xs text-[#142820] flex items-center space-x-2 font-medium">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{ownerFeedback}</span>
          </div>
        )}

        {/* Owner Account Details & Authorized Performance Metrics */}
        {ownerData?.is_connected ? (
          <div className="space-y-4">
            <div className="p-4 bg-[#F7FAF7] border border-[#DCE8DC] rounded-xl flex items-center justify-between text-xs">
              <div>
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Google Account Email</span>
                <span className="font-bold text-[#142820]">
                  {ownerData.account_email || 'Google account identity unavailable'}
                </span>
              </div>
              <div className="text-right">
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Last Synchronized</span>
                <span className="font-mono text-[#587568]">
                  {ownerData.last_synced_at ? new Date(ownerData.last_synced_at).toLocaleString() : 'Never'}
                </span>
              </div>
            </div>

            {/* Owner Performance KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3.5 rounded-xl bg-white border border-[#B8DFC9]">
                <span className="text-[10px] font-bold uppercase text-[#587568] block">GBP Search Impressions</span>
                <span className="text-xl font-black text-[#142820] mt-0.5 block">
                  {ownerData.profile?.search_impressions !== null && ownerData.profile?.search_impressions !== undefined
                    ? ownerData.profile.search_impressions.toLocaleString()
                    : 'Not available'}
                </span>
                <span className="text-[10px] text-[#587568]">GBP API Search Insights</span>
              </div>

              <div className="p-3.5 rounded-xl bg-white border border-[#B8DFC9]">
                <span className="text-[10px] font-bold uppercase text-[#587568] block">GBP Maps Impressions</span>
                <span className="text-xl font-black text-[#142820] mt-0.5 block">
                  {ownerData.profile?.maps_impressions !== null && ownerData.profile?.maps_impressions !== undefined
                    ? ownerData.profile.maps_impressions.toLocaleString()
                    : 'Not available'}
                </span>
                <span className="text-[10px] text-[#587568]">GBP API Maps Insights</span>
              </div>

              <div className="p-3.5 rounded-xl bg-white border border-[#B8DFC9]">
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Phone Call Clicks</span>
                <span className="text-xl font-black text-[#142820] mt-0.5 block">
                  {ownerData.profile?.call_clicks !== null && ownerData.profile?.call_clicks !== undefined
                    ? ownerData.profile.call_clicks.toLocaleString()
                    : 'Not available'}
                </span>
                <span className="text-[10px] text-[#587568]">Authorized Call Metric</span>
              </div>

              <div className="p-3.5 rounded-xl bg-white border border-[#B8DFC9]">
                <span className="text-[10px] font-bold uppercase text-[#587568] block">Website Clicks</span>
                <span className="text-xl font-black text-[#142820] mt-0.5 block">
                  {ownerData.profile?.website_clicks !== null && ownerData.profile?.website_clicks !== undefined
                    ? ownerData.profile.website_clicks.toLocaleString()
                    : 'Not available'}
                </span>
                <span className="text-[10px] text-[#587568]">Authorized Website Metric</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-4 bg-[#F7FAF7] border border-[#DCE8DC] rounded-xl text-xs text-[#587568] space-y-1">
            <div className="font-bold text-[#142820]">Not connected</div>
            <p className="text-[11px]">
              Public Google information is still available above. Click <strong>Connect Google Business Profile</strong> to initiate Google OAuth 2.0 authorization and access private performance insights.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

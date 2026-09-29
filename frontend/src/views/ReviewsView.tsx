import React, { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Star,
  MessageSquare,
  Sparkles,
  CheckCircle2,
  Send,
  ThumbsUp,
  AlertCircle,
  Filter,
  Check,
  RefreshCw,
  Search,
  ExternalLink,
  MapPin,
  Building2,
  Calendar,
  Clock,
  ArrowUpDown,
  Tag,
  HelpCircle,
  ChevronRight,
  ShieldCheck,
  Mail,
  X
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { Review, PublicPlaceInfo, PublicReviewSummary, PublicReviewsResponse } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { Modal } from '../components/ui/Modal';
import api from '../api/client';
import { getErrorMessage } from '../utils/error';

interface PlaceSearchResult {
  place_id: string;
  name: string;
  formatted_address?: string;
  rating?: number | null;
  user_rating_count?: number | null;
  maps_url?: string;
  website_url?: string;
  primary_type?: string;
  latitude?: number;
  longitude?: number;
}

export const ReviewsView: React.FC = () => {
  const navigate = useNavigate();
  const { activeProject } = useProject();

  // Review & Summary State
  const [reviews, setReviews] = useState<Review[]>([]);
  const [summary, setSummary] = useState<PublicReviewSummary | null>(null);
  const [place, setPlace] = useState<PublicPlaceInfo | null>(null);
  const [status, setStatus] = useState<string>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Filters & Sorting State
  const [filterSentiment, setFilterSentiment] = useState<string>('all');
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('relevance');

  // AI Response Drafting State
  const [draftingId, setDraftingId] = useState<number | null>(null);
  const [editingReply, setEditingReply] = useState<{ [id: number]: string }>({});
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Place Search & Selection Modal State
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [placeSearchInput, setPlaceSearchInput] = useState('');
  const [placeSearchResults, setPlaceSearchResults] = useState<PlaceSearchResult[]>([]);
  const [isSearchingPlaces, setIsSearchingPlaces] = useState(false);
  const [isSelectingPlace, setIsSelectingPlace] = useState(false);

  // Fetch Public Reviews from backend
  const fetchReviews = async (showLoadingSpinner: boolean = true) => {
    if (!activeProject) return;
    try {
      if (showLoadingSpinner) setLoading(true);
      setErrorMessage(null);

      const params = new URLSearchParams();
      if (filterSentiment !== 'all') params.set('sentiment', filterSentiment);
      if (filterCategory !== 'all') params.set('category', filterCategory);
      if (searchQuery.trim()) params.set('search', searchQuery.trim());
      if (sortBy !== 'relevance') params.set('sort_by', sortBy);

      const endpoint = `/local-seo/reviews/${activeProject.id}?${params.toString()}`;
      const resp = await api.get(endpoint);

      if (resp.data && typeof resp.data === 'object') {
        const data: PublicReviewsResponse = resp.data;
        setStatus(data.status || 'found');
        setErrorMessage(data.error || null);
        setPlace(data.place || null);
        setReviews(data.reviews || []);
        setSummary(data.summary || null);
      } else if (Array.isArray(resp.data)) {
        setReviews(resp.data);
        setStatus('found');
      }
    } catch (e: any) {
      console.error('Failed to load reviews:', e);
      setErrorMessage(getErrorMessage(e, 'Google review synchronization is currently unavailable.'));
      setStatus('error');
    } finally {
      if (showLoadingSpinner) setLoading(false);
    }
  };

  // Manual Refresh / Sync Action
  const handleRefreshReviews = async () => {
    if (!activeProject) return;
    try {
      setRefreshing(true);
      setStatusMsg(null);
      const resp = await api.post(`/local-seo/reviews/${activeProject.id}/public-sync`);

      if (resp.data && resp.data.reviews) {
        setReviews(resp.data.reviews);
        setSummary(resp.data.summary);
        setPlace(resp.data.place);
        setStatus('found');
        setStatusMsg({
          type: 'success',
          text: `Successfully refreshed ${resp.data.reviews.length} public customer reviews.`
        });
      } else {
        await fetchReviews(false);
        setStatusMsg({
          type: 'success',
          text: 'Public customer reviews refreshed successfully.'
        });
      }
    } catch (e: any) {
      console.error('Failed to refresh reviews:', e);
      setStatusMsg({
        type: 'error',
        text: getErrorMessage(e, 'Google review synchronization is currently unavailable.')
      });
    } finally {
      setRefreshing(false);
    }
  };

  // Search candidate Google Places
  const handleSearchPlaces = async () => {
    if (!placeSearchInput.trim() || !activeProject) return;
    try {
      setIsSearchingPlaces(true);
      const resp = await api.get(`/local-seo/places/search`, {
        params: {
          project_id: activeProject.id,
          query: placeSearchInput.trim()
        }
      });
      if (resp.data && Array.isArray(resp.data.places)) {
        setPlaceSearchResults(resp.data.places);
      } else {
        setPlaceSearchResults([]);
      }
    } catch (e: any) {
      console.error('Place search failed:', e);
      setStatusMsg({
        type: 'error',
        text: getErrorMessage(e, 'Failed to search Google Places. Try searching by exact business name or address.')
      });
    } finally {
      setIsSearchingPlaces(false);
    }
  };

  // Bind selected Place to Project
  const handleSelectPlaceCandidate = async (candidate: PlaceSearchResult) => {
    if (!activeProject) return;
    try {
      setIsSelectingPlace(true);
      const resp = await api.post(`/local-seo/places/select`, {
        project_id: activeProject.id,
        place_id: candidate.place_id,
        name: candidate.name,
        formatted_address: candidate.formatted_address,
        maps_url: candidate.maps_url,
        website_url: candidate.website_url,
        rating: candidate.rating,
        user_rating_count: candidate.user_rating_count,
        latitude: candidate.latitude,
        longitude: candidate.longitude
      });

      setIsSearchModalOpen(false);
      setPlaceSearchResults([]);
      setStatusMsg({
        type: 'success',
        text: `Connected "${candidate.name}". Live public reviews synchronized!`
      });

      if (resp.data && resp.data.reviews) {
        setReviews(resp.data.reviews);
        setSummary(resp.data.summary);
        setPlace(resp.data.place);
        setStatus('found');
      } else {
        await fetchReviews(true);
      }
    } catch (e: any) {
      console.error('Failed to select place:', e);
      setStatusMsg({
        type: 'error',
        text: getErrorMessage(e, 'Failed to bind Google Place ID to project.')
      });
    } finally {
      setIsSelectingPlace(false);
    }
  };

  // Generate AI Response Draft
  const handleGenerateAIDraft = async (reviewId: number) => {
    try {
      setDraftingId(reviewId);
      setStatusMsg(null);
      const resp = await api.post(`/local-seo/reviews/${reviewId}/draft-response`, {
        custom_tone: 'professional_friendly'
      });

      const draft = resp.data.draft_response || resp.data.response_text;
      if (draft) {
        setEditingReply(prev => ({ ...prev, [reviewId]: draft }));
        setReviews(prev =>
          prev.map(r =>
            r.id === reviewId ? { ...r, response_text: draft, response_status: 'drafted' } : r
          )
        );
        setStatusMsg({
          type: 'success',
          text: 'AI response draft generated. Review and approve below.'
        });
      }
    } catch (e: any) {
      console.error('Failed to generate AI draft:', e);
      setStatusMsg({
        type: 'error',
        text: getErrorMessage(e, 'Failed to generate AI response draft.')
      });
    } finally {
      setDraftingId(null);
    }
  };

  // Save / Approve Draft Response
  const handleSaveApproveResponse = async (reviewId: number) => {
    try {
      const responseText = editingReply[reviewId];
      if (!responseText || !responseText.trim()) {
        setStatusMsg({ type: 'error', text: 'Response text cannot be empty.' });
        return;
      }

      await api.post(`/local-seo/reviews/${reviewId}/approve`, {
        response_text: responseText.trim(),
        action: 'save_draft'
      });

      setReviews(prev =>
        prev.map(r =>
          r.id === reviewId
            ? { ...r, response_text: responseText.trim(), response_status: 'approved' }
            : r
        )
      );

      setStatusMsg({
        type: 'success',
        text: 'Review response approved and saved successfully.'
      });
    } catch (e: any) {
      console.error('Failed to save response:', e);
      setStatusMsg({
        type: 'error',
        text: getErrorMessage(e, 'Failed to save review response.')
      });
    }
  };

  // Load reviews on initial mount or when filter changes
  useEffect(() => {
    fetchReviews(true);
  }, [activeProject, filterSentiment, filterCategory, sortBy]);

  // Debounced search query
  useEffect(() => {
    const handler = setTimeout(() => {
      fetchReviews(false);
    }, 400);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Formatted Date Helper
  const formatReviewDate = (isoStr?: string | null) => {
    if (!isoStr) return 'Recent';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
    } catch {
      return 'Recent';
    }
  };

  const formatSyncDateTime = (isoStr?: string | null) => {
    if (!isoStr) return 'Not yet synchronized';
    try {
      const d = new Date(isoStr);
      return d.toLocaleString('en-US', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return isoStr;
    }
  };

  // Distinct categories available in current dataset
  const availableCategories = useMemo(() => {
    const set = new Set<string>();
    reviews.forEach(r => {
      if (r.category) set.add(r.category);
    });
    return Array.from(set);
  }, [reviews]);

  if (!activeProject) {
    return (
      <EmptyState
        icon={Star}
        badge="Reviews Intelligence"
        title="Select a Project"
        description="Select a business project to view public Google reviews, analyze sentiment themes, and monitor local reputation."
      />
    );
  }

  const totalGoogleRevs = summary?.total_google_reviews ?? place?.user_rating_count ?? reviews.length;
  const reviewsAvailableCount = summary?.reviews_available ?? reviews.length;
  const avgRatingVal = summary?.average_rating ?? place?.rating ?? (reviews.length > 0 ? (reviews.reduce((acc, r) => acc + r.rating, 0) / reviews.length) : null);
  const positiveCount = summary?.positive_count ?? reviews.filter(r => (r.sentiment || '').toLowerCase() === 'positive').length;
  const neutralCount = summary?.neutral_count ?? reviews.filter(r => (r.sentiment || '').toLowerCase() === 'neutral').length;
  const negativeCount = summary?.negative_count ?? reviews.filter(r => (r.sentiment || '').toLowerCase() === 'negative').length;
  const lastSyncStr = formatSyncDateTime(summary?.last_synced_at || place?.last_synced_at);
  const connectedAccount = summary?.connected_google_account || place?.connected_google_account;

  return (
    <div className="space-y-6">
      {/* ─── Header & Business Info ─── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <Star className="w-6 h-6 text-[#236B4F]" />
            <span>Customer Reviews & Reputation</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real customer review intelligence and public reputation insights powered by Google Places API (New).
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {place?.place_id ? (
            <button
              onClick={() => {
                setPlaceSearchInput(activeProject.name || '');
                setIsSearchModalOpen(true);
              }}
              className="px-3 py-2 bg-white border border-slate-200 hover:border-[#236B4F] text-slate-700 text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5 shadow-xs cursor-pointer"
              title="Switch or change bound Google place"
            >
              <MapPin className="w-3.5 h-3.5 text-[#236B4F]" />
              <span>Change Place</span>
            </button>
          ) : (
            <button
              onClick={() => {
                setPlaceSearchInput(activeProject.name || '');
                setIsSearchModalOpen(true);
              }}
              className="px-3.5 py-2 bg-[#236B4F] text-white text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5 shadow-xs hover:bg-[#1D5A42] cursor-pointer"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Find Business on Google</span>
            </button>
          )}

          <button
            onClick={handleRefreshReviews}
            disabled={refreshing || !place?.place_id}
            className="px-4 py-2 bg-[#236B4F] hover:bg-[#1D5A42] text-white text-xs font-bold rounded-xl transition-all flex items-center space-x-2 disabled:opacity-40 shadow-xs cursor-pointer"
            title="Fetch fresh live public reviews directly via Google Places API"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>{refreshing ? 'Refreshing...' : 'Refresh Reviews'}</span>
          </button>
        </div>
      </div>

      {/* Status Notifications */}
      {statusMsg && (
        <div
          className={`p-3.5 rounded-xl border flex items-center space-x-2.5 text-xs ${
            statusMsg.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : 'bg-rose-50 border-rose-200 text-rose-900'
          }`}
        >
          {statusMsg.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-[#236B4F] shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          )}
          <span className="flex-1 font-medium">{statusMsg.text}</span>
          <button
            onClick={() => setStatusMsg(null)}
            className="font-bold opacity-60 hover:opacity-100 px-1 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* Product-Level Notice State Banners */}
      {status === 'not_configured' && (
        <div className="p-4 rounded-2xl border border-amber-200 bg-amber-50 text-amber-900 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <div className="font-bold text-sm text-amber-900">Google review synchronization is currently unavailable</div>
              <div className="mt-0.5 text-amber-800">
                Connect your business Google location or verify platform service connections to enable live review intelligence.
              </div>
            </div>
          </div>
          <Link
            to="/connections"
            className="px-3.5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-bold text-xs shrink-0 self-start sm:self-auto shadow-2xs"
          >
            View Connections
          </Link>
        </div>
      )}

      {status === 'no_place_id' && (
        <div className="p-5 rounded-2xl border border-blue-200 bg-blue-50/60 text-blue-900 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start space-x-3.5">
            <div className="w-9 h-9 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
              <MapPin className="w-5 h-5" />
            </div>
            <div>
              <div className="font-extrabold text-sm text-blue-950">Select a Google business location to load customer reviews</div>
              <p className="mt-0.5 text-xs text-blue-800">
                Search and connect your business's Google Place to pull official rating metrics, review cards, and sentiment intelligence.
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              setPlaceSearchInput(activeProject.name || '');
              setIsSearchModalOpen(true);
            }}
            className="px-4 py-2.5 bg-[#236B4F] hover:bg-[#1D5A42] text-white font-bold text-xs rounded-xl shadow-xs shrink-0 cursor-pointer"
          >
            Find Google Business Place
          </button>
        </div>
      )}

      {/* ─── Top Summary Metrics Strip ─── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Business Center Card */}
        <div className="col-span-2 sm:col-span-3 lg:col-span-2 p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Business Location</span>
              {place?.maps_url && (
                <a
                  href={place.maps_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] font-bold text-[#236B4F] hover:underline flex items-center gap-1"
                >
                  <span>Google Maps</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
            <h3 className="font-extrabold text-slate-900 text-sm mt-1 truncate">
              {place?.name || activeProject.name}
            </h3>
            <p className="text-[11px] text-slate-500 truncate mt-0.5">
              {place?.formatted_address || 'No address bound'}
            </p>

            {/* Connected Business Google Account Banner */}
            {connectedAccount && (
              <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center gap-1.5 text-[11px] text-slate-600 font-medium truncate">
                <Mail className="w-3 h-3 text-[#236B4F] shrink-0" />
                <span className="text-slate-400">Connected Account:</span>
                <span className="font-bold text-slate-800 truncate">{connectedAccount}</span>
              </div>
            )}
          </div>
          <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-400">
            <span>Last Synced:</span>
            <span className="font-semibold text-slate-600">{lastSyncStr}</span>
          </div>
        </div>

        {/* Rating Metric */}
        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Rating</span>
            <Star className="w-4 h-4 text-amber-500 fill-amber-400" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-black text-slate-900">
              {avgRatingVal !== null ? Number(avgRatingVal).toFixed(1) : '—'}
            </div>
            {avgRatingVal !== null ? (
              <div className="text-[11px] text-amber-600 font-semibold mt-0.5 flex items-center gap-1">
                <span>{'★'.repeat(Math.max(1, Math.min(5, Math.round(avgRatingVal))))}</span>
                <span className="text-slate-400 font-normal">/ 5.0</span>
              </div>
            ) : (
              <div className="text-[11px] text-slate-400 font-normal mt-0.5">
                Rating unavailable
              </div>
            )}
          </div>
          <div className="mt-2 text-[10px] text-slate-400 font-medium">
            Google Places API
          </div>
        </div>

        {/* Total Lifetime Reviews Metric */}
        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Total Reviews</span>
            <MessageSquare className="w-4 h-4 text-[#236B4F]" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-black text-slate-900">{totalGoogleRevs}</div>
            <div className="text-[11px] text-slate-500 font-medium mt-0.5">
              Total on Google
            </div>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 font-medium">
            Lifetime count
          </div>
        </div>

        {/* Reviews Retrieved & Available Metric */}
        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Reviews Analyzed</span>
            <ShieldCheck className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-black text-indigo-900">{reviewsAvailableCount}</div>
            <div className="text-[11px] text-indigo-700 font-medium mt-0.5">
              {totalGoogleRevs > reviewsAvailableCount && reviewsAvailableCount > 0
                ? `${reviewsAvailableCount} of ${totalGoogleRevs} listing reviews`
                : 'Available & Analyzed'}
            </div>
          </div>
          <div className="mt-2 text-[10px] text-indigo-500 font-medium">
            {totalGoogleRevs > reviewsAvailableCount && reviewsAvailableCount > 0
              ? 'Public audit sample collected'
              : 'Full content verified'}
          </div>
        </div>

        {/* Sentiment Polarity Metric */}
        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Sentiment</span>
            <Sparkles className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2 space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-emerald-700 font-bold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> Pos
              </span>
              <span className="font-extrabold text-slate-800">{positiveCount}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-600 font-bold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" /> Neu
              </span>
              <span className="font-extrabold text-slate-800">{neutralCount}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-rose-600 font-bold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-rose-500 inline-block" /> Neg
              </span>
              <span className="font-extrabold text-slate-800">{negativeCount}</span>
            </div>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 font-medium">
            Natural language analysis
          </div>
        </div>
      </div>

      {/* ─── Search, Filter, and Sorting Bar ─── */}
      <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search reviews by keyword, customer name, topic, or category..."
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-[#236B4F]/20 focus:border-[#236B4F]"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            )}
          </div>

          {/* Sentiment Filter Pills */}
          <div className="flex items-center space-x-1.5 shrink-0 overflow-x-auto pb-1 md:pb-0">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mr-1">
              Sentiment:
            </span>
            {(['all', 'positive', 'neutral', 'negative'] as const).map((sent) => (
              <button
                key={sent}
                onClick={() => setFilterSentiment(sent)}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition-all capitalize cursor-pointer ${
                  filterSentiment === sent
                    ? 'bg-[#236B4F] text-white shadow-2xs'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {sent === 'all' ? 'All Sentiments' : sent}
              </button>
            ))}
          </div>

          {/* Sort Selector */}
          <div className="flex items-center space-x-2 shrink-0">
            <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              aria-label="Sort reviews"
              className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-[#236B4F]/20"
            >
              <option value="relevance">Google Relevance</option>
              <option value="newest">Newest Published</option>
              <option value="rating_desc">Highest Rating (5★)</option>
              <option value="rating_asc">Lowest Rating (1★)</option>
            </select>
          </div>
        </div>

        {/* Dynamic Category Filter Pills */}
        <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-slate-100">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mr-1">
            Category:
          </span>
          <button
            onClick={() => setFilterCategory('all')}
            className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              filterCategory === 'all'
                ? 'bg-[#236B4F] text-white shadow-2xs'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            All Categories
          </button>
          {availableCategories.map((cat: string) => (
            <button
              key={cat}
              onClick={() => setFilterCategory(cat)}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                filterCategory === cat
                  ? 'bg-[#236B4F] text-white shadow-2xs'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* ─── Active Reviews List: One Independent Visual Card per Review ─── */}
      <div className="space-y-4">
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center text-slate-400 bg-white rounded-2xl border border-slate-200">
            <RefreshCw className="w-7 h-7 animate-spin text-[#236B4F] mb-3" />
            <p className="text-xs font-bold text-slate-700">Loading customer reviews...</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Fetching review intelligence and dynamic sentiment classification</p>
          </div>
        ) : reviews.length === 0 ? (
          <div className="p-12 text-center bg-white rounded-2xl border border-slate-200">
            <Star className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h3 className="font-extrabold text-slate-900 text-sm">No Customer Reviews Found</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              {filterSentiment !== 'all' || filterCategory !== 'all' || searchQuery
                ? 'No reviews match your currently applied search filters. Try clearing filters.'
                : 'No reviews are currently available for this business location.'}
            </p>
            {place?.place_id && (
              <button
                onClick={handleRefreshReviews}
                className="mt-4 px-4 py-2 bg-[#236B4F] hover:bg-[#1D5A42] text-white rounded-xl text-xs font-bold shadow-xs cursor-pointer"
              >
                Synchronize Reviews
              </button>
            )}
          </div>
        ) : (
          reviews.map((rev) => {
            const hasDraft = Boolean(rev.response_text || editingReply[rev.id] !== undefined);
            const isDrafting = draftingId === rev.id;
            const categoryBanner = rev.category || 'OTHER';
            const mapsLink = rev.google_maps_uri || place?.maps_url || 'https://maps.google.com';
            const topicList: string[] = Array.isArray(rev.topic_list) && rev.topic_list.length > 0
              ? rev.topic_list
              : (Array.isArray(rev.topics) && rev.topics.length > 0 ? rev.topics : ['Overall Experience']);

            return (
              <div
                key={rev.id}
                className="bg-white rounded-2xl border border-[#DCE8DC] p-5 shadow-xs space-y-4 hover:border-[#236B4F]/40 transition-all"
              >
                {/* 1. Category Banner & Attribution Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Category Banner Badge */}
                    <span className="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider bg-[#EBF2EB] text-[#236B4F] border border-[#DCE8DC]">
                      [ {categoryBanner} ]
                    </span>

                    {/* Source Provenance Tag */}
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                      (rev as any).access_mode === 'OWNER_AUTHORIZED' || rev.source === 'Google Business Profile' || (rev.source && rev.source.includes('Authorized'))
                        ? 'bg-purple-50 text-purple-700 border-purple-200'
                        : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    }`}>
                      {(rev as any).access_mode === 'OWNER_AUTHORIZED' || rev.source === 'Google Business Profile' || (rev.source && rev.source.includes('Authorized'))
                        ? 'OWNER-AUTHORIZED GOOGLE REVIEW'
                        : 'PUBLIC GOOGLE OBSERVATION'}
                    </span>

                    {/* Source Provider */}
                    {rev.source && (
                      <span className="text-[10px] text-slate-500 font-medium bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                        {rev.source.includes('SerpApi')
                          ? 'SerpApi — Google Maps Reviews'
                          : rev.source.includes('Business Profile')
                          ? 'Google Business Profile — Authorized'
                          : rev.source}
                      </span>
                    )}

                    {/* Sentiment Badge */}
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold capitalize ${
                      rev.sentiment === 'positive'
                        ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                        : rev.sentiment === 'negative'
                        ? 'bg-rose-100 text-rose-800 border border-rose-200'
                        : rev.sentiment === 'neutral'
                        ? 'bg-slate-100 text-slate-700 border border-slate-200'
                        : 'bg-slate-50 text-slate-500 border border-slate-200'
                    }`}>
                      Sentiment: {rev.sentiment || 'Not analyzed'}
                    </span>
                  </div>

                  {/* Rating Stars */}
                  {rev.rating !== null && rev.rating !== undefined ? (
                    <div className="flex items-center space-x-1">
                      <div className="flex text-amber-400 text-sm">
                        {'★'.repeat(Math.min(5, Math.max(1, rev.rating)))}
                        <span className="text-slate-200">
                          {'★'.repeat(Math.max(0, 5 - rev.rating))}
                        </span>
                      </div>
                      <span className="text-xs font-black text-slate-800 ml-1">
                        {rev.rating} / 5
                      </span>
                    </div>
                  ) : (
                    <div className="text-xs font-medium text-slate-400 italic">
                      Rating unavailable
                    </div>
                  )}
                </div>

                {/* 2. Reviewer Attribution & Date */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    {rev.author_photo_url ? (
                      <img
                        src={rev.author_photo_url}
                        alt={rev.author_name}
                        className="w-9 h-9 rounded-full object-cover border border-slate-200"
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = 'none';
                        }}
                      />
                    ) : (
                      <div className="w-9 h-9 rounded-full bg-[#236B4F] text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-xs">
                        {rev.author_name ? rev.author_name[0] : 'G'}
                      </div>
                    )}

                    <div>
                      <div className="flex items-center space-x-2">
                        {rev.author_uri ? (
                          <a
                            href={rev.author_uri}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-extrabold text-slate-900 text-sm hover:text-[#236B4F] hover:underline"
                          >
                            {rev.author_name}
                          </a>
                        ) : (
                          <h4 className="font-extrabold text-slate-900 text-sm">
                            {rev.author_name}
                          </h4>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-400 font-medium flex items-center gap-1.5 mt-0.5">
                        <Calendar className="w-3 h-3 text-slate-400" />
                        <span>{formatReviewDate(rev.review_date || rev.published_at)}</span>
                        {rev.relative_publish_time_description && (
                          <>
                            <span>•</span>
                            <span>{rev.relative_publish_time_description}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* View on Google Maps Link */}
                  {mapsLink && (
                    <a
                      href={mapsLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold text-[#236B4F] bg-[#F7FAF7] hover:bg-[#EBF2EB] border border-[#DCE8DC] transition-colors"
                    >
                      <span>View on Google Maps</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>

                {/* 3. Review Text */}
                <p className="text-xs text-slate-700 leading-relaxed font-medium bg-slate-50/70 p-3.5 rounded-xl border border-slate-100">
                  "{rev.review_text || 'No review comment provided (Rating only).'}"
                </p>

                {/* 4. Dynamic Topic Chips */}
                {topicList.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mr-1 flex items-center gap-1">
                      <Tag className="w-3 h-3 text-slate-400" /> Topics:
                    </span>
                    {topicList.map((topic, tIdx) => (
                      <span
                        key={tIdx}
                        className="px-2.5 py-0.5 bg-slate-100 text-slate-700 rounded-md text-[10px] font-semibold border border-slate-200"
                      >
                        {topic}
                      </span>
                    ))}
                  </div>
                )}

                {/* 5. AI Response Assistance Workflow */}
                <div className="bg-[#F7FAF7] p-4 rounded-xl border border-[#EBF2EB] space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Sparkles className="w-4 h-4 text-[#236B4F]" />
                      <span className="text-xs font-bold text-slate-800">
                        AI Response Workflow
                      </span>
                      {rev.response_status === 'approved' || rev.response_status === 'published' ? (
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-emerald-100 text-emerald-800 border border-emerald-200">
                          {rev.response_status === 'published' ? 'Published' : 'Saved'}
                        </span>
                      ) : rev.response_status === 'drafted' || hasDraft ? (
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-amber-100 text-amber-800 border border-amber-200">
                          Draft
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-slate-100 text-slate-600">
                          Unanswered
                        </span>
                      )}
                    </div>

                    {!hasDraft && (
                      <button
                        onClick={() => handleGenerateAIDraft(rev.id)}
                        disabled={isDrafting}
                        className="px-3 py-1.5 bg-[#236B4F] hover:bg-[#1D5A42] text-white rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 disabled:opacity-50 shadow-xs cursor-pointer"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>{isDrafting ? 'Drafting Response...' : 'Generate Response'}</span>
                      </button>
                    )}
                  </div>

                  {hasDraft && (
                    <div className="space-y-2">
                      <textarea
                        value={editingReply[rev.id] !== undefined ? editingReply[rev.id] : (rev.response_text || '')}
                        onChange={(e) =>
                          setEditingReply(prev => ({ ...prev, [rev.id]: e.target.value }))
                        }
                        rows={3}
                        placeholder="Draft response to customer review..."
                        className="w-full p-3 bg-white border border-slate-200 rounded-xl text-xs font-medium text-slate-800 placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-[#236B4F]/20 focus:border-[#236B4F]"
                      />
                      <div className="flex items-center justify-end space-x-2">
                        <button
                          onClick={() => handleGenerateAIDraft(rev.id)}
                          disabled={isDrafting}
                          className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold transition-all flex items-center space-x-1 cursor-pointer"
                        >
                          <Sparkles className="w-3 h-3 text-[#236B4F]" />
                          <span>{isDrafting ? 'Regenerating...' : 'Regenerate'}</span>
                        </button>
                        <button
                          onClick={() => handleSaveApproveResponse(rev.id)}
                          className="px-3.5 py-1.5 bg-[#236B4F] hover:bg-[#1D5A42] text-white rounded-lg text-xs font-bold transition-all flex items-center space-x-1.5 shadow-xs cursor-pointer"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Save Response</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ─── Interactive Google Place Search & Selection Modal ─── */}
      {isSearchModalOpen && (
        <Modal
          isOpen={isSearchModalOpen}
          onClose={() => setIsSearchModalOpen(false)}
          maxWidth="2xl"
          icon={<MapPin className="w-5 h-5 text-[#236B4F]" />}
          title="Select Google Business Location"
          subtitle="Search Google Places to connect public business profile & reviews"
          bodyClassName="space-y-5 p-6"
        >
          {/* Search Input Box */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#587568]" />
              <input
                type="text"
                value={placeSearchInput}
                onChange={(e) => setPlaceSearchInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearchPlaces()}
                placeholder="Enter business name, address, or city..."
                className="w-full pl-9 pr-4 py-2.5 bg-[#F7FAF7] border border-[#DCE8DC] rounded-xl text-xs font-medium text-[#142820] placeholder:text-[#587568] focus:outline-hidden focus:ring-2 focus:ring-[#236B4F]/20 focus:border-[#236B4F]"
              />
            </div>
            <button
              onClick={handleSearchPlaces}
              disabled={isSearchingPlaces || !placeSearchInput.trim()}
              className="px-4 py-2.5 btn-primary-gradient text-white rounded-xl text-xs font-bold transition-all disabled:opacity-40 flex items-center space-x-1.5 shadow-xs cursor-pointer"
            >
              <Search className="w-3.5 h-3.5" />
              <span>{isSearchingPlaces ? 'Searching...' : 'Search'}</span>
            </button>
          </div>

          {/* Candidate Search Results */}
          <div className="max-h-[320px] overflow-y-auto space-y-2.5 pr-1">
            {isSearchingPlaces ? (
              <div className="py-12 text-center text-[#587568]">
                <RefreshCw className="w-6 h-6 animate-spin text-[#236B4F] mx-auto mb-2" />
                <p className="text-xs font-bold text-[#142820]">Searching Google Places...</p>
              </div>
            ) : placeSearchResults.length > 0 ? (
              placeSearchResults.map((candidate) => (
                <div
                  key={candidate.place_id}
                  className="p-3.5 rounded-2xl border border-[#DCE8DC] hover:border-[#236B4F] bg-white transition-all flex items-center justify-between gap-3 group shadow-2xs"
                >
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className="font-extrabold text-[#142820] text-xs truncate">
                        {candidate.name}
                      </span>
                      {candidate.rating && (
                        <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-900 border border-amber-200 text-[10px] font-bold flex items-center gap-0.5">
                          <span>★</span>
                          <span>{candidate.rating.toFixed(1)}</span>
                          {candidate.user_rating_count && (
                            <span className="text-[#587568] font-normal">({candidate.user_rating_count})</span>
                          )}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-[#587568] truncate">
                      {candidate.formatted_address || 'Address not provided'}
                    </p>
                  </div>

                  <button
                    onClick={() => handleSelectPlaceCandidate(candidate)}
                    disabled={isSelectingPlace}
                    className="px-3.5 py-1.5 btn-primary-gradient text-white rounded-xl text-xs font-bold shadow-xs shrink-0 transition-all flex items-center space-x-1 disabled:opacity-50 cursor-pointer"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>Select Place</span>
                  </button>
                </div>
              ))
            ) : (
              <div className="py-8 text-center text-[#587568] text-xs">
                Type your business name above and click Search to locate your Google Place.
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
};

export default ReviewsView;

import React, { useState, useEffect } from 'react';
import {
  Flame,
  Plus,
  Search,
  Download,
  FileSpreadsheet,
  FileText,
  TrendingUp,
  Star,
  ExternalLink,
  Shield,
  Sparkles,
  Trash2,
  MapPin,
  Tag,
  Layers,
  Compass,
  CheckCircle2,
  AlertCircle,
  Loader2
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { Competitor, CompetitorCandidate } from '../types';
import { EmptyState } from '../components/ui/EmptyState';
import { normalizeExternalUrl } from '../utils/url';
import { Modal } from '../components/ui/Modal';
import api from '../api/client';

export const CompetitorsView: React.FC = () => {
  const { activeProject } = useProject();
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Modals
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  
  // Manual Add Form
  const [name, setName] = useState('');
  const [domain, setDomain] = useState('');
  const [category, setCategory] = useState('');
  const [placeId, setPlaceId] = useState('');
  const [address, setAddress] = useState('');
  const [addingManual, setAddingManual] = useState(false);

  // Search Competitors State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchLocation, setSearchLocation] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<CompetitorCandidate[]>([]);
  const [searchSearched, setSearchSearched] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [addingCandidate, setAddingCandidate] = useState<string | null>(null);

  // Filters & Search in View
  const [sourceFilter, setSourceFilter] = useState<'all' | 'manual' | 'geogrid'>('all');
  const [searchTerm, setSearchTerm] = useState('');

  // Export Loading States
  const [exportingCsv, setExportingCsv] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);

  const fetchCompetitors = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/local-seo/competitors/${activeProject.id}`);
      setCompetitors(resp.data || []);
    } catch (e) {
      console.error('Failed to load competitors:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setCompetitors([]);
    setSearchResults([]);
    setSearchSearched(false);
    setSearchError(null);
    fetchCompetitors();
    if (activeProject) {
      setSearchQuery(activeProject.primary_category || `${activeProject.name} competitors`);
    }
  }, [activeProject?.id]);

  const handleAddManualCompetitor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !name.trim()) return;
    try {
      setAddingManual(true);
      await api.post('/local-seo/competitors', {
        project_id: activeProject.id,
        name: name.trim(),
        domain: domain.trim() || undefined,
        website: domain.trim() || undefined,
        category: category.trim() || undefined,
        place_id: placeId.trim() || undefined,
        address: address.trim() || undefined,
        source: 'manual'
      });
      setName('');
      setDomain('');
      setCategory('');
      setPlaceId('');
      setAddress('');
      setIsManualModalOpen(false);
      await fetchCompetitors();
    } catch (e) {
      console.error('Failed to add competitor manually:', e);
    } finally {
      setAddingManual(false);
    }
  };

  const handleSearchCompetitors = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject) return;
    try {
      setSearching(true);
      setSearchError(null);
      const resp = await api.post('/local-seo/competitors/search', {
        project_id: activeProject.id,
        query: searchQuery.trim() || undefined,
        location: searchLocation.trim() || undefined
      });
      setSearchResults(resp.data?.results || []);
      setSearchSearched(true);
    } catch (err: any) {
      console.error('Competitor discovery search failed:', err);
      setSearchError('Competitor search could not be completed. Please check your SERP provider configuration or try again.');
    } finally {
      setSearching(false);
    }
  };

  const handleAddFromSearch = async (cand: CompetitorCandidate) => {
    if (!activeProject) return;
    try {
      setAddingCandidate(cand.place_id || cand.domain || cand.title);
      await api.post('/local-seo/competitors', {
        project_id: activeProject.id,
        name: cand.title,
        domain: cand.domain || undefined,
        website: cand.domain || undefined,
        rating: cand.rating,
        reviews_count: cand.reviews_count,
        place_id: cand.place_id,
        address: cand.address,
        phone: cand.phone,
        category: cand.category,
        source: 'manual'
      });
      // Mark as tracked locally
      setSearchResults((prev) =>
        prev.map((item) =>
          (item.place_id && item.place_id === cand.place_id) ||
          (item.domain && item.domain === cand.domain) ||
          item.title === cand.title
            ? { ...item, is_already_tracked: true }
            : item
        )
      );
      await fetchCompetitors();
    } catch (err) {
      console.error('Failed to add candidate as competitor:', err);
    } finally {
      setAddingCandidate(null);
    }
  };

  const handleDeleteCompetitor = async (competitorId: number) => {
    try {
      await api.delete(`/local-seo/competitors/${competitorId}`);
      setCompetitors((prev) => prev.filter((c) => c.id !== competitorId));
    } catch (e) {
      console.error('Failed to delete competitor:', e);
    }
  };

  const handleDownloadCsv = async () => {
    if (!activeProject) return;
    try {
      setExportingCsv(true);
      const response = await api.get(`/local-seo/competitors/${activeProject.id}/export/csv`, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `competitors_${activeProject.name.toLowerCase().replace(/\s+/g, '_')}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Failed to export competitors CSV:', e);
    } finally {
      setExportingCsv(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!activeProject) return;
    try {
      setExportingPdf(true);
      const response = await api.get(`/local-seo/competitors/${activeProject.id}/export/pdf`, {
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `competitor_benchmarking_${activeProject.name.toLowerCase().replace(/\s+/g, '_')}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Failed to export competitors PDF:', e);
    } finally {
      setExportingPdf(false);
    }
  };

  // Filtered Competitors List
  const filteredCompetitors = competitors.filter((comp) => {
    const src = comp.source || 'manual';
    if (sourceFilter === 'manual' && src !== 'manual' && src !== 'manual_and_geogrid') {
      return false;
    }
    if (sourceFilter === 'geogrid' && src !== 'geogrid' && src !== 'manual_and_geogrid') {
      return false;
    }
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      const matchName = comp.name?.toLowerCase().includes(q);
      const matchDomain = comp.domain?.toLowerCase().includes(q);
      const matchCat = comp.category?.toLowerCase().includes(q) || comp.categories?.some((c) => c.toLowerCase().includes(q));
      return matchName || matchDomain || matchCat;
    }
    return true;
  });

  // Summary Metrics
  const totalCount = competitors.length;
  const validRatings = competitors.filter((c) => c.rating !== null && c.rating !== undefined).map((c) => c.rating!);
  const avgRating = validRatings.length > 0 ? (validRatings.reduce((a, b) => a + b, 0) / validRatings.length).toFixed(1) : null;
  const validReviews = competitors.map((c) => c.reviews_count || (c as any).total_reviews || 0);
  const avgReviews = totalCount > 0 ? Math.round(validReviews.reduce((a, b) => a + b, 0) / totalCount) : 0;
  const validRanks = competitors.filter((c) => c.avg_maps_rank !== null && c.avg_maps_rank !== undefined).map((c) => c.avg_maps_rank!);
  const avgMapsRank = validRanks.length > 0 ? (validRanks.reduce((a, b) => a + b, 0) / validRanks.length).toFixed(1) : null;

  if (!activeProject) {
    return (
      <EmptyState
        icon={Flame}
        badge="Competitor Benchmark"
        title="Select a Project"
        description="Select a business project to benchmark local rankings, review volume, and domain authority against nearby competitors."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header & 4 Top-Level Action Buttons */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <Flame className="w-6 h-6 text-purple-600" />
            <span>Local Competitor Benchmarking</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Track and benchmark Google Maps local pack visibility, rating, and review acquisition against direct competitors.
          </p>
        </div>

        {/* 4 Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Button 1: Search Competitors */}
          <button
            onClick={() => setIsSearchModalOpen(true)}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200 shadow-sm transition-all"
          >
            <Sparkles className="w-3.5 h-3.5 text-purple-600" />
            <span>Search Competitors</span>
          </button>

          {/* Button 2: Add Competitor Manually */}
          <button
            onClick={() => setIsManualModalOpen(true)}
            className="flex items-center space-x-1.5 px-3.5 py-2 btn-vibrant-primary text-white rounded-xl text-xs font-bold shadow-sm transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Competitor</span>
          </button>

          {/* Button 3: Download CSV */}
          <button
            onClick={handleDownloadCsv}
            disabled={exportingCsv || competitors.length === 0}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-white text-slate-700 hover:bg-slate-50 border border-slate-200 shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {exportingCsv ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-600" />
            ) : (
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
            )}
            <span>Download CSV</span>
          </button>

          {/* Button 4: Download PDF */}
          <button
            onClick={handleDownloadPdf}
            disabled={exportingPdf || competitors.length === 0}
            className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-white text-slate-700 hover:bg-slate-50 border border-slate-200 shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {exportingPdf ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-600" />
            ) : (
              <FileText className="w-3.5 h-3.5 text-rose-600" />
            )}
            <span>Download PDF</span>
          </button>
        </div>
      </div>

      {/* Benchmarking Summary KPIs */}
      {competitors.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-1">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">Tracked Competitors</span>
            <div className="flex items-baseline space-x-2">
              <span className="text-2xl font-black text-slate-900">{totalCount}</span>
              <span className="text-xs text-purple-600 font-semibold">Active Monitoring</span>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-1">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">Avg Google Rating</span>
            <div className="flex items-baseline space-x-1.5">
              <span className="text-2xl font-black text-amber-500">{avgRating ? `${avgRating} ★` : '—'}</span>
              <span className="text-xs text-slate-400">across local pack</span>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-1">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">Avg Review Volume</span>
            <div className="flex items-baseline space-x-2">
              <span className="text-2xl font-black text-slate-900">{avgReviews}</span>
              <span className="text-xs text-slate-400">reviews / business</span>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-white border border-slate-200 shadow-sm space-y-1">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">Avg Maps Rank</span>
            <div className="flex items-baseline space-x-2">
              <span className="text-2xl font-black text-purple-700">{avgMapsRank ? `#${avgMapsRank}` : '—'}</span>
              <span className="text-xs text-slate-400">geo-grid visibility</span>
            </div>
          </div>
        </div>
      )}

      {/* Filter & Search Bar */}
      {competitors.length > 0 && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3 rounded-2xl border border-slate-200 shadow-sm">
          {/* Source Tabs */}
          <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-xl text-xs font-bold text-slate-600">
            <button
              onClick={() => setSourceFilter('all')}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                sourceFilter === 'all'
                  ? 'bg-white text-purple-700 shadow-sm'
                  : 'hover:text-slate-900'
              }`}
            >
              All ({competitors.length})
            </button>
            <button
              onClick={() => setSourceFilter('manual')}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                sourceFilter === 'manual'
                  ? 'bg-white text-purple-700 shadow-sm'
                  : 'hover:text-slate-900'
              }`}
            >
              Manual ({competitors.filter((c) => c.source === 'manual' || c.source === 'manual_and_geogrid').length})
            </button>
            <button
              onClick={() => setSourceFilter('geogrid')}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                sourceFilter === 'geogrid'
                  ? 'bg-white text-purple-700 shadow-sm'
                  : 'hover:text-slate-900'
              }`}
            >
              Geo-Grid ({competitors.filter((c) => c.source === 'geogrid' || c.source === 'manual_and_geogrid').length})
            </button>
          </div>

          {/* Search Box */}
          <div className="relative max-w-xs w-full">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search competitors by name or domain..."
              className="w-full pl-8 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-purple-500 font-medium"
            />
          </div>
        </div>
      )}

      {/* Competitor Grid */}
      {filteredCompetitors.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCompetitors.map((comp) => {
            const src = comp.source || 'manual';
            return (
              <div
                key={comp.id}
                className="card-vibrant p-5 space-y-4 transition-all relative group hover:shadow-md hover:border-purple-200"
              >
                {/* Card Header */}
                <div className="flex items-start justify-between">
                  <div className="space-y-0.5 max-w-[70%]">
                    <h3 className="font-extrabold text-slate-900 text-sm truncate" title={comp.name}>
                      {comp.name}
                    </h3>
                    {comp.domain && normalizeExternalUrl(comp.domain) ? (
                      <a
                        href={normalizeExternalUrl(comp.domain)!}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-purple-700 hover:underline flex items-center space-x-1 font-mono truncate"
                      >
                        <span className="truncate">{comp.domain}</span>
                        <ExternalLink className="w-2.5 h-2.5 flex-shrink-0" />
                      </a>
                    ) : comp.domain ? (
                      <span className="text-xs text-slate-600 font-mono truncate block">{comp.domain}</span>
                    ) : null}
                  </div>

                  <div className="flex items-center space-x-1.5 flex-shrink-0">
                    {/* Source Badge */}
                    {src === 'manual_and_geogrid' ? (
                      <span className="px-2 py-0.5 rounded-full bg-purple-50 text-purple-800 text-[10px] font-bold border border-purple-200">
                        Manual + Grid
                      </span>
                    ) : src === 'geogrid' ? (
                      <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 text-[10px] font-bold border border-emerald-200">
                        Geo-Grid
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-[10px] font-bold border border-slate-200">
                        Manual
                      </span>
                    )}

                    {/* Delete Button */}
                    <button
                      onClick={() => handleDeleteCompetitor(comp.id)}
                      aria-label="Remove competitor"
                      title="Remove competitor"
                      className="p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Key Metrics Grid */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                    <span className="text-[10px] text-slate-500 font-bold block">Avg Maps Rank</span>
                    <span className="text-base font-black text-slate-900 mt-0.5 block">
                      {comp.avg_maps_rank !== null && comp.avg_maps_rank !== undefined
                        ? `#${comp.avg_maps_rank.toFixed(1)}`
                        : '—'}
                    </span>
                    {comp.best_rank !== null && comp.best_rank !== undefined && (
                      <span className="text-[10px] text-slate-400 mt-0.5 block">
                        Best #{comp.best_rank} &bull; Worst #{comp.worst_rank ?? '—'}
                      </span>
                    )}
                  </div>

                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                    <span className="text-[10px] text-slate-500 font-bold block">Reviews & Rating</span>
                    <span className="text-base font-black text-amber-500 mt-0.5 block">
                      {comp.rating !== null && comp.rating !== undefined ? `${comp.rating} ★` : '—'}{' '}
                      <span className="text-xs text-slate-500 font-normal">
                        ({comp.reviews_count ?? (comp as any).total_reviews ?? 0})
                      </span>
                    </span>
                    {comp.grid_appearances ? (
                      <span className="text-[10px] text-emerald-600 font-semibold mt-0.5 block">
                        {comp.grid_appearances} grid points
                      </span>
                    ) : (
                      <span className="text-[10px] text-slate-400 mt-0.5 block">Local Google Listing</span>
                    )}
                  </div>
                </div>

                {/* Context Details: Keywords & Category */}
                {(comp.keywords_found && comp.keywords_found.length > 0) || comp.category ? (
                  <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center gap-1.5 text-[11px]">
                    {comp.category && (
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
                        {comp.category}
                      </span>
                    )}
                    {comp.keywords_found?.slice(0, 3).map((kw, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-purple-50 text-purple-700 font-medium flex items-center space-x-1"
                      >
                        <Tag className="w-2.5 h-2.5 text-purple-500" />
                        <span>{kw}</span>
                      </span>
                    ))}
                    {comp.keywords_found && comp.keywords_found.length > 3 && (
                      <span className="text-[10px] text-slate-400">+{comp.keywords_found.length - 3} more</span>
                    )}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : competitors.length > 0 ? (
        <div className="text-center py-12 bg-white rounded-2xl border border-slate-200 space-y-2">
          <p className="text-sm font-bold text-slate-700">No competitors match your filter criteria.</p>
          <button
            onClick={() => {
              setSourceFilter('all');
              setSearchTerm('');
            }}
            className="text-xs text-purple-600 font-bold hover:underline"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <EmptyState
          icon={Flame}
          badge="No Competitors"
          title="No Competitors Configured"
          description="Add nearby businesses in your industry or run a Geo-Grid scan to automatically benchmark Google Maps rank positions and review volume."
          actionText="Add Target Competitor"
          onAction={() => setIsManualModalOpen(true)}
        />
      )}

      {/* Modal 1: Search Competitors via SERP API */}
      <Modal
        isOpen={isSearchModalOpen}
        onClose={() => setIsSearchModalOpen(false)}
        maxWidth="2xl"
        title="Discover Competitors via SERP API"
        description="Query live Google Local Pack & Organic rankings"
        footer={
          <div className="flex justify-end w-full">
            <button
              type="button"
              onClick={() => setIsSearchModalOpen(false)}
              className="px-4 py-2 rounded-lg bg-slate-200 text-slate-700 hover:bg-slate-300 text-xs font-bold"
            >
              Close
            </button>
          </div>
        }
      >
        <div className="space-y-4">
          {/* Search Query Form */}
          <form onSubmit={handleSearchCompetitors} className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div>
                <label className="text-slate-700 font-bold block mb-1">Search Keyword / Category</label>
                <input
                  type="text"
                  required
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="e.g. Electricians or Plumber"
                  className="w-full bg-white border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
                />
              </div>
              <div>
                <label className="text-slate-700 font-bold block mb-1">Target Location (Optional)</label>
                <input
                  type="text"
                  value={searchLocation}
                  onChange={(e) => setSearchLocation(e.target.value)}
                  placeholder="e.g. Brisbane, QLD"
                  className="w-full bg-white border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
                />
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={searching || !searchQuery.trim()}
                className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg text-xs font-bold flex items-center space-x-1.5 shadow-xs disabled:opacity-50"
              >
                {searching ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Scanning SERP...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-3.5 h-3.5" />
                    <span>Run Discovery Search</span>
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Search Results List */}
          <div className="space-y-3">
            {searchError && (
              <div className="p-3 bg-rose-50 text-rose-800 rounded-xl text-xs flex items-center space-x-2 border border-rose-200">
                <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-600" />
                <span>{searchError}</span>
              </div>
            )}

            {searching && (
              <div className="text-center py-12 space-y-2">
                <Loader2 className="w-8 h-8 animate-spin text-emerald-600 mx-auto" />
                <p className="text-xs font-bold text-slate-600">Querying live Google Local Pack & Organic rankings...</p>
              </div>
            )}

            {!searching && searchResults.length > 0 && (
              <div className="space-y-2.5">
                <div className="flex items-center justify-between text-xs text-slate-500 font-medium px-1">
                  <span>Discovered Candidates ({searchResults.length})</span>
                  <span>Source: Local SERP</span>
                </div>
                {searchResults.map((cand, idx) => {
                  const candId = cand.place_id || cand.domain || cand.title;
                  const isAdding = addingCandidate === candId;

                  return (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl border border-slate-200 bg-white hover:border-emerald-200 transition-all flex items-center justify-between gap-3"
                    >
                      <div className="space-y-1 max-w-[70%]">
                        <div className="flex items-center space-x-2">
                          {cand.position && (
                            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-bold">
                              #{cand.position}
                            </span>
                          )}
                          <h4 className="font-extrabold text-slate-900 text-xs truncate">{cand.title}</h4>
                        </div>

                        {cand.domain && (
                          <span className="text-[11px] font-mono text-emerald-700 block truncate">{cand.domain}</span>
                        )}

                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                          {cand.rating !== null && cand.rating !== undefined && (
                            <span className="text-amber-500 font-bold">
                              {cand.rating} ★ ({cand.reviews_count ?? 0})
                            </span>
                          )}
                          {cand.address && (
                            <span className="text-slate-400 truncate max-w-xs flex items-center space-x-0.5">
                              <MapPin className="w-2.5 h-2.5" />
                              <span>{cand.address}</span>
                            </span>
                          )}
                        </div>
                      </div>

                      <div>
                        {cand.is_already_tracked ? (
                          <span className="px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-800 text-xs font-bold border border-emerald-200 flex items-center space-x-1">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                            <span>Tracked</span>
                          </span>
                        ) : (
                          <button
                            onClick={() => handleAddFromSearch(cand)}
                            disabled={isAdding}
                            className="px-3 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold flex items-center space-x-1 shadow-xs disabled:opacity-50"
                          >
                            {isAdding ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Plus className="w-3.5 h-3.5" />
                            )}
                            <span>Track</span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {!searching && searchSearched && searchResults.length === 0 && !searchError && (
              <div className="text-center py-10 space-y-1">
                <p className="text-xs font-bold text-slate-700">No new competitor candidates found for this query.</p>
                <p className="text-[11px] text-slate-400">Try modifying your keyword phrase or location.</p>
              </div>
            )}

            {!searching && !searchSearched && (
              <div className="text-center py-10 space-y-1">
                <p className="text-xs font-bold text-slate-600">Enter a keyword or category above to scan Google local search.</p>
                <p className="text-[11px] text-slate-400">Directly import discovered local competitors to your project.</p>
              </div>
            )}
          </div>
        </div>
      </Modal>

      {/* Modal 2: Add Competitor Manually */}
      <Modal
        isOpen={isManualModalOpen}
        onClose={() => setIsManualModalOpen(false)}
        maxWidth="md"
        title="Add Local Competitor"
        description="Manually track a specific competitor"
      >
        <form onSubmit={handleAddManualCompetitor} className="space-y-3 text-xs">
          <div>
            <label className="text-slate-700 block mb-1 font-bold">Business Name *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Brisbane Elite Electricians"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
            />
          </div>

          <div>
            <label className="text-slate-700 block mb-1 font-bold">Website Domain</label>
            <input
              type="text"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="e.g. brisbaneeliteelectricians.com.au"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
            />
          </div>

          <div>
            <label className="text-slate-700 block mb-1 font-bold">Primary Category (Optional)</label>
            <input
              type="text"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. Electrician, Plumbing, Furniture"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
            />
          </div>

          <div>
            <label className="text-slate-700 block mb-1 font-bold">Location / Address (Optional)</label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="e.g. 100 Queen St, Brisbane QLD"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
            />
          </div>

          <div>
            <label className="text-slate-700 block mb-1 font-bold">Google Place ID (Optional)</label>
            <input
              type="text"
              value={placeId}
              onChange={(e) => setPlaceId(e.target.value)}
              placeholder="e.g. ChIJ..."
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
            />
          </div>

          <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setIsManualModalOpen(false)}
              className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 font-bold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={addingManual || !name.trim()}
              className="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold flex items-center space-x-1 disabled:opacity-50"
            >
              {addingManual ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
              <span>Save Competitor</span>
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

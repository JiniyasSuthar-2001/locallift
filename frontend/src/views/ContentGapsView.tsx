import React, { useState, useEffect, useMemo } from 'react';
import {
  Sparkles,
  MapPin,
  Layers,
  Target,
  ArrowRight,
  BookOpen,
  RotateCw,
  Search,
  Filter,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  X,
  Copy,
  Check,
  Award,
  FileText,
  Lightbulb,
  ExternalLink,
  ShieldCheck,
  Tag
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { ContentOpportunity } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { Modal } from '../components/ui/Modal';
import api from '../api/client';

export const ContentGapsView: React.FC = () => {
  const { activeProject } = useProject();
  const [opportunities, setOpportunities] = useState<ContentOpportunity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters & Sorting
  const [searchQuery, setSearchQuery] = useState('');
  const [pageTypeFilter, setPageTypeFilter] = useState('all');
  const [priorityFilter, setPriorityFilter] = useState('all');
  const [sortBy, setSortBy] = useState<'score' | 'priority' | 'volume' | 'title'>('score');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 6;

  // Detail Drawer Modal
  const [selectedOpp, setSelectedOpp] = useState<ContentOpportunity | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const fetchOpportunities = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      setError(null);
      const resp = await api.get(`/ai/content-opportunities/${activeProject.id}`);
      setOpportunities(resp.data || []);
    } catch (e: any) {
      console.error('Failed to load content opportunities:', e);
      setError('Unable to load content opportunities. Please check connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setCurrentPage(1);
    fetchOpportunities();
  }, [activeProject?.id]);

  const handleCopy = (text: string, fieldId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldId);
    setTimeout(() => setCopiedField(null), 2000);
  };

  // Filtered and Sorted Opportunities
  const filteredOpportunities = useMemo(() => {
    return opportunities
      .filter((opp) => {
        const q = searchQuery.toLowerCase().trim();
        const matchesSearch =
          !q ||
          (opp.topic && opp.topic.toLowerCase().includes(q)) ||
          (opp.title && opp.title.toLowerCase().includes(q)) ||
          (opp.primary_keyword && opp.primary_keyword.toLowerCase().includes(q)) ||
          (opp.location && opp.location.toLowerCase().includes(q)) ||
          (opp.target_slug && opp.target_slug.toLowerCase().includes(q));

        const matchesType =
          pageTypeFilter === 'all' ||
          (opp.page_type && opp.page_type.toLowerCase().includes(pageTypeFilter.toLowerCase())) ||
          (opp.recommended_page_type && opp.recommended_page_type.toLowerCase().includes(pageTypeFilter.toLowerCase()));

        const matchesPriority =
          priorityFilter === 'all' ||
          (opp.priority && opp.priority.toLowerCase() === priorityFilter.toLowerCase()) ||
          (opp.business_value && opp.business_value.toLowerCase() === priorityFilter.toLowerCase());

        return matchesSearch && matchesType && matchesPriority;
      })
      .sort((a, b) => {
        if (sortBy === 'score') {
          return (b.opportunity_score ?? 0) - (a.opportunity_score ?? 0);
        }
        if (sortBy === 'volume') {
          return (b.search_volume ?? 0) - (a.search_volume ?? 0);
        }
        if (sortBy === 'priority') {
          const priorityOrder: Record<string, number> = { high: 3, medium: 2, low: 1 };
          const pA = priorityOrder[(a.priority || a.business_value || 'medium').toLowerCase()] || 2;
          const pB = priorityOrder[(b.priority || b.business_value || 'medium').toLowerCase()] || 2;
          return pB - pA;
        }
        return (a.topic || '').localeCompare(b.topic || '');
      });
  }, [opportunities, searchQuery, pageTypeFilter, priorityFilter, sortBy]);

  // Pagination Slice
  const totalPages = Math.max(1, Math.ceil(filteredOpportunities.length / pageSize));
  const paginatedOpportunities = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredOpportunities.slice(start, start + pageSize);
  }, [filteredOpportunities, currentPage, pageSize]);

  if (!activeProject) {
    return (
      <EmptyState
        icon={Sparkles}
        badge="Content Gaps"
        title="Select a Project"
        description="Select a business project to discover missing suburban location landing pages and high-value service topics."
      />
    );
  }

  const getScoreColor = (score?: number | null) => {
    if (score == null) return 'text-slate-600 bg-slate-50 border-slate-200';
    if (score >= 85) return 'text-emerald-700 bg-emerald-50 border-emerald-200';
    if (score >= 70) return 'text-purple-700 bg-purple-50 border-purple-200';
    return 'text-amber-700 bg-amber-50 border-amber-200';
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <Sparkles className="w-6 h-6 text-purple-600" />
            <span>Content & Landing Page Opportunities</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Data-driven recommendations for missing suburban landing pages, service pillars, and commercial pricing guides for {activeProject.domain}.
          </p>
        </div>

        <button
          onClick={fetchOpportunities}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-[#142820] bg-white border border-[#DCE8DC] hover:bg-[#F1F7F1] transition-all shadow-xs self-start sm:self-auto disabled:opacity-50"
        >
          <RotateCw className={`w-3.5 h-3.5 text-[#236B4F] ${loading ? 'animate-spin' : ''}`} />
          <span>{loading ? 'Analyzing Signals...' : 'Refresh Opportunities'}</span>
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 font-medium">
          {error}
        </div>
      )}

      {/* Controls: Search, Filters, Sort */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-white p-3 rounded-2xl border border-slate-200 shadow-xs">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="Search opportunities by keyword, topic, or location..."
            className="w-full pl-9 pr-4 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:border-purple-400 transition-colors"
          />
        </div>

        {/* Dropdowns */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Page Type Filter */}
          <div className="flex items-center space-x-1.5 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-xl">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={pageTypeFilter}
              onChange={(e) => {
                setPageTypeFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="bg-transparent text-xs font-semibold text-slate-800 focus:outline-none cursor-pointer"
            >
              <option value="all">All Page Types</option>
              <option value="suburban">Suburban Landing Pages</option>
              <option value="service">Service Pages</option>
              <option value="pricing">Commercial Pricing Guides</option>
              <option value="guide">Commercial Guides</option>
            </select>
          </div>

          {/* Priority Filter */}
          <div className="flex items-center space-x-1.5 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-xl">
            <select
              value={priorityFilter}
              onChange={(e) => {
                setPriorityFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="bg-transparent text-xs font-semibold text-slate-800 focus:outline-none cursor-pointer"
            >
              <option value="all">All Priorities</option>
              <option value="high">High Priority</option>
              <option value="medium">Medium Priority</option>
              <option value="low">Low Priority</option>
            </select>
          </div>

          {/* Sort By */}
          <div className="flex items-center space-x-1.5 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-xl">
            <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-transparent text-xs font-semibold text-slate-800 focus:outline-none cursor-pointer"
            >
              <option value="score">Opportunity Score</option>
              <option value="priority">Priority</option>
              <option value="volume">Search Volume</option>
              <option value="title">Topic A-Z</option>
            </select>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {loading && opportunities.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 space-y-3">
          <div className="w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin shadow-md shadow-purple-500/10" />
          <p className="text-xs font-semibold text-slate-600">
            Synthesizing keywords, crawled pages, GSC queries, and suburban matrices...
          </p>
        </div>
      )}

      {/* Opportunities Grid */}
      {!loading && paginatedOpportunities.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {paginatedOpportunities.map((opp, idx) => {
              const score = opp.opportunity_score;
              const priority = opp.priority || opp.business_value || 'High';

              return (
                <div
                  key={idx}
                  className="bg-white rounded-2xl border border-slate-200 p-5 space-y-4 flex flex-col justify-between hover:border-purple-300 hover:shadow-md transition-all group"
                >
                  <div className="space-y-3">
                    {/* Header Badges */}
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 border border-purple-200 truncate">
                        {opp.recommended_page_type || opp.page_type}
                      </span>
                      <div className="flex items-center space-x-1.5 shrink-0">
                        <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded-md border ${getScoreColor(score)}`}>
                          {score != null ? `${score}/100 Score` : 'Score Pending'}
                        </span>
                      </div>
                    </div>

                    {/* Topic / Title */}
                    <div>
                      <h3 className="font-extrabold text-slate-900 text-sm leading-snug group-hover:text-purple-700 transition-colors">
                        {opp.title || opp.topic}
                      </h3>
                      <div className="text-[11px] text-slate-400 font-mono mt-1 truncate">
                        {opp.target_slug}
                      </div>
                    </div>

                    {/* Key Metrics Pill Box */}
                    <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 space-y-1.5 text-xs">
                      <div className="flex justify-between items-center">
                        <span className="text-slate-500 text-[11px]">Primary Keyword:</span>
                        <span className="font-bold text-slate-900 text-[11px] truncate max-w-[140px]">
                          {opp.target_keyword || opp.primary_keyword}
                        </span>
                      </div>
                      {opp.location && (
                        <div className="flex justify-between items-center">
                          <span className="text-slate-500 text-[11px]">Location:</span>
                          <span className="font-semibold text-slate-700 text-[11px] flex items-center gap-1">
                            <MapPin className="w-3 h-3 text-rose-500" />
                            {opp.location}
                          </span>
                        </div>
                      )}
                      <div className="flex justify-between items-center">
                        <span className="text-slate-500 text-[11px]">Search Intent:</span>
                        <span className="font-medium text-slate-700 text-[11px]">
                          {opp.search_intent}
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-slate-500 text-[11px]">Demand Signal:</span>
                        <span className="text-purple-700 font-bold text-[11px]">
                          {opp.search_volume !== null && opp.search_volume !== undefined
                            ? `${opp.search_volume} searches/mo`
                            : (opp.search_volume_status || 'High Local Intent')}
                        </span>
                      </div>
                    </div>

                    {/* Secondary Keywords Preview */}
                    {opp.secondary_keywords && opp.secondary_keywords.length > 0 && (
                      <div className="space-y-1">
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                          Keywords to Cover ({opp.secondary_keywords.length})
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {opp.secondary_keywords.slice(0, 3).map((sk, sIdx) => (
                            <span
                              key={sIdx}
                              className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 truncate max-w-[120px]"
                            >
                              {sk}
                            </span>
                          ))}
                          {opp.secondary_keywords.length > 3 && (
                            <span className="text-[10px] px-1.5 py-0.5 text-slate-400 font-semibold">
                              +{opp.secondary_keywords.length - 3} more
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Action Button */}
                  <button
                    onClick={() => setSelectedOpp(opp)}
                    className="w-full mt-2 py-2 px-3 rounded-xl bg-slate-50 hover:bg-purple-50 text-slate-700 hover:text-purple-700 border border-slate-200 hover:border-purple-300 text-xs font-bold transition-all flex items-center justify-center space-x-1.5 cursor-pointer"
                  >
                    <span>View Content Strategy & Brief</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between bg-white px-4 py-3 rounded-2xl border border-slate-200 text-xs">
              <span className="text-slate-500 font-medium">
                Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, filteredOpportunities.length)} of {filteredOpportunities.length} opportunities
              </span>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="font-bold text-slate-800 px-2">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Empty State when filters return 0 */}
      {!loading && opportunities.length > 0 && filteredOpportunities.length === 0 && (
        <div className="text-center py-16 bg-white rounded-2xl border border-slate-200 p-8 space-y-3">
          <Search className="w-8 h-8 text-slate-300 mx-auto" />
          <h3 className="text-sm font-bold text-slate-800">No opportunities match the selected filters</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Try adjusting your search query, page type, or priority filters to view available recommendations.
          </p>
          <button
            onClick={() => {
              setSearchQuery('');
              setPageTypeFilter('all');
              setPriorityFilter('all');
            }}
            className="text-xs font-bold text-purple-600 hover:underline pt-2 inline-block"
          >
            Clear All Filters
          </button>
        </div>
      )}

      {/* Empty State when 0 opportunities exist at all */}
      {!loading && opportunities.length === 0 && (
        <EmptyState
          icon={Sparkles}
          badge="Content Intelligence"
          title="No Content Opportunities Generated Yet"
          description="Click 'Refresh Opportunities' or run a Central Intelligence Scan to discover suburban location landing pages and keyword ranking targets."
          actionText="Generate Content Opportunities"
          onAction={fetchOpportunities}
        />
      )}

      {/* ─── DETAIL DRAWER / CONTENT BRIEF MODAL ─── */}
      <Modal
        isOpen={Boolean(selectedOpp)}
        onClose={() => setSelectedOpp(null)}
        maxWidth="2xl"
        title={selectedOpp?.title || selectedOpp?.topic || 'Content Opportunity'}
        description={
          selectedOpp
            ? `Recommended URL: ${selectedOpp.target_slug || ''}`
            : undefined
        }
        footer={
          <div className="flex items-center justify-between w-full">
            <span className="text-slate-500 text-xs">
              Target location: <strong className="text-slate-800">{selectedOpp?.location || activeProject.name}</strong>
            </span>
            <button
              onClick={() => setSelectedOpp(null)}
              className="px-5 py-2 rounded-xl bg-[#236B4F] text-white text-xs font-bold hover:bg-[#1D5A42] transition-colors shadow-xs"
            >
              Done
            </button>
          </div>
        }
      >
        {selectedOpp && (
          <div className="space-y-5 text-xs divide-y divide-slate-100">
            {/* Badges */}
            <div className="flex items-center space-x-2 pb-1">
              <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800">
                {selectedOpp.recommended_page_type || selectedOpp.page_type}
              </span>
              <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200">
                {selectedOpp.opportunity_score != null ? `${selectedOpp.opportunity_score}/100 Score` : 'Score Pending'}
              </span>
              <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200">
                {selectedOpp.priority || 'High'} Priority
              </span>
            </div>

            {/* Strategy & AI Recommendation */}
            <div className="space-y-2 pt-4">
              <div className="flex items-center space-x-2 text-slate-900 font-bold text-sm">
                <Lightbulb className="w-4 h-4 text-amber-500" />
                <span>Strategic Content Recommendation</span>
              </div>
              <div className="p-4 rounded-xl bg-emerald-50/70 border border-emerald-100 text-slate-800 leading-relaxed">
                {selectedOpp.ai_recommendation || (
                  `Target '${selectedOpp.target_keyword || selectedOpp.primary_keyword}'. Create a dedicated localized landing page featuring clear heading hierarchy, client proof, LocalBusiness schema, and location-targeted service highlights.`
                )}
              </div>
            </div>

            {/* Structured Content Brief */}
            <div className="pt-4 space-y-3">
              <div className="flex items-center space-x-2 text-slate-900 font-bold text-sm">
                <FileText className="w-4 h-4 text-[#236B4F]" />
                <span>Structured Page Blueprint</span>
              </div>

              <div className="space-y-2.5">
                {/* Suggested H1 */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      Suggested H1 Tag
                    </span>
                    <span className="font-bold text-slate-900 text-xs mt-0.5 block">
                      {selectedOpp.content_brief?.suggested_h1 || (selectedOpp.title || selectedOpp.topic)}
                    </span>
                  </div>
                  <button
                    onClick={() => handleCopy(selectedOpp.content_brief?.suggested_h1 || selectedOpp.topic, 'h1')}
                    className="p-1.5 text-slate-400 hover:text-slate-700"
                    title="Copy H1"
                  >
                    {copiedField === 'h1' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>

                {/* Meta Description */}
                {selectedOpp.content_brief?.meta_description && (
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-start justify-between gap-2">
                    <div>
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                        Suggested Meta Description
                      </span>
                      <span className="text-slate-700 text-xs mt-0.5 block leading-relaxed">
                        {selectedOpp.content_brief.meta_description}
                      </span>
                    </div>
                    <button
                      onClick={() => handleCopy(selectedOpp.content_brief!.meta_description!, 'meta')}
                      className="p-1.5 text-slate-400 hover:text-slate-700"
                      title="Copy Meta Description"
                    >
                      {copiedField === 'meta' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                )}

                {/* Word Count & Schema Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="text-[10px] font-bold text-slate-400 uppercase block">Target Word Count</span>
                    <span className="text-sm font-black text-slate-800">
                      {selectedOpp.content_brief?.recommended_word_count || 850}+ words
                    </span>
                  </div>
                  <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-100">
                    <span className="text-[10px] font-bold text-slate-400 uppercase block">Recommended Schema</span>
                    <span className="text-xs font-bold text-emerald-700 truncate block">
                      {selectedOpp.content_brief?.schema_type || 'LocalBusiness / Service'}
                    </span>
                  </div>
                  <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-100 col-span-2 sm:col-span-1">
                    <span className="text-[10px] font-bold text-slate-400 uppercase block">Call to Action</span>
                    <span className="text-xs font-bold text-slate-800 truncate block">
                      {selectedOpp.content_brief?.cta || 'Book Consultation / Call Now'}
                    </span>
                  </div>
                </div>

                {/* Key Sections Outline */}
                {selectedOpp.content_brief?.key_sections && selectedOpp.content_brief.key_sections.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      Recommended Section Outline
                    </span>
                    <ul className="space-y-1 pl-1">
                      {selectedOpp.content_brief.key_sections.map((sec, sIdx) => (
                        <li key={sIdx} className="flex items-center space-x-2 text-slate-700 font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                          <span>{sec}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {/* Keywords to Include */}
            <div className="pt-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-slate-900 font-bold text-sm">
                  <Tag className="w-4 h-4 text-teal-600" />
                  <span>LSI & Secondary Keywords</span>
                </div>
                <button
                  onClick={() => handleCopy((selectedOpp.secondary_keywords || []).join(', '), 'keywords')}
                  className="text-[11px] font-bold text-emerald-700 hover:underline flex items-center gap-1 cursor-pointer"
                >
                  {copiedField === 'keywords' ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-600" />
                      <span>Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy All Keywords</span>
                    </>
                  )}
                </button>
              </div>

              <div className="flex flex-wrap gap-1.5">
                <span className="px-2.5 py-1 rounded-lg bg-emerald-100 text-emerald-900 font-bold border border-emerald-200">
                  {selectedOpp.target_keyword || selectedOpp.primary_keyword} (Primary)
                </span>
                {(selectedOpp.secondary_keywords || []).map((sk, skIdx) => (
                  <span
                    key={skIdx}
                    className="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-800 font-medium border border-slate-200"
                  >
                    {sk}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

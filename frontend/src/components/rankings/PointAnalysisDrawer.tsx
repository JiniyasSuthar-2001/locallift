import React, { useEffect, useState } from 'react';
import {
  X,
  MapPin,
  TrendingUp,
  Compass,
  Building2,
  ExternalLink,
  Star,
  MessageSquare,
  Globe,
  Phone,
  HelpCircle,
  CheckCircle2,
  AlertTriangle,
  ChevronUp,
  ChevronDown,
  Layers,
  Search,
  Sparkles,
  Info,
  ArrowUpRight,
  ShieldAlert,
  Clock
} from 'lucide-react';
import { GridPoint, PointAnalysisData, PointCompetitor } from '../../types';
import api from '../../api/client';
import { Drawer } from '../ui/Drawer';

interface PointAnalysisDrawerProps {
  point: GridPoint | null;
  scanId?: number;
  projectId?: number;
  keyword?: string;
  centerName?: string;
  onClose: () => void;
}

export const PointAnalysisDrawer: React.FC<PointAnalysisDrawerProps> = ({
  point,
  scanId,
  projectId,
  keyword,
  centerName,
  onClose
}) => {
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<PointAnalysisData | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'competitors' | 'diagnostics'>('overview');

  useEffect(() => {
    let isMounted = true;
    if (!point) {
      setAnalysis(null);
      return;
    }

    const fetchAnalysis = async () => {
      const ptNum = point.point_number ?? 0;
      if (projectId && scanId) {
        setLoading(true);
        try {
          const resp = await api.get(`/keywords/${projectId}/grid/scans/${scanId}/points/${ptNum}`);
          if (isMounted && resp.data) {
            setAnalysis(resp.data);
            setLoading(false);
            return;
          }
        } catch (e) {
          console.warn('Asynchronous point analysis fetch error, generating local view', e);
        }
      }

      // Local fallback generation
      if (isMounted) {
        const lat = point.lat ?? point.latitude ?? null;
        const lng = point.lng ?? point.longitude ?? null;
        const dist = point.distance_km ?? 0;
        const dir = point.direction || (dist === 0 ? 'Center' : 'Local');
        const depth = rank ? (rank <= 10 ? 10 : rank <= 25 ? 25 : rank <= 50 ? 50 : 100) : 20;

        const competitors = (point.competitors || []) as PointCompetitor[];
        const above = competitors.filter(c => rank != null && c.position < rank);
        const below = competitors.filter(c => rank != null && c.position > rank);
        const target = competitors.find(c => c.is_target) || null;

        const what = rank != null
          ? `Your business ranked #${rank} for '${point.keyword || keyword || 'target keyword'}' at this GPS scan coordinate.`
          : status === 'PROVIDER_ERROR' || status === 'ERROR'
          ? `SERP query encountered an error: ${point.error || 'Provider communication failure.'}`
          : `Your business was Not Found within the scanned local result depth (Top ${depth}).`;

        const coordsStr = lat != null && lng != null ? `(${lat.toFixed(5)}, ${lng.toFixed(5)})` : 'Coordinates unavailable';
        const where = `GPS: ${coordsStr} · ${dist} km ${dir} of ${centerName || 'Center'}`;

        const why: string[] = [];
        if (rank === 1) {
          why.push('Observed: Dominant #1 Local Pack position with maximum local proximity and relevance.');
        } else if (rank && rank <= 3) {
          why.push('Observed: Qualified inside the Google Local 3-Pack with strong local authority.');
        } else if (rank && rank > 3) {
          why.push(`Observed: Ranked #${rank}, outside the initial 3-pack view.`);
          if (above.length > 0) {
            const topComp = above[0];
            if (topComp.reviews_count && (target?.reviews_count || 0) < topComp.reviews_count) {
              why.push(`Observed Signal: Competitor '${topComp.title}' ranks #${topComp.position} with ${topComp.reviews_count} reviews (vs ${target?.reviews_count || 0} for your business).`);
            }
            if (topComp.rating && (target?.rating || 0) < topComp.rating) {
              why.push(`Detected Signal: Competitor '${topComp.title}' holds a ${topComp.rating}★ rating.`);
            }
          }
        } else {
          why.push(`Observed: Business profile not detected in the Top ${depth} search results at this location.`);
          why.push('Potential contributing signal: Geo-distance from business center or competitor density in this quadrant.');
        }

        setAnalysis({
          point_number: ptNum,
          scan_id: scanId || 0,
          project_id: projectId || 0,
          location: {
            point_number: ptNum,
            row: point.row,
            col: point.col,
            latitude: lat,
            longitude: lng,
            distance_km: dist,
            direction: dir,
            area_name: point.area_name || 'Area name unavailable',
            center_name: centerName,
            keyword: point.keyword || keyword || '',
            searched_at: point.searched_at
          },
          ranking: {
            business_name: point.matched_business || 'Your Business',
            rank: point.rank,
            status: point.status,
            result_depth: depth,
            ranking_url: point.ranking_url,
            place_id: point.matched_place_id || undefined,
            matched_place_id: point.matched_place_id || undefined,
            matched_domain: point.matched_domain || undefined,
            provider: point.provider,
            error: point.error || undefined
          },
          competitors_hierarchy: {
            competitors_above: above,
            target_business: target,
            competitors_below: below,
            total_competitors_evaluated: competitors.length,
            result_depth: depth,
            not_found_in_depth: rank == null
          },
          diagnostics: {
            what,
            where,
            how: [
              ...(point.matched_business ? [{ field: 'Business Name', value: point.matched_business, provider_observed: true }] : []),
              ...(point.matched_domain ? [{ field: 'Domain', value: point.matched_domain, provider_observed: true }] : []),
              ...(point.matched_place_id ? [{ field: 'Place ID', value: point.matched_place_id, provider_observed: true }] : []),
              ...(point.ranking_url ? [{ field: 'Maps URL', value: point.ranking_url, provider_observed: true }] : [])
            ],
            why
          }
        });
        setLoading(false);
      }
    };

    fetchAnalysis();

    return () => {
      isMounted = false;
    };
  }, [point, scanId, projectId, keyword, centerName]);

  if (!point) return null;

  const rank = point.rank;
  const status = (point.status || '').toUpperCase();
  const isErr = status === 'PROVIDER_ERROR' || status === 'ERROR' || status === 'TIMEOUT';
  const isNF = status === 'NOT_FOUND' || (status === 'SUCCESS' && rank === null);

  const badgeColor = isErr
    ? 'bg-slate-100 text-slate-800 border-slate-300'
    : isNF
    ? 'bg-rose-100 text-rose-800 border-rose-300'
    : rank && rank <= 3
    ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
    : rank && rank <= 7
    ? 'bg-blue-100 text-blue-800 border-blue-300'
    : rank && rank <= 15
    ? 'bg-amber-100 text-amber-800 border-amber-300'
    : 'bg-rose-100 text-rose-800 border-rose-300';

  const rankLabel = isErr
    ? 'ERROR'
    : isNF
    ? 'NOT FOUND'
    : `#${rank} LOCAL RANK`;

  const headerContent = (
    <div className="flex items-start justify-between gap-4 w-full pr-2">
      <div>
        <div className="flex flex-wrap items-center gap-2 mb-1.5">
          <span className="px-2.5 py-0.5 rounded-md text-xs font-black bg-[#236B4F] text-white">
            POINT #{point.point_number ?? 1}
          </span>
          <span className={`px-2.5 py-0.5 rounded-md text-xs font-bold border ${badgeColor}`}>
            {rankLabel}
          </span>
          {point.direction && (
            <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-slate-200 text-slate-700">
              {point.distance_km != null ? `${point.distance_km} km ` : ''}{point.direction}
            </span>
          )}
        </div>
        <h2 className="text-base font-bold text-slate-900 line-clamp-1">
          {point.keyword || keyword || 'Target Keyword Analysis'}
        </h2>
        <p className="text-xs text-slate-500 flex items-center gap-1.5 mt-0.5">
          <MapPin className="w-3.5 h-3.5 text-[#236B4F]" />
          <span className="font-bold text-slate-800">
            Area: {analysis?.location?.area_name || point.area_name || 'Area name unavailable'}
          </span>
          <span>·</span>
          <span>{(point.lat ?? point.latitude)?.toFixed(5)}, {(point.lng ?? point.longitude)?.toFixed(5)}</span>
        </p>
      </div>
    </div>
  );

  return (
    <Drawer
      isOpen={!!point}
      onClose={onClose}
      maxWidth="2xl"
      headerContent={headerContent}
      showCloseButton={true}
      bodyClassName="flex flex-col p-0"
    >
      {/* ─── Navigation Tabs ─── */}
      <div className="flex items-center border-b border-slate-200 bg-white px-5 shrink-0">
        <button
          onClick={() => setActiveTab('overview')}
          className={`py-3 px-3 text-xs font-bold border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === 'overview'
              ? 'border-[#236B4F] text-[#236B4F]'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          <Compass className="w-3.5 h-3.5" />
          Location & Rank
        </button>
        <button
          onClick={() => setActiveTab('competitors')}
          className={`py-3 px-3 text-xs font-bold border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === 'competitors'
              ? 'border-[#236B4F] text-[#236B4F]'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          Competitors Above / Below
          {analysis?.competitors_hierarchy && (
            <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-slate-100 text-slate-700 font-semibold">
              {analysis.competitors_hierarchy.total_competitors_evaluated}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('diagnostics')}
          className={`py-3 px-3 text-xs font-bold border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === 'diagnostics'
              ? 'border-[#236B4F] text-[#236B4F]'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          What / Where / How / Why
        </button>
      </div>

      {/* ─── Body Content Scroll Area ─── */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {loading ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-8 h-8 border-3 border-[#236B4F] border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-slate-500 font-medium">Loading point analysis & competitor hierarchy...</p>
          </div>
        ) : (
          <>
            {/* ══════════ TAB 1: OVERVIEW & LOCATION ══════════ */}
            {activeTab === 'overview' && (
              <div className="space-y-5">
                {/* Ranking Summary Banner */}
                <div className={`p-4 rounded-xl border ${badgeColor} space-y-2`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black uppercase tracking-wider">
                      Observed Position
                    </span>
                    <span className="text-lg font-extrabold">
                      {rank ? `#${rank}` : isErr ? 'ERROR' : 'NOT FOUND'}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed font-medium">
                    {analysis?.diagnostics.what || (
                      rank
                        ? `Your business is positioned at #${rank} for this coordinate.`
                        : 'Your business was not found in top search results at this location.'
                    )}
                  </p>
                </div>

                {/* Location Details Card */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3 shadow-sm">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-[#236B4F]" />
                    Geographic Location
                  </h3>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-slate-400 block text-[10px] font-semibold uppercase">Area / Locality</span>
                      <span className="font-semibold text-slate-800">{analysis?.location?.area_name || point.area_name || 'Area name unavailable'}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-semibold uppercase">Scan Center</span>
                      <span className="font-semibold text-slate-800">{centerName || 'Business Location'}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-semibold uppercase">Exact Latitude</span>
                      <span className="font-semibold text-slate-800">{(point.lat ?? point.latitude)?.toFixed(6)}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-semibold uppercase">Exact Longitude</span>
                      <span className="font-semibold text-slate-800">{(point.lng ?? point.longitude)?.toFixed(6)}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-semibold uppercase">Distance from Center</span>
                      <span className="font-semibold text-slate-800">{point.distance_km ?? 0} km</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px] font-semibold uppercase">Compass Direction</span>
                      <span className="font-semibold text-slate-800">{point.direction || 'Center'}</span>
                    </div>
                    <div className="col-span-2 pt-1 border-t border-slate-100">
                      <span className="text-slate-400 block text-[10px] font-semibold uppercase">Grid Coordinates</span>
                      <span className="font-medium text-slate-600">Row {point.row + 1}, Col {point.col + 1} (Point #{point.point_number ?? 1})</span>
                    </div>
                  </div>
                </div>

                {/* Ranking Metadata Card */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3 shadow-sm">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                    <TrendingUp className="w-3.5 h-3.5 text-[#236B4F]" />
                    SERP & Business Data
                  </h3>
                  <div className="space-y-2.5 text-xs">
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Business Matched</span>
                      <span className="font-semibold text-slate-800">{point.matched_business || '—'}</span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Domain</span>
                      <span className="font-semibold text-slate-800">{point.matched_domain || '—'}</span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Place ID</span>
                      <span className="font-mono text-[11px] text-slate-700">{point.matched_place_id || '—'}</span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Result Depth Scanned</span>
                      <span className="font-semibold text-slate-800">Top {analysis?.ranking.result_depth || 20}</span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Provider</span>
                      <span className="font-semibold text-slate-800">{point.provider || 'SerpApi'}</span>
                    </div>
                    {point.ranking_url && (
                      <div className="pt-1">
                        <a
                          href={point.ranking_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs font-semibold text-[#236B4F] hover:underline"
                        >
                          View Local Search URL <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    )}
                    {point.error && (
                      <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 text-xs">
                        <span className="font-bold block mb-0.5">Provider Error:</span>
                        {point.error}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* ══════════ TAB 2: COMPETITORS ABOVE AND BELOW ══════════ */}
            {activeTab === 'competitors' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>Scanned Depth: <strong>Top {analysis?.competitors_hierarchy.result_depth || 20}</strong></span>
                  <span>Total Evaluated: <strong>{analysis?.competitors_hierarchy.total_competitors_evaluated || 0}</strong></span>
                </div>

                {/* COMPETITORS ABOVE YOU */}
                {analysis?.competitors_hierarchy.competitors_above && analysis.competitors_hierarchy.competitors_above.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-rose-700 uppercase tracking-wider">
                      <ChevronUp className="w-4 h-4" />
                      Competitors Above You ({analysis.competitors_hierarchy.competitors_above.length})
                    </div>
                    <div className="space-y-1.5">
                      {analysis.competitors_hierarchy.competitors_above.map((comp) => (
                        <CompetitorCard key={`comp-above-${comp.position}`} competitor={comp} isTarget={false} />
                      ))}
                    </div>
                  </div>
                )}

                {/* YOUR BUSINESS */}
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-[#236B4F] uppercase tracking-wider">
                    <Building2 className="w-4 h-4" />
                    Your Business
                  </div>
                  {rank != null ? (
                    <CompetitorCard
                      competitor={analysis?.competitors_hierarchy.target_business || {
                        position: rank,
                        title: point.matched_business || 'Your Business',
                        domain: point.matched_domain || '',
                        is_target: true
                      }}
                      isTarget={true}
                    />
                  ) : (
                    <div className="p-3.5 rounded-xl border border-rose-200 bg-rose-50 text-xs text-rose-800">
                      <div className="font-bold mb-1 flex items-center gap-1">
                        <AlertTriangle className="w-4 h-4 text-rose-600" />
                        Business Not Found in Scanned Depth
                      </div>
                      <p className="text-rose-700">
                        Your business was not found within the Top {analysis?.competitors_hierarchy.result_depth || 20} search results at this coordinate.
                      </p>
                    </div>
                  )}
                </div>

                {/* COMPETITORS BELOW YOU */}
                {analysis?.competitors_hierarchy.competitors_below && analysis.competitors_hierarchy.competitors_below.length > 0 && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-blue-700 uppercase tracking-wider">
                      <ChevronDown className="w-4 h-4" />
                      Competitors Below You ({analysis.competitors_hierarchy.competitors_below.length})
                    </div>
                    <div className="space-y-1.5">
                      {analysis.competitors_hierarchy.competitors_below.map((comp) => (
                        <CompetitorCard key={`comp-below-${comp.position}`} competitor={comp} isTarget={false} />
                      ))}
                    </div>
                  </div>
                )}

                {/* If Not Found, render top discovered competitors */}
                {rank == null && analysis?.competitors_hierarchy.competitors_above.length === 0 && (
                  <div className="space-y-2">
                    <div className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                      Top Discovered Local Results
                    </div>
                    <div className="space-y-1.5">
                      {((point.competitors || []) as PointCompetitor[]).map((comp) => (
                        <CompetitorCard key={`comp-discovered-${comp.position}`} competitor={comp} isTarget={false} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ══════════ TAB 3: WHAT / WHERE / HOW / WHY ══════════ */}
            {activeTab === 'diagnostics' && (
              <div className="space-y-5">
                {/* WHAT */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-[#236B4F] text-white text-[11px] font-black flex items-center justify-center">1</span>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[#236B4F]">WHAT — Observed Ranking</h3>
                  </div>
                  <p className="text-xs text-slate-800 leading-relaxed font-medium pl-7">
                    {analysis?.diagnostics.what}
                  </p>
                </div>

                {/* WHERE */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-blue-600 text-white text-[11px] font-black flex items-center justify-center">2</span>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-blue-700">WHERE — Geographic Coordinates</h3>
                  </div>
                  <p className="text-xs text-slate-800 leading-relaxed font-medium pl-7">
                    {analysis?.diagnostics.where}
                  </p>
                </div>

                {/* HOW */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-amber-600 text-white text-[11px] font-black flex items-center justify-center">3</span>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-amber-700">HOW — Provider-Observed Fields</h3>
                  </div>
                  <div className="pl-7 space-y-1.5">
                    {analysis?.diagnostics.how && analysis.diagnostics.how.length > 0 ? (
                      analysis.diagnostics.how.map((item, idx) => (
                        <div key={idx} className="flex items-center justify-between text-xs py-1 border-b border-slate-100">
                          <span className="text-slate-500 font-medium">{item.field}</span>
                          <span className="font-semibold text-slate-800 break-all">{item.value}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-slate-500 italic">No direct profile attributes returned for unranked query.</p>
                    )}
                  </div>
                </div>

                {/* WHY */}
                <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-purple-600 text-white text-[11px] font-black flex items-center justify-center">4</span>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-purple-700">WHY — Evidence-Based Diagnostics</h3>
                  </div>
                  <div className="pl-7 space-y-2">
                    {analysis?.diagnostics.why && analysis.diagnostics.why.length > 0 ? (
                      analysis.diagnostics.why.map((reason, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-xs text-slate-800 leading-relaxed">
                          <CheckCircle2 className="w-3.5 h-3.5 text-[#236B4F] shrink-0 mt-0.5" />
                          <span>{reason}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-slate-500 italic">Insufficient evidence collected for diagnostic causality.</p>
                    )}
                    <div className="pt-2 text-[10px] text-slate-400 italic">
                      * Evidence-based signals are derived directly from observed SERP ranking metadata and competitor comparison metrics.
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Drawer>
  );
};

const CompetitorCard: React.FC<{ competitor: PointCompetitor; isTarget: boolean }> = ({ competitor, isTarget }) => {
  return (
    <div
      className={`p-3 rounded-xl border transition-all text-xs ${
        isTarget
          ? 'bg-emerald-50/80 border-emerald-300 ring-2 ring-[#236B4F]/30'
          : 'bg-white border-slate-200 hover:border-slate-300'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2.5">
          <span
            className={`w-6 h-6 rounded-lg text-xs font-black flex items-center justify-center shrink-0 ${
              isTarget
                ? 'bg-[#236B4F] text-white'
                : competitor.position <= 3
                ? 'bg-emerald-100 text-emerald-800'
                : competitor.position <= 7
                ? 'bg-blue-100 text-blue-800'
                : 'bg-slate-100 text-slate-700'
            }`}
          >
            #{competitor.position}
          </span>
          <div className="space-y-0.5">
            <div className="font-bold text-slate-900 flex items-center gap-1.5">
              <span>{competitor.title}</span>
              {isTarget && (
                <span className="px-1.5 py-0.2 rounded text-[9px] font-black uppercase bg-[#236B4F] text-white">
                  YOU
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-slate-500 text-[11px]">
              {competitor.rating != null && (
                <span className="flex items-center gap-0.5 font-semibold text-amber-700">
                  <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                  {competitor.rating}
                  {competitor.reviews_count != null && (
                    <span className="text-slate-400 font-normal">({competitor.reviews_count})</span>
                  )}
                </span>
              )}
              {competitor.category && (
                <span className="text-slate-600 font-medium">· {competitor.category}</span>
              )}
              {competitor.domain && (
                <span className="text-slate-400 font-mono text-[10px]">· {competitor.domain}</span>
              )}
            </div>
            {competitor.address && (
              <p className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                {competitor.address}
              </p>
            )}
          </div>
        </div>

        {competitor.link && (
          <a
            href={competitor.link}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            title="Open link"
          >
            <ArrowUpRight className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import {
  MapPin,
  Navigation,
  Sparkles,
  Filter,
  RotateCw,
  Search,
  Layers,
  History,
  GitCompare,
  TrendingUp,
  ChevronDown,
  Clock,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  X
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { GeoGridScan, Keyword } from '../types';
import { LocalGridMap } from '../components/rankings/LocalGridMap';
import { LocationPickerModal } from '../components/rankings/LocationPickerModal';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';
import { getErrorMessage } from '../utils/error';

interface HistoryEntry {
  id: number;
  keyword_id?: number;
  keyword?: string;
  center_name?: string;
  center_lat: number;
  center_lng: number;
  radius_km: number;
  grid_size: number;
  average_rank?: number;
  local_visibility_pct?: number;
  total_points: number;
  completed_points: number;
  ranking_found_points: number;
  not_found_points: number;
  provider_error_points: number;
  scan_status: string;
  scanned_at: string;
}

interface ComparisonResult {
  scan_a_id: number;
  scan_b_id: number;
  average_rank_a?: number;
  average_rank_b?: number;
  rank_delta?: number;
  visibility_pct_a?: number;
  visibility_pct_b?: number;
  visibility_delta?: number;
  point_comparisons?: Array<{
    point_number: number;
    lat: number;
    lng: number;
    rank_a?: number;
    rank_b?: number;
    delta?: number;
    improved?: boolean;
    declined?: boolean;
    unchanged?: boolean;
  }>;
}

export const LocalGridRankingsView: React.FC = () => {
  const { activeProject } = useProject();
  const [scan, setScan] = useState<GeoGridScan | null>(null);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [selectedKeywordId, setSelectedKeywordId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [isPickerOpen, setIsPickerOpen] = useState(false);

  // History & Comparison state
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [compareScanA, setCompareScanA] = useState<number | null>(null);
  const [compareScanB, setCompareScanB] = useState<number | null>(null);
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [comparing, setComparing] = useState(false);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);

  const fetchKeywords = async () => {
    if (!activeProject) return;
    try {
      const resp = await api.get(`/keywords/${activeProject.id}`);
      const list: Keyword[] = Array.isArray(resp.data) ? resp.data : [];
      setKeywords(list);
      if (list.length > 0 && selectedKeywordId === null) {
        setSelectedKeywordId(list[0].id);
      }
    } catch (e: any) {
      console.error('Failed to load project keywords:', e);
    }
  };

  const fetchHistory = async (keywordId?: number) => {
    if (!activeProject) return;
    try {
      const endpoint = keywordId
        ? `/keywords/${activeProject.id}/grid/history?keyword_id=${keywordId}`
        : `/keywords/${activeProject.id}/grid/history`;
      const resp = await api.get(endpoint);
      setHistory(Array.isArray(resp.data) ? resp.data : []);
    } catch (e) {
      console.error('Failed to load scan history:', e);
    }
  };

  const fetchScan = async (keywordId?: number) => {
    if (!activeProject) return;
    try {
      setLoading(true);
      setScanError(null);
      const endpoint = keywordId
        ? `/keywords/${activeProject.id}/grid?keyword_id=${keywordId}`
        : `/keywords/${activeProject.id}/grid`;
      const resp = await api.get(endpoint);
      setScan(resp.data);
      if (resp.data?.keyword_id) {
        setSelectedKeywordId(resp.data.keyword_id);
      }
    } catch (e: any) {
      console.error('Failed to load grid scan:', e);
      if (e.response?.status === 404) {
        setScan(null);
      } else {
        setScanError(getErrorMessage(e, 'Failed to load grid scan from backend.'));
      }
    } finally {
      setLoading(false);
    }
  };

  const loadSpecificScan = async (scanId: number) => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/keywords/${activeProject.id}/grid/scans/${scanId}`);
      setScan(resp.data);
      setShowHistory(false);
    } catch (e) {
      console.error('Failed to load scan by ID:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = async () => {
    if (!activeProject || !compareScanA || !compareScanB) return;
    try {
      setComparing(true);
      const resp = await api.get(
        `/keywords/${activeProject.id}/grid/compare?scan_a_id=${compareScanA}&scan_b_id=${compareScanB}`
      );
      setComparison(resp.data);
      setIsCompareModalOpen(true);
    } catch (e: any) {
      console.error('Failed to compare scans:', e);
      alert(getErrorMessage(e, 'Failed to compare scans.'));
    } finally {
      setComparing(false);
    }
  };

  // Immediate state flushing on project switch
  useEffect(() => {
    setScan(null);
    setKeywords([]);
    setSelectedKeywordId(null);
    setScanError(null);
    setHistory([]);
    setComparison(null);

    if (activeProject?.id) {
      fetchKeywords();
      fetchScan();
      fetchHistory();
    }
  }, [activeProject?.id]);

  const handleStartScanWithLocation = async (params: {
    location_id?: number;
    center_lat?: number;
    center_lng?: number;
    center_name?: string;
    keyword_id?: number;
    keyword: string;
    radius_km?: number;
    grid_size?: number;
  }) => {
    if (!activeProject) return;
    const cleanKeyword = params.keyword?.trim();
    if (!cleanKeyword) {
      setScanError('Target SEO keyword is required. Select a tracked keyword or enter a search term.');
      return;
    }

    try {
      setIsScanning(true);
      setScanError(null);

      await api.post(`/keywords/${activeProject.id}/grid/rescan`, {
        keyword_id: params.keyword_id,
        keyword: cleanKeyword,
        location_id: params.location_id,
        center_lat: params.center_lat,
        center_lng: params.center_lng,
        center_name: params.center_name,
        radius_km: params.radius_km || 5.0,
        grid_size: params.grid_size || 5
      });

      setIsPickerOpen(false);
      await fetchScan(params.keyword_id);
      await fetchHistory(params.keyword_id);
    } catch (e: any) {
      console.error('Grid rescan failed:', e);
      setScanError(getErrorMessage(e, 'Geo-Grid scan failed.'));
    } finally {
      setIsScanning(false);
    }
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={MapPin}
        badge="Geo-Grid"
        title="Select a Project"
        description="Select an active project to view discrete GPS ranking matrices across the service territory."
      />
    );
  }

  const initialKeyword = scan?.keyword || (keywords.length > 0 ? keywords[0].keyword : '');
  const initialKeywordId = scan?.keyword_id || selectedKeywordId || (keywords.length > 0 ? keywords[0].id : undefined);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <MapPin className="w-6 h-6 text-emerald-600" />
            <span>Local Visibility — 5x5 Geo-Grid Rankings</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Geographic local rank intelligence: 25 discrete GPS search points centered on your business address.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Keyword Quick Switcher */}
          {keywords.length > 0 && (
            <div className="flex items-center space-x-2 bg-white px-3 py-1.5 rounded-xl border border-slate-200 shadow-xs">
              <Search className="w-4 h-4 text-emerald-600 shrink-0" />
              <span className="text-xs font-bold text-slate-600">Keyword:</span>
              <select
                value={selectedKeywordId || ''}
                onChange={(e) => {
                  const kid = parseInt(e.target.value);
                  setSelectedKeywordId(kid);
                  fetchScan(kid);
                  fetchHistory(kid);
                }}
                className="text-xs font-semibold text-slate-900 bg-transparent focus:outline-none cursor-pointer"
              >
                {keywords.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.keyword} {k.current_rank ? `(#${k.current_rank})` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* History Toggle Button */}
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border transition-all ${
              showHistory
                ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                : 'bg-white border-slate-200 text-slate-700 hover:border-emerald-300'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>History ({history.length})</span>
          </button>
        </div>
      </div>

      {/* History Drawer / Panel */}
      {showHistory && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center space-x-2">
              <History className="w-4 h-4 text-emerald-600" />
              <h3 className="text-sm font-black text-slate-900">Historical Geo-Grid Scans</h3>
            </div>
            <span className="text-xs text-slate-500">Select scans to view or compare</span>
          </div>

          {history.length === 0 ? (
            <p className="text-xs text-slate-400 py-4 text-center">No past scans recorded for this keyword.</p>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {history.map((h) => (
                  <div
                    key={h.id}
                    onClick={() => loadSpecificScan(h.id)}
                    className={`p-3 rounded-xl border text-left cursor-pointer transition-all ${
                      scan?.scan_id === h.id || scan?.id === h.id
                        ? 'border-emerald-500 bg-emerald-50/50 ring-1 ring-emerald-400'
                        : 'border-slate-200 hover:border-emerald-300 bg-slate-50/50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-bold text-slate-800">
                        {h.keyword || 'Search scan'}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        {new Date(h.scanned_at).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-xs">
                      <div>
                        <span className="text-slate-500 text-[10px]">Avg Rank:</span>{' '}
                        <span className="font-black text-slate-800">
                          {h.average_rank !== null && h.average_rank !== undefined ? `#${h.average_rank}` : 'N/A'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[10px]">Visibility:</span>{' '}
                        <span className="font-black text-emerald-700">
                          {h.local_visibility_pct !== null && h.local_visibility_pct !== undefined ? `${h.local_visibility_pct}%` : 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Comparison Selector */}
              {history.length >= 2 && (
                <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center gap-3">
                  <span className="text-xs font-bold text-slate-700 flex items-center space-x-1">
                    <GitCompare className="w-3.5 h-3.5 text-purple-600" />
                    <span>Compare Scans:</span>
                  </span>
                  <select
                    value={compareScanA || ''}
                    onChange={(e) => setCompareScanA(parseInt(e.target.value) || null)}
                    className="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white"
                  >
                    <option value="">Select Scan A (Baseline)</option>
                    {history.map((h) => (
                      <option key={h.id} value={h.id}>
                        Scan #{h.id} — {new Date(h.scanned_at).toLocaleDateString()} ({h.local_visibility_pct || 0}%)
                      </option>
                    ))}
                  </select>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                  <select
                    value={compareScanB || ''}
                    onChange={(e) => setCompareScanB(parseInt(e.target.value) || null)}
                    className="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white"
                  >
                    <option value="">Select Scan B (Comparison)</option>
                    {history.map((h) => (
                      <option key={h.id} value={h.id}>
                        Scan #{h.id} — {new Date(h.scanned_at).toLocaleDateString()} ({h.local_visibility_pct || 0}%)
                      </option>
                    ))}
                  </select>
                  <button
                    disabled={!compareScanA || !compareScanB || compareScanA === compareScanB || comparing}
                    onClick={handleCompare}
                    className="px-3 py-1 bg-purple-600 text-white text-xs font-bold rounded-lg hover:bg-purple-700 disabled:opacity-40"
                  >
                    {comparing ? 'Comparing...' : 'Compare Movement'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Comparison Modal */}
      {isCompareModalOpen && comparison && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <GitCompare className="w-5 h-5 text-purple-600" />
                <h3 className="text-base font-black text-slate-900">Scan Comparison Analysis</h3>
              </div>
              <button
                onClick={() => setIsCompareModalOpen(false)}
                className="p-1 text-slate-400 hover:text-slate-700 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Summary Deltas */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Avg Rank A</div>
                <div className="text-lg font-black text-slate-800">
                  {comparison.average_rank_a !== undefined ? `#${comparison.average_rank_a}` : 'N/A'}
                </div>
              </div>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Avg Rank B</div>
                <div className="text-lg font-black text-slate-800">
                  {comparison.average_rank_b !== undefined ? `#${comparison.average_rank_b}` : 'N/A'}
                </div>
              </div>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Rank Delta</div>
                <div className={`text-lg font-black ${
                  (comparison.rank_delta || 0) > 0 ? 'text-emerald-600' : (comparison.rank_delta || 0) < 0 ? 'text-rose-600' : 'text-slate-700'
                }`}>
                  {(comparison.rank_delta || 0) > 0 ? `+${comparison.rank_delta}` : comparison.rank_delta || 0}
                </div>
              </div>
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Visibility Change</div>
                <div className={`text-lg font-black ${
                  (comparison.visibility_delta || 0) > 0 ? 'text-emerald-600' : (comparison.visibility_delta || 0) < 0 ? 'text-rose-600' : 'text-slate-700'
                }`}>
                  {(comparison.visibility_delta || 0) > 0 ? `+${comparison.visibility_delta}%` : `${comparison.visibility_delta || 0}%`}
                </div>
              </div>
            </div>

            {/* Point Movement Breakdown */}
            {comparison.point_comparisons && comparison.point_comparisons.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-700">Point-by-Point Movement (25 Coordinates)</h4>
                <div className="grid grid-cols-5 gap-1.5 p-3 bg-slate-50 rounded-xl border border-slate-200 text-center">
                  {comparison.point_comparisons.map((pt) => {
                    const improved = pt.improved;
                    const declined = pt.declined;
                    return (
                      <div
                        key={pt.point_number}
                        className={`p-2 rounded-lg border text-xs ${
                          improved
                            ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
                            : declined
                            ? 'bg-rose-50 border-rose-300 text-rose-800'
                            : 'bg-white border-slate-200 text-slate-600'
                        }`}
                      >
                        <div className="text-[9px] font-mono text-slate-400">Pt #{pt.point_number}</div>
                        <div className="font-black text-xs mt-0.5">
                          {pt.rank_a ? `#${pt.rank_a}` : 'NF'} → {pt.rank_b ? `#${pt.rank_b}` : 'NF'}
                        </div>
                        <div className="text-[10px] font-bold mt-0.5">
                          {improved ? `▲ +${pt.delta}` : declined ? `▼ ${pt.delta}` : '—'}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {scanError && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start space-x-3">
          <div className="font-bold shrink-0">⚠️ Error:</div>
          <div>
            <div className="font-semibold">{scanError}</div>
            {scanError.includes('LOCATION_COORDINATES_REQUIRED') && (
              <div className="mt-1 text-slate-600">
                Please go to Project Settings or click <strong>Re-scan Grid</strong> to select a location or enter manual GPS coordinates.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Grid Component */}
      <LocalGridMap scan={scan} onRescan={() => setIsPickerOpen(true)} isScanning={isScanning} />

      {/* Location Picker Modal */}
      <LocationPickerModal
        isOpen={isPickerOpen}
        onClose={() => setIsPickerOpen(false)}
        projectId={activeProject.id}
        onStartScan={handleStartScanWithLocation}
        isScanning={isScanning}
        initialKeyword={initialKeyword}
        initialKeywordId={initialKeywordId}
        initialRadius={scan?.radius_km || 5.0}
        initialGridSize={scan?.grid_size || 5}
      />
    </div>
  );
};

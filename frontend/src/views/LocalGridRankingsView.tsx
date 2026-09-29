import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
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
  ChevronLeft,
  ChevronRight,
  Clock,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  Settings,
  ExternalLink,
  X,
  FileDown,
  Download,
  FileText,
  CheckCircle2,
  Calendar
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { GeoGridScan, GridPoint, Keyword } from '../types';
import { LocalGridMap } from '../components/rankings/LocalGridMap';
import { LocationPickerModal } from '../components/rankings/LocationPickerModal';
import { EmptyState } from '../components/ui/EmptyState';
import { Modal } from '../components/ui/Modal';
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
  const [selectedPoint, setSelectedPoint] = useState<GridPoint | null>(null);
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [selectedKeywordId, setSelectedKeywordId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [isPickerOpen, setIsPickerOpen] = useState(false);

  // PDF downloading states
  const [downloadingPdfUrl, setDownloadingPdfUrl] = useState<string | null>(null);

  // History & Pagination state
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyPage, setHistoryPage] = useState<number>(1);
  const [historyPageSize] = useState<number>(20);
  const [historyTotal, setHistoryTotal] = useState<number>(0);
  const [historyTotalPages, setHistoryTotalPages] = useState<number>(1);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);

  // Scan Comparison state
  const [showCompareSection, setShowCompareSection] = useState(false);
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

  const fetchHistory = async (page: number = 1, keywordId?: number) => {
    if (!activeProject) return;
    try {
      setHistoryLoading(true);
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(historyPageSize));
      if (keywordId || selectedKeywordId) {
        params.set('keyword_id', String(keywordId || selectedKeywordId));
      }

      const endpoint = `/keywords/${activeProject.id}/grid/history?${params.toString()}`;
      const resp = await api.get(endpoint);

      if (resp.data && typeof resp.data === 'object' && !Array.isArray(resp.data)) {
        const items = resp.data.items || resp.data.records || [];
        setHistory(items);
        setHistoryTotal(resp.data.total || items.length);
        setHistoryPage(resp.data.page || page);
        setHistoryTotalPages(resp.data.total_pages || Math.ceil((resp.data.total || items.length) / historyPageSize) || 1);
      } else if (Array.isArray(resp.data)) {
        setHistory(resp.data);
        setHistoryTotal(resp.data.length);
        setHistoryPage(1);
        setHistoryTotalPages(Math.ceil(resp.data.length / historyPageSize) || 1);
      }
    } catch (e) {
      console.error('Failed to load scan history:', e);
    } finally {
      setHistoryLoading(false);
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
      setSelectedPoint(null);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (e) {
      console.error('Failed to load scan by ID:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPdf = async (url: string, defaultFilename: string) => {
    if (!activeProject) return;
    try {
      setDownloadingPdfUrl(url);
      const resp = await api.get(url, {
        responseType: 'blob'
      });
      const blob = new Blob([resp.data], { type: 'application/pdf' });
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = defaultFilename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    } catch (e: any) {
      console.error('Failed to download PDF:', e);
      alert(getErrorMessage(e, 'Failed to generate and download PDF report.'));
    } finally {
      setDownloadingPdfUrl(null);
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

  // Flush and reload state on project switch
  useEffect(() => {
    setScan(null);
    setSelectedPoint(null);
    setKeywords([]);
    setSelectedKeywordId(null);
    setScanError(null);
    setHistory([]);
    setHistoryPage(1);
    setHistoryTotal(0);
    setHistoryTotalPages(1);
    setComparison(null);

    if (activeProject?.id) {
      fetchKeywords();
      fetchScan();
      fetchHistory(1);
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
      }, {
        timeout: 180000 // 3 minutes timeout
      });

      setIsPickerOpen(false);
      await fetchScan(params.keyword_id);
      await fetchHistory(1, params.keyword_id);
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

  // Helpers for formatted dates
  const formatScanDate = (isoStr: string) => {
    if (!isoStr) return 'N/A';
    const d = new Date(isoStr);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  const formatScanTime = (isoStr: string) => {
    if (!isoStr) return 'N/A';
    const d = new Date(isoStr);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
  };

  const currentScanId = scan?.id || scan?.scan_id;

  return (
    <div className="space-y-6">
      {/* ─── Header & Keyword Switcher ─── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <MapPin className="w-6 h-6 text-[#236B4F]" />
            <span>Local Visibility — Geo-Grid Rankings</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Geographic local rank intelligence: discrete GPS coordinate search points centered on your business location.
          </p>
          <div className="mt-2 text-[11px] text-[#2E4E40] bg-[#F1F7F1] px-3 py-1.5 rounded-lg border border-[#D0E6D0] flex items-center gap-1.5 max-w-2xl">
            <span className="font-bold text-[#142820] shrink-0">Search Surface Notice:</span>
            <span>Geo-Grid uses Google Maps coordinate-based local search. Discrete GPS ranks reflect geographic proximity and are not expected to equal Google Search Local Pack or Organic rankings.</span>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Keyword Quick Switcher */}
          {keywords.length > 0 && (
            <div className="flex items-center space-x-2 bg-white px-3 py-1.5 rounded-xl border border-slate-200 shadow-xs">
              <Search className="w-4 h-4 text-[#236B4F] shrink-0" />
              <span className="text-xs font-bold text-slate-600">Keyword:</span>
              <select
                value={selectedKeywordId || ''}
                onChange={(e) => {
                  const kid = parseInt(e.target.value);
                  setSelectedKeywordId(kid);
                  fetchScan(kid);
                  fetchHistory(1, kid);
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

          {/* Quick Scan Launcher Button */}
          <button
            onClick={() => setIsPickerOpen(true)}
            className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-[#236B4F] text-white hover:bg-[#1D5A42] transition-all shadow-xs"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
            <span>New Scan</span>
          </button>
        </div>
      </div>

      {scanError && (
        <div className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
          scanError.includes('SERP_PROVIDER_NOT_CONFIGURED') || scanError.toLowerCase().includes('not configured')
            ? 'bg-amber-50/90 border-amber-200 text-amber-900'
            : 'bg-rose-50/90 border-rose-200 text-rose-900'
        }`}>
          <div className="flex items-start space-x-2.5">
            <AlertCircle className={`w-4 h-4 shrink-0 mt-0.5 ${
              scanError.includes('SERP_PROVIDER_NOT_CONFIGURED') || scanError.toLowerCase().includes('not configured')
                ? 'text-amber-600'
                : 'text-rose-600'
            }`} />
            <div>
              <div className="font-bold">
                {scanError.includes('SERP_PROVIDER_NOT_CONFIGURED') || scanError.toLowerCase().includes('not configured')
                  ? 'SERP Provider Not Configured'
                  : scanError.includes('LOCATION_COORDINATES_REQUIRED')
                  ? 'Location Coordinates Required'
                  : scanError.includes('INVALID_LATITUDE') || scanError.includes('INVALID_LONGITUDE')
                  ? 'Invalid Coordinates'
                  : 'Geo-Grid Scan Notice'}
              </div>
              <div className="mt-0.5 text-slate-700">
                {scanError.includes('SERP_PROVIDER_NOT_CONFIGURED')
                  ? 'Connect your SerpApi account in Settings to enable Geo-Grid rankings.'
                  : scanError.includes('LOCATION_COORDINATES_REQUIRED')
                  ? 'Add a valid latitude and longitude for this business location to run a coordinate scan.'
                  : scanError}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-2 shrink-0 self-start sm:self-auto">
            {scanError.includes('SERP_PROVIDER_NOT_CONFIGURED') || scanError.toLowerCase().includes('not configured') ? (
              <Link
                to="/settings"
                className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-lg font-bold text-xs bg-amber-600 hover:bg-amber-700 text-white shadow-2xs transition-all"
              >
                <Settings className="w-3.5 h-3.5" />
                <span>Open SERP Settings</span>
                <ExternalLink className="w-3 h-3 ml-0.5" />
              </Link>
            ) : scanError.includes('LOCATION_COORDINATES_REQUIRED') || scanError.includes('INVALID_') ? (
              <button
                onClick={() => setIsPickerOpen(true)}
                className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-lg font-bold text-xs bg-[#236B4F] hover:bg-[#1D5A42] text-white shadow-2xs transition-all"
              >
                <MapPin className="w-3.5 h-3.5" />
                <span>Set Location Coordinates</span>
              </button>
            ) : null}
          </div>
        </div>
      )}

      {/* ─── 1. Interactive Geo-Grid Map & Selected Point Analysis ─── */}
      <LocalGridMap
        scan={scan}
        onRescan={() => setIsPickerOpen(true)}
        isScanning={isScanning}
        selectedPoint={selectedPoint}
        onSelectPoint={setSelectedPoint}
      />

      {/* ─── 2. Three Primary PDF Download Actions ─── */}
      <div className="bg-white rounded-2xl border border-[#DCE8DC] p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#EBF2EB] pb-3">
          <div>
            <h2 className="text-base font-black text-slate-900 flex items-center gap-2">
              <FileDown className="w-5 h-5 text-[#236B4F]" />
              <span>Geo-Grid PDF Reports</span>
            </h2>
            <p className="text-xs text-[#587568] mt-0.5">
              Export high-fidelity vector PDF reports generated from immutable database records.
            </p>
          </div>
          {selectedPoint && (
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#EBF2EB] text-[#236B4F] text-xs font-bold">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#236B4F]" />
              <span>Selected: Point #{selectedPoint.point_number}</span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* BUTTON 1: Download Latest Full Scan */}
          <div className="flex flex-col justify-between p-4 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-slate-50 hover:border-[#236B4F]/30 transition-all">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-black uppercase text-[#236B4F] tracking-wider">
                  Full Scan Report
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-200 text-slate-700">
                  {scan ? `${scan.grid_size || 5}×${scan.grid_size || 5} Matrix` : 'Latest'}
                </span>
              </div>
              <h3 className="text-sm font-bold text-slate-900">
                Download Latest Full Scan
              </h3>
              <p className="text-xs text-slate-500">
                Complete audit including executive metrics, map visualization, all discrete grid points, and full competitor breakdown.
              </p>
            </div>

            <button
              id="btn-download-latest-scan"
              disabled={!scan || downloadingPdfUrl !== null}
              onClick={() => {
                if (currentScanId) {
                  handleDownloadPdf(
                    `/keywords/${activeProject.id}/grid/scans/${currentScanId}/pdf`,
                    `geogrid-scan-${currentScanId}.pdf`
                  );
                } else {
                  handleDownloadPdf(
                    `/keywords/${activeProject.id}/grid/pdf/latest${selectedKeywordId ? `?keyword_id=${selectedKeywordId}` : ''}`,
                    `geogrid-latest-scan.pdf`
                  );
                }
              }}
              className="mt-4 flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-xl text-xs font-bold text-white bg-[#236B4F] hover:bg-[#1D5A42] disabled:opacity-40 transition-colors shadow-xs"
            >
              {downloadingPdfUrl?.includes('/grid/scans/') || downloadingPdfUrl?.includes('/pdf/latest') ? (
                <>
                  <RotateCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Generating PDF...</span>
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  <span>Download Latest Full Scan</span>
                </>
              )}
            </button>
          </div>

          {/* BUTTON 2: Download Current + Previous 2 Scans */}
          <div className="flex flex-col justify-between p-4 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-slate-50 hover:border-purple-300 transition-all">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-black uppercase text-purple-700 tracking-wider">
                  Trend Comparison
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800">
                  Max 3 Scans
                </span>
              </div>
              <h3 className="text-sm font-bold text-slate-900">
                Download Current + Previous 2 Scans
              </h3>
              <p className="text-xs text-slate-500">
                Chronological comparison report containing the current scan and the 2 immediately previous scans with rank and visibility movements.
              </p>
            </div>

            <button
              id="btn-download-recent-scans"
              disabled={downloadingPdfUrl !== null}
              onClick={() => {
                handleDownloadPdf(
                  `/keywords/${activeProject.id}/grid/pdf/recent-scans${selectedKeywordId ? `?keyword_id=${selectedKeywordId}` : ''}`,
                  `geogrid-recent-scans-trend.pdf`
                );
              }}
              className="mt-4 flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-xl text-xs font-bold text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-40 transition-colors shadow-xs"
            >
              {downloadingPdfUrl?.includes('/pdf/recent-scans') ? (
                <>
                  <RotateCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Generating Multi-Scan PDF...</span>
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  <span>Download Current + Previous 2 Scans</span>
                </>
              )}
            </button>
          </div>

          {/* BUTTON 3: Download Selected Grid Point */}
          <div className={`flex flex-col justify-between p-4 rounded-xl border transition-all ${
            selectedPoint
              ? 'border-emerald-300 bg-emerald-50/40'
              : 'border-slate-200 bg-slate-50/50'
          }`}>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-black uppercase text-emerald-800 tracking-wider">
                  Single Point Deep-Dive
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  selectedPoint ? 'bg-emerald-200 text-emerald-900' : 'bg-slate-200 text-slate-600'
                }`}>
                  {selectedPoint ? `Point #${selectedPoint.point_number}` : 'None Selected'}
                </span>
              </div>
              <h3 className="text-sm font-bold text-slate-900">
                Download Selected Grid Point
              </h3>
              <p className="text-xs text-slate-500">
                {selectedPoint
                  ? `Dedicated diagnostic report for Point #${selectedPoint.point_number} (${selectedPoint.direction || 'Center'}), including depth analysis and competitor ranking hierarchy.`
                  : 'Click any coordinate pin on the interactive map above to enable dedicated point PDF download.'}
              </p>
            </div>

            <button
              id="btn-download-selected-point"
              disabled={!selectedPoint || !currentScanId || downloadingPdfUrl !== null}
              onClick={() => {
                if (currentScanId && selectedPoint) {
                  handleDownloadPdf(
                    `/keywords/${activeProject.id}/grid/scans/${currentScanId}/points/${selectedPoint.point_number}/pdf`,
                    `geogrid-scan-${currentScanId}-point-${selectedPoint.point_number}.pdf`
                  );
                }
              }}
              className="mt-4 flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-xl text-xs font-bold text-white bg-[#236B4F] hover:bg-[#1D5A42] disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-xs"
            >
              {downloadingPdfUrl?.includes('/points/') ? (
                <>
                  <RotateCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Generating Point PDF...</span>
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  <span>
                    {selectedPoint
                      ? `Download Point #${selectedPoint.point_number} PDF`
                      : 'Download Selected Grid Point'}
                  </span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ─── 3. Scan History Section ─── */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2">
            <History className="w-5 h-5 text-[#236B4F]" />
            <div>
              <h2 className="text-base font-black text-slate-900">Scan History</h2>
              <p className="text-xs text-slate-500">
                Historical records with immutable ranking snapshots and per-scan PDF exports.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowCompareSection(!showCompareSection)}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border border-slate-200 bg-white hover:border-purple-300 text-slate-700 transition-all"
            >
              <GitCompare className="w-3.5 h-3.5 text-purple-600" />
              <span>Compare Scans</span>
            </button>
            <button
              onClick={() => fetchHistory(historyPage)}
              disabled={historyLoading}
              className="p-1.5 rounded-xl border border-slate-200 hover:border-[#236B4F] text-slate-600 transition-colors"
              title="Refresh History"
            >
              <RotateCw className={`w-4 h-4 ${historyLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Scan Comparison Toolbar */}
        {showCompareSection && history.length >= 2 && (
          <div className="p-4 bg-purple-50/50 rounded-xl border border-purple-200/70 flex flex-wrap items-center gap-3">
            <span className="text-xs font-bold text-slate-700 flex items-center space-x-1.5">
              <GitCompare className="w-4 h-4 text-purple-600" />
              <span>Compare Two Historical Scans:</span>
            </span>
            <select
              value={compareScanA || ''}
              onChange={(e) => setCompareScanA(parseInt(e.target.value) || null)}
              className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white font-medium text-slate-800"
            >
              <option value="">Select Scan A (Baseline)</option>
              {history.map((h) => (
                <option key={h.id} value={h.id}>
                  Scan #{h.id} — {formatScanDate(h.scanned_at)} ({h.local_visibility_pct || 0}%)
                </option>
              ))}
            </select>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={compareScanB || ''}
              onChange={(e) => setCompareScanB(parseInt(e.target.value) || null)}
              className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white font-medium text-slate-800"
            >
              <option value="">Select Scan B (Comparison)</option>
              {history.map((h) => (
                <option key={h.id} value={h.id}>
                  Scan #{h.id} — {formatScanDate(h.scanned_at)} ({h.local_visibility_pct || 0}%)
                </option>
              ))}
            </select>
            <button
              disabled={!compareScanA || !compareScanB || compareScanA === compareScanB || comparing}
              onClick={handleCompare}
              className="px-3.5 py-1.5 bg-purple-600 text-white text-xs font-bold rounded-lg hover:bg-purple-700 disabled:opacity-40 transition-colors shadow-2xs"
            >
              {comparing ? 'Comparing...' : 'Compare Scans'}
            </button>
          </div>
        )}

        {/* History Table */}
        {historyLoading ? (
          <div className="py-12 flex flex-col items-center justify-center text-slate-400">
            <RotateCw className="w-6 h-6 animate-spin text-[#236B4F] mb-2" />
            <span className="text-xs font-medium">Loading scan history...</span>
          </div>
        ) : history.length === 0 ? (
          <div className="py-12 text-center text-slate-400">
            <History className="w-8 h-8 mx-auto text-slate-300 mb-2" />
            <p className="text-xs font-semibold">No scan history recorded yet for this project.</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Run a Geo-Grid scan to generate records and download reports.</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-600 font-bold">
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Time</th>
                  <th className="py-3 px-4">Radius</th>
                  <th className="py-3 px-4">Grid Size</th>
                  <th className="py-3 px-4 text-center">Avg Rank</th>
                  <th className="py-3 px-4 text-center">Visibility</th>
                  <th className="py-3 px-4 text-right">Download</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {history.map((h) => {
                  const isCurrent = (scan?.id === h.id || scan?.scan_id === h.id);
                  const isRowDownloading = downloadingPdfUrl === `/keywords/${activeProject.id}/grid/scans/${h.id}/pdf`;

                  return (
                    <tr
                      key={h.id}
                      className={`transition-colors hover:bg-slate-50/80 ${
                        isCurrent ? 'bg-emerald-50/30 font-semibold' : ''
                      }`}
                    >
                      <td className="py-3 px-4 text-slate-800">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          <span>{formatScanDate(h.scanned_at)}</span>
                          {isCurrent && (
                            <span className="ml-1.5 px-1.5 py-0.2 rounded text-[9px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                              Active
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-slate-600">
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 text-slate-400" />
                          <span>{formatScanTime(h.scanned_at)}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-slate-700">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-slate-100 font-medium text-slate-800">
                          {h.radius_km} km
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-700 font-medium">
                        {h.grid_size} × {h.grid_size}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {h.average_rank != null ? (
                          <span className="font-bold text-slate-800">#{h.average_rank.toFixed(1)}</span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-center">
                        {h.local_visibility_pct != null ? (
                          <span className="font-bold text-emerald-700">{h.local_visibility_pct.toFixed(0)}%</span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => loadSpecificScan(h.id)}
                            className="px-2.5 py-1 rounded-lg text-[11px] font-semibold text-slate-600 hover:text-[#236B4F] hover:bg-slate-100 transition-colors"
                            title="Load onto map"
                          >
                            View
                          </button>
                          <button
                            onClick={() =>
                              handleDownloadPdf(
                                `/keywords/${activeProject.id}/grid/scans/${h.id}/pdf`,
                                `geogrid-scan-${h.id}.pdf`
                              )
                            }
                            disabled={downloadingPdfUrl !== null}
                            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-[11px] font-bold text-white bg-[#236B4F] hover:bg-[#1D5A42] disabled:opacity-40 transition-colors shadow-2xs"
                          >
                            {isRowDownloading ? (
                              <>
                                <RotateCw className="w-3 h-3 animate-spin" />
                                <span>Exporting...</span>
                              </>
                            ) : (
                              <>
                                <Download className="w-3 h-3" />
                                <span>Download PDF</span>
                              </>
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* ─── 4. Pagination Controls (20 scans per page) ─── */}
        {historyTotal > 0 && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2 text-xs text-slate-500">
            <div>
              Showing {Math.min((historyPage - 1) * historyPageSize + 1, historyTotal)} to{' '}
              {Math.min(historyPage * historyPageSize, historyTotal)} of {historyTotal} scans (20 scans per page)
            </div>

            <div className="flex items-center space-x-1">
              <button
                disabled={historyPage <= 1 || historyLoading}
                onClick={() => fetchHistory(historyPage - 1)}
                className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed font-medium text-slate-700"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Previous</span>
              </button>

              {Array.from({ length: historyTotalPages }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  disabled={historyLoading}
                  onClick={() => fetchHistory(p)}
                  className={`w-8 h-8 rounded-lg font-bold text-xs transition-colors ${
                    historyPage === p
                      ? 'bg-[#236B4F] text-white'
                      : 'border border-slate-200 bg-white hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  {p}
                </button>
              ))}

              <button
                disabled={historyPage >= historyTotalPages || historyLoading}
                onClick={() => fetchHistory(historyPage + 1)}
                className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed font-medium text-slate-700"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Comparison Modal */}
      {isCompareModalOpen && comparison && (
        <Modal
          isOpen={isCompareModalOpen}
          onClose={() => setIsCompareModalOpen(false)}
          maxWidth="2xl"
          icon={<GitCompare className="w-5 h-5 text-[#236B4F]" />}
          title="Scan Comparison Analysis"
          subtitle="Point-by-point rank and visibility deltas"
          bodyClassName="space-y-5 p-6"
        >
          {/* Summary Deltas */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 bg-[#F7FAF7] rounded-xl border border-[#DCE8DC]">
              <div className="text-[10px] font-bold text-[#587568] uppercase">Avg Rank A</div>
              <div className="text-lg font-black text-[#142820]">
                {comparison.average_rank_a !== undefined ? `#${comparison.average_rank_a}` : 'N/A'}
              </div>
            </div>
            <div className="p-3 bg-[#F7FAF7] rounded-xl border border-[#DCE8DC]">
              <div className="text-[10px] font-bold text-[#587568] uppercase">Avg Rank B</div>
              <div className="text-lg font-black text-[#142820]">
                {comparison.average_rank_b !== undefined ? `#${comparison.average_rank_b}` : 'N/A'}
              </div>
            </div>
            <div className="p-3 bg-[#F7FAF7] rounded-xl border border-[#DCE8DC]">
              <div className="text-[10px] font-bold text-[#587568] uppercase">Rank Delta</div>
              <div className={`text-lg font-black ${
                (comparison.rank_delta || 0) > 0 ? 'text-emerald-700' : (comparison.rank_delta || 0) < 0 ? 'text-rose-700' : 'text-[#142820]'
              }`}>
                {(comparison.rank_delta || 0) > 0 ? `+${comparison.rank_delta}` : comparison.rank_delta || 0}
              </div>
            </div>
            <div className="p-3 bg-[#F7FAF7] rounded-xl border border-[#DCE8DC]">
              <div className="text-[10px] font-bold text-[#587568] uppercase">Visibility Change</div>
              <div className={`text-lg font-black ${
                (comparison.visibility_delta || 0) > 0 ? 'text-emerald-700' : (comparison.visibility_delta || 0) < 0 ? 'text-rose-700' : 'text-[#142820]'
              }`}>
                {(comparison.visibility_delta || 0) > 0 ? `+${comparison.visibility_delta}%` : `${comparison.visibility_delta || 0}%`}
              </div>
            </div>
          </div>

          {/* Point Movement Breakdown */}
          {comparison.point_comparisons && comparison.point_comparisons.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-[#142820]">Point-by-Point Movement Matrix</h4>
              <div className="grid grid-cols-5 gap-1.5 p-3 bg-[#F7FAF7] rounded-xl border border-[#DCE8DC] text-center">
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
                          : 'bg-white border-[#DCE8DC] text-[#2E4E40]'
                      }`}
                    >
                      <div className="text-[9px] font-mono text-[#587568]">Pt #{pt.point_number}</div>
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
        </Modal>
      )}

      {/* ─── Location Picker Modal (Preserved 100% Unchanged) ─── */}
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
        onScanCompleted={() => {
          fetchScan(selectedKeywordId || undefined);
          fetchHistory(1, selectedKeywordId || undefined);
        }}
      />
    </div>
  );
};

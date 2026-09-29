import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Location, Keyword } from '../../types';
import {
  MapPin,
  X,
  Navigation,
  CheckCircle2,
  AlertCircle,
  Search,
  RotateCw,
  StopCircle,
  AlertTriangle,
  ArrowRight
} from 'lucide-react';
import api from '../../api/client';
import { getErrorMessage } from '../../utils/error';
import { Modal } from '../ui/Modal';

interface LocationPickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: number;
  onStartScan: (params: {
    location_id?: number;
    center_lat?: number;
    center_lng?: number;
    center_name?: string;
    keyword_id?: number;
    keyword: string;
    radius_km?: number;
    grid_size?: number;
  }) => Promise<void>;
  isScanning: boolean;
  initialKeyword?: string;
  initialKeywordId?: number;
  initialRadius?: number;
  initialGridSize?: number;
  onScanCompleted?: () => void;
}

export interface LiveGridScanProgress {
  scanId: number;
  status: 'running' | 'completed' | 'completed_with_errors' | 'cancelled' | 'failed' | 'cancelling';
  completedPoints: number;
  totalPoints: number;
  progressPct: number;
  keyword: string;
  averageRank: number | null;
  visibilityPct: number;
  message?: string;
  error?: string | null;
}

export const LocationPickerModal: React.FC<LocationPickerModalProps> = ({
  isOpen,
  onClose,
  projectId,
  onStartScan,
  isScanning: propIsScanning,
  initialKeyword = '',
  initialKeywordId,
  initialRadius = 5.0,
  initialGridSize = 5,
  onScanCompleted
}) => {
  const [locations, setLocations] = useState<Location[]>([]);
  const [loadingLocations, setLoadingLocations] = useState(false);
  const [selectedLocationId, setSelectedLocationId] = useState<number | null>(null);
  const [isManualMode, setIsManualMode] = useState(false);

  // Tracked Keywords
  const [trackedKeywords, setTrackedKeywords] = useState<Keyword[]>([]);
  const [loadingKeywords, setLoadingKeywords] = useState(false);
  const [selectedKeywordId, setSelectedKeywordId] = useState<number | null>(initialKeywordId || null);
  const [isCustomKeyword, setIsCustomKeyword] = useState(false);

  // Form parameters
  const [keyword, setKeyword] = useState(initialKeyword);
  const [radiusKm, setRadiusKm] = useState(initialRadius);
  const [gridSize, setGridSize] = useState(initialGridSize);

  // Manual coordinate inputs
  const [manualName, setManualName] = useState('Custom Coordinates');
  const [manualLat, setManualLat] = useState('');
  const [manualLng, setManualLng] = useState('');

  // Live progress and cancellation state
  const [scanState, setScanState] = useState<'idle' | 'starting' | 'scanning' | 'cancelling' | 'completed' | 'cancelled' | 'failed'>('idle');
  const [liveProgress, setLiveProgress] = useState<LiveGridScanProgress | null>(null);
  const pollTimerRef = useRef<any>(null);

  // Validation error
  const [validationError, setValidationError] = useState<string | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (isOpen && projectId) {
      fetchLocations();
      fetchTrackedKeywords();
      setKeyword(initialKeyword);
      setSelectedKeywordId(initialKeywordId || null);
      setRadiusKm(initialRadius);
      setGridSize(initialGridSize);
      setValidationError(null);
      setScanState('idle');
      setLiveProgress(null);
    }
    return () => {
      stopPolling();
    };
  }, [isOpen, projectId]);

  const fetchLocations = async () => {
    try {
      setLoadingLocations(true);
      const resp = await api.get(`/projects/${projectId}/locations`);
      const locs: Location[] = resp.data || [];
      setLocations(locs);
      if (locs.length > 0 && selectedLocationId === null) {
        setSelectedLocationId(locs[0].id);
      }
    } catch (e: any) {
      console.error('Failed to fetch project locations:', e);
    } finally {
      setLoadingLocations(false);
    }
  };

  const fetchTrackedKeywords = async () => {
    try {
      setLoadingKeywords(true);
      const resp = await api.get(`/keywords/${projectId}`);
      const list: Keyword[] = Array.isArray(resp.data) ? resp.data : [];
      setTrackedKeywords(list);

      if (list.length > 0) {
        if (initialKeywordId) {
          const matched = list.find((k) => k.id === initialKeywordId);
          if (matched) {
            setSelectedKeywordId(matched.id);
            setKeyword(matched.keyword);
            return;
          }
        }
        if (initialKeyword) {
          const matched = list.find((k) => k.keyword.toLowerCase() === initialKeyword.toLowerCase());
          if (matched) {
            setSelectedKeywordId(matched.id);
            setKeyword(matched.keyword);
            return;
          }
        }
        if (!initialKeyword) {
          setSelectedKeywordId(list[0].id);
          setKeyword(list[0].keyword);
        }
      } else {
        setIsCustomKeyword(true);
      }
    } catch (e: any) {
      console.error('Failed to fetch project keywords:', e);
    } finally {
      setLoadingKeywords(false);
    }
  };

  if (!isOpen) return null;

  const pollScanStatus = async (scanId: number) => {
    try {
      const resp = await api.get(`/keywords/${projectId}/grid/scans/${scanId}`);
      const data = resp.data;

      const completed = data.completed_points || 0;
      const total = data.total_points || (gridSize * gridSize);
      const pct = data.progress_pct || Math.round((completed / total) * 100);

      setLiveProgress({
        scanId: data.scan_id || scanId,
        status: data.scan_status || data.status,
        completedPoints: completed,
        totalPoints: total,
        progressPct: pct,
        keyword: data.keyword || keyword,
        averageRank: data.average_rank,
        visibilityPct: data.local_visibility_pct || 0,
        message: data.cancellation_reason
      });

      const st = data.scan_status || data.status;
      if (st === 'completed' || st === 'completed_with_errors') {
        stopPolling();
        setScanState('completed');
        if (onScanCompleted) onScanCompleted();
      } else if (st === 'cancelled') {
        stopPolling();
        setScanState('cancelled');
        if (onScanCompleted) onScanCompleted();
      } else if (st === 'failed') {
        stopPolling();
        setScanState('failed');
      }
    } catch (e: any) {
      console.error('Error polling grid scan:', e);
    }
  };

  const handleCancelScan = async () => {
    if (!liveProgress?.scanId) return;
    try {
      setScanState('cancelling');
      await api.post(`/keywords/${projectId}/grid/scans/${liveProgress.scanId}/cancel`);
    } catch (e: any) {
      console.error('Failed to cancel scan:', e);
      setValidationError(getErrorMessage(e, 'Failed to cancel scan.'));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const cleanKeyword = keyword.trim();
    if (!cleanKeyword) {
      setValidationError('A search keyword is required for Geo-Grid ranking scans.');
      return;
    }

    let payload: any = {
      keyword_id: selectedKeywordId || undefined,
      keyword: cleanKeyword,
      radius_km: radiusKm,
      grid_size: gridSize
    };

    if (isManualMode) {
      const latNum = parseFloat(manualLat);
      const lngNum = parseFloat(manualLng);

      if (isNaN(latNum) || latNum < -90 || latNum > 90) {
        setValidationError('Latitude must be a valid number between -90 and 90 degrees.');
        return;
      }
      if (isNaN(lngNum) || lngNum < -180 || lngNum > 180) {
        setValidationError('Longitude must be a valid number between -180 and 180 degrees.');
        return;
      }

      payload.center_lat = latNum;
      payload.center_lng = lngNum;
      payload.center_name = manualName || 'Custom Location';
    } else {
      if (!selectedLocationId) {
        setValidationError('Please select a saved location or switch to manual coordinates.');
        return;
      }
      const selectedLoc = locations.find((l) => l.id === selectedLocationId);
      payload.location_id = selectedLocationId;
      payload.center_name = selectedLoc?.name;
    }

    try {
      setScanState('starting');
      const startResp = await api.post(`/keywords/${projectId}/grid/start-scan`, payload);
      const scanId = startResp.data?.scan_id || startResp.data?.id;

      setLiveProgress({
        scanId: scanId,
        status: 'running',
        completedPoints: 0,
        totalPoints: gridSize * gridSize,
        progressPct: 0,
        keyword: cleanKeyword,
        averageRank: null,
        visibilityPct: 0
      });
      setScanState('scanning');

      // Start Polling
      stopPolling();
      pollTimerRef.current = setInterval(() => {
        pollScanStatus(scanId);
      }, 1200);
    } catch (e: any) {
      console.error('Failed to start grid scan:', e);
      setScanState('idle');
      setValidationError(getErrorMessage(e, 'Failed to initialize Geo-Grid scan.'));
    }
  };

  const handleFinishAndClose = () => {
    stopPolling();
    onClose();
  };

  const isScanningActive = scanState === 'scanning' || scanState === 'cancelling' || scanState === 'starting';

  const modalIcon = (
    <div className={`w-10 h-10 rounded-2xl flex items-center justify-center font-bold ${
      scanState === 'completed'
        ? 'bg-emerald-100 text-emerald-700'
        : scanState === 'cancelled'
        ? 'bg-amber-100 text-amber-700'
        : 'bg-[#EAF2EA] text-[#236B4F]'
    }`}>
      <MapPin className="w-5 h-5" />
    </div>
  );

  const modalTitle = (
    <div>
      <h2 className="text-base sm:text-lg font-black text-[#142820]">
        {scanState === 'idle' && 'Run 5x5 Geo-Grid Scan'}
        {isScanningActive && 'Scanning Geo-Grid Matrix...'}
        {scanState === 'completed' && 'Geo-Grid Scan Complete'}
        {scanState === 'cancelled' && 'Geo-Grid Scan Cancelled'}
        {scanState === 'failed' && 'Geo-Grid Scan Failed'}
      </h2>
      <p className="text-xs text-[#587568]">
        {scanState === 'idle'
          ? 'Target a canonical SEO keyword across your service coordinates'
          : `Target: "${liveProgress?.keyword || keyword}"`}
      </p>
    </div>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleFinishAndClose}
      maxWidth="lg"
      icon={modalIcon}
      title={modalTitle}
      showCloseButton={!scanState || scanState !== 'cancelling'}
      closeOnBackdropClick={!isScanningActive}
      bodyClassName="space-y-6"
    >
      {validationError && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{validationError}</span>
          </div>
        )}

        {/* Dynamic State Body */}
        {scanState === 'idle' && (
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Target Keyword Selection */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Target SEO Keyword
                </label>
                {trackedKeywords.length > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      setIsCustomKeyword(!isCustomKeyword);
                      if (isCustomKeyword && trackedKeywords.length > 0) {
                        setSelectedKeywordId(trackedKeywords[0].id);
                        setKeyword(trackedKeywords[0].keyword);
                      } else {
                        setSelectedKeywordId(null);
                      }
                    }}
                    className="text-[11px] font-bold text-purple-600 hover:text-purple-800 underline"
                  >
                    {isCustomKeyword ? 'Select from Tracked Keywords' : 'Enter Custom Keyword'}
                  </button>
                )}
              </div>

              {!isCustomKeyword && trackedKeywords.length > 0 ? (
                <select
                  value={selectedKeywordId || ''}
                  onChange={(e) => {
                    const id = parseInt(e.target.value);
                    const matched = trackedKeywords.find((k) => k.id === id);
                    if (matched) {
                      setSelectedKeywordId(matched.id);
                      setKeyword(matched.keyword);
                    }
                  }}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-slate-900 text-xs font-semibold focus:ring-2 focus:ring-purple-500 focus:outline-none bg-white"
                >
                  {trackedKeywords.map((k) => (
                    <option key={k.id} value={k.id}>
                      {k.keyword} {k.current_rank ? `(#${k.current_rank})` : ''}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="relative">
                  <input
                    type="text"
                    required
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                    placeholder="e.g. commercial solar panels sydney"
                    className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-slate-900 text-xs font-semibold focus:ring-2 focus:ring-purple-500 focus:outline-none"
                  />
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                </div>
              )}
            </div>

            {/* Mode Toggle */}
            <div className="flex bg-slate-100 p-1 rounded-xl">
              <button
                type="button"
                onClick={() => setIsManualMode(false)}
                className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  !isManualMode ? 'bg-white shadow-xs text-purple-700' : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                Saved Locations
              </button>
              <button
                type="button"
                onClick={() => setIsManualMode(true)}
                className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
                  isManualMode ? 'bg-white shadow-xs text-purple-700' : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                Manual Coordinates
              </button>
            </div>

            {/* Saved Locations Mode */}
            {!isManualMode ? (
              <div className="space-y-3">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Select Business Location Center
                </label>
                {loadingLocations ? (
                  <div className="py-8 text-center text-xs text-slate-400">Loading locations...</div>
                ) : locations.length === 0 ? (
                  <div className="p-4 rounded-xl border border-dashed border-slate-300 text-center space-y-2">
                    <p className="text-xs text-slate-500">No saved locations found for this project.</p>
                    <button
                      type="button"
                      onClick={() => setIsManualMode(true)}
                      className="text-xs font-bold text-purple-600 hover:underline"
                    >
                      Enter Manual Coordinates →
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {locations.map((loc) => (
                      <div
                        key={loc.id}
                        onClick={() => setSelectedLocationId(loc.id)}
                        className={`p-3 rounded-2xl border transition-all cursor-pointer flex items-center justify-between ${
                          selectedLocationId === loc.id
                            ? 'border-purple-600 bg-purple-50/50 ring-2 ring-purple-100'
                            : 'border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        <div className="flex items-center space-x-3">
                          <div className={`p-2 rounded-xl ${selectedLocationId === loc.id ? 'bg-purple-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                            <MapPin className="w-4 h-4" />
                          </div>
                          <div>
                            <div className="text-xs font-bold text-slate-900">{loc.name}</div>
                            <div className="text-[11px] text-slate-500">
                              {loc.city ? `${loc.city}, ${loc.state || ''}` : loc.address || 'Coordinates only'}
                              {loc.latitude && loc.longitude && (
                                <span className="ml-1 text-[10px] text-slate-400 font-mono">
                                  ({loc.latitude.toFixed(4)}, {loc.longitude.toFixed(4)})
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        {selectedLocationId === loc.id && (
                          <CheckCircle2 className="w-4 h-4 text-purple-600" />
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              /* Manual Coordinates Mode */
              <div className="space-y-3 bg-slate-50 p-4 rounded-2xl border border-slate-200">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Center Label / Suburb</label>
                  <input
                    type="text"
                    value={manualName}
                    onChange={(e) => setManualName(e.target.value)}
                    placeholder="e.g. Sydney CBD Office"
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs font-medium focus:ring-2 focus:ring-purple-500 focus:outline-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 mb-1">Latitude</label>
                    <input
                      type="number"
                      step="any"
                      required
                      value={manualLat}
                      onChange={(e) => setManualLat(e.target.value)}
                      placeholder="e.g. -33.8688"
                      className="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs font-medium focus:ring-2 focus:ring-purple-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 mb-1">Longitude</label>
                    <input
                      type="number"
                      step="any"
                      required
                      value={manualLng}
                      onChange={(e) => setManualLng(e.target.value)}
                      placeholder="e.g. 151.2093"
                      className="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs font-medium focus:ring-2 focus:ring-purple-500 focus:outline-none"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Grid Settings */}
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div>
                <label className="block text-[11px] font-bold text-slate-600 mb-1">Radius (km)</label>
                <select
                  value={radiusKm}
                  onChange={(e) => setRadiusKm(parseFloat(e.target.value))}
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-800 bg-white"
                >
                  <option value={2.5}>2.5 km (Hyperlocal)</option>
                  <option value={5.0}>5.0 km (Local)</option>
                  <option value={7.5}>7.5 km (Standard)</option>
                  <option value={10.0}>10.0 km (Wide)</option>
                  <option value={15.0}>15.0 km (Metro)</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-bold text-slate-600 mb-1">Grid Size</label>
                <select
                  value={gridSize}
                  onChange={(e) => setGridSize(parseInt(e.target.value))}
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs font-semibold text-slate-800 bg-white"
                >
                  <option value={3}>3 x 3 Matrix (9 points)</option>
                  <option value={5}>5 x 5 Matrix (25 points)</option>
                  <option value={7}>7 x 7 Matrix (49 points)</option>
                </select>
              </div>
            </div>

            {/* Modal Action Buttons */}
            <div className="flex items-center justify-end space-x-3 border-t border-slate-100 pt-4">
              <button
                type="button"
                onClick={handleFinishAndClose}
                className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition-all"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md hover:shadow-lg transition-all"
              >
                <Navigation className="w-3.5 h-3.5" />
                <span>Run {gridSize}x{gridSize} Geo-Grid Scan</span>
              </button>
            </div>
          </form>
        )}

        {/* Live Running / Cancelling Progress State */}
        {isScanningActive && (
          <div className="space-y-6 py-2">
            <div className="p-4 rounded-2xl bg-purple-50/70 border border-purple-100 space-y-3">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2 font-bold text-purple-900">
                  <RotateCw className="w-4 h-4 text-purple-600 animate-spin shrink-0" />
                  <span>
                    {scanState === 'cancelling'
                      ? 'Cancelling scan... Halting remaining points'
                      : `Scanning point ${liveProgress?.completedPoints ?? 0} of ${liveProgress?.totalPoints ?? 25}`}
                  </span>
                </div>
                <span className="font-mono font-black text-purple-700">
                  {liveProgress?.progressPct ?? 0}%
                </span>
              </div>

              <div className="w-full bg-purple-200/60 h-2.5 rounded-full overflow-hidden">
                <div
                  className="bg-gradient-to-r from-purple-600 to-indigo-600 h-full rounded-full transition-all duration-300"
                  style={{ width: `${liveProgress?.progressPct ?? 0}%` }}
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Completed</span>
                <span className="text-base font-black text-slate-900">{liveProgress?.completedPoints ?? 0}</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Pending</span>
                <span className="text-base font-black text-slate-900">
                  {Math.max(0, (liveProgress?.totalPoints ?? 25) - (liveProgress?.completedPoints ?? 0))}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Total Points</span>
                <span className="text-base font-black text-slate-900">{liveProgress?.totalPoints ?? 25}</span>
              </div>
            </div>

            {/* Actions: Run in Background + Cancel (Part 9) */}
            <div className="flex items-center justify-between border-t border-slate-100 pt-4">
              <button
                type="button"
                onClick={() => {
                  onClose();
                }}
                className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold text-[#236B4F] bg-[#F1F7F1] border border-[#B8DFC9] hover:bg-[#EAF2EA] transition-all cursor-pointer"
              >
                <span>Run in Background</span>
              </button>
              <button
                type="button"
                onClick={handleCancelScan}
                disabled={scanState === 'cancelling'}
                className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold text-rose-700 bg-rose-50 border border-rose-200 hover:bg-rose-100 transition-all disabled:opacity-50 cursor-pointer"
              >
                <StopCircle className="w-3.5 h-3.5" />
                <span>{scanState === 'cancelling' ? 'Cancelling...' : 'Cancel Scan'}</span>
              </button>
            </div>
          </div>
        )}

        {/* Terminal States (Completed / Cancelled / Failed) */}
        {(scanState === 'completed' || scanState === 'cancelled' || scanState === 'failed') && (
          <div className="space-y-6 py-2">
            <div className={`p-4 rounded-2xl border space-y-2 ${
              scanState === 'completed'
                ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                : scanState === 'cancelled'
                ? 'bg-amber-50/70 border-amber-200 text-amber-900'
                : 'bg-rose-50/70 border-rose-200 text-rose-900'
            }`}>
              <div className="flex items-center space-x-2 font-bold text-sm">
                {scanState === 'completed' && <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />}
                {scanState === 'cancelled' && <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />}
                {scanState === 'failed' && <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />}
                <span>
                  {scanState === 'completed' && '5x5 Geo-Grid Scan Completed'}
                  {scanState === 'cancelled' && 'Geo-Grid Scan Cancelled by User'}
                  {scanState === 'failed' && 'Geo-Grid Scan Failed'}
                </span>
              </div>
              <p className="text-xs opacity-80">
                {scanState === 'completed' && `All ${liveProgress?.totalPoints ?? 25} points successfully evaluated and saved to your project.`}
                {scanState === 'cancelled' && `${liveProgress?.completedPoints ?? 0} points were evaluated before cancellation. Partial results have been preserved.`}
                {scanState === 'failed' && (liveProgress?.message || 'The SERP scan could not be completed. Please check your SERP settings.')}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 text-center text-xs">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Average Rank</span>
                <span className="text-lg font-black text-slate-900">
                  {liveProgress?.averageRank ? `#${liveProgress.averageRank}` : 'N/A'}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Top 3 Visibility</span>
                <span className="text-lg font-black text-slate-900">
                  {liveProgress?.visibilityPct ?? 0}%
                </span>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 border-t border-slate-100 pt-4">
              <button
                type="button"
                onClick={handleFinishAndClose}
                className="px-5 py-2.5 rounded-xl text-xs font-bold btn-primary-gradient shadow-md hover:shadow-lg transition-all flex items-center space-x-2 cursor-pointer"
              >
                <span>View Results on Map</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
    </Modal>
  );
};

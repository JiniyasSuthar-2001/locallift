import React, { useState, useMemo } from 'react';
import { GeoGridScan, GridPoint } from '../../types';
import {
  MapPin,
  Navigation,
  CheckCircle2,
  RotateCw,
  AlertCircle,
  Clock,
  Building2,
  Search,
  ExternalLink,
  Eye,
  Target,
  XCircle,
  HelpCircle
} from 'lucide-react';
import { StatusBadge } from '../ui/StatusBadge';
import { EmptyState } from '../ui/EmptyState';

interface LocalGridMapProps {
  scan: GeoGridScan | null;
  onRescan?: () => void;
  isScanning?: boolean;
}

/** Rank-based color system (Section 9) — always shows text alongside color */
function getRankStyle(rank: number | null, status: string) {
  const normalized = (status || '').toUpperCase();

  if (normalized === 'PROVIDER_ERROR' || normalized === 'ERROR') {
    return { bg: 'bg-slate-200', border: 'border-slate-400', text: 'text-slate-700', label: 'ERR' };
  }
  if (normalized === 'TIMEOUT') {
    return { bg: 'bg-slate-200', border: 'border-slate-400', text: 'text-slate-700', label: 'TO' };
  }
  if (normalized === 'NOT_FOUND' || (normalized === 'SUCCESS' && rank === null)) {
    return { bg: 'bg-rose-100', border: 'border-rose-400', text: 'text-rose-800', label: 'NF' };
  }
  if (normalized === 'PENDING' || normalized === '') {
    return { bg: 'bg-slate-100', border: 'border-slate-300', text: 'text-slate-500', label: '—' };
  }

  // Rank-based coloring
  if (rank != null) {
    if (rank <= 3) return { bg: 'bg-emerald-100', border: 'border-emerald-500', text: 'text-emerald-900', label: `#${rank}` };
    if (rank <= 7) return { bg: 'bg-blue-100', border: 'border-blue-500', text: 'text-blue-900', label: `#${rank}` };
    if (rank <= 15) return { bg: 'bg-amber-100', border: 'border-amber-500', text: 'text-amber-900', label: `#${rank}` };
    return { bg: 'bg-rose-100', border: 'border-rose-500', text: 'text-rose-900', label: `#${rank}` };
  }

  return { bg: 'bg-slate-100', border: 'border-slate-300', text: 'text-slate-500', label: '—' };
}

export const LocalGridMap: React.FC<LocalGridMapProps> = ({ scan, onRescan, isScanning }) => {
  const [selectedPin, setSelectedPin] = useState<GridPoint | null>(null);

  const rawPoints: GridPoint[] = scan?.points || scan?.grid_points || [];

  // ─── Geographic positioning ───
  // Calculate bounds from actual point coordinates to create proportional layout (always called at top)
  const geoLayout = useMemo(() => {
    if (!rawPoints || rawPoints.length === 0) return null;
    const lats = rawPoints.map(p => p.lat ?? p.latitude ?? 0).filter(Boolean);
    const lngs = rawPoints.map(p => p.lng ?? p.longitude ?? 0).filter(Boolean);

    if (lats.length === 0 || lngs.length === 0) return null;

    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);

    const latRange = maxLat - minLat || 0.01;
    const lngRange = maxLng - minLng || 0.01;

    return { minLat, maxLat, minLng, maxLng, latRange, lngRange };
  }, [rawPoints]);

  if (!scan || rawPoints.length === 0) {
    return (
      <EmptyState
        icon={MapPin}
        badge="Geo-Grid"
        title="No Geo-Grid Scan Yet"
        description="Run a 5×5 Geo-Grid scan to evaluate local search rankings at 25 discrete GPS coordinates across your service territory."
        actionText="Run Geo-Grid Scan"
        onAction={onRescan}
      />
    );
  }

  const gridSize = scan.grid_size || 5;
  const totalPoints = scan.total_points ?? rawPoints.length;
  const isIncomplete = rawPoints.length < 25 && scan.scan_status === 'completed';

  const centerLat = scan.center?.lat ?? scan.center_lat;
  const centerLng = scan.center?.lng ?? scan.center_lng;
  const centerName = scan.center?.name ?? scan.center_name;

  // Compute metrics
  const completedPoints = scan.completed_points ?? rawPoints.length;
  const rankingFound = scan.ranking_found_points ?? rawPoints.filter(p => p.rank != null && p.rank > 0).length;
  const notFoundPts = scan.not_found_points ?? rawPoints.filter(p => (p.status || '').toUpperCase() === 'NOT_FOUND').length;
  const errorPts = scan.provider_error_points ?? rawPoints.filter(p => ['PROVIDER_ERROR', 'ERROR'].includes((p.status || '').toUpperCase())).length;
  const timeoutPts = scan.timeout_points ?? rawPoints.filter(p => (p.status || '').toUpperCase() === 'TIMEOUT').length;

  const rankedPoints = rawPoints.filter(p => p.rank != null && p.rank > 0);
  const avgRank = scan.average_rank ?? (rankedPoints.length > 0
    ? rankedPoints.reduce((sum, p) => sum + (p.rank || 0), 0) / rankedPoints.length
    : null);
  const visibility = scan.local_visibility_pct;

  return (
    <div className="rounded-2xl border border-[#DCE8DC] bg-white overflow-hidden">
      {/* ─── Header ─── */}
      <div className="px-6 py-4 border-b border-[#EBF2EB] bg-[#F7FAF7]">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-black uppercase tracking-wider text-[#236B4F]">
                {gridSize}×{gridSize} GEO-GRID
              </span>
              <StatusBadge status={`${scan.radius_km} km`} variant="blue" />
              {scan.scan_status === 'completed' && (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-900 border border-emerald-200">COMPLETED</span>
              )}
              {scan.scan_status === 'completed_with_errors' && (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-200">WITH ERRORS</span>
              )}
              {scan.scan_status === 'failed' && (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-900 border border-rose-200">FAILED</span>
              )}
            </div>
            {scan.keyword && (
              <div className="text-xs text-[#587568]">
                <span className="font-semibold">Keyword:</span> {scan.keyword}
              </div>
            )}
            {centerName && (
              <div className="text-[11px] text-[#587568]">
                <span className="font-semibold">Center:</span> {centerName} ({centerLat?.toFixed(4)}, {centerLng?.toFixed(4)})
              </div>
            )}
          </div>

          <button
            onClick={onRescan}
            disabled={isScanning}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-[#236B4F] hover:bg-[#1D5A42] disabled:opacity-50 transition-colors shadow-sm self-start"
          >
            <RotateCw className={`w-4 h-4 ${isScanning ? 'animate-spin' : ''}`} />
            {isScanning ? 'Scanning...' : 'Re-scan'}
          </button>
        </div>
      </div>

      {/* ─── Incomplete banner ─── */}
      {isIncomplete && (
        <div className="px-6 py-2 bg-amber-50 border-b border-amber-200 text-xs text-amber-800 font-medium">
          ⚠ Incomplete scan: {rawPoints.length}/{totalPoints} points received. Some grid positions may be missing.
        </div>
      )}

      {/* ─── Metrics Strip ─── */}
      <div className="px-6 py-3 border-b border-[#EBF2EB] flex flex-wrap gap-4">
        <Metric label="Total" value={totalPoints} />
        <Metric label="Completed" value={completedPoints} />
        <Metric label="Ranked" value={rankingFound} color="emerald" />
        <Metric label="Not Found" value={notFoundPts} color={notFoundPts > 0 ? 'rose' : undefined} />
        <Metric label="Errors" value={errorPts} color={errorPts > 0 ? 'rose' : undefined} />
        <Metric label="Timeouts" value={timeoutPts} color={timeoutPts > 0 ? 'amber' : undefined} />
        <Metric label="Avg Rank" value={avgRank != null ? avgRank.toFixed(1) : 'N/A'} />
        <Metric label="Visibility" value={visibility != null ? `${visibility.toFixed(0)}%` : 'N/A'} color="emerald" />
      </div>

      {/* ─── Geographic Grid Visualization ─── */}
      <div className="p-6">
        {geoLayout ? (
          <div className="relative" style={{ width: '100%', paddingBottom: '80%', maxHeight: '500px' }}>
            <div className="absolute inset-0">
              {/* Grid background lines */}
              <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                {/* Horizontal lines */}
                {[20, 40, 60, 80].map(y => (
                  <line key={`h${y}`} x1="0" y1={y} x2="100" y2={y} stroke="#EBF2EB" strokeWidth="0.3" />
                ))}
                {/* Vertical lines */}
                {[20, 40, 60, 80].map(x => (
                  <line key={`v${x}`} x1={x} y1="0" x2={x} y2="100" stroke="#EBF2EB" strokeWidth="0.3" />
                ))}
              </svg>

              {/* Center marker */}
              {centerLat != null && centerLng != null && (
                <div
                  className="absolute z-20 transform -translate-x-1/2 -translate-y-1/2"
                  style={{
                    left: `${((centerLng - geoLayout.minLng) / geoLayout.lngRange) * 84 + 8}%`,
                    top: `${(1 - (centerLat - geoLayout.minLat) / geoLayout.latRange) * 84 + 8}%`,
                  }}
                >
                  <div className="relative">
                    <div className="w-6 h-6 rounded-full bg-[#236B4F] border-2 border-white shadow-lg flex items-center justify-center">
                      <Building2 className="w-3.5 h-3.5 text-white" />
                    </div>
                    <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap text-[8px] font-bold text-[#236B4F] bg-white/90 px-1 rounded">
                      CENTER
                    </div>
                  </div>
                </div>
              )}

              {/* Grid points — positioned by real coordinates */}
              {rawPoints.map((point, idx) => {
                const lat = point.lat ?? point.latitude ?? 0;
                const lng = point.lng ?? point.longitude ?? 0;
                const style = getRankStyle(point.rank, point.status || '');
                const isSelected = selectedPin?.point_number === point.point_number && selectedPin?.row === point.row;

                const xPct = ((lng - geoLayout.minLng) / geoLayout.lngRange) * 84 + 8;
                const yPct = (1 - (lat - geoLayout.minLat) / geoLayout.latRange) * 84 + 8;

                return (
                  <button
                    key={`${point.point_number ?? idx}`}
                    className={`absolute z-10 transform -translate-x-1/2 -translate-y-1/2 transition-all duration-150 hover:scale-125 ${isSelected ? 'scale-125 z-30' : ''}`}
                    style={{ left: `${xPct}%`, top: `${yPct}%` }}
                    onClick={() => setSelectedPin(isSelected ? null : point)}
                    title={`Point ${point.point_number ?? idx + 1}: ${style.label} (${lat.toFixed(4)}, ${lng.toFixed(4)})`}
                  >
                    <div className={`w-9 h-9 rounded-xl ${style.bg} border-2 ${style.border} flex items-center justify-center shadow-sm ${isSelected ? 'ring-2 ring-[#236B4F] ring-offset-1' : ''}`}>
                      <span className={`text-[11px] font-black ${style.text}`}>{style.label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          /* Fallback: row/column matrix if no geo coordinates */
          <div className="space-y-2">
            {Array.from({ length: gridSize }, (_, r) => {
              const rowPoints = rawPoints.filter(p => p.row === r).sort((a, b) => a.col - b.col);
              return (
                <div key={r} className="flex items-center justify-center gap-2">
                  {rowPoints.length > 0 ? rowPoints.map((point, idx) => {
                    const style = getRankStyle(point.rank, point.status || '');
                    const isSelected = selectedPin?.point_number === point.point_number;
                    return (
                      <button
                        key={idx}
                        onClick={() => setSelectedPin(isSelected ? null : point)}
                        className={`w-12 h-12 rounded-xl ${style.bg} border-2 ${style.border} flex items-center justify-center transition-all hover:scale-110 ${isSelected ? 'ring-2 ring-[#236B4F] ring-offset-1 scale-110' : ''}`}
                      >
                        <span className={`text-xs font-black ${style.text}`}>{style.label}</span>
                      </button>
                    );
                  }) : (
                    <div className="text-xs text-slate-400">Row {r + 1}: no points</div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ─── Legend ─── */}
        <div className="flex flex-wrap items-center gap-3 mt-4 pt-3 border-t border-[#EBF2EB]">
          <span className="text-[10px] font-bold text-[#587568] uppercase">Legend:</span>
          <LegendItem bg="bg-emerald-100" border="border-emerald-500" label="#1-3 Strong" />
          <LegendItem bg="bg-blue-100" border="border-blue-500" label="#4-7 Good" />
          <LegendItem bg="bg-amber-100" border="border-amber-500" label="#8-15 Moderate" />
          <LegendItem bg="bg-rose-100" border="border-rose-500" label="#16+ Weak" />
          <LegendItem bg="bg-rose-100" border="border-rose-400" label="NF Not Found" />
          <LegendItem bg="bg-slate-200" border="border-slate-400" label="ERR/TO Error" />
          <LegendItem bg="bg-[#236B4F]" border="border-white" label="● Center" isCenter />
        </div>
      </div>

      {/* ─── Point Detail Inspector ─── */}
      {selectedPin && (
        <div className="px-6 pb-6">
          <div className="rounded-2xl border border-[#DCE8DC] bg-[#F7FAF7] p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-black text-[#142820]">
                Point #{selectedPin.point_number ?? '—'} Detail
              </h3>
              <button onClick={() => setSelectedPin(null)} className="text-[#587568] hover:text-[#142820]">
                <XCircle className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              <DetailField label="Coordinates" value={`${(selectedPin.lat ?? selectedPin.latitude)?.toFixed(5)}, ${(selectedPin.lng ?? selectedPin.longitude)?.toFixed(5)}`} />
              <DetailField label="Rank" value={selectedPin.rank != null ? `#${selectedPin.rank}` : 'Not found'} />
              <DetailField label="Status" value={selectedPin.status || 'N/A'} />
              <DetailField label="Keyword" value={selectedPin.keyword || scan.keyword || 'N/A'} />
              <DetailField label="Provider" value={selectedPin.provider || scan.provider?.name || 'N/A'} />
              <DetailField label="Business Found" value={selectedPin.matched_business || 'N/A'} />
              <DetailField label="Place ID" value={selectedPin.matched_place_id || 'N/A'} />
              <DetailField label="Domain" value={selectedPin.matched_domain || 'N/A'} />
              {selectedPin.error && (
                <DetailField label="Error" value={selectedPin.error} isError />
              )}
              <DetailField label="Searched At" value={selectedPin.searched_at ? new Date(selectedPin.searched_at).toLocaleString() : 'N/A'} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ─── Sub-components ───

const Metric: React.FC<{ label: string; value: string | number; color?: string }> = ({ label, value, color }) => {
  const colorClass = color === 'emerald' ? 'text-emerald-700' : color === 'rose' ? 'text-rose-700' : color === 'amber' ? 'text-amber-700' : 'text-[#142820]';
  return (
    <div className="text-center min-w-[60px]">
      <div className="text-[10px] font-bold uppercase tracking-wider text-[#587568]">{label}</div>
      <div className={`text-sm font-black ${colorClass}`}>{value}</div>
    </div>
  );
};

const LegendItem: React.FC<{ bg: string; border: string; label: string; isCenter?: boolean }> = ({ bg, border, label, isCenter }) => (
  <div className="flex items-center gap-1">
    <div className={`w-4 h-4 rounded ${bg} border ${border} ${isCenter ? 'flex items-center justify-center' : ''}`}>
      {isCenter && <Building2 className="w-2.5 h-2.5 text-white" />}
    </div>
    <span className="text-[10px] font-medium text-[#587568]">{label}</span>
  </div>
);

const DetailField: React.FC<{ label: string; value: string; isError?: boolean }> = ({ label, value, isError }) => (
  <div className="space-y-0.5">
    <div className="text-[10px] font-bold uppercase tracking-wider text-[#587568]">{label}</div>
    <div className={`text-xs font-semibold ${isError ? 'text-rose-700' : 'text-[#142820]'} break-all`}>
      {value}
    </div>
  </div>
);

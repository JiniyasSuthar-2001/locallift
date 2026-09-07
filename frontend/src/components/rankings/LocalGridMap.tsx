import React, { useState } from 'react';
import { GeoGridScan, GridPoint } from '../../types';
import { MapPin, Navigation, Eye, CheckCircle2, RotateCw, Sparkles, AlertCircle } from 'lucide-react';
import { StatusBadge } from '../ui/StatusBadge';
import { EmptyState } from '../ui/EmptyState';

interface LocalGridMapProps {
  scan: GeoGridScan | null;
  onRescan?: () => void;
  isScanning?: boolean;
}

export const LocalGridMap: React.FC<LocalGridMapProps> = ({ scan, onRescan, isScanning }) => {
  const [selectedPin, setSelectedPin] = useState<GridPoint | null>(null);

  if (!scan || !scan.grid_points || scan.grid_points.length === 0) {
    return (
      <EmptyState
        icon={MapPin}
        badge="5x5 Geo-Grid"
        title="No Geo-Grid Scan Yet"
        description="Run a 5x5 Geo-Grid scan to map Google Maps Local Pack rank positions at discrete GPS coordinates across your service area."
        actionText="Run 5x5 Geo-Grid Scan"
        onAction={onRescan}
      />
    );
  }

  // Group by rows
  const gridSize = scan.grid_size || 5;
  const rows = Array.from({ length: gridSize }, (_, r) =>
    scan.grid_points.filter((p) => p.row === r).sort((a, b) => a.col - b.col)
  );

  return (
    <div className="card-vibrant p-6 space-y-6">
      {/* Top Controls & Metrics */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-black uppercase tracking-wider text-purple-700">
              5x5 GEO-GRID RANK MATRIX
            </span>
            <StatusBadge status={`${scan.radius_km}km Radius`} variant="blue" />
            {scan.scan_status === 'completed' && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-900 border border-emerald-200">
                COMPLETED
              </span>
            )}
            {scan.scan_status === 'completed_with_errors' && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-200">
                COMPLETED WITH ERRORS
              </span>
            )}
            {scan.scan_status === 'failed' && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-900 border border-rose-200">
                SCAN FAILED
              </span>
            )}
            {scan.total_points !== undefined && (
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                {scan.successful_points ?? 0}/{scan.total_points} Points ({scan.failed_points ?? 0} Failed)
              </span>
            )}
          </div>
          <h3 className="text-lg font-black text-slate-900 mt-1 flex items-center space-x-2">
            <span>Center: {scan.center_name}</span>
          </h3>
        </div>

        <div className="flex items-center space-x-6">
          <div className="text-right">
            <div className="text-[10px] uppercase font-bold text-slate-500">Local Visibility</div>
            <div className="text-xl font-black text-purple-700">{scan.local_visibility_pct}%</div>
          </div>

          <div className="text-right">
            <div className="text-[10px] uppercase font-bold text-slate-500">Avg Rank</div>
            <div className="text-xl font-black text-slate-900">
              {scan.average_rank !== null && scan.average_rank !== undefined && scan.average_rank > 0
                ? `#${scan.average_rank}`
                : '—'}
            </div>
          </div>

          {onRescan && (
            <button
              onClick={onRescan}
              disabled={isScanning}
              className="flex items-center space-x-2 px-4 py-2 btn-vibrant-primary rounded-xl text-xs font-bold shadow-sm transition-all"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
              <span>{isScanning ? 'Scanning Grid...' : 'Re-scan Grid'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Grid Matrix Visualizer & Details Split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
        {/* Interactive 5x5 Map Grid */}
        <div className="lg:col-span-7 bg-slate-50 p-6 rounded-2xl border border-slate-200/80 flex flex-col items-center justify-center relative shadow-inner">
          <div className="space-y-3">
            {rows.map((row, rIdx) => (
              <div key={rIdx} className="flex space-x-3">
                {row.map((point, cIdx) => {
                  const isSelected = selectedPin?.lat === point.lat && selectedPin?.lng === point.lng;
                  let bgStyle = 'bg-slate-400 hover:bg-slate-300 text-white';
                  let displayLabel = '—';

                  if (point.rank !== null && point.rank !== undefined) {
                    displayLabel = `#${point.rank}`;
                    if (point.rank <= 3) {
                      bgStyle = 'bg-emerald-600 hover:bg-emerald-500 text-white';
                    } else if (point.rank <= 6) {
                      bgStyle = 'bg-amber-500 hover:bg-amber-400 text-white';
                    } else {
                      bgStyle = 'bg-rose-600 hover:bg-rose-500 text-white';
                    }
                  } else if (point.status === 'failed' || point.pin_status === 'failed') {
                    displayLabel = '!';
                    bgStyle = 'bg-rose-800 hover:bg-rose-700 text-white';
                  }

                  return (
                    <button
                      key={cIdx}
                      onClick={() => setSelectedPin(point)}
                      className={`w-12 h-12 rounded-full flex flex-col items-center justify-center font-black text-sm transition-all transform hover:scale-110 shadow-md ${bgStyle} ${
                        isSelected ? 'ring-4 ring-purple-600 scale-110' : ''
                      }`}
                      title={`Coordinates: ${point.lat}, ${point.lng} | Rank: ${displayLabel}`}
                    >
                      <span>{displayLabel}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-center gap-4 text-[11px] text-slate-600 font-semibold">
            <span className="flex items-center space-x-1.5">
              <span className="w-3 h-3 rounded-full bg-emerald-600 inline-block" />
              <span>Rank 1-3 (Top Pack)</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="w-3 h-3 rounded-full bg-amber-500 inline-block" />
              <span>Rank 4-6 (Mid Pack)</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="w-3 h-3 rounded-full bg-rose-600 inline-block" />
              <span>Rank 7+ (Drop-off)</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="w-3 h-3 rounded-full bg-slate-400 inline-block" />
              <span>Not in Top Pack</span>
            </span>
          </div>
        </div>

        {/* Pin Inspector Details */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-slate-50 p-5 rounded-2xl border border-slate-200">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center space-x-1.5">
              <Navigation className="w-4 h-4 text-purple-600" />
              <span>GPS Node Diagnostic</span>
            </h4>

            {selectedPin ? (
              <div className="space-y-3 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-200">
                  <span className="text-slate-500 font-medium">Local Pack Position:</span>
                  <span className="font-black text-slate-900 text-sm">
                    {selectedPin.rank !== null && selectedPin.rank !== undefined ? `#${selectedPin.rank}` : 'Not Ranked in Top Pack'}
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200">
                  <span className="text-slate-500 font-medium">Latitude:</span>
                  <span className="font-mono text-slate-800 font-semibold">{selectedPin.lat}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200">
                  <span className="text-slate-500 font-medium">Longitude:</span>
                  <span className="font-mono text-slate-800 font-semibold">{selectedPin.lng}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-200">
                  <span className="text-slate-500 font-medium">Local Visibility:</span>
                  <StatusBadge
                    status={
                      selectedPin.rank && selectedPin.rank <= 3
                        ? 'Top 3 Pack'
                        : selectedPin.rank && selectedPin.rank <= 6
                        ? 'Mid Pack'
                        : selectedPin.rank
                        ? 'Low Visibility'
                        : 'Unranked'
                    }
                  />
                </div>
                {selectedPin.competitor_ahead && (
                  <div className="py-1">
                    <span className="text-slate-500 font-medium block mb-0.5">Top Competitor in Local Pack:</span>
                    <span className="text-purple-900 font-bold">{selectedPin.competitor_ahead}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-slate-500 py-6 text-center font-medium">
                Click on any circular grid pin to inspect localized ranking metrics and competitor share at that specific GPS node.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

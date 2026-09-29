import React, { useState, useEffect, useRef } from 'react';
import { GeoGridScan, GridPoint } from '../../types';
import {
  MapPin,
  Building2,
  RotateCw,
  ZoomIn,
  ZoomOut,
  Info,
  Navigation,
  LocateFixed,
  AlertTriangle,
  CheckCircle2
} from 'lucide-react';
import { EmptyState } from '../ui/EmptyState';
import { PointAnalysisDrawer } from './PointAnalysisDrawer';
import { loadGoogleMapsScript, isGoogleMapsLoaded } from '../../utils/googleMapsLoader';
import { loadLeafletScript, isLeafletLoaded } from '../../utils/leafletLoader';

declare const google: any;

interface LocalGridMapProps {
  scan: GeoGridScan | null;
  onRescan?: () => void;
  isScanning?: boolean;
  selectedPoint?: GridPoint | null;
  onSelectPoint?: (point: GridPoint | null) => void;
}

/** Rank-based color system & badge styling */
function getRankStyle(rank: number | null, status: string) {
  const normalized = (status || '').toUpperCase();

  if (normalized === 'PROVIDER_ERROR' || normalized === 'ERROR') {
    return {
      bg: 'bg-slate-200',
      border: 'border-slate-500',
      text: 'text-slate-800',
      fillColor: '#64748B',
      textColor: '#1E293B',
      label: 'ERR'
    };
  }
  if (normalized === 'TIMEOUT') {
    return {
      bg: 'bg-slate-200',
      border: 'border-slate-500',
      text: 'text-slate-800',
      fillColor: '#64748B',
      textColor: '#1E293B',
      label: 'TO'
    };
  }
  if (normalized === 'NOT_FOUND' || (normalized === 'SUCCESS' && rank === null)) {
    return {
      bg: 'bg-rose-100',
      border: 'border-rose-500',
      text: 'text-rose-900',
      fillColor: '#F43F5E',
      textColor: '#881337',
      label: 'NF'
    };
  }
  if (normalized === 'PENDING' || normalized === '') {
    return {
      bg: 'bg-slate-100',
      border: 'border-slate-300',
      text: 'text-slate-500',
      fillColor: '#94A3B8',
      textColor: '#475569',
      label: '—'
    };
  }

  // Rank-based coloring
  if (rank != null) {
    if (rank <= 3) {
      return {
        bg: 'bg-emerald-500',
        border: 'border-emerald-700',
        text: 'text-white font-extrabold',
        fillColor: '#10B981',
        textColor: '#FFFFFF',
        label: `#${rank}`
      };
    }
    if (rank <= 7) {
      return {
        bg: 'bg-blue-500',
        border: 'border-blue-700',
        text: 'text-white font-extrabold',
        fillColor: '#3B82F6',
        textColor: '#FFFFFF',
        label: `#${rank}`
      };
    }
    if (rank <= 15) {
      return {
        bg: 'bg-amber-400',
        border: 'border-amber-600',
        text: 'text-slate-900 font-extrabold',
        fillColor: '#F59E0B',
        textColor: '#0F172A',
        label: `#${rank}`
      };
    }
    return {
      bg: 'bg-rose-500',
      border: 'border-rose-700',
      text: 'text-white font-extrabold',
      fillColor: '#EF4444',
      textColor: '#FFFFFF',
      label: `#${rank}`
    };
  }

  return {
    bg: 'bg-slate-100',
    border: 'border-slate-300',
    text: 'text-slate-500',
    fillColor: '#94A3B8',
    textColor: '#475569',
    label: '—'
  };
}

/**
 * Creates an SVG Data URL icon for Google Maps & Leaflet Markers
 */
function createGridPinSvg(label: string, pointNum: number, fillColor: string, isSelected: boolean): string {
  const size = isSelected ? 42 : 34;
  const radius = isSelected ? 12 : 9;
  const strokeColor = isSelected ? '#236B4F' : '#FFFFFF';
  const strokeWidth = isSelected ? 3 : 2;

  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
      ${isSelected ? `<circle cx="${size / 2}" cy="${size / 2}" r="${(size / 2) - 2}" fill="none" stroke="#236B4F" stroke-width="3" opacity="0.85"/>` : ''}
      <rect x="${isSelected ? 5 : 2}" y="${isSelected ? 5 : 2}" width="${size - (isSelected ? 10 : 4)}" height="${size - (isSelected ? 10 : 4)}" rx="${radius}" fill="${fillColor}" stroke="${strokeColor}" stroke-width="${strokeWidth}"/>
      <text x="${size / 2}" y="${(size / 2) + 4}" text-anchor="middle" fill="#FFFFFF" font-size="${isSelected ? '12px' : '10px'}" font-weight="900" font-family="Outfit, Inter, sans-serif">${label}</text>
      <circle cx="${size - 6}" cy="6" r="6" fill="#1E293B" stroke="#FFFFFF" stroke-width="1.5"/>
      <text x="${size - 6}" y="9" text-anchor="middle" fill="#FFFFFF" font-size="7px" font-weight="bold" font-family="Inter, sans-serif">${pointNum}</text>
    </svg>
  `;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg.trim())}`;
}

function createCenterPinSvg(): string {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44">
      <circle cx="22" cy="22" r="20" fill="#236B4F" fill-opacity="0.3"/>
      <circle cx="22" cy="22" r="14" fill="#236B4F" stroke="#FFFFFF" stroke-width="2.5"/>
      <rect x="17" y="16" width="10" height="12" rx="1.5" fill="#FFFFFF"/>
      <rect x="19" y="18" width="2" height="2" fill="#236B4F"/>
      <rect x="23" y="18" width="2" height="2" fill="#236B4F"/>
      <rect x="19" y="21" width="2" height="2" fill="#236B4F"/>
      <rect x="23" y="21" width="2" height="2" fill="#236B4F"/>
      <rect x="20" y="24" width="4" height="4" fill="#236B4F"/>
    </svg>
  `;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg.trim())}`;
}

export const LocalGridMap: React.FC<LocalGridMapProps> = ({
  scan,
  onRescan,
  isScanning,
  selectedPoint: controlledPoint,
  onSelectPoint
}) => {
  const [internalPoint, setInternalPoint] = useState<GridPoint | null>(null);
  const selectedPoint = controlledPoint !== undefined ? controlledPoint : internalPoint;

  const handleSelectPoint = (pt: GridPoint | null) => {
    setInternalPoint(pt);
    onSelectPoint?.(pt);
  };

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const gmapInstanceRef = useRef<any>(null);
  const gmarkersRef = useRef<any[]>([]);
  const gcircleRef = useRef<any>(null);

  const leafletInstanceRef = useRef<any>(null);
  const leafletMarkersRef = useRef<any[]>([]);
  const leafletCircleRef = useRef<any>(null);
  const leafletTileLayerRef = useRef<any>(null);

  const [mapEngine, setMapEngine] = useState<'google' | 'leaflet' | 'loading'>('loading');

  const rawPoints: GridPoint[] = scan?.points || scan?.grid_points || [];

  const centerLat = scan?.center?.lat ?? scan?.center_lat ?? 0;
  const centerLng = scan?.center?.lng ?? scan?.center_lng ?? 0;
  const centerName = scan?.center?.name ?? scan?.center_name ?? 'Business Center';
  const radiusKm = scan?.radius_km ?? 5.0;
  const gridSize = scan?.grid_size ?? 5;

  // 1. Engine Initialization Strategy: Google Maps first -> Fallback to Leaflet Satellite
  useEffect(() => {
    const apiKey = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '').trim();
    let isMounted = true;

    if (apiKey) {
      loadGoogleMapsScript({ apiKey })
        .then(() => {
          if (isMounted) setMapEngine('google');
        })
        .catch(() => {
          if (isMounted) {
            loadLeafletScript()
              .then(() => { if (isMounted) setMapEngine('leaflet'); })
              .catch(() => { if (isMounted) setMapEngine('leaflet'); });
          }
        });
    } else {
      // No Google Maps API key provided -> load interactive Leaflet satellite engine
      loadLeafletScript()
        .then(() => {
          if (isMounted) setMapEngine('leaflet');
        })
        .catch(() => {
          if (isMounted) setMapEngine('leaflet');
        });
    }

    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Render Google Map when Google engine is active (Satellite Hybrid Default)
  useEffect(() => {
    if (mapEngine !== 'google' || !mapContainerRef.current || !scan || rawPoints.length === 0) return;
    if (typeof window === 'undefined' || !(window as any).google?.maps) return;

    const gmaps = (window as any).google.maps;

    const effectiveCenterLat = centerLat || (rawPoints[0]?.lat ?? rawPoints[0]?.latitude ?? 0);
    const effectiveCenterLng = centerLng || (rawPoints[0]?.lng ?? rawPoints[0]?.longitude ?? 0);

    if (!gmapInstanceRef.current) {
      const map = new gmaps.Map(mapContainerRef.current, {
        center: { lat: effectiveCenterLat, lng: effectiveCenterLng },
        zoom: 12,
        mapTypeId: gmaps.MapTypeId.HYBRID,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        zoomControl: false,
        styles: [
          {
            featureType: 'poi',
            elementType: 'labels',
            stylers: [{ visibility: 'off' }]
          }
        ]
      });
      gmapInstanceRef.current = map;
    }

    const map = gmapInstanceRef.current;
    map.setMapTypeId(gmaps.MapTypeId.HYBRID);

    // Clear previous markers
    gmarkersRef.current.forEach(m => m.setMap(null));
    gmarkersRef.current = [];

    // Clear previous radius circle
    if (gcircleRef.current) {
      gcircleRef.current.setMap(null);
      gcircleRef.current = null;
    }

    const bounds = new gmaps.LatLngBounds();

    // Add Center Marker and Circle
    if (centerLat && centerLng) {
      const centerLatLng = { lat: centerLat, lng: centerLng };
      bounds.extend(centerLatLng);

      const circle = new gmaps.Circle({
        strokeColor: '#236B4F',
        strokeOpacity: 0.9,
        strokeWeight: 2,
        fillColor: '#236B4F',
        fillOpacity: 0.1,
        map,
        center: centerLatLng,
        radius: radiusKm * 1000
      });
      gcircleRef.current = circle;

      const centerMarker = new gmaps.Marker({
        position: centerLatLng,
        map,
        title: `${centerName} (Center Location)`,
        zIndex: 9999,
        icon: {
          url: createCenterPinSvg(),
          scaledSize: new gmaps.Size(44, 44),
          anchor: new gmaps.Point(22, 22)
        }
      });
      gmarkersRef.current.push(centerMarker);
    }

    // Add 49 Grid Markers
    rawPoints.forEach((pt, idx) => {
      const ptLat = pt.lat ?? pt.latitude;
      const ptLng = pt.lng ?? pt.longitude;
      if (ptLat == null || ptLng == null) return;

      const ptLatLng = { lat: ptLat, lng: ptLng };
      bounds.extend(ptLatLng);

      const style = getRankStyle(pt.rank, pt.status || '');
      const isSelected = selectedPoint?.point_number === pt.point_number || (selectedPoint?.lat === ptLat && selectedPoint?.lng === ptLng);
      const ptNum = pt.point_number != null ? pt.point_number : idx + 1;

      const marker = new gmaps.Marker({
        position: ptLatLng,
        map,
        title: `Node #${ptNum}: ${style.label}`,
        zIndex: isSelected ? 1000 : 100 + idx,
        icon: {
          url: createGridPinSvg(style.label, ptNum, style.fillColor, isSelected),
          scaledSize: isSelected ? new gmaps.Size(42, 42) : new gmaps.Size(34, 34),
          anchor: isSelected ? new gmaps.Point(21, 21) : new gmaps.Point(17, 17)
        }
      });

      marker.addListener('click', () => {
        handleSelectPoint(pt);
        map.panTo(ptLatLng);
      });

      gmarkersRef.current.push(marker);
    });

    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { top: 40, right: 40, bottom: 40, left: 40 });
    }
  }, [mapEngine, scan, rawPoints, centerLat, centerLng, radiusKm, selectedPoint]);

  // 3. Render Leaflet Map when Leaflet engine is active (Permanent Satellite Imagery)
  useEffect(() => {
    if (mapEngine !== 'leaflet' || !mapContainerRef.current || !scan || rawPoints.length === 0) return;
    if (typeof window === 'undefined' || !(window as any).L) return;

    const L = (window as any).L;

    const effectiveCenterLat = centerLat || (rawPoints[0]?.lat ?? rawPoints[0]?.latitude ?? 0);
    const effectiveCenterLng = centerLng || (rawPoints[0]?.lng ?? rawPoints[0]?.longitude ?? 0);

    if (!leafletInstanceRef.current) {
      const container = mapContainerRef.current;
      if ((container as any)._leaflet_id) {
        (container as any)._leaflet_id = null;
      }

      const map = L.map(container, {
        center: [effectiveCenterLat, effectiveCenterLng],
        zoom: 12,
        zoomControl: false,
        attributionControl: false
      });
      leafletInstanceRef.current = map;
    }

    const map = leafletInstanceRef.current;

    // Permanent High-Resolution Satellite Layer
    if (leafletTileLayerRef.current) {
      map.removeLayer(leafletTileLayerRef.current);
    }

    const satelliteTileUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
    const tileLayer = L.tileLayer(satelliteTileUrl, {
      maxZoom: 19,
      subdomains: 'abcd'
    }).addTo(map);
    leafletTileLayerRef.current = tileLayer;

    // Clear previous markers
    leafletMarkersRef.current.forEach(m => map.removeLayer(m));
    leafletMarkersRef.current = [];

    // Clear previous circle
    if (leafletCircleRef.current) {
      map.removeLayer(leafletCircleRef.current);
      leafletCircleRef.current = null;
    }

    const latLngs: any[] = [];

    // Center marker & radius circle
    if (centerLat && centerLng) {
      latLngs.push([centerLat, centerLng]);

      const circle = L.circle([centerLat, centerLng], {
        radius: radiusKm * 1000,
        color: '#236B4F',
        weight: 2,
        fillColor: '#236B4F',
        fillOpacity: 0.1
      }).addTo(map);
      leafletCircleRef.current = circle;

      const centerIcon = L.divIcon({
        className: 'custom-leaflet-center-pin',
        html: `
          <div style="width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; cursor: pointer;">
            <img src="${createCenterPinSvg()}" width="44" height="44" style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.35));" />
          </div>
        `,
        iconSize: [44, 44],
        iconAnchor: [22, 22]
      });

      const centerMarker = L.marker([centerLat, centerLng], {
        icon: centerIcon,
        zIndexOffset: 9999,
        title: `${centerName} (Center Location)`
      }).addTo(map);

      leafletMarkersRef.current.push(centerMarker);
    }

    // Add 49 Grid Pins
    rawPoints.forEach((pt, idx) => {
      const ptLat = pt.lat ?? pt.latitude;
      const ptLng = pt.lng ?? pt.longitude;
      if (ptLat == null || ptLng == null) return;

      latLngs.push([ptLat, ptLng]);

      const style = getRankStyle(pt.rank, pt.status || '');
      const isSelected = selectedPoint?.point_number === pt.point_number || (selectedPoint?.lat === ptLat && selectedPoint?.lng === ptLng);
      const ptNum = pt.point_number != null ? pt.point_number : idx + 1;
      const size = isSelected ? 42 : 34;

      const pinIcon = L.divIcon({
        className: `custom-leaflet-grid-pin-${ptNum}`,
        html: `
          <div style="width: ${size}px; height: ${size}px; cursor: pointer; transition: transform 0.15s ease;">
            <img src="${createGridPinSvg(style.label, ptNum, style.fillColor, isSelected)}" width="${size}" height="${size}" style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.35));" />
          </div>
        `,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2]
      });

      const marker = L.marker([ptLat, ptLng], {
        icon: pinIcon,
        zIndexOffset: isSelected ? 1000 : 100 + idx,
        title: `Node #${ptNum}: ${style.label}`
      }).addTo(map);

      marker.on('click', () => {
        handleSelectPoint(pt);
        map.panTo([ptLat, ptLng], { animate: true });
      });

      leafletMarkersRef.current.push(marker);
    });

    if (latLngs.length > 0) {
      const bounds = L.latLngBounds(latLngs);
      map.fitBounds(bounds, { padding: [40, 40] });
    }
  }, [mapEngine, scan, rawPoints, centerLat, centerLng, radiusKm, selectedPoint]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (leafletInstanceRef.current) {
        leafletInstanceRef.current.remove();
        leafletInstanceRef.current = null;
      }
      gmapInstanceRef.current = null;
    };
  }, []);

  const handleZoomIn = () => {
    if (mapEngine === 'google' && gmapInstanceRef.current) {
      gmapInstanceRef.current.setZoom(gmapInstanceRef.current.getZoom() + 1);
    } else if (mapEngine === 'leaflet' && leafletInstanceRef.current) {
      leafletInstanceRef.current.zoomIn();
    }
  };

  const handleZoomOut = () => {
    if (mapEngine === 'google' && gmapInstanceRef.current) {
      gmapInstanceRef.current.setZoom(gmapInstanceRef.current.getZoom() - 1);
    } else if (mapEngine === 'leaflet' && leafletInstanceRef.current) {
      leafletInstanceRef.current.zoomOut();
    }
  };

  const handleRecenter = () => {
    if (centerLat && centerLng) {
      if (mapEngine === 'google' && gmapInstanceRef.current) {
        gmapInstanceRef.current.panTo({ lat: centerLat, lng: centerLng });
        gmapInstanceRef.current.setZoom(13);
      } else if (mapEngine === 'leaflet' && leafletInstanceRef.current) {
        leafletInstanceRef.current.setView([centerLat, centerLng], 13, { animate: true });
      }
    }
  };

  const hasValidCoordinates = (centerLat !== 0 || centerLng !== 0) || rawPoints.some(p => (p.lat ?? p.latitude ?? 0) !== 0);

  if (!scan || rawPoints.length === 0 || !hasValidCoordinates) {
    return (
      <div className="rounded-2xl border border-[#DCE8DC] bg-white p-8 shadow-xs">
        <EmptyState
          icon={MapPin}
          badge="Geo-Grid Visibility"
          title={!hasValidCoordinates && scan ? "Location coordinates unavailable" : "No Geo-Grid Data Available"}
          description={!hasValidCoordinates && scan ? "Please configure valid geographic coordinates for this business location to render a Geo-Grid map." : "Run a 3×3, 5×5, or 7×7 geo-grid scan to visualize your local ranking dominance across geographic satellite coordinates."}
          actionText={onRescan ? 'Run Geo-Grid Scan' : undefined}
          onAction={onRescan}
        />
      </div>
    );
  }

  // Summary Metrics Computation
  const validRankPoints = rawPoints.filter(p => p.rank != null && p.rank > 0);
  const totalPoints = rawPoints.length;
  const avgRank = validRankPoints.length > 0
    ? (validRankPoints.reduce((acc, p) => acc + (p.rank || 0), 0) / validRankPoints.length).toFixed(1)
    : '—';
  const top3Count = rawPoints.filter(p => p.rank != null && p.rank <= 3).length;
  const top3Pct = totalPoints > 0 ? Math.round((top3Count / totalPoints) * 100) : 0;
  const notFoundCount = rawPoints.filter(p => p.rank == null || (p.status || '').toUpperCase() === 'NOT_FOUND').length;
  const precision = scan.location_precision || 'UNKNOWN';
  const isCityFallback = precision === 'CITY_LEVEL';
  const isExact = precision === 'EXACT';
  const isAddressResolved = precision === 'ADDRESS_RESOLVED';

  return (
    <div className="rounded-2xl border border-[#DCE8DC] bg-white shadow-xs overflow-hidden animate-fade-in">
      {/* ─── Header & Scan Overview Bar ─── */}
      <div className="p-4 sm:p-5 border-b border-[#EBF2EB] bg-[#F7FAF7] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl gradient-brand flex items-center justify-center text-white shadow-xs shrink-0">
            <MapPin className="w-5 h-5 text-white stroke-[2.2]" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-extrabold text-[#142820]">
                {scan.keyword || 'Target Keyword'}
              </h3>
              <span className="px-2 py-0.5 text-[11px] font-semibold rounded-md border bg-emerald-50 text-emerald-900 border-emerald-300">
                {gridSize}×{gridSize} Grid ({totalPoints} pts)
              </span>

              {/* Location Precision Badge */}
              {isExact && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold rounded-md border bg-emerald-100/80 text-emerald-800 border-emerald-300">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  Exact Coordinates
                </span>
              )}
              {isAddressResolved && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold rounded-md border bg-blue-50 text-blue-800 border-blue-200">
                  <MapPin className="w-3 h-3 text-blue-600" />
                  Address Resolved
                </span>
              )}
              {isCityFallback && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-bold rounded-md border bg-amber-50 text-amber-800 border-amber-300">
                  <AlertTriangle className="w-3 h-3 text-amber-600" />
                  City Fallback
                </span>
              )}
            </div>
            <div className="text-xs text-[#587568] flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1 font-medium">
              <span className="flex items-center gap-1 text-[#142820] font-semibold">
                <Building2 className="w-3.5 h-3.5 text-[#236B4F]" />
                {centerName}
              </span>
              <span>•</span>
              <span className="font-mono text-[11px] text-slate-600">
                {centerLat.toFixed(5)}, {centerLng.toFixed(5)}
              </span>
              <span>•</span>
              <span>{radiusKm} km radius</span>
              {scan.center_address && (
                <>
                  <span>•</span>
                  <span className="text-slate-600 truncate max-w-xs" title={scan.center_address}>
                    {scan.center_address}
                  </span>
                </>
              )}
              {(scan as any).search_engine && (
                <>
                  <span>•</span>
                  <span className="capitalize">{(scan as any).search_engine}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Quick KPI Strip */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <div className="px-3 py-1.5 rounded-xl bg-white border border-[#DCE8DC] shadow-2xs text-center">
            <div className="text-[10px] uppercase font-bold text-[#587568] tracking-wider">Avg Rank</div>
            <div className="text-sm font-black text-[#142820]">{avgRank}</div>
          </div>
          <div className="px-3 py-1.5 rounded-xl bg-emerald-50 border border-emerald-200 text-center">
            <div className="text-[10px] uppercase font-bold text-emerald-700 tracking-wider">Top 3 Dominance</div>
            <div className="text-sm font-black text-emerald-800">{top3Pct}% ({top3Count}/{totalPoints})</div>
          </div>
          <div className="px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-center">
            <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Not in Top 20</div>
            <div className="text-sm font-black text-slate-700">{notFoundCount}</div>
          </div>

          {onRescan && (
            <button
              onClick={onRescan}
              disabled={isScanning}
              className="px-3.5 py-2 rounded-xl bg-[#236B4F] hover:bg-[#1B553E] text-white text-xs font-bold transition-all shadow-xs flex items-center gap-1.5 disabled:opacity-50"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
              <span>{isScanning ? 'Scanning...' : 'Rescan'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Warning banner for city-level fallback or scan warning */}
      {(isCityFallback || scan.warning_message) && (
        <div className="px-4 py-2.5 bg-amber-50/90 border-b border-amber-200 text-amber-900 text-xs flex items-center gap-2 font-medium">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>
            {scan.warning_message ||
              "Exact business coordinates were not available. This Geo-Grid is using city-level location and may be less precise."}
          </span>
        </div>
      )}

      {/* ─── Interactive Satellite Map Viewport ─── */}
      <div className="relative w-full h-[540px] bg-slate-900 overflow-hidden">
        {/* Map Container Target */}
        <div ref={mapContainerRef} className="w-full h-full z-0" />

        {/* Top-Left: Map Guidance Badge */}
        <div className="absolute top-3.5 left-3.5 z-[400] bg-white/95 backdrop-blur-md px-3 py-1.5 rounded-xl border border-slate-200/90 shadow-sm text-xs font-semibold text-slate-700 flex items-center gap-2">
          <Navigation className="w-3.5 h-3.5 text-[#236B4F]" />
          <span>Click any GPS pin to inspect node ranking & competitor share</span>
        </div>

        {/* Bottom-Right: Navigation & Zoom Floating Controls */}
        <div className="absolute bottom-3.5 right-3.5 z-[400] flex flex-col gap-1.5 bg-white/95 backdrop-blur-md p-1 rounded-xl border border-slate-200/90 shadow-sm">
          <button
            onClick={handleZoomIn}
            title="Zoom In"
            className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            title="Zoom Out"
            className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <div className="w-full h-px bg-slate-200 my-0.5" />
          <button
            onClick={handleRecenter}
            title="Center Business Location"
            className="w-8 h-8 flex items-center justify-center rounded-lg text-[#236B4F] hover:bg-emerald-50 transition-colors"
          >
            <LocateFixed className="w-4 h-4" />
          </button>
        </div>

        {/* Bottom-Left: Satellite Mode Badge */}
        <div className="absolute bottom-3.5 left-3.5 z-[400] bg-black/60 backdrop-blur-md px-2.5 py-1 rounded-lg border border-white/20 shadow-2xs text-[10px] font-semibold text-white flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Satellite View</span>
        </div>
      </div>

      {/* ─── Ranking Categories Legend ─── */}
      <div className="p-3.5 bg-[#F7FAF7] border-t border-[#EBF2EB] flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3 font-semibold text-slate-600">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Legend:</span>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-md bg-emerald-500 border border-emerald-700 inline-block shadow-2xs" />
            <span>Rank 1–3</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-md bg-blue-500 border border-blue-700 inline-block shadow-2xs" />
            <span>Rank 4–7</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-md bg-amber-400 border border-amber-600 inline-block shadow-2xs" />
            <span>Rank 8–15</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-md bg-rose-500 border border-rose-700 inline-block shadow-2xs" />
            <span>Rank 16+</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-md bg-rose-100 border border-rose-500 inline-block shadow-2xs" />
            <span>Not in Top 20 (NF)</span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 text-slate-500 text-[11px] font-medium">
          <Info className="w-3.5 h-3.5 text-slate-400" />
          <span>Coordinates spaced by {radiusKm} km radius from business center</span>
        </div>
      </div>

      {/* ─── Point Analysis Drawer ─── */}
      {selectedPoint && (
        <PointAnalysisDrawer
          point={selectedPoint}
          onClose={() => handleSelectPoint(null)}
          centerName={centerName}
          keyword={scan.keyword}
          scanId={scan.id}
          projectId={scan.project_id}
        />
      )}
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { MapPin, Navigation, Sparkles, Filter, RotateCw } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { GeoGridScan } from '../types';
import { LocalGridMap } from '../components/rankings/LocalGridMap';
import { LocationPickerModal } from '../components/rankings/LocationPickerModal';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';
import { getErrorMessage } from '../utils/error';

export const LocalGridRankingsView: React.FC = () => {
  const { activeProject } = useProject();
  const [scan, setScan] = useState<GeoGridScan | null>(null);
  const [loading, setLoading] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [isPickerOpen, setIsPickerOpen] = useState(false);

  const fetchScan = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      setScanError(null);
      const resp = await api.get(`/keywords/${activeProject.id}/grid`);
      setScan(resp.data);
    } catch (e: any) {
      console.error('Failed to load grid scan:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScan();
  }, [activeProject?.id]);

  const handleOpenPicker = () => {
    setIsPickerOpen(true);
  };

  const handleStartScanWithLocation = async (params: {
    location_id?: number;
    center_lat?: number;
    center_lng?: number;
    center_name?: string;
    keyword?: string;
    radius_km?: number;
    grid_size?: number;
  }) => {
    if (!activeProject) return;
    try {
      setIsScanning(true);
      setScanError(null);

      const fallbackKeyword = activeProject.primary_category
        ? `${activeProject.primary_category.toLowerCase()} near me`
        : `${activeProject.name} near me`;

      await api.post(`/keywords/${activeProject.id}/grid/rescan`, {
        keyword_id: scan?.keyword_id,
        keyword: params.keyword || scan?.center_name || fallbackKeyword,
        location_id: params.location_id,
        center_lat: params.center_lat,
        center_lng: params.center_lng,
        center_name: params.center_name,
        radius_km: params.radius_km || 7.5,
        grid_size: params.grid_size || 5
      });

      setIsPickerOpen(false);
      await fetchScan();
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

  const initialKeyword = scan?.center_name || (activeProject.primary_category ? `${activeProject.primary_category.toLowerCase()} near me` : `${activeProject.name} near me`);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <MapPin className="w-6 h-6 text-purple-600" />
            <span>5x5 Geo-Grid Rankings Map</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Simulate localized Google Maps search rankings across a 5x5 geographic matrix centered at your canonical business coordinates.
          </p>
        </div>
      </div>

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
      <LocalGridMap scan={scan} onRescan={handleOpenPicker} isScanning={isScanning} />

      {/* Location Picker Modal */}
      <LocationPickerModal
        isOpen={isPickerOpen}
        onClose={() => setIsPickerOpen(false)}
        projectId={activeProject.id}
        onStartScan={handleStartScanWithLocation}
        isScanning={isScanning}
        initialKeyword={initialKeyword}
        initialRadius={scan?.radius_km || 7.5}
        initialGridSize={scan?.grid_size || 5}
      />
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { MapPin, Navigation, Sparkles, Filter, RotateCw } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { GeoGridScan } from '../types';
import { LocalGridMap } from '../components/rankings/LocalGridMap';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const LocalGridRankingsView: React.FC = () => {
  const { activeProject } = useProject();
  const [scan, setScan] = useState<GeoGridScan | null>(null);
  const [loading, setLoading] = useState(false);
  const [isScanning, setIsScanning] = useState(false);

  const fetchScan = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/keywords/${activeProject.id}/grid`);
      setScan(resp.data);
    } catch (e) {
      console.error('Failed to load grid scan:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScan();
  }, [activeProject?.id]);

  const handleRescan = async () => {
    if (!activeProject) return;
    try {
      setIsScanning(true);
      await api.post(`/keywords/${activeProject.id}/grid/rescan`, {
        radius_km: 7.5,
        grid_size: 5
      });
      await fetchScan();
    } catch (e) {
      console.error('Grid rescan failed:', e);
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

      {/* Main Grid Component */}
      <LocalGridMap scan={scan} onRescan={handleRescan} isScanning={isScanning} />
    </div>
  );
};

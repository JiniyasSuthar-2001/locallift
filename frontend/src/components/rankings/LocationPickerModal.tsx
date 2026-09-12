import React, { useState, useEffect } from 'react';
import { Location } from '../../types';
import { MapPin, X, Navigation, CheckCircle2, Plus, AlertCircle } from 'lucide-react';
import api from '../../api/client';
import { getErrorMessage } from '../../utils/error';

interface LocationPickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: number;
  onStartScan: (params: {
    location_id?: number;
    center_lat?: number;
    center_lng?: number;
    center_name?: string;
    keyword?: string;
    radius_km?: number;
    grid_size?: number;
  }) => Promise<void>;
  isScanning: boolean;
  initialKeyword?: string;
  initialRadius?: number;
  initialGridSize?: number;
}

export const LocationPickerModal: React.FC<LocationPickerModalProps> = ({
  isOpen,
  onClose,
  projectId,
  onStartScan,
  isScanning,
  initialKeyword = '',
  initialRadius = 7.5,
  initialGridSize = 5
}) => {
  const [locations, setLocations] = useState<Location[]>([]);
  const [loadingLocations, setLoadingLocations] = useState(false);
  const [selectedLocationId, setSelectedLocationId] = useState<number | null>(null);
  const [isManualMode, setIsManualMode] = useState(false);

  // Form parameters
  const [keyword, setKeyword] = useState(initialKeyword);
  const [radiusKm, setRadiusKm] = useState(initialRadius);
  const [gridSize, setGridSize] = useState(initialGridSize);

  // Manual coordinate inputs
  const [manualName, setManualName] = useState('Custom Coordinates');
  const [manualLat, setManualLat] = useState('');
  const [manualLng, setManualLng] = useState('');

  // Validation error
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && projectId) {
      fetchLocations();
      setKeyword(initialKeyword);
      setRadiusKm(initialRadius);
      setGridSize(initialGridSize);
      setValidationError(null);
    }
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

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

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

      await onStartScan({
        center_lat: latNum,
        center_lng: lngNum,
        center_name: manualName || 'Custom Location',
        keyword,
        radius_km: radiusKm,
        grid_size: gridSize
      });
    } else {
      if (!selectedLocationId) {
        setValidationError('Please select a saved location or switch to manual coordinates.');
        return;
      }
      const selectedLoc = locations.find((l) => l.id === selectedLocationId);

      await onStartScan({
        location_id: selectedLocationId,
        center_name: selectedLoc?.name,
        keyword,
        radius_km: radiusKm,
        grid_size: gridSize
      });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-slate-100 space-y-6 relative overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center space-x-2">
            <div className="w-10 h-10 rounded-2xl bg-purple-100 flex items-center justify-center text-purple-600 font-bold">
              <MapPin className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-black text-slate-900">Run 5x5 Geo-Grid Scan</h2>
              <p className="text-xs text-slate-500">Select business location or enter custom GPS coordinates</p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isScanning}
            className="w-8 h-8 rounded-full bg-slate-100 text-slate-400 hover:text-slate-600 flex items-center justify-center transition-all"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {validationError && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{validationError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Target Keyword */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
              Search Keyword / Query
            </label>
            <input
              type="text"
              required
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="e.g. plumber near me"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-slate-900 text-xs font-medium focus:ring-2 focus:ring-purple-500 focus:outline-none"
            />
          </div>

          {/* Location Mode Toggle */}
          <div className="flex rounded-xl bg-slate-100 p-1 text-xs font-bold">
            <button
              type="button"
              onClick={() => setIsManualMode(false)}
              className={`flex-1 py-2 rounded-lg transition-all ${
                !isManualMode ? 'bg-white text-purple-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Saved Locations ({locations.length})
            </button>
            <button
              type="button"
              onClick={() => setIsManualMode(true)}
              className={`flex-1 py-2 rounded-lg transition-all ${
                isManualMode ? 'bg-white text-purple-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Manual Coordinates
            </button>
          </div>

          {/* Location Selector */}
          {!isManualMode ? (
            <div className="space-y-3 max-h-48 overflow-y-auto pr-1">
              {loadingLocations ? (
                <div className="text-center py-6 text-xs text-slate-400 font-medium">Loading saved locations...</div>
              ) : locations.length === 0 ? (
                <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs font-medium text-center">
                  No saved locations found for this project. Switch to <strong>Manual Coordinates</strong> or add a location in Project Settings.
                </div>
              ) : (
                locations.map((loc) => {
                  const isSelected = selectedLocationId === loc.id;
                  return (
                    <div
                      key={loc.id}
                      onClick={() => setSelectedLocationId(loc.id)}
                      className={`p-3.5 rounded-2xl border transition-all cursor-pointer flex items-center justify-between ${
                        isSelected
                          ? 'border-purple-600 bg-purple-50/50 ring-2 ring-purple-500/20'
                          : 'border-slate-200 hover:border-slate-300 bg-slate-50/50'
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="font-bold text-xs text-slate-900 flex items-center space-x-1.5">
                          <MapPin className="w-3.5 h-3.5 text-purple-600 shrink-0" />
                          <span>{loc.name}</span>
                        </div>
                        <div className="text-[11px] text-slate-500 font-medium">
                          {[loc.address, loc.city, loc.state].filter(Boolean).join(', ') || 'No address specified'}
                        </div>
                        {loc.latitude !== undefined && loc.latitude !== null && (
                          <div className="text-[10px] font-mono text-purple-700 font-semibold">
                            GPS: {loc.latitude.toFixed(4)}, {loc.longitude?.toFixed(4)}
                          </div>
                        )}
                      </div>
                      <div
                        className={`w-5 h-5 rounded-full flex items-center justify-center border transition-all ${
                          isSelected ? 'bg-purple-600 border-purple-600 text-white' : 'border-slate-300 bg-white'
                        }`}
                      >
                        {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          ) : (
            /* Manual Coordinate Input Form */
            <div className="space-y-3 p-3.5 rounded-2xl bg-slate-50 border border-slate-200">
              <div>
                <label className="block text-[11px] font-bold text-slate-600 mb-1">Center Name</label>
                <input
                  type="text"
                  value={manualName}
                  onChange={(e) => setManualName(e.target.value)}
                  placeholder="e.g. Downtown Branch"
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs font-medium focus:ring-2 focus:ring-purple-500 focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Latitude (-90 to 90)</label>
                  <input
                    type="number"
                    step="any"
                    required
                    value={manualLat}
                    onChange={(e) => setManualLat(e.target.value)}
                    placeholder="e.g. 37.7749"
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs font-medium focus:ring-2 focus:ring-purple-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Longitude (-180 to 180)</label>
                  <input
                    type="number"
                    step="any"
                    required
                    value={manualLng}
                    onChange={(e) => setManualLng(e.target.value)}
                    placeholder="e.g. -122.4194"
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
              onClick={onClose}
              disabled={isScanning}
              className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isScanning}
              className="flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md hover:shadow-lg transition-all"
            >
              <Navigation className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
              <span>{isScanning ? 'Scanning Grid...' : 'Run 5x5 Geo-Grid Scan'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

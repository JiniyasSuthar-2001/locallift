import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useProject } from './ProjectContext';
import api from '../api/client';

export interface ScanStageInfo {
  key: string;
  label: string;
  status: 'WAITING' | 'RUNNING' | 'SUCCESS' | 'PARTIAL' | 'FAILED' | 'NOT_CONFIGURED' | 'SKIPPED';
  started_at: string | null;
  completed_at: string | null;
  execution_time_ms?: number | null;
  records_found: number | null;
  records_saved: number | null;
  message: string;
  error: string | null;
  action?: string | null;
}

export interface IntelligenceScanState {
  scan_id: number;
  project_id: number;
  status: 'QUEUED' | 'RUNNING' | 'PARTIAL' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  progress_pct: number;
  current_stage: string;
  current_stage_label: string;
  completed_stages_count: number;
  total_stages_count: number;
  stages: Record<string, ScanStageInfo>;
  results_summary?: Record<string, any>;
  error_summary?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ScanContextType {
  activeScan: IntelligenceScanState | null;
  isScanning: boolean;
  isProgressModalOpen: boolean;
  isCompleteModalOpen: boolean;
  startScan: () => Promise<void>;
  cancelScan: () => Promise<void>;
  closeProgressModal: () => void;
  openProgressModal: () => void;
  closeCompleteModal: () => void;
  refreshAllProjectData: () => Promise<void>;
}

const ScanContext = createContext<ScanContextType | undefined>(undefined);

export const ScanProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { activeProject, refreshDashboard, refreshProjects } = useProject();
  const [activeScan, setActiveScan] = useState<IntelligenceScanState | null>(null);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [isProgressModalOpen, setIsProgressModalOpen] = useState<boolean>(false);
  const [isCompleteModalOpen, setIsCompleteModalOpen] = useState<boolean>(false);

  const activeProjectRef = useRef<number | null>(null);
  activeProjectRef.current = activeProject?.id || null;

  const pollIntervalRef = useRef<any>(null);
  const consecutiveErrorsRef = useRef<number>(0);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  const refreshAllProjectData = useCallback(async () => {
    if (!activeProjectRef.current) return;
    try {
      await Promise.allSettled([
        refreshDashboard(),
        refreshProjects(activeProjectRef.current)
      ]);
    } catch (e) {
      console.error('Error refreshing project data after scan:', e);
    }
  }, [refreshDashboard, refreshProjects]);

  const pollScanStatus = useCallback(async (projectId: number, scanId: number) => {
    try {
      const resp = await api.get(`/projects/${projectId}/intelligence-scan/${scanId}`);
      consecutiveErrorsRef.current = 0;
      const scanData: IntelligenceScanState = resp.data;

      // Ensure response matches currently active project
      if (activeProjectRef.current !== projectId) {
        stopPolling();
        return;
      }

      setActiveScan(scanData);

      const isTerminal = ['COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED'].includes(scanData.status);

      if (isTerminal) {
        setIsScanning(false);
        stopPolling();
        // Transition from progress modal to completion modal on terminal state
        setIsProgressModalOpen(false);
        setIsCompleteModalOpen(true);
        // Refresh project data across LocalLift automatically
        await refreshAllProjectData();
      } else {
        setIsScanning(true);
      }
    } catch (e) {
      consecutiveErrorsRef.current += 1;
      console.warn(`Polling error #${consecutiveErrorsRef.current} for scan #${scanId}:`, e);
      if (consecutiveErrorsRef.current >= 8) {
        console.error(`Aborting scan polling due to persistent network errors for scan #${scanId}`);
        stopPolling();
        setIsScanning(false);
      }
    }
  }, [refreshAllProjectData, stopPolling]);

  const startScan = useCallback(async () => {
    if (!activeProject) return;
    const projId = activeProject.id;
    try {
      setIsProgressModalOpen(true);
      setIsCompleteModalOpen(false);
      setIsScanning(true);

      const resp = await api.post(`/projects/${projId}/intelligence-scan`);
      const scanData: IntelligenceScanState = resp.data;
      setActiveScan(scanData);

      // Start polling
      stopPolling();
      pollIntervalRef.current = setInterval(() => {
        if (activeProjectRef.current === projId) {
          pollScanStatus(projId, scanData.scan_id);
        } else {
          stopPolling();
        }
      }, 1500);
    } catch (e) {
      console.error('Failed to start intelligence scan:', e);
      setIsScanning(false);
      setIsProgressModalOpen(false);
    }
  }, [activeProject, pollScanStatus, stopPolling]);

  const cancelScan = useCallback(async () => {
    if (!activeProject || !activeScan) return;
    const projId = activeProject.id;
    const scanId = activeScan.scan_id;

    // Immediately stop frontend polling to prevent race conditions
    stopPolling();
    setIsScanning(false);

    try {
      const resp = await api.post(`/projects/${projId}/intelligence-scan/${scanId}/cancel`);
      const scanData: IntelligenceScanState = resp.data;
      setActiveScan(scanData);
      setIsProgressModalOpen(false);
      setIsCompleteModalOpen(true);
      await refreshAllProjectData();
    } catch (e) {
      console.error('Failed to cancel intelligence scan:', e);
      // Fallback local update if network error
      setActiveScan(prev => prev ? {
        ...prev,
        status: 'CANCELLED',
        current_stage: 'cancelled',
        current_stage_label: 'Local SEO Scan Cancelled'
      } : null);
      setIsProgressModalOpen(false);
      setIsCompleteModalOpen(true);
    }
  }, [activeProject, activeScan, stopPolling, refreshAllProjectData]);

  // Check latest scan when project changes
  useEffect(() => {
    stopPolling();
    setActiveScan(null);
    setIsScanning(false);
    setIsProgressModalOpen(false);
    setIsCompleteModalOpen(false);

    if (!activeProject?.id) return;
    const projId = activeProject.id;

    api.get(`/projects/${projId}/intelligence-scan/latest`)
      .then(resp => {
        if (activeProjectRef.current !== projId) return;
        if (resp.data?.has_scan && resp.data?.scan) {
          const scanData: IntelligenceScanState = resp.data.scan;
          setActiveScan(scanData);
          if (scanData.status === 'RUNNING' || scanData.status === 'QUEUED') {
            setIsScanning(true);
            setIsProgressModalOpen(true);
            pollIntervalRef.current = setInterval(() => {
              if (activeProjectRef.current === projId) {
                pollScanStatus(projId, scanData.scan_id);
              } else {
                stopPolling();
              }
            }, 1500);
          } else {
            // Completed scan remains available for views, but do not pop open progress modal on load
            setIsScanning(false);
            setIsProgressModalOpen(false);
          }
        }
      })
      .catch(err => {
        console.error('Failed to fetch latest scan for project:', err);
      });

    return () => {
      stopPolling();
    };
  }, [activeProject?.id, pollScanStatus, stopPolling]);

  return (
    <ScanContext.Provider
      value={{
        activeScan,
        isScanning,
        isProgressModalOpen,
        isCompleteModalOpen,
        startScan,
        cancelScan,
        closeProgressModal: () => setIsProgressModalOpen(false),
        openProgressModal: () => setIsProgressModalOpen(true),
        closeCompleteModal: () => setIsCompleteModalOpen(false),
        refreshAllProjectData
      }}
    >
      {children}
    </ScanContext.Provider>
  );
};

export const useProjectScan = () => {
  const context = useContext(ScanContext);
  if (!context) {
    throw new Error('useProjectScan must be used within a ScanProvider');
  }
  return context;
};

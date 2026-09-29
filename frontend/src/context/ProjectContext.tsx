import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { Project, DashboardSummary } from '../types';
import api from '../api/client';
import { useAuth } from './AuthContext';

interface ProjectContextType {
  projects: Project[];
  activeProject: Project | null;
  activeProjectId: number | null;
  organizationId: number | null;
  projectName: string;
  domain: string;
  projectStatus: string;
  location: string;
  isSwitchingProject: boolean;
  switchProject: (proj: Project | null) => Promise<void>;
  setActiveProject: (proj: Project | null) => void;
  dashboard: DashboardSummary | null;
  loading: boolean;
  isDashboardLoading: boolean;
  refreshDashboard: () => Promise<void>;
  refreshProjects: (preferredProjectId?: number) => Promise<Project[]>;
  getProjectSignal: () => AbortSignal | undefined;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProjectState] = useState<Project | null>(null);
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isDashboardLoading, setIsDashboardLoading] = useState<boolean>(false);
  const [isSwitchingProject, setIsSwitchingProject] = useState<boolean>(false);

  // Active project ref to avoid stale closure reads
  const activeProjectRef = useRef<Project | null>(null);
  activeProjectRef.current = activeProject;

  // Active AbortController for project-scoped HTTP cancellation (Part 15)
  const abortControllerRef = useRef<AbortController | null>(null);

  const getProjectSignal = useCallback(() => {
    return abortControllerRef.current?.signal;
  }, []);

  const switchProject = useCallback(async (proj: Project | null) => {
    const oldProject = activeProjectRef.current;
    if (oldProject?.id === proj?.id) {
      return;
    }

    setIsSwitchingProject(true);

    // 1. Cancel in-flight frontend HTTP requests for old project (Part 15)
    if (abortControllerRef.current) {
      try {
        abortControllerRef.current.abort('Project switched');
      } catch (err) {
        // Abort error is normal
      }
    }
    abortControllerRef.current = new AbortController();

    // 2. Clear old project data from local state immediately (Part 32 & 34)
    setDashboard(null);

    // 3. Backend Hard Isolation: Cancel active jobs & scans for old project (Part 3 & 4)
    if (oldProject?.id) {
      try {
        api.post(`/projects/${oldProject.id}/cancel-active-scans`).catch((err) => {
          console.warn(`[Project Isolation] Notice: Could not cancel old scans:`, err);
        });
      } catch (e) {
        // Safe catch
      }
    }

    // 4. Update authoritative active project
    activeProjectRef.current = proj;
    setActiveProjectState(proj);

    // Transition delay to let UI smoothly switch without flash of old data
    setTimeout(() => {
      setIsSwitchingProject(false);
    }, 250);
  }, []);

  const setActiveProject = useCallback((proj: Project | null) => {
    switchProject(proj);
  }, [switchProject]);

  const fetchDashboard = useCallback(async (projectId: number) => {
    if (!projectId) return;
    try {
      setIsDashboardLoading(true);
      const resp = await api.get(`/projects/${projectId}/dashboard`, {
        signal: abortControllerRef.current?.signal
      });
      // Only set dashboard if project didn't change while request was in-flight
      if (activeProjectRef.current?.id === projectId) {
        setDashboard(resp.data);
      }
    } catch (e: any) {
      if (e?.name !== 'CanceledError' && e?.code !== 'ERR_CANCELED') {
        if (activeProjectRef.current?.id === projectId) {
          console.error(`Failed to load dashboard for project ${projectId}:`, e);
        }
      }
    } finally {
      if (activeProjectRef.current?.id === projectId) {
        setIsDashboardLoading(false);
      }
    }
  }, []);

  const fetchProjects = useCallback(async (preferredProjectId?: number): Promise<Project[]> => {
    if (!isAuthenticated) {
      setProjects([]);
      setActiveProjectState(null);
      setDashboard(null);
      setLoading(false);
      return [];
    }

    try {
      setLoading(true);
      const resp = await api.get('/projects');
      const list: Project[] = Array.isArray(resp.data) ? resp.data : [];
      setProjects(list);

      if (list.length > 0) {
        const targetId = preferredProjectId || activeProjectRef.current?.id;
        const matched = targetId ? list.find(p => p.id === targetId) : null;
        const selected = matched || list[0];
        activeProjectRef.current = selected;
        setActiveProjectState(selected);
      } else {
        activeProjectRef.current = null;
        setActiveProjectState(null);
        setDashboard(null);
      }
      return list;
    } catch (e) {
      console.error('Failed to load projects:', e);
      return [];
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  // Initial load when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      fetchProjects();
    } else {
      setProjects([]);
      activeProjectRef.current = null;
      setActiveProjectState(null);
      setDashboard(null);
      setLoading(false);
    }
  }, [isAuthenticated, fetchProjects]);

  // Fetch dashboard whenever active project changes
  useEffect(() => {
    if (activeProject?.id) {
      fetchDashboard(activeProject.id);
    } else {
      setDashboard(null);
    }
  }, [activeProject?.id, fetchDashboard]);

  const refreshDashboard = async () => {
    if (activeProject?.id) {
      await fetchDashboard(activeProject.id);
    }
  };

  const refreshProjects = async (preferredProjectId?: number): Promise<Project[]> => {
    return await fetchProjects(preferredProjectId);
  };

  // Derive location string safely
  const loc = activeProject?.locations && activeProject.locations.length > 0 ? activeProject.locations[0] : null;
  const locationString = loc
    ? [loc.city, loc.state, loc.country].filter(Boolean).join(', ')
    : (activeProject?.country || 'Location not set');

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProject,
        activeProjectId: activeProject?.id || null,
        organizationId: activeProject?.organization_id || null,
        projectName: activeProject?.name || '',
        domain: activeProject?.domain || '',
        projectStatus: activeProject?.status || 'active',
        location: locationString,
        isSwitchingProject,
        switchProject,
        setActiveProject,
        dashboard,
        loading,
        isDashboardLoading,
        refreshDashboard,
        refreshProjects,
        getProjectSignal
      }}
    >
      {children}
      {/* Lightweight Project Switch Overlay (Part 34) */}
      {isSwitchingProject && (
        <div className="fixed inset-0 z-50 bg-white/60 backdrop-blur-xs flex items-center justify-center pointer-events-none transition-all duration-150">
          <div className="px-5 py-3 rounded-2xl bg-white border border-[#DCE8DC] shadow-xl flex items-center space-x-3 text-xs font-bold text-[#142820]">
            <div className="w-4 h-4 border-2 border-[#236B4F] border-t-transparent rounded-full animate-spin" />
            <span>Switching project...</span>
          </div>
        </div>
      )}
    </ProjectContext.Provider>
  );
};

export const useProject = () => {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
};

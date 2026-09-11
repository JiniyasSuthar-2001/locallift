import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { Project, DashboardSummary } from '../types';
import api from '../api/client';
import { useAuth } from './AuthContext';

interface ProjectContextType {
  projects: Project[];
  activeProject: Project | null;
  setActiveProject: (proj: Project | null) => void;
  dashboard: DashboardSummary | null;
  loading: boolean;
  isDashboardLoading: boolean;
  refreshDashboard: () => Promise<void>;
  refreshProjects: (preferredProjectId?: number) => Promise<Project[]>;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProjectState] = useState<Project | null>(null);
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isDashboardLoading, setIsDashboardLoading] = useState<boolean>(false);

  // Active project ref to avoid stale closure reads
  const activeProjectRef = useRef<Project | null>(null);
  activeProjectRef.current = activeProject;

  const setActiveProject = useCallback((proj: Project | null) => {
    if (activeProjectRef.current?.id !== proj?.id) {
      setDashboard(null);
    }
    activeProjectRef.current = proj;
    setActiveProjectState(proj);
  }, []);

  const fetchDashboard = useCallback(async (projectId: number) => {
    if (!projectId) return;
    try {
      setIsDashboardLoading(true);
      const resp = await api.get(`/projects/${projectId}/dashboard`);
      // Only set dashboard if project didn't change while request was in-flight
      if (activeProjectRef.current?.id === projectId) {
        setDashboard(resp.data);
      }
    } catch (e: any) {
      if (activeProjectRef.current?.id === projectId) {
        console.error(`Failed to load dashboard for project ${projectId}:`, e);
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
      setActiveProject(null);
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
        // Retain specified preferred project, or existing active project, or select first
        const targetId = preferredProjectId || activeProjectRef.current?.id;
        const matched = targetId ? list.find(p => p.id === targetId) : null;
        const selected = matched || list[0];
        setActiveProject(selected);
      } else {
        setActiveProject(null);
        setDashboard(null);
      }
      return list;
    } catch (e) {
      console.error('Failed to load projects:', e);
      return [];
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, setActiveProject]);

  // Initial load when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      fetchProjects();
    } else {
      setProjects([]);
      setActiveProject(null);
      setDashboard(null);
      setLoading(false);
    }
  }, [isAuthenticated, fetchProjects, setActiveProject]);

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

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProject,
        setActiveProject,
        dashboard,
        loading,
        isDashboardLoading,
        refreshDashboard,
        refreshProjects
      }}
    >
      {children}
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

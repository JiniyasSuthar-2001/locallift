import React, { createContext, useContext, useState, useEffect } from 'react';
import { Project, DashboardSummary } from '../types';
import api from '../api/client';
import { useAuth } from './AuthContext';

interface ProjectContextType {
  projects: Project[];
  activeProject: Project | null;
  setActiveProject: (proj: Project) => void;
  dashboard: DashboardSummary | null;
  loading: boolean;
  refreshDashboard: () => Promise<void>;
  refreshProjects: () => Promise<void>;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchProjects = async () => {
    if (!isAuthenticated) return;
    try {
      setLoading(true);
      const resp = await api.get('/projects');
      setProjects(resp.data);
      if (resp.data.length > 0) {
        // Retain current selection if valid or select first
        const found = resp.data.find((p: Project) => p.id === activeProject?.id);
        const current = found || resp.data[0];
        setActiveProject(current);
        await fetchDashboard(current.id);
      }
    } catch (e) {
      console.error('Failed to load projects:', e);
    } finally {
      setLoading(false);
    }
  };

  const fetchDashboard = async (projectId: number) => {
    try {
      const resp = await api.get(`/projects/${projectId}/dashboard`);
      setDashboard(resp.data);
    } catch (e) {
      console.error('Failed to load dashboard:', e);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchProjects();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (activeProject) {
      fetchDashboard(activeProject.id);
    }
  }, [activeProject?.id]);

  const refreshDashboard = async () => {
    if (activeProject) {
      await fetchDashboard(activeProject.id);
    }
  };

  const refreshProjects = async () => {
    await fetchProjects();
  };

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProject,
        setActiveProject,
        dashboard,
        loading,
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

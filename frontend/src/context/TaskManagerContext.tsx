import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useProject } from './ProjectContext';
import { CheckCircle2, AlertTriangle, X, ChevronRight, Activity, XCircle } from 'lucide-react';

export type TaskStatus =
  | 'QUEUED'
  | 'RUNNING'
  | 'COMPLETED'
  | 'COMPLETED_WITH_ERRORS'
  | 'FAILED'
  | 'CANCEL_REQUESTED'
  | 'CANCELLED'
  | 'EXPIRED';

export interface ScanTask {
  id: number;
  project_id: number;
  project_name: string;
  job_type: 'keyword_rank' | 'geo_grid' | 'citation_discovery' | 'website_audit' | 'intelligence_scan';
  status: TaskStatus;
  progress: number; // 0 to 100
  total: number;
  processed: number;
  successful: number;
  failed: number;
  not_found: number;
  errors: number;
  current_stage: string;
  started_at?: string;
  completed_at?: string;
  isBackground?: boolean;
}

interface TaskManagerContextType {
  tasks: ScanTask[];
  activeTasks: ScanTask[];
  activeCount: number;
  completedModalTask: ScanTask | null;
  closeCompletedModal: () => void;
  runInBackground: (taskId: number) => void;
  cancelTask: (taskId: number, jobType?: string) => Promise<void>;
  notifyJobCreated: (task: ScanTask) => void;
  refreshTasks: () => Promise<void>;
}

const TaskManagerContext = createContext<TaskManagerContextType | undefined>(undefined);

export const TaskManagerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { activeProject } = useProject();
  const [tasks, setTasks] = useState<ScanTask[]>([]);
  const [completedModalTask, setCompletedModalTask] = useState<ScanTask | null>(null);
  const prevStatusesRef = useRef<Map<number, TaskStatus>>(new Map());
  const activeProjectIdRef = useRef<number | null>(null);
  activeProjectIdRef.current = activeProject?.id || null;

  // Track previous statuses to detect when a background task completes
  const updateTasksAndCheckCompletions = useCallback((incomingTasks: ScanTask[]) => {
    setTasks(incomingTasks);

    incomingTasks.forEach((task) => {
      const prevStatus = prevStatusesRef.current.get(task.id);
      if (
        (prevStatus === 'RUNNING' || prevStatus === 'QUEUED') &&
        (task.status === 'COMPLETED' || task.status === 'COMPLETED_WITH_ERRORS')
      ) {
        // Trigger Global Completion Popup (Part 11)
        setCompletedModalTask(task);
      }
      prevStatusesRef.current.set(task.id, task.status);
    });
  }, []);

  const refreshTasks = useCallback(async () => {
    const currentProjectId = activeProjectIdRef.current;
    if (!currentProjectId) {
      setTasks([]);
      return;
    }

    try {
      // 1. Fetch ScanJobs for current project
      const jobsResp = await api.get(`/projects/${currentProjectId}/jobs?limit=10`);
      const backendJobs = Array.isArray(jobsResp.data) ? jobsResp.data : [];

      const parsedTasks: ScanTask[] = backendJobs.map((j: any) => {
        const total = j.total_items || 1;
        const processed = j.processed_items || 0;
        const pct = Math.min(100, Math.round((processed / total) * 100));
        return {
          id: j.id,
          project_id: j.project_id,
          project_name: activeProject?.name || `Project #${j.project_id}`,
          job_type: j.job_type,
          status: j.status as TaskStatus,
          progress: pct,
          total: j.total_items || 0,
          processed: j.processed_items || 0,
          successful: j.successful_items || 0,
          failed: j.failed_items || 0,
          not_found: j.not_found_items || 0,
          errors: j.error_count || 0,
          current_stage: j.current_stage || '',
          started_at: j.started_at,
          completed_at: j.completed_at,
        };
      });

      // 2. Fetch active Geo-Grid scans if any
      try {
        const gridResp = await api.get(`/projects/${currentProjectId}/grid/scans?limit=3`);
        const grids = Array.isArray(gridResp.data) ? gridResp.data : [];
        grids.forEach((g: any) => {
          if (['running', 'queued', 'in_progress'].includes(g.scan_status)) {
            const total = g.total_points || 25;
            const processed = g.completed_points || 0;
            parsedTasks.unshift({
              id: 900000 + g.id,
              project_id: g.project_id,
              project_name: activeProject?.name || `Project #${g.project_id}`,
              job_type: 'geo_grid',
              status: 'RUNNING',
              progress: Math.min(100, Math.round((processed / total) * 100)),
              total,
              processed,
              successful: g.ranking_found_points || 0,
              failed: (g.provider_error_points || 0) + (g.timeout_points || 0),
              not_found: g.not_found_points || 0,
              errors: (g.provider_error_points || 0) + (g.timeout_points || 0),
              current_stage: `Scanning point ${processed}/${total}`,
              started_at: g.scanned_at,
            });
          }
        });
      } catch {
        // Ignore if grid scans endpoint is not queried
      }

      // Verify that the responses belong to the current active project
      if (activeProjectIdRef.current === currentProjectId) {
        updateTasksAndCheckCompletions(parsedTasks);
      }
    } catch (e) {
      console.warn('Failed to poll background tasks:', e);
    }
  }, [activeProject?.name, updateTasksAndCheckCompletions]);

  // Global Single Polling Timer (Part 13)
  useEffect(() => {
    let intervalId: any = null;

    // Check if there are active tasks in state
    const hasActive = tasks.some((t) => t.status === 'RUNNING' || t.status === 'QUEUED');

    // Always poll once on project load, and poll every 2.5s if active tasks exist
    refreshTasks();

    if (hasActive && activeProject) {
      intervalId = setInterval(() => {
        refreshTasks();
      }, 2500);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [activeProject?.id, tasks.some((t) => t.status === 'RUNNING' || t.status === 'QUEUED'), refreshTasks]);

  const notifyJobCreated = useCallback((task: ScanTask) => {
    setTasks((prev) => [task, ...prev.filter((t) => t.id !== task.id)]);
    prevStatusesRef.current.set(task.id, task.status);
  }, []);

  const runInBackground = useCallback((taskId: number) => {
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, isBackground: true } : t))
    );
  }, []);

  const cancelTask = useCallback(async (taskId: number, jobType?: string) => {
    if (!activeProject) return;
    try {
      if (taskId >= 900000 || jobType === 'geo_grid') {
        const rawGridId = taskId >= 900000 ? taskId - 900000 : taskId;
        await api.post(`/projects/${activeProject.id}/grid/scans/${rawGridId}/cancel`);
      } else {
        await api.post(`/projects/${activeProject.id}/jobs/${taskId}/cancel`);
      }
      setTasks((prev) =>
        prev.map((t) =>
          t.id === taskId
            ? { ...t, status: 'CANCEL_REQUESTED' as TaskStatus, current_stage: 'Cancellation requested...' }
            : t
        )
      );
    } catch (e) {
      console.error(`Failed to cancel task ${taskId}:`, e);
    }
  }, [activeProject]);

  const closeCompletedModal = useCallback(() => {
    setCompletedModalTask(null);
  }, []);

  const activeTasks = tasks.filter(
    (t) => t.status === 'RUNNING' || t.status === 'QUEUED' || t.status === 'CANCEL_REQUESTED'
  );

  return (
    <TaskManagerContext.Provider
      value={{
        tasks,
        activeTasks,
        activeCount: activeTasks.length,
        completedModalTask,
        closeCompletedModal,
        runInBackground,
        cancelTask,
        notifyJobCreated,
        refreshTasks,
      }}
    >
      {children}
      {/* Global Completion Popup (Part 11) */}
      {completedModalTask && (
        <GlobalScanCompleteModal
          task={completedModalTask}
          onClose={closeCompletedModal}
        />
      )}
    </TaskManagerContext.Provider>
  );
};

export const useTaskManager = () => {
  const context = useContext(TaskManagerContext);
  if (!context) {
    throw new Error('useTaskManager must be used within a TaskManagerProvider');
  }
  return context;
};

// ─── Global Scan Complete Modal (Part 11) ──────────────────────────────────

interface ModalProps {
  task: ScanTask;
  onClose: () => void;
}

export const GlobalScanCompleteModal: React.FC<ModalProps> = ({ task, onClose }) => {
  const navigate = useNavigate();
  const isErrors = task.status === 'COMPLETED_WITH_ERRORS' || task.errors > 0;
  const isKeyword = task.job_type === 'keyword_rank';
  const isGrid = task.job_type === 'geo_grid';

  const title = isKeyword
    ? 'Keyword Scan Complete'
    : isGrid
    ? 'Geo-Grid Scan Complete'
    : 'Background Scan Complete';

  const viewUrl = isKeyword
    ? '/rankings/keywords'
    : isGrid
    ? '/rankings/grid'
    : '/';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/40 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl border border-[#DCE8DC] shadow-2xl max-w-md w-full p-6 space-y-5 animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                isErrors ? 'bg-amber-50 text-amber-600' : 'bg-emerald-50 text-emerald-600'
              }`}
            >
              {isErrors ? <AlertTriangle className="w-5 h-5" /> : <CheckCircle2 className="w-5 h-5" />}
            </div>
            <div>
              <h3 className="text-base font-black text-[#142820]">{title}</h3>
              <p className="text-xs text-[#587568] font-medium">Project: {task.project_name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Breakdown Stats */}
        <div className="rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] p-3.5 space-y-2">
          <div className="text-[11px] font-bold text-[#142820] uppercase tracking-wider">
            Scan Results Summary
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2 rounded-lg bg-white border border-[#EBF2EB]">
              <span className="text-[#587568] block text-[10px] uppercase font-bold">Total Scanned</span>
              <span className="text-sm font-black text-[#142820]">
                {task.processed} / {task.total}
              </span>
            </div>
            <div className="p-2 rounded-lg bg-white border border-[#EBF2EB]">
              <span className="text-emerald-700 block text-[10px] uppercase font-bold">
                {isKeyword ? 'Rankings Found' : 'Successful Points'}
              </span>
              <span className="text-sm font-black text-emerald-800">{task.successful}</span>
            </div>
            <div className="p-2 rounded-lg bg-white border border-[#EBF2EB]">
              <span className="text-slate-600 block text-[10px] uppercase font-bold">Not Found</span>
              <span className="text-sm font-black text-slate-700">{task.not_found}</span>
            </div>
            <div className="p-2 rounded-lg bg-white border border-[#EBF2EB]">
              <span className="text-rose-700 block text-[10px] uppercase font-bold">Errors / Timeouts</span>
              <span className="text-sm font-black text-rose-800">{task.errors}</span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end space-x-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-bold text-[#587568] hover:bg-slate-100 transition-colors"
          >
            Close
          </button>
          <button
            onClick={() => {
              onClose();
              navigate(viewUrl);
            }}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-[#236B4F] hover:bg-[#1D5A42] transition-colors shadow-sm"
          >
            <span>{isKeyword ? 'View Results' : isGrid ? 'View Geo-Grid' : 'View Results'}</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};

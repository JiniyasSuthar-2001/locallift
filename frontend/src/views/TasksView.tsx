import React, { useState, useEffect } from 'react';
import {
  CheckSquare,
  Plus,
  Filter,
  Calendar,
  Clock,
  CheckCircle2,
  Trash2,
  Sparkles
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { SEOTask } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const TasksView: React.FC = () => {
  const { activeProject, refreshDashboard } = useProject();
  const [tasks, setTasks] = useState<SEOTask[]>([]);
  const [viewMode, setViewMode] = useState<'board' | 'list'>('board');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('Technical SEO');
  const [priority, setPriority] = useState('medium');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchTasks = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/tasks/${activeProject.id}`);
      setTasks(resp.data || []);
    } catch (e) {
      console.error('Failed to load tasks:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [activeProject?.id]);

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !title.trim()) return;
    try {
      await api.post('/tasks', {
        project_id: activeProject.id,
        title: title.trim(),
        category,
        priority,
        description,
        status: 'open'
      });
      setTitle('');
      setDescription('');
      setIsModalOpen(false);
      await fetchTasks();
      await refreshDashboard();
    } catch (err) {
      console.error('Failed to create task:', err);
    }
  };

  const handleStatusChange = async (taskId: number, newStatus: string) => {
    try {
      await api.patch(`/tasks/${taskId}`, { status: newStatus });
      await fetchTasks();
      await refreshDashboard();
    } catch (e) {
      console.error('Failed to update task status:', e);
    }
  };

  const columns = [
    { id: 'open', title: 'Open Backlog' },
    { id: 'in_progress', title: 'In Progress' },
    { id: 'waiting', title: 'Waiting / Review' },
    { id: 'completed', title: 'Completed' }
  ];

  if (!activeProject) {
    return (
      <EmptyState
        icon={CheckSquare}
        badge="SEO Tasks"
        title="Select a Project"
        description="Select a business project to manage technical remediation tasks, schema updates, and content optimization workflows."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <CheckSquare className="w-6 h-6 text-purple-600" />
            <span>SEO Task Board & Operations</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Convert detected audit issues into trackable optimization tasks and monitor implementation for {activeProject.domain}.
          </p>
        </div>

        <div className="flex items-center space-x-3 self-start">
          <div className="bg-slate-100 p-1 rounded-xl flex text-xs font-bold border border-slate-200">
            <button
              onClick={() => setViewMode('board')}
              className={`px-3 py-1.5 rounded-lg transition-all ${viewMode === 'board' ? 'bg-white text-purple-900 shadow-sm border border-slate-200' : 'text-slate-600'}`}
            >
              Kanban Board
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 rounded-lg transition-all ${viewMode === 'list' ? 'bg-white text-purple-900 shadow-sm border border-slate-200' : 'text-slate-600'}`}
            >
              List View
            </button>
          </div>

          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center space-x-1.5 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Create Task</span>
          </button>
        </div>
      </div>

      {/* Kanban Board View */}
      {viewMode === 'board' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 items-start">
          {columns.map((col) => {
            const colTasks = tasks.filter((t) => t.status === col.id);
            return (
              <div
                key={col.id}
                className="card-vibrant p-4 space-y-3 min-h-[420px]"
              >
                <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                  <span className="text-xs font-black text-slate-900 uppercase tracking-wider">
                    {col.title}
                  </span>
                  <span className="text-xs font-black px-2 py-0.5 rounded-full bg-purple-50 text-purple-800 border border-purple-200">
                    {colTasks.length}
                  </span>
                </div>

                <div className="space-y-3">
                  {colTasks.map((t) => (
                    <div
                      key={t.id}
                      className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/60 hover:border-purple-300 hover:bg-white transition-all space-y-2 shadow-sm"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-[10px] uppercase font-bold text-slate-500">
                          {t.category}
                        </span>
                        <StatusBadge status={t.priority} />
                      </div>

                      <h4 className="text-xs font-extrabold text-slate-900 leading-snug">{t.title}</h4>

                      {t.description && (
                        <p className="text-[11px] text-slate-600 line-clamp-2 leading-relaxed font-medium">
                          {t.description}
                        </p>
                      )}

                      <div className="pt-2 border-t border-slate-200 flex items-center justify-between text-[11px]">
                        <select
                          value={t.status}
                          onChange={(e) => handleStatusChange(t.id, e.target.value)}
                          className="bg-white border border-slate-200 text-slate-800 font-bold text-[10px] rounded-lg px-2 py-1 focus:outline-none cursor-pointer"
                        >
                          <option value="open">Open</option>
                          <option value="in_progress">In Progress</option>
                          <option value="waiting">Waiting</option>
                          <option value="completed">Completed</option>
                        </select>

                        {t.due_date && (
                          <span className="text-slate-500 flex items-center font-mono text-[10px]">
                            <Clock className="w-3 h-3 mr-1 text-slate-400" />
                            {new Date(t.due_date).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                  {colTasks.length === 0 && (
                    <div className="text-center py-12 text-xs text-slate-400 border border-dashed border-slate-200 rounded-xl font-medium">
                      No tasks in this lane
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* List View */}
      {viewMode === 'list' && (
        <div className="card-vibrant overflow-hidden">
          {tasks.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                  <tr>
                    <th className="p-3.5">Task Title</th>
                    <th className="p-3.5">Category</th>
                    <th className="p-3.5">Priority</th>
                    <th className="p-3.5">Status</th>
                    <th className="p-3.5">Due Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-sans">
                  {tasks.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="p-3.5 font-bold text-slate-900 max-w-sm truncate">{t.title}</td>
                      <td className="p-3.5 text-slate-600">{t.category}</td>
                      <td className="p-3.5">
                        <StatusBadge status={t.priority} />
                      </td>
                      <td className="p-3.5">
                        <StatusBadge status={t.status} />
                      </td>
                      <td className="p-3.5 text-slate-500 font-mono">
                        {t.due_date ? new Date(t.due_date).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              icon={CheckSquare}
              badge="No Tasks"
              title="No SEO Tasks Created"
              description="Convert detected problems into actionable tasks to assign deadlines and monitor improvements."
              actionText="Create First Task"
              onAction={() => setIsModalOpen(true)}
            />
          )}
        </div>
      )}

      {/* Create Task Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl border border-slate-200">
            <h3 className="text-base font-black text-slate-900">Create New SEO Task</h3>
            <form onSubmit={handleCreateTask} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-700 block mb-1 font-bold">Task Title</label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Implement LocalBusiness Schema on /locations"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="text-slate-700 block mb-1 font-bold">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium cursor-pointer"
                >
                  <option>Technical SEO</option>
                  <option>On-Page SEO</option>
                  <option>Schema & Structured Data</option>
                  <option>Citations & NAP</option>
                  <option>Google Business Profile</option>
                  <option>Content & Growth</option>
                </select>
              </div>

              <div>
                <label className="text-slate-700 block mb-1 font-bold">Priority</label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium cursor-pointer"
                >
                  <option value="high">High Priority</option>
                  <option value="medium">Medium Priority</option>
                  <option value="low">Low Priority</option>
                </select>
              </div>

              <div>
                <label className="text-slate-700 block mb-1 font-bold">Description / Notes</label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Specific optimization instructions or code snippets..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 font-bold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg btn-vibrant-primary text-white font-bold"
                >
                  Save Task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  FolderKanban,
  Plus,
  Search,
  Globe,
  MapPin,
  Users2,
  ExternalLink,
  BarChart2,
  Edit2,
  Archive,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Building2,
  Sparkles,
  RefreshCw,
  FolderOpen
} from 'lucide-react';
import api from '../api/client';
import { useProject } from '../context/ProjectContext';
import { getErrorMessage } from '../utils/error';
import { Project, BusinessCategory } from '../types';

export const MyProjectsView: React.FC = () => {
  const navigate = useNavigate();
  const { projects, activeProject, setActiveProject, refreshProjects } = useProject();

  const [loading, setLoading] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'archived'>('all');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Create Project Modal State
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newName, setNewName] = useState<string>('');
  const [newDomain, setNewDomain] = useState<string>('');
  const [newCategory, setNewCategory] = useState<string>('Local Contractor / Service');
  const [newCity, setNewCity] = useState<string>('');
  const [newState, setNewState] = useState<string>('');
  const [newPhone, setNewPhone] = useState<string>('');
  const [categorySuggestions, setCategorySuggestions] = useState<BusinessCategory[]>([]);
  const [creating, setCreating] = useState<boolean>(false);

  // Edit Project Modal State
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [editName, setEditName] = useState<string>('');
  const [editDomain, setEditDomain] = useState<string>('');
  const [editCategory, setEditCategory] = useState<string>('');
  const [savingEdit, setSavingEdit] = useState<boolean>(false);

  // Load category suggestions for autocomplete
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const res = await api.get<{ items: BusinessCategory[] }>('/projects/categories?popular_only=true&limit=20');
        setCategorySuggestions(res.data.items);
      } catch (e) {
        // Fallback silently
      }
    };
    fetchCategories();
  }, []);

  const handleOpenDashboard = (project: Project) => {
    setActiveProject(project);
    navigate('/');
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newDomain.trim()) return;
    setCreating(true);
    setErrorMsg(null);
    try {
      const cleanDomain = newDomain.trim().replace(/^https?:\/\//, '').replace(/\/+$/, '');
      const res = await api.post<Project>('/projects', {
        name: newName.trim(),
        domain: cleanDomain,
        primary_category: newCategory,
        country: 'United States',
        location: newCity ? {
          name: `${newName.trim()} Primary Location`,
          city: newCity.trim(),
          state: newState.trim() || undefined,
          phone: newPhone.trim() || undefined,
          country: 'United States'
        } : undefined
      });

      setSuccessMsg(`Project "${res.data.name}" created successfully.`);
      setShowCreateModal(false);
      setNewName('');
      setNewDomain('');
      setNewCity('');
      setNewState('');
      setNewPhone('');
      await refreshProjects(res.data.id);
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to create project.'));
    } finally {
      setCreating(false);
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingProject) return;
    setSavingEdit(true);
    setErrorMsg(null);
    try {
      await api.put(`/projects/${editingProject.id}`, {
        name: editName.trim(),
        domain: editDomain.trim().replace(/^https?:\/\//, '').replace(/\/+$/, ''),
        primary_category: editCategory.trim()
      });
      setSuccessMsg('Project updated successfully.');
      setEditingProject(null);
      await refreshProjects(editingProject.id);
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to update project.'));
    } finally {
      setSavingEdit(false);
    }
  };

  const handleToggleArchive = async (project: Project) => {
    const willArchive = !project.is_archived;
    try {
      await api.put(`/projects/${project.id}`, {
        is_archived: willArchive,
        status: willArchive ? 'archived' : 'active'
      });
      setSuccessMsg(willArchive ? `Archived "${project.name}".` : `Restored "${project.name}".`);
      await refreshProjects(project.id);
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to update archive status.'));
    }
  };

  // Filter projects by search and status
  const filteredProjects = projects.filter((p) => {
    const matchesSearch =
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.domain.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.primary_category.toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;
    if (statusFilter === 'active') return !p.is_archived;
    if (statusFilter === 'archived') return !!p.is_archived;
    return true;
  });

  return (
    <div className="max-w-6xl space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2.5">
            <FolderKanban className="w-6 h-6 text-purple-600" />
            <span>My Projects</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage, collaborate, and assign teams to the local SEO projects within your organization scope.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="px-5 py-2.5 btn-vibrant-primary text-xs font-bold rounded-xl shadow-md transition-all flex items-center space-x-2 shrink-0"
        >
          <Plus className="w-4 h-4" />
          <span>Create Project</span>
        </button>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-2 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span className="flex-1">{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-400 hover:text-rose-600 font-bold">✕</button>
        </div>
      )}
      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center space-x-2 text-xs text-emerald-800">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
          <span className="flex-1">{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700 font-bold">✕</button>
        </div>
      )}

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-3.5 border border-slate-200/80 rounded-2xl shadow-xs">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search projects by name, domain, or category..."
            className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
          />
        </div>

        <div className="flex items-center space-x-1 text-xs font-bold">
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              statusFilter === 'all'
                ? 'bg-purple-100 text-purple-800 font-black'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            All ({projects.length})
          </button>
          <button
            onClick={() => setStatusFilter('active')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              statusFilter === 'active'
                ? 'bg-purple-100 text-purple-800 font-black'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            Active ({projects.filter((p) => !p.is_archived).length})
          </button>
          <button
            onClick={() => setStatusFilter('archived')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              statusFilter === 'archived'
                ? 'bg-purple-100 text-purple-800 font-black'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            Archived ({projects.filter((p) => p.is_archived).length})
          </button>
        </div>
      </div>

      {/* Projects Grid */}
      {filteredProjects.length === 0 ? (
        <div className="text-center py-16 bg-white border border-dashed border-slate-200 rounded-2xl space-y-3">
          <FolderKanban className="w-8 h-8 text-slate-400 mx-auto" />
          <div className="text-sm font-bold text-slate-700">No Projects Found</div>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            {searchQuery
              ? `No projects matching "${searchQuery}".`
              : 'Create your first local SEO project to get started.'}
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 btn-vibrant-primary text-xs font-bold rounded-xl inline-flex items-center space-x-1.5"
          >
            <Plus className="w-4 h-4" />
            <span>Create New Project</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredProjects.map((project) => {
            const isActiveInContext = activeProject?.id === project.id;
            const teamSeats = project.team_member_count || 1;

            return (
              <div
                key={project.id}
                className={`card-vibrant p-5 border rounded-2xl bg-white shadow-xs hover:shadow-md transition-all flex flex-col justify-between space-y-4 ${
                  isActiveInContext
                    ? 'border-purple-400 ring-2 ring-purple-100'
                    : 'border-slate-200/80 hover:border-purple-200'
                }`}
              >
                {/* Card Top */}
                <div className="space-y-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <h3 className="text-sm font-black text-slate-900 truncate">{project.name}</h3>
                        {isActiveInContext && (
                          <span className="text-[9px] font-black px-1.5 py-0.2 rounded-md bg-purple-600 text-white shrink-0">
                            Active
                          </span>
                        )}
                      </div>
                      <a
                        href={`https://${project.domain}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-purple-600 hover:underline flex items-center space-x-1 mt-0.5 truncate"
                      >
                        <Globe className="w-3 h-3 text-slate-400 shrink-0" />
                        <span className="truncate">{project.domain}</span>
                        <ExternalLink className="w-2.5 h-2.5 shrink-0 opacity-60" />
                      </a>
                    </div>

                    <span
                      className={`text-[9px] font-bold px-2 py-0.5 rounded-md shrink-0 ${
                        project.is_archived
                          ? 'bg-slate-100 text-slate-600'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      }`}
                    >
                      {project.is_archived ? 'Archived' : 'Active'}
                    </span>
                  </div>

                  <div className="flex items-center space-x-2 text-[11px] text-slate-500">
                    <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 font-medium truncate">
                      {project.primary_category}
                    </span>
                  </div>

                  {project.locations && project.locations.length > 0 && (
                    <div className="flex items-center space-x-1.5 text-[11px] text-slate-400">
                      <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                      <span className="truncate">
                        {project.locations[0].city || 'Main City'}, {project.locations[0].state || 'US'}
                      </span>
                    </div>
                  )}
                </div>

                {/* Card Middle: Team badge */}
                <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                  <Link
                    to={`/projects/${project.id}#team`}
                    className="flex items-center space-x-1.5 text-slate-600 hover:text-purple-600 font-bold transition-colors"
                  >
                    <Users2 className="w-3.5 h-3.5 text-purple-600" />
                    <span>{teamSeats} / 3 Team Members</span>
                  </Link>

                  <div className="text-[11px] font-bold text-slate-400">
                    Score: {project.health_score !== null && project.health_score !== undefined ? (
                      <><strong className="text-slate-800">{project.health_score}</strong>/100</>
                    ) : (
                      <span className="text-slate-500 font-medium">Not yet calculated</span>
                    )}
                  </div>
                </div>

                {/* Card Footer Actions */}
                <div className="pt-2 border-t border-slate-100 flex items-center justify-between gap-2">
                  <button
                    onClick={() => handleOpenDashboard(project)}
                    className="flex-1 py-2 btn-vibrant-primary rounded-xl text-xs font-bold shadow-xs transition-all flex items-center justify-center space-x-1.5"
                  >
                    <BarChart2 className="w-3.5 h-3.5" />
                    <span>Dashboard</span>
                  </button>

                  <Link
                    to={`/projects/${project.id}`}
                    className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-all"
                    title="Project Details & Team"
                  >
                    Details
                  </Link>

                  <button
                    onClick={() => {
                      setEditingProject(project);
                      setEditName(project.name);
                      setEditDomain(project.domain);
                      setEditCategory(project.primary_category);
                    }}
                    className="p-2 text-slate-400 hover:text-purple-600 hover:bg-purple-50 rounded-xl transition-all"
                    title="Edit Project"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>

                  <button
                    onClick={() => handleToggleArchive(project)}
                    className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-all"
                    title={project.is_archived ? 'Restore' : 'Archive'}
                  >
                    <Archive className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* MODAL: Create Project */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-7 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-black text-slate-900 flex items-center space-x-2">
                <Plus className="w-5 h-5 text-purple-600" />
                <span>Create New Local SEO Project</span>
              </h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateProject} className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  Business / Project Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Apex Dental Studio"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  Website Domain <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={newDomain}
                  onChange={(e) => setNewDomain(e.target.value)}
                  placeholder="e.g. apexdentalstudio.com"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Primary Business Category</label>
                <input
                  type="text"
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  list="category-options"
                  placeholder="Select or type category..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
                <datalist id="category-options">
                  {categorySuggestions.map((cat) => (
                    <option key={cat.id} value={cat.name} />
                  ))}
                </datalist>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">City (Optional)</label>
                  <input
                    type="text"
                    value={newCity}
                    onChange={(e) => setNewCity(e.target.value)}
                    placeholder="e.g. Denver"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">State / Province</label>
                  <input
                    type="text"
                    value={newState}
                    onChange={(e) => setNewState(e.target.value)}
                    placeholder="e.g. CO"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-5 py-2 btn-vibrant-primary text-xs font-bold rounded-xl shadow-md transition-all flex items-center space-x-1.5 disabled:opacity-50"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>{creating ? 'Creating...' : 'Create Project'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: Edit Project */}
      {editingProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-black text-slate-900 flex items-center space-x-2">
                <Edit2 className="w-5 h-5 text-purple-600" />
                <span>Edit Project</span>
              </h3>
              <button
                onClick={() => setEditingProject(null)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Project Name</label>
                <input
                  type="text"
                  required
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Website Domain</label>
                <input
                  type="text"
                  required
                  value={editDomain}
                  onChange={(e) => setEditDomain(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Primary Category</label>
                <input
                  type="text"
                  required
                  value={editCategory}
                  onChange={(e) => setEditCategory(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingProject(null)}
                  className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingEdit}
                  className="px-5 py-2 btn-vibrant-primary text-xs font-bold rounded-xl shadow-md transition-all disabled:opacity-50"
                >
                  <span>{savingEdit ? 'Saving...' : 'Save Changes'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

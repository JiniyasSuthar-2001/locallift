import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  FolderKanban,
  ArrowLeft,
  Globe,
  MapPin,
  Building2,
  Calendar,
  Users2,
  Settings,
  ExternalLink,
  Edit2,
  Archive,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  BarChart2,
  Layers,
  Sparkles
} from 'lucide-react';
import api from '../api/client';
import { useProject } from '../context/ProjectContext';
import { getErrorMessage } from '../utils/error';
import { Project } from '../types';
import { ProjectTeamSection } from '../components/team/ProjectTeamSection';

export const ProjectDetailsView: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { setActiveProject, refreshProjects } = useProject();

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'team'>('overview');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Edit modal
  const [showEditModal, setShowEditModal] = useState<boolean>(false);
  const [editName, setEditName] = useState<string>('');
  const [editDomain, setEditDomain] = useState<string>('');
  const [editCategory, setEditCategory] = useState<string>('');
  const [savingEdit, setSavingEdit] = useState<boolean>(false);

  const fetchProjectDetails = async () => {
    if (!projectId) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.get<Project>(`/projects/${projectId}`);
      setProject(res.data);
      setEditName(res.data.name);
      setEditDomain(res.data.domain);
      setEditCategory(res.data.primary_category);
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to load project details.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjectDetails();
  }, [projectId]);

  const handleOpenDashboard = () => {
    if (project) {
      setActiveProject(project);
      navigate('/');
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!project) return;
    setSavingEdit(true);
    setErrorMsg(null);
    try {
      const res = await api.put<Project>(`/projects/${project.id}`, {
        name: editName.trim(),
        domain: editDomain.trim(),
        primary_category: editCategory.trim()
      });
      setProject(res.data);
      setSuccessMsg('Project updated successfully.');
      setShowEditModal(false);
      await refreshProjects(project.id);
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to update project.'));
    } finally {
      setSavingEdit(false);
    }
  };

  const handleToggleArchive = async () => {
    if (!project) return;
    const willArchive = !project.is_archived;
    try {
      const res = await api.put<Project>(`/projects/${project.id}`, {
        is_archived: willArchive,
        status: willArchive ? 'archived' : 'active'
      });
      setProject(res.data);
      setSuccessMsg(willArchive ? 'Project archived.' : 'Project restored.');
      await refreshProjects(project.id);
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to change project archive state.'));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-16 text-xs text-slate-500">
        <span>Loading project details...</span>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="p-8 text-center space-y-3">
        <AlertCircle className="w-8 h-8 text-rose-500 mx-auto" />
        <h3 className="text-base font-black text-slate-800">Project Not Found</h3>
        <p className="text-xs text-slate-500">You may not have permission to view this project.</p>
        <Link to="/projects" className="inline-block px-4 py-2 btn-vibrant-primary text-xs font-bold rounded-xl">
          Back to My Projects
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl space-y-6">
      {/* Top Back Link & Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate('/projects')}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-all"
            title="Back to My Projects"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-black text-slate-900 tracking-tight">{project.name}</h1>
              <span
                className={`text-[10px] font-black px-2 py-0.5 rounded-full ${
                  project.is_archived
                    ? 'bg-slate-200 text-slate-700'
                    : 'bg-emerald-100 text-emerald-800'
                }`}
              >
                {project.is_archived ? 'Archived' : 'Active'}
              </span>
            </div>
            <div className="flex items-center space-x-2 text-xs text-slate-500 mt-0.5">
              <Globe className="w-3.5 h-3.5 text-slate-400" />
              <span>{project.domain}</span>
              <span>•</span>
              <span>{project.primary_category}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={handleOpenDashboard}
            className="px-4 py-2 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all flex items-center space-x-1.5"
          >
            <BarChart2 className="w-4 h-4" />
            <span>Open Dashboard</span>
          </button>
          <button
            onClick={() => setShowEditModal(true)}
            className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-all flex items-center space-x-1"
          >
            <Edit2 className="w-3.5 h-3.5" />
            <span>Edit</span>
          </button>
          <button
            onClick={handleToggleArchive}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-all"
            title={project.is_archived ? 'Restore Project' : 'Archive Project'}
          >
            <Archive className="w-4 h-4" />
          </button>
        </div>
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

      {/* Tab Navigation */}
      <div className="flex items-center space-x-2 border-b border-slate-200 pb-2 text-xs font-bold">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition-all ${
            activeTab === 'overview'
              ? 'bg-purple-50 text-purple-700 border border-purple-200 shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <FolderKanban className="w-4 h-4" />
          <span>Project Overview & Metadata</span>
        </button>

        <button
          onClick={() => setActiveTab('team')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition-all ${
            activeTab === 'team'
              ? 'bg-purple-50 text-purple-700 border border-purple-200 shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <Users2 className="w-4 h-4" />
          <span>Team & Collaborators (Max 3)</span>
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Metadata Card */}
          <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl bg-white space-y-4">
            <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
              <Building2 className="w-4 h-4 text-purple-600" />
              <span>Project Configuration</span>
            </h3>

            <div className="space-y-3 text-xs">
              <div>
                <span className="text-slate-400 font-medium block">Project Name</span>
                <span className="font-bold text-slate-800">{project.name}</span>
              </div>
              <div>
                <span className="text-slate-400 font-medium block">Website Domain</span>
                <a
                  href={`https://${project.domain}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-bold text-purple-600 hover:underline flex items-center space-x-1"
                >
                  <span>{project.domain}</span>
                  <ExternalLink className="w-3 h-3 text-slate-400" />
                </a>
              </div>
              <div>
                <span className="text-slate-400 font-medium block">Primary Business Category</span>
                <span className="font-bold text-slate-800">{project.primary_category}</span>
              </div>
              <div>
                <span className="text-slate-400 font-medium block">Target Country</span>
                <span className="font-bold text-slate-800">{project.country}</span>
              </div>
              <div>
                <span className="text-slate-400 font-medium block">Created Date</span>
                <span className="font-medium text-slate-600">
                  {new Date(project.created_at).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                </span>
              </div>
            </div>
          </div>

          {/* Location Card */}
          <div className="card-vibrant p-6 border border-slate-200/80 rounded-2xl bg-white space-y-4">
            <h3 className="text-sm font-black text-slate-900 flex items-center space-x-2">
              <MapPin className="w-4 h-4 text-purple-600" />
              <span>Primary Business Location</span>
            </h3>

            {project.locations && project.locations.length > 0 ? (
              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-slate-400 font-medium block">Location Name</span>
                  <span className="font-bold text-slate-800">{project.locations[0].name}</span>
                </div>
                <div>
                  <span className="text-slate-400 font-medium block">Address</span>
                  <span className="font-medium text-slate-700">
                    {project.locations[0].address || 'No street address specified'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-slate-400 font-medium block">City / State</span>
                    <span className="font-medium text-slate-700">
                      {project.locations[0].city || 'N/A'}, {project.locations[0].state || ''}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 font-medium block">Postal Code</span>
                    <span className="font-medium text-slate-700">{project.locations[0].postal_code || 'N/A'}</span>
                  </div>
                </div>
                <div>
                  <span className="text-slate-400 font-medium block">Telephone</span>
                  <span className="font-medium text-slate-700">{project.locations[0].phone || 'No phone set'}</span>
                </div>
                {project.locations[0].latitude && project.locations[0].longitude && (
                  <div>
                    <span className="text-slate-400 font-medium block">Coordinates</span>
                    <span className="font-mono text-[11px] text-slate-600">
                      {project.locations[0].latitude.toFixed(4)}, {project.locations[0].longitude.toFixed(4)}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-slate-400 italic py-4">No location configured.</div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'team' && <ProjectTeamSection projectId={project.id} />}

      {/* EDIT MODAL */}
      {showEditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-black text-slate-900 flex items-center space-x-2">
                <Edit2 className="w-5 h-5 text-purple-600" />
                <span>Edit Project Details</span>
              </h3>
              <button
                onClick={() => setShowEditModal(false)}
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
                <label className="font-bold text-slate-700 block mb-1">Primary Business Category</label>
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
                  onClick={() => setShowEditModal(false)}
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

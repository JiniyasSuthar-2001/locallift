import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Users2,
  Mail,
  Shield,
  FolderKanban,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
  Search,
  UserPlus,
  Plus
} from 'lucide-react';
import api from '../api/client';
import { getErrorMessage } from '../utils/error';
import { TeamDirectoryMember } from '../types';
import { useProject } from '../context/ProjectContext';
import { useAuth } from '../context/AuthContext';
import { ALL_AVAILABLE_PERMISSIONS } from '../components/team/ProjectTeamSection';

export const TeamDirectoryView: React.FC = () => {
  const { memberId } = useParams<{ memberId?: string }>();
  const { projects, activeProject } = useProject();
  const { user } = useAuth();
  const [members, setMembers] = useState<TeamDirectoryMember[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Invite Modal State
  const [showInviteModal, setShowInviteModal] = useState<boolean>(false);
  const [selectedProjectId, setSelectedProjectId] = useState<number | string>(
    activeProject?.id || (projects.length > 0 ? projects[0].id : '')
  );
  const [inviteEmail, setInviteEmail] = useState<string>('');
  const [inviteRole, setInviteRole] = useState<string>('SEO Specialist');
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([
    'project_overview',
    'seo_audit',
    'local_seo',
    'gbp_monitoring',
    'reports',
    'tasks'
  ]);
  const [inviting, setInviting] = useState<boolean>(false);

  const fetchDirectory = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.get<TeamDirectoryMember[]>('/team');
      setMembers(res.data);
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to load team directory.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDirectory();
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects.length > 0) {
      setSelectedProjectId(activeProject?.id || projects[0].id);
    }
  }, [projects, activeProject]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim() || !selectedProjectId) return;
    setInviting(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await api.post(`/projects/${selectedProjectId}/team/invite`, {
        email: inviteEmail.trim(),
        role: inviteRole,
        permissions: selectedPermissions
      });
      const targetProj = projects.find((p) => String(p.id) === String(selectedProjectId));
      setSuccessMsg(`Invitation sent to ${inviteEmail}${targetProj ? ` for project "${targetProj.name}"` : ''}.`);
      setShowInviteModal(false);
      setInviteEmail('');
      await fetchDirectory();
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to send invitation.'));
    } finally {
      setInviting(false);
    }
  };

  const filteredMembers = members.filter((m) => {
    return (
      m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.global_role.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  const selectedMember = memberId
    ? members.find((m) => String(m.user_id) === String(memberId))
    : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center p-16 text-xs text-slate-500 space-x-2">
        <RefreshCw className="w-4 h-4 animate-spin text-purple-600" />
        <span>Loading team directory...</span>
      </div>
    );
  }

  return (
    <div className="max-w-5xl space-y-6">
      {/* Header with Invite Member Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2.5">
            <Users2 className="w-6 h-6 text-purple-600" />
            <span>Team Directory & Project Assignments</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Centralized directory of all organization members, project collaborators, and their active project permissions.
          </p>
        </div>

        {projects.length > 0 && (
          <button
            onClick={() => setShowInviteModal(true)}
            className="px-4 py-2.5 btn-vibrant-primary text-xs font-bold rounded-xl shadow-md transition-all flex items-center space-x-1.5 shrink-0 self-start sm:self-auto"
          >
            <UserPlus className="w-4 h-4" />
            <span>Invite Member</span>
          </button>
        )}
      </div>

      {/* Notifications */}
      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center space-x-2 text-xs text-emerald-800 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
          <span className="flex-1 font-medium">{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} aria-label="Dismiss notification" className="text-emerald-500 hover:text-emerald-800 text-xs font-bold">✕</button>
        </div>
      )}

      {errorMsg && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-2 text-xs text-rose-700 animate-fade-in">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span className="flex-1">{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} aria-label="Dismiss error notification" className="text-rose-500 hover:text-rose-800 text-xs font-bold">✕</button>
        </div>
      )}

      {/* Search Bar */}
      <div className="bg-white p-3.5 border border-slate-200/80 rounded-2xl shadow-xs max-w-md">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search collaborators by name or email..."
            className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
          />
        </div>
      </div>

      {/* Directory Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {filteredMembers.map((member) => (
          <div
            key={member.user_id}
            className="card-vibrant p-5 border border-slate-200/80 rounded-2xl bg-white shadow-xs space-y-4"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 text-white font-bold text-sm flex items-center justify-center shadow-xs">
                  {member.name[0]}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-sm font-black text-slate-900">{member.name}</h3>
                    <span className="text-[10px] font-bold px-2 py-0.2 rounded-md bg-purple-50 text-purple-700 border border-purple-200">
                      {member.global_role}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">{member.email}</div>
                </div>
              </div>

              <span className="text-[11px] font-bold text-slate-400">
                {member.project_count} Project{member.project_count === 1 ? '' : 's'}
              </span>
            </div>

            {/* Assigned Projects */}
            <div className="pt-3 border-t border-slate-100 space-y-2">
              <span className="text-[11px] font-bold text-slate-700 block">Assigned Projects & Permissions:</span>
              {member.projects.length === 0 ? (
                <div className="text-[11px] text-slate-400 italic">No specific project assignments yet.</div>
              ) : (
                <div className="space-y-2">
                  {member.projects.map((p) => (
                    <div
                      key={p.id}
                      className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/60 text-xs flex flex-col space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <Link
                          to={`/projects/${p.id}`}
                          className="font-bold text-slate-800 hover:text-purple-600 flex items-center space-x-1"
                        >
                          <span>{p.name}</span>
                          <ExternalLink className="w-3 h-3 text-slate-400" />
                        </Link>
                        <span className="text-[10px] font-bold px-2 py-0.2 rounded bg-purple-100 text-purple-800">
                          {p.role}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {p.permissions.slice(0, 4).map((perm) => (
                          <span
                            key={perm}
                            className="text-[9px] font-medium px-1.5 py-0.2 rounded bg-white border border-slate-200 text-slate-600"
                          >
                            {perm.replace('_', ' ')}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* MODAL: Invite Member */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-black text-slate-900 flex items-center space-x-2">
                <UserPlus className="w-5 h-5 text-purple-600" />
                <span>Invite Collaborator</span>
              </h3>
              <button
                onClick={() => setShowInviteModal(false)}
                aria-label="Close invite modal"
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleInvite} className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  Target Project <span className="text-rose-500">*</span>
                </label>
                <select
                  value={selectedProjectId}
                  onChange={(e) => setSelectedProjectId(e.target.value)}
                  required
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                >
                  {projects.map((proj) => (
                    <option key={proj.id} value={proj.id}>
                      {proj.name} ({proj.domain})
                    </option>
                  ))}
                </select>
                <p className="text-[10px] text-slate-400 mt-1">
                  Select which project this team member will be granted access to.
                </p>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  Collaborator Email <span className="text-rose-500">*</span>
                </label>
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="colleague@example.com"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
                <p className="text-[10px] text-slate-400 mt-1">
                  If they don't have a LocalLift account yet, they will receive a pending invitation upon registering with this email.
                </p>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Project Role Title</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                >
                  <option value="SEO Specialist">SEO Specialist</option>
                  <option value="Local SEO Manager">Local SEO Manager</option>
                  <option value="Content Specialist">Content Specialist</option>
                  <option value="Technical SEO Auditor">Technical SEO Auditor</option>
                  <option value="Client Stakeholder">Client Stakeholder (Viewer)</option>
                  <option value="Member">Team Member</option>
                </select>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-2">Project Permissions</label>
                <div className="space-y-2 max-h-48 overflow-y-auto border border-slate-100 rounded-xl p-2.5 bg-slate-50/50">
                  {ALL_AVAILABLE_PERMISSIONS.map((p) => {
                    const isChecked = selectedPermissions.includes(p.id);
                    return (
                      <label key={p.id} className="flex items-center space-x-2.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedPermissions([...selectedPermissions, p.id]);
                            } else {
                              setSelectedPermissions(selectedPermissions.filter((id) => id !== p.id));
                            }
                          }}
                          className="rounded border-slate-300 text-purple-600 focus:ring-purple-500"
                        />
                        <span className="text-[11px] font-medium text-slate-800">{p.label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={inviting}
                  className="px-5 py-2 btn-vibrant-primary text-xs font-bold rounded-xl shadow-md transition-all flex items-center space-x-1.5 disabled:opacity-50"
                >
                  <Mail className="w-3.5 h-3.5" />
                  <span>{inviting ? 'Sending Invite...' : 'Send Project Invitation'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

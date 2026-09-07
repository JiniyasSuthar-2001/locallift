import React, { useState, useEffect } from 'react';
import {
  Users2,
  Plus,
  Mail,
  Shield,
  ShieldCheck,
  Trash2,
  RefreshCw,
  XCircle,
  CheckCircle2,
  AlertCircle,
  Clock,
  UserPlus,
  Lock,
  Edit2
import api from '../../api/client';
import { getErrorMessage } from '../../utils/error';
import { ProjectTeamSummary, TeamMember, TeamInvitation } from '../../types';

interface ProjectTeamSectionProps {
  projectId: number;
}

const ALL_AVAILABLE_PERMISSIONS = [
  { id: 'project_overview', label: 'Project Overview & Dashboard' },
  { id: 'seo_audit', label: 'Website Audit & Schema' },
  { id: 'local_seo', label: 'Local SEO, Reviews & Citations' },
  { id: 'gbp_monitoring', label: 'GBP Monitoring (No Credential Access)' },
  { id: 'google_ads', label: 'Google Ads Telemetry' },
  { id: 'reports', label: 'Executive PDF Reports' },
  { id: 'tasks', label: 'SEO Task Board Management' },
  { id: 'templates', label: 'Template Hub' },
  { id: 'settings', label: 'Project Settings' },
  { id: 'team_management', label: 'Team Member Management' }
];

export const ProjectTeamSection: React.FC<ProjectTeamSectionProps> = ({ projectId }) => {
  const [teamData, setTeamData] = useState<ProjectTeamSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Invite Modal State
  const [showInviteModal, setShowInviteModal] = useState<boolean>(false);
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

  // Edit Access Modal State
  const [editingMember, setEditingMember] = useState<TeamMember | null>(null);
  const [editRole, setEditRole] = useState<string>('');
  const [editPermissions, setEditPermissions] = useState<string[]>([]);
  const [savingEdit, setSavingEdit] = useState<boolean>(false);

  // Remove confirmation
  const [removingMember, setRemovingMember] = useState<TeamMember | null>(null);
  const [cancellingInvitation, setCancellingInvitation] = useState<TeamInvitation | null>(null);

  const fetchTeam = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.get<ProjectTeamSummary>(`/projects/${projectId}/team`);
      setTeamData(res.data);
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to load project team.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTeam();
  }, [projectId]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setErrorMsg(null);
    try {
      await api.post(`/projects/${projectId}/team/invite`, {
        email: inviteEmail.trim(),
        role: inviteRole,
        permissions: selectedPermissions
      });
      setSuccessMsg(`Invitation sent to ${inviteEmail}.`);
      setShowInviteModal(false);
      setInviteEmail('');
      await fetchTeam();
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to send invitation.'));
    } finally {
      setInviting(false);
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingMember) return;
    setSavingEdit(true);
    setErrorMsg(null);
    try {
      await api.patch(`/projects/${projectId}/team/members/${editingMember.id}`, {
        role: editRole,
        permissions: editPermissions
      });
      setSuccessMsg(`Permissions updated for ${editingMember.name}.`);
      setEditingMember(null);
      await fetchTeam();
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to update member.'));
    } finally {
      setSavingEdit(false);
    }
  };

  const handleRemoveMember = async () => {
    if (!removingMember) return;
    try {
      await api.delete(`/projects/${projectId}/team/members/${removingMember.id}`);
      setSuccessMsg(`Removed ${removingMember.name} from project team.`);
      setRemovingMember(null);
      await fetchTeam();
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to remove member.'));
    }
  };

  const handleCancelInvitation = async () => {
    if (!cancellingInvitation) return;
    try {
      await api.delete(`/projects/${projectId}/team/invitations/${cancellingInvitation.id}`);
      setSuccessMsg(`Cancelled invitation for ${cancellingInvitation.email}.`);
      setCancellingInvitation(null);
      await fetchTeam();
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to cancel invitation.'));
    }
  };

  const handleResendInvitation = async (invitationId: number) => {
    try {
      await api.post(`/projects/${projectId}/team/invitations/${invitationId}/resend`);
      setSuccessMsg('Invitation resent and extended by 7 days.');
      await fetchTeam();
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to resend invitation.'));
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 flex items-center justify-center space-x-2">
        <RefreshCw className="w-4 h-4 animate-spin text-purple-600" />
        <span>Loading project team...</span>
      </div>
    );
  }

  if (!teamData) {
    return null;
  }

  const seatsFull = teamData.seats_used >= teamData.max_seats;

  return (
    <div className="space-y-6">
      {/* Notifications */}
      {errorMsg && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-2 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span className="flex-1">{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-400 hover:text-rose-600 font-bold">
            ✕
          </button>
        </div>
      )}
      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center space-x-2 text-xs text-emerald-800">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
          <span className="flex-1">{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700 font-bold">
            ✕
          </button>
        </div>
      )}

      {/* Team Header & Seat Summary Card */}
      <div className="card-vibrant p-5 border border-slate-200/80 rounded-2xl bg-white space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-black text-slate-900 flex items-center space-x-2">
                <Users2 className="w-5 h-5 text-purple-600" />
                <span>Project Team & Access</span>
              </h3>
              <span
                className={`text-[10px] font-black px-2.5 py-0.5 rounded-full border ${
                  seatsFull
                    ? 'bg-amber-50 text-amber-800 border-amber-200'
                    : 'bg-purple-50 text-purple-800 border-purple-200'
                }`}
              >
                {teamData.seats_used} / {teamData.max_seats} Team Seats Used
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Collaborators can work on permitted project modules without ever accessing the owner's Google account or raw credentials.
            </p>
          </div>

          <button
            onClick={() => setShowInviteModal(true)}
            disabled={seatsFull}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 shadow-sm ${
              seatsFull
                ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                : 'btn-vibrant-primary'
            }`}
            title={seatsFull ? 'Maximum 3 team members reached' : 'Invite Team Member'}
          >
            <UserPlus className="w-4 h-4" />
            <span>Add Team Member</span>
          </button>
        </div>

        {seatsFull && (
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-[11px] text-amber-800 flex items-center space-x-2">
            <Lock className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              <strong>Project Seat Limit Reached:</strong> Each LocalLift project supports a maximum of 3 team members. To add another collaborator, remove an existing member or cancel a pending invitation.
            </span>
          </div>
        )}

        {/* Team List Table */}
        <div className="divide-y divide-slate-100">
          {/* Owner Row */}
          <div className="py-3 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 text-white font-bold text-xs flex items-center justify-center shadow-xs">
                {teamData.owner.name[0]}
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-bold text-slate-900">{teamData.owner.name}</span>
                  <span className="text-[10px] font-black px-2 py-0.2 rounded-md bg-purple-100 text-purple-800">
                    Project Owner
                  </span>
                </div>
                <div className="text-[11px] text-slate-400">{teamData.owner.email}</div>
              </div>
            </div>
            <span className="text-[11px] font-semibold text-slate-500">Full Access (All Modules)</span>
          </div>

          {/* Active Members */}
          {teamData.members.map((member) => (
            <div key={member.id} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center space-x-3">
                <div className="w-9 h-9 rounded-full bg-slate-100 text-slate-700 font-bold text-xs flex items-center justify-center border border-slate-200">
                  {member.name[0]}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold text-slate-900">{member.name}</span>
                    <span className="text-[10px] font-bold px-2 py-0.2 rounded-md bg-slate-100 text-slate-700 border border-slate-200">
                      {member.role}
                    </span>
                    <span className="inline-flex items-center space-x-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded">
                      <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
                      <span>Active</span>
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400">{member.email}</div>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <div className="flex flex-wrap gap-1 max-w-xs justify-end">
                  {member.permissions.slice(0, 3).map((p) => (
                    <span key={p} className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-slate-100 text-slate-600">
                      {p.replace('_', ' ')}
                    </span>
                  ))}
                  {member.permissions.length > 3 && (
                    <span className="text-[9px] font-bold px-1 py-0.2 rounded bg-purple-50 text-purple-700">
                      +{member.permissions.length - 3} more
                    </span>
                  )}
                </div>

                <button
                  onClick={() => {
                    setEditingMember(member);
                    setEditRole(member.role);
                    setEditPermissions(member.permissions);
                  }}
                  className="p-1.5 text-slate-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-all"
                  title="Edit Permissions"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                </button>

                <button
                  onClick={() => setRemovingMember(member)}
                  className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-all"
                  title="Remove from project"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}

          {/* Pending Invitations */}
          {teamData.pending_invitations.map((inv) => (
            <div key={inv.id} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-purple-50/30 -mx-5 px-5">
              <div className="flex items-center space-x-3">
                <div className="w-9 h-9 rounded-full bg-purple-100 text-purple-700 font-bold text-xs flex items-center justify-center">
                  <Mail className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold text-slate-800">{inv.email}</span>
                    <span className="text-[10px] font-black px-2 py-0.2 rounded-md bg-amber-100 text-amber-800 border border-amber-200">
                      Invitation Pending
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Role: {inv.role} • Invited by {inv.invited_by_name || 'Owner'}
                  </div>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleResendInvitation(inv.id)}
                  className="px-2.5 py-1 bg-white hover:bg-purple-50 border border-purple-200 text-purple-700 rounded-lg text-[11px] font-bold transition-all flex items-center space-x-1"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Resend</span>
                </button>
                <button
                  onClick={() => setCancellingInvitation(inv)}
                  className="px-2.5 py-1 bg-white hover:bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-[11px] font-bold transition-all"
                >
                  Cancel
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* MODAL: Invite Team Member */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-black text-slate-900 flex items-center space-x-2">
                <UserPlus className="w-5 h-5 text-purple-600" />
                <span>Invite Project Team Member</span>
              </h3>
              <button
                onClick={() => setShowInviteModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleInvite} className="space-y-4 text-xs">
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

      {/* MODAL: Edit Member Permissions */}
      {editingMember && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-base font-black text-slate-900 flex items-center space-x-2">
                <Edit2 className="w-5 h-5 text-purple-600" />
                <span>Edit Access for {editingMember.name}</span>
              </h3>
              <button
                onClick={() => setEditingMember(null)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Project Role Title</label>
                <input
                  type="text"
                  value={editRole}
                  onChange={(e) => setEditRole(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-2">Project Permissions</label>
                <div className="space-y-2 max-h-48 overflow-y-auto border border-slate-100 rounded-xl p-2.5 bg-slate-50/50">
                  {ALL_AVAILABLE_PERMISSIONS.map((p) => {
                    const isChecked = editPermissions.includes(p.id);
                    return (
                      <label key={p.id} className="flex items-center space-x-2.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setEditPermissions([...editPermissions, p.id]);
                            } else {
                              setEditPermissions(editPermissions.filter((id) => id !== p.id));
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
                  onClick={() => setEditingMember(null)}
                  className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingEdit}
                  className="px-5 py-2 btn-vibrant-primary text-xs font-bold rounded-xl shadow-md transition-all flex items-center space-x-1.5 disabled:opacity-50"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>{savingEdit ? 'Saving...' : 'Save Permissions'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CONFIRM MODAL: Remove Member */}
      {removingMember && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center space-x-3 text-rose-600">
              <AlertCircle className="w-6 h-6" />
              <h3 className="text-base font-black text-slate-900">Remove Team Member?</h3>
            </div>
            <p className="text-xs text-slate-500">
              Are you sure you want to remove <strong className="text-slate-800">{removingMember.name}</strong> from this project? Their account and assignments in other projects will remain untouched.
            </p>
            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                onClick={() => setRemovingMember(null)}
                className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleRemoveMember}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm"
              >
                Yes, Remove
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CONFIRM MODAL: Cancel Invitation */}
      {cancellingInvitation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center space-x-3 text-amber-600">
              <AlertCircle className="w-6 h-6" />
              <h3 className="text-base font-black text-slate-900">Cancel Invitation?</h3>
            </div>
            <p className="text-xs text-slate-500">
              Cancel the pending invitation for <strong className="text-slate-800">{cancellingInvitation.email}</strong>? This seat will immediately become available for other collaborators.
            </p>
            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                onClick={() => setCancellingInvitation(null)}
                className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-50"
              >
                Keep Invitation
              </button>
              <button
                onClick={handleCancelInvitation}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm"
              >
                Yes, Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import {
  Mail,
  CheckCircle2,
  XCircle,
  ShieldCheck,
  Building2,
  UserCheck,
  Clock,
  Sparkles,
  ArrowRight
} from 'lucide-react';
import api from '../../api/client';
import { useProject } from '../../context/ProjectContext';
import { useAuth } from '../../context/AuthContext';
import { getErrorMessage } from '../../utils/error';
import { UserPendingInvitation } from '../../types';

export const InvitationNotificationModal: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const { refreshProjects } = useProject();
  const [invitations, setInvitations] = useState<UserPendingInvitation[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [minimized, setMinimized] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const fetchPendingInvitations = async () => {
    if (!isAuthenticated) {
      setInvitations([]);
      return;
    }
    try {
      const res = await api.get<UserPendingInvitation[]>('/invitations/pending');
      setInvitations(res.data || []);
      if (res.data && res.data.length > 0) {
        setMinimized(false);
      }
    } catch (e) {
      // Ignore background check errors
    }
  };

  useEffect(() => {
    if (!isAuthenticated) {
      setInvitations([]);
      return;
    }
    fetchPendingInvitations();
    // Re-check periodically every 60 seconds
    const interval = setInterval(fetchPendingInvitations, 60000);
    return () => clearInterval(interval);
  }, [isAuthenticated]);

  if (invitations.length === 0) {
    return null;
  }

  const currentInvite = invitations[currentIndex] || invitations[0];

  const handleAccept = async (invitationId: number) => {
    setSubmitting(true);
    setFeedback(null);
    try {
      const res = await api.post<{ success: boolean; message: string; project_id: number }>(
        `/invitations/${invitationId}/accept`
      );
      setFeedback({ type: 'success', message: res.data.message || 'Invitation accepted!' });
      await refreshProjects(res.data.project_id);
      
      setTimeout(() => {
        setInvitations(prev => prev.filter(i => i.id !== invitationId));
        setFeedback(null);
        setSubmitting(false);
      }, 1200);
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: getErrorMessage(err, 'Failed to accept invitation.')
      });
      setSubmitting(false);
    }
  };

  const handleDecline = async (invitationId: number) => {
    setSubmitting(true);
    setFeedback(null);
    try {
      await api.post(`/invitations/${invitationId}/decline`);
      setFeedback({ type: 'success', message: 'Invitation declined.' });
      
      setTimeout(() => {
        setInvitations(prev => prev.filter(i => i.id !== invitationId));
        setFeedback(null);
        setSubmitting(false);
      }, 1000);
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: getErrorMessage(err, 'Failed to decline invitation.')
      });
      setSubmitting(false);
    }
  };

  if (minimized) {
    return (
      <div className="fixed bottom-5 right-5 z-50 animate-bounce">
        <button
          onClick={() => setMinimized(false)}
          className="flex items-center space-x-2 px-4 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-2xl shadow-xl font-bold text-xs hover:scale-105 transition-all"
        >
          <Mail className="w-4 h-4 text-purple-200" />
          <span>{invitations.length} Pending Project Invitation{invitations.length > 1 ? 's' : ''}</span>
        </button>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-7 shadow-2xl border border-slate-200 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-purple-600 to-pink-600 flex items-center justify-center text-white shadow-md shadow-purple-500/20">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-base font-black text-slate-900">Project Team Invitation</h3>
              <p className="text-xs text-slate-400 font-medium">
                Invitation {currentIndex + 1} of {invitations.length}
              </p>
            </div>
          </div>

          <button
            onClick={() => setMinimized(true)}
            className="text-xs text-slate-400 hover:text-slate-600 font-bold px-2 py-1 rounded-lg hover:bg-slate-100 transition-all"
          >
            Decide Later
          </button>
        </div>

        {/* Feedback Alert */}
        {feedback && (
          <div
            className={`p-3 rounded-xl flex items-center space-x-2 text-xs font-bold ${
              feedback.type === 'success'
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                : 'bg-rose-50 text-rose-800 border border-rose-200'
            }`}
          >
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <XCircle className="w-4 h-4 text-rose-600 shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
        )}

        {/* Invitation Card */}
        <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-4">
          <div>
            <div className="text-[11px] uppercase font-black tracking-wider text-purple-700 mb-1">
              {currentInvite.organization_name}
            </div>
            <h4 className="text-lg font-black text-slate-900 leading-tight">
              {currentInvite.project_name}
            </h4>
            <p className="text-xs text-slate-500 mt-0.5">
              Invited by <strong className="text-slate-800">{currentInvite.invited_by_name}</strong> to collaborate as <span className="font-bold text-purple-700">{currentInvite.role}</span>.
            </p>
          </div>

          {/* Permissions Breakdown */}
          <div>
            <div className="text-[11px] font-bold text-slate-700 mb-2 flex items-center space-x-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-purple-600" />
              <span>Assigned Project Permissions:</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {currentInvite.permissions.map(perm => (
                <span
                  key={perm}
                  className="px-2.5 py-0.5 bg-white border border-slate-200 rounded-lg text-[10px] font-bold text-slate-700 shadow-2xs"
                >
                  {perm.replace('_', ' ')}
                </span>
              ))}
            </div>
          </div>

          <div className="flex items-center space-x-2 text-[11px] text-slate-400 font-medium pt-1">
            <Clock className="w-3.5 h-3.5" />
            <span>Invitation expires: {new Date(currentInvite.expires_at).toLocaleDateString()}</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end space-x-3 pt-2">
          <button
            type="button"
            disabled={submitting}
            onClick={() => handleDecline(currentInvite.id)}
            className="px-4 py-2.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-bold rounded-xl transition-all disabled:opacity-50"
          >
            Decline
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={() => handleAccept(currentInvite.id)}
            className="px-6 py-2.5 btn-vibrant-primary text-xs font-bold rounded-xl shadow-md transition-all flex items-center space-x-2 disabled:opacity-50"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>{submitting ? 'Accepting...' : 'Accept Invitation'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

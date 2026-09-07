import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { RotateCw, CheckCircle2, AlertCircle, Store } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { getErrorMessage } from '../utils/error';
import api from '../api/client';

export const GoogleCallbackView: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { activeProject, refreshDashboard } = useProject();
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const processCallback = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const error = searchParams.get('error');

      if (error) {
        setStatus('error');
        setErrorMessage(`Google authorization failed: ${error}`);
        return;
      }

      if (!code) {
        setStatus('error');
        setErrorMessage('No authorization code provided in the callback URL.');
        return;
      }

      try {
        try {
          await api.post('/connections/google/callback', {
            code,
            state
          });
        } catch (e) {
          await api.post('/gbp/oauth/callback', {
            code,
            state,
            project_id: activeProject?.id
          });
        }
        setStatus('success');
        await refreshDashboard();
        setTimeout(() => {
          navigate('/settings');
        }, 1500);
      } catch (err: any) {
        setStatus('error');
        setErrorMessage(
          getErrorMessage(err, 'Failed to complete Google OAuth authentication with LocalLift backend.')
        );
      }
    };

    processCallback();
  }, [searchParams, activeProject?.id, navigate, refreshDashboard]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="card-vibrant max-w-md w-full p-8 text-center space-y-5">
        <div className="w-16 h-16 rounded-2xl bg-purple-50 text-purple-600 flex items-center justify-center mx-auto">
          {status === 'processing' && <RotateCw className="w-8 h-8 animate-spin" />}
          {status === 'success' && <CheckCircle2 className="w-8 h-8 text-emerald-600" />}
          {status === 'error' && <AlertCircle className="w-8 h-8 text-rose-600" />}
        </div>

        <div>
          <h2 className="text-xl font-black text-slate-900">
            {status === 'processing' && 'Connecting Google Account...'}
            {status === 'success' && 'Google Business Profile Connected!'}
            {status === 'error' && 'Connection Failed'}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {status === 'processing' && 'Exchanging security tokens and discovering your business locations...'}
            {status === 'success' && 'Redirecting to your Google Business Profile hub...'}
            {status === 'error' && (errorMessage || 'An error occurred during authentication.')}
          </p>
        </div>

        {status === 'error' && (
          <button
            onClick={() => navigate('/google/gbp')}
            className="px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold transition-all inline-block"
          >
            Back to GBP Hub
          </button>
        )}
      </div>
    </div>
  );
};

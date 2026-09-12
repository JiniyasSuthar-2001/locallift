import React, { useState, useEffect } from 'react';
import {
  Settings,
  Link2,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Building2,
  Globe,
  Shield,
  Layers,
  Sparkles,
  Info,
  Server,
  Activity,
  RefreshCw,
  Cpu,
  Check
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import { ConnectionsView } from './ConnectionsView';
import { EmptyState } from '../components/ui/EmptyState';
import { StatusBadge } from '../components/ui/StatusBadge';
import api from '../api/client';
import { getErrorMessage } from '../utils/error';

interface SERPHealth {
  provider: string;
  status: string;
  base_url: string;
  default_engine: string;
  fallback_provider?: string;
  fallback_configured?: boolean;
  latency_ms?: number;
  message?: string;
}

export const SettingsView: React.FC = () => {
  const { user } = useAuth();
  const { activeProject, refreshProjects } = useProject();
  const [activeTab, setActiveTab] = useState<'connections' | 'serp' | 'general'>('connections');

  // Form State
  const [name, setName] = useState('');
  const [domain, setDomain] = useState('');
  const [primaryCategory, setPrimaryCategory] = useState('');
  const [country, setCountry] = useState('United States');

  // Request State
  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // SERP Health State
  const [serpHealth, setSerpHealth] = useState<SERPHealth | null>(null);
  const [isTestingSerp, setIsTestingSerp] = useState(false);
  const [testResultMsg, setTestResultMsg] = useState<string | null>(null);

  // Sync form state when activeProject changes
  useEffect(() => {
    if (activeProject) {
      setName(activeProject.name || '');
      setDomain(activeProject.domain || '');
      setPrimaryCategory(activeProject.primary_category || 'Local Business');
      setCountry(activeProject.country || 'United States');
      setSuccessMsg(null);
      setErrorMsg(null);
    }
  }, [activeProject?.id, activeProject?.name, activeProject?.domain, activeProject?.primary_category, activeProject?.country]);

  // Load SERP health on mount
  useEffect(() => {
    fetchSerpHealth();
  }, []);

  const fetchSerpHealth = async () => {
    try {
      const resp = await api.get('/serp/health');
      setSerpHealth(resp.data);
    } catch {
      setSerpHealth({
        provider: 'openserp',
        status: 'UNAVAILABLE',
        base_url: 'http://127.0.0.1:7000',
        default_engine: 'google',
        fallback_provider: 'serpapi',
        fallback_configured: false,
        message: 'Could not connect to OpenSERP server.'
      });
    }
  };

  const handleTestSerp = async () => {
    setIsTestingSerp(true);
    setTestResultMsg(null);
    try {
      const resp = await api.post('/serp/test-connection', {
        base_url: serpHealth?.base_url || 'http://127.0.0.1:7000',
        engine: serpHealth?.default_engine || 'google'
      });
      setTestResultMsg(resp.data?.message || `Status: ${resp.data?.status}`);
      await fetchSerpHealth();
    } catch (err: any) {
      setTestResultMsg(getErrorMessage(err, 'Connection test failed.'));
    } finally {
      setIsTestingSerp(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject) return;
    if (!name.trim() || !domain.trim()) {
      setErrorMsg('Project name and target domain are required.');
      return;
    }

    setIsSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const cleanDomain = domain.trim().replace(/^https?:\/\//, '').replace(/\/+$/, '');
      await api.put(`/projects/${activeProject.id}`, {
        name: name.trim(),
        domain: cleanDomain,
        primary_category: primaryCategory.trim() || 'Local Business',
        country: country.trim() || 'United States'
      });

      await refreshProjects(activeProject.id);
      setSuccessMsg('Project configuration saved and synchronized successfully.');
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to update project settings.'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-5xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-[#142820] tracking-tight flex items-center space-x-2.5">
          <Settings className="w-6 h-6 text-[#236B4F]" />
          <span>Platform & Infrastructure Settings</span>
        </h1>
        <p className="text-xs text-[#587568] mt-1">
          Manage agency connections, Google multi-service integrations, self-hosted OpenSERP engine, and project metadata.
        </p>
      </div>

      {/* Settings Navigation Tabs */}
      <div className="flex items-center space-x-2 border-b border-[#DCE8DC] pb-2 text-xs font-bold">
        <button
          onClick={() => setActiveTab('connections')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition-all ${
            activeTab === 'connections'
              ? 'bg-[#EAF2EA] text-[#142820] font-bold border border-[#B8DFC9] shadow-2xs'
              : 'text-[#587568] hover:text-[#142820] hover:bg-[#F1F7F1]'
          }`}
        >
          <Link2 className="w-4 h-4 text-[#236B4F]" />
          <span>Google Platform Connections</span>
        </button>

        <button
          onClick={() => setActiveTab('serp')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition-all ${
            activeTab === 'serp'
              ? 'bg-[#EAF2EA] text-[#142820] font-bold border border-[#B8DFC9] shadow-2xs'
              : 'text-[#587568] hover:text-[#142820] hover:bg-[#F1F7F1]'
          }`}
        >
          <Server className="w-4 h-4 text-[#236B4F]" />
          <span>SERP Provider (OpenSERP)</span>
        </button>

        <button
          onClick={() => setActiveTab('general')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition-all ${
            activeTab === 'general'
              ? 'bg-[#EAF2EA] text-[#142820] font-bold border border-[#B8DFC9] shadow-2xs'
              : 'text-[#587568] hover:text-[#142820] hover:bg-[#F1F7F1]'
          }`}
        >
          <Sliders className="w-4 h-4 text-[#236B4F]" />
          <span>Project & Metadata Settings</span>
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'connections' && <ConnectionsView />}

      {/* SERP Provider Configuration Tab */}
      {activeTab === 'serp' && (
        <div className="space-y-6">
          <div className="card-nature p-6 space-y-6">
            <div className="flex items-start justify-between border-b border-[#EBF2EB] pb-4">
              <div>
                <div className="flex items-center space-x-3">
                  <h3 className="text-base font-extrabold text-[#142820] tracking-tight">
                    Self-Hosted OpenSERP Engine
                  </h3>
                  <StatusBadge status={serpHealth?.status || 'UNAVAILABLE'} />
                </div>
                <p className="text-xs text-[#587568] mt-1">
                  Open source, self-hosted search engine scraper and ranking normalizer. Runs locally without third-party API fees.
                </p>
              </div>

              <button
                onClick={handleTestSerp}
                disabled={isTestingSerp}
                className="btn-secondary-nature px-3.5 py-1.5 rounded-xl text-xs flex items-center space-x-2"
              >
                <RefreshCw className={`w-3.5 h-3.5 text-[#236B4F] ${isTestingSerp ? 'animate-spin' : ''}`} />
                <span>Test Connection</span>
              </button>
            </div>

            {testResultMsg && (
              <div className="p-3 bg-[#F1F7F1] border border-[#B8DFC9] rounded-xl text-xs text-[#142820] flex items-center space-x-2">
                <Info className="w-4 h-4 text-[#236B4F] shrink-0" />
                <span>{testResultMsg}</span>
              </div>
            )}

            {/* Configuration Details Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="p-4 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-2">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#587568]">Primary Provider</span>
                <div className="text-sm font-bold text-[#142820] flex items-center space-x-2">
                  <Cpu className="w-4 h-4 text-[#236B4F]" />
                  <span>OpenSERP (Self-Hosted)</span>
                </div>
                <p className="text-[11px] text-[#587568]">
                  Container: <code className="bg-[#EAF2EA] px-1.5 py-0.5 rounded text-[#174A38] font-mono">karust/openserp:latest</code>
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-2">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#587568]">Endpoint URL</span>
                <div className="text-sm font-bold font-mono text-[#142820]">
                  {serpHealth?.base_url || 'http://127.0.0.1:7000'}
                </div>
                <p className="text-[11px] text-[#587568]">
                  Default Engine: <span className="font-semibold text-[#142820] capitalize">{serpHealth?.default_engine || 'google'}</span>
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-2">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#587568]">Fallback Provider</span>
                <div className="text-sm font-bold text-[#142820] flex items-center space-x-2">
                  <Activity className="w-4 h-4 text-[#39B982]" />
                  <span>SerpApi (Optional Fallback)</span>
                </div>
                <p className="text-[11px] text-[#587568]">
                  Status: {serpHealth?.fallback_configured ? (
                    <span className="font-semibold text-[#065F46]">Configured & Ready</span>
                  ) : (
                    <span className="text-[#587568]">Optional (Unconfigured)</span>
                  )}
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-2">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#587568]">Performance & Latency</span>
                <div className="text-sm font-bold text-[#142820]">
                  {serpHealth?.latency_ms !== undefined && serpHealth?.latency_ms !== null
                    ? `${serpHealth.latency_ms} ms`
                    : '—'}
                </div>
                <p className="text-[11px] text-[#587568]">
                  Zero per-search vendor billing on self-hosted infrastructure.
                </p>
              </div>
            </div>

            {/* Truthful Architecture Notice */}
            <div className="p-4 rounded-xl bg-[#F1F7F1] border border-[#B8DFC9] space-y-2 text-xs text-[#2E4E40]">
              <div className="flex items-start space-x-2.5">
                <Info className="w-4 h-4 text-[#236B4F] shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-[#142820]">Infrastructure & Throughput Note: </span>
                  <span>
                    Self-hosted OpenSERP operates directly on your infrastructure without vendor API tokens. Actual query capacity is governed by local network conditions, search engine rate limits, and proxy configuration. Failed scans fail closed with honest diagnostics rather than false rankings.
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* General Project Settings Tab */}
      {activeTab === 'general' && (
        <div className="space-y-6">
          {!activeProject ? (
            <EmptyState
              icon={Building2}
              badge="Project Settings"
              title="No Active Project Selected"
              description="Select or create a business project to configure project parameters and domain targets."
            />
          ) : (
            <>
              {/* Notifications */}
              {successMsg && (
                <div className="p-3.5 bg-[#ECFDF5] border border-[#A7F3D0] rounded-xl flex items-center space-x-2 text-xs text-[#065F46] animate-in fade-in">
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-[#065F46]" />
                  <span className="flex-1 font-semibold">{successMsg}</span>
                  <button onClick={() => setSuccessMsg(null)} aria-label="Dismiss notification" className="text-[#065F46] hover:opacity-80 text-xs font-bold">✕</button>
                </div>
              )}

              {errorMsg && (
                <div className="p-3.5 bg-[#FEF2F2] border border-[#FECACA] rounded-xl flex items-center space-x-2 text-xs text-[#991B1B] animate-in fade-in">
                  <AlertCircle className="w-4 h-4 shrink-0 text-[#991B1B]" />
                  <span className="flex-1 font-semibold">{errorMsg}</span>
                  <button onClick={() => setErrorMsg(null)} aria-label="Dismiss error notification" className="text-[#991B1B] hover:opacity-80 text-xs font-bold">✕</button>
                </div>
              )}

              <div className="card-nature p-6 space-y-6">
                <form onSubmit={handleSave} className="space-y-6 text-xs">
                  <div>
                    <h3 className="text-sm font-extrabold text-[#142820] mb-1 flex items-center space-x-2">
                      <Building2 className="w-4 h-4 text-[#236B4F]" />
                      <span>Active Project Configuration</span>
                    </h3>
                    <p className="text-[11px] text-[#587568] mb-4">
                      Update metadata, primary business taxonomy, and domain bindings for the current project.
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="text-[#142820] font-bold block mb-1">Active Project Name</label>
                        <input
                          type="text"
                          required
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          placeholder="e.g. Apex Electrical Services"
                          className="w-full bg-[#F7FAF7] border border-[#DCE8DC] rounded-xl p-2.5 text-[#142820] focus:outline-none focus:border-[#236B4F] font-medium"
                        />
                      </div>

                      <div>
                        <label className="text-[#142820] font-bold block mb-1">Target Website Domain</label>
                        <input
                          type="text"
                          required
                          value={domain}
                          onChange={(e) => setDomain(e.target.value)}
                          placeholder="e.g. apexelectrical.com.au"
                          className="w-full bg-[#F7FAF7] border border-[#DCE8DC] rounded-xl p-2.5 text-[#142820] focus:outline-none focus:border-[#236B4F] font-medium"
                        />
                      </div>

                      <div>
                        <label className="text-[#142820] font-bold block mb-1">Primary Business Category</label>
                        <input
                          type="text"
                          value={primaryCategory}
                          onChange={(e) => setPrimaryCategory(e.target.value)}
                          placeholder="e.g. Electrician, Plumber, Dental Clinic"
                          className="w-full bg-[#F7FAF7] border border-[#DCE8DC] rounded-xl p-2.5 text-[#142820] focus:outline-none focus:border-[#236B4F] font-medium"
                        />
                      </div>

                      <div>
                        <label className="text-[#142820] font-bold block mb-1">Target Country</label>
                        <input
                          type="text"
                          value={country}
                          onChange={(e) => setCountry(e.target.value)}
                          placeholder="e.g. United States, Australia, United Kingdom"
                          className="w-full bg-[#F7FAF7] border border-[#DCE8DC] rounded-xl p-2.5 text-[#142820] focus:outline-none focus:border-[#236B4F] font-medium"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-[#DCE8DC]">
                    <h3 className="text-sm font-extrabold text-[#142820] mb-1 flex items-center space-x-2">
                      <Shield className="w-4 h-4 text-[#236B4F]" />
                      <span>Account & Organization Reference</span>
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3">
                      <div>
                        <label className="text-[#142820] font-bold block mb-1">Account Email</label>
                        <input
                          type="email"
                          disabled
                          value={user?.email || ''}
                          className="w-full bg-[#EAF2EA] border border-[#DCE8DC] rounded-xl p-2.5 text-[#587568] font-medium cursor-not-allowed"
                        />
                      </div>
                      <div>
                        <label className="text-[#142820] font-bold block mb-1">User Role</label>
                        <input
                          type="text"
                          disabled
                          value={user?.role || 'Admin'}
                          className="w-full bg-[#EAF2EA] border border-[#DCE8DC] rounded-xl p-2.5 text-[#587568] font-medium cursor-not-allowed"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-end pt-4 border-t border-[#DCE8DC]">
                    <button
                      type="submit"
                      disabled={isSaving}
                      className="px-6 py-2.5 btn-primary-gradient rounded-xl text-xs font-bold transition-all disabled:opacity-50 flex items-center space-x-2"
                    >
                      {isSaving ? (
                        <span>Saving...</span>
                      ) : (
                        <span>Save Configuration</span>
                      )}
                    </button>
                  </div>
                </form>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

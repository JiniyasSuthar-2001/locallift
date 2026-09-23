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
  Key,
  Check
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import { ConnectionsView } from './ConnectionsView';
import { EmptyState } from '../components/ui/EmptyState';
import { StatusBadge } from '../components/ui/StatusBadge';
import api from '../api/client';
import { CountrySelector } from '../components/ui/CountrySelector';
import { getErrorMessage } from '../utils/error';

interface SERPConfig {
  provider: string;
  has_key: boolean;
  masked_key: string | null;
  connection_status: string;
  status_message: string;
  last_tested_at: string | null;
  base_url?: string | null;
}

export const SettingsView: React.FC = () => {
  const { user } = useAuth();
  const { activeProject, refreshProjects } = useProject();
  const [activeTab, setActiveTab] = useState<'connections' | 'serp' | 'general'>('connections');

  // Form State
  const [name, setName] = useState('');
  const [domain, setDomain] = useState('');
  const [primaryCategory, setPrimaryCategory] = useState('');
  const [country, setCountry] = useState('');

  // Request State
  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // SERP Config State
  const [serpConfig, setSerpConfig] = useState<SERPConfig | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>('serpapi');
  const [apiKeyInput, setApiKeyInput] = useState<string>('');
  const [baseUrlInput, setBaseUrlInput] = useState<string>('');
  const [isSavingSerpKey, setIsSavingSerpKey] = useState(false);
  const [isTestingSerpKey, setIsTestingSerpKey] = useState(false);
  const [serpResultMsg, setSerpResultMsg] = useState<string | null>(null);
  const [serpResultError, setSerpResultError] = useState<string | null>(null);

  // Sync form state when activeProject changes
  useEffect(() => {
    if (activeProject) {
      setName(activeProject.name || '');
      setDomain(activeProject.domain || '');
      setPrimaryCategory(activeProject.primary_category || 'Local Business');
      setCountry(activeProject.country || '');
      setSuccessMsg(null);
      setErrorMsg(null);
    }
  }, [activeProject?.id, activeProject?.name, activeProject?.domain, activeProject?.primary_category, activeProject?.country]);

  // Load SERP config on mount
  useEffect(() => {
    fetchSerpConfig();
  }, []);

  const fetchSerpConfig = async () => {
    try {
      const resp = await api.get('/serp/config');
      setSerpConfig(resp.data);
      if (resp.data?.provider) {
        setSelectedProvider(resp.data.provider);
      }
      if (resp.data?.base_url) {
        setBaseUrlInput(resp.data.base_url);
      }
    } catch {
      setSerpConfig({
        provider: 'serpapi',
        has_key: false,
        masked_key: null,
        connection_status: 'not_configured',
        status_message: 'SERP API key not configured. Add your SerpApi API key to enable rank tracking.',
        last_tested_at: null
      });
    }
  };

  const handleSaveSerpKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingSerpKey(true);
    setSerpResultMsg(null);
    setSerpResultError(null);

    try {
      const resp = await api.post('/serp/config', {
        provider: selectedProvider,
        api_key: apiKeyInput.trim() || undefined,
        base_url: baseUrlInput.trim() || undefined
      });
      setSerpConfig(resp.data);
      setApiKeyInput('');
      setSerpResultMsg('SERP API configuration saved successfully.');
      setTimeout(() => setSerpResultMsg(null), 4000);
    } catch (err: any) {
      setSerpResultError(getErrorMessage(err, 'Failed to save SERP API configuration.'));
    } finally {
      setIsSavingSerpKey(false);
    }
  };

  const handleTestSerpKey = async () => {
    setIsTestingSerpKey(true);
    setSerpResultMsg(null);
    setSerpResultError(null);
    try {
      const resp = await api.post('/serp/test-connection', {
        provider: selectedProvider,
        api_key: apiKeyInput.trim() || undefined,
        base_url: baseUrlInput.trim() || undefined
      });

      if (resp.data?.success) {
        setSerpResultMsg(resp.data?.message || 'SERP connection test passed successfully!');
      } else {
        setSerpResultError(resp.data?.message || 'Connection test failed.');
      }
      await fetchSerpConfig();
    } catch (err: any) {
      setSerpResultError(getErrorMessage(err, 'Connection test failed.'));
    } finally {
      setIsTestingSerpKey(false);
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
        country: country.trim() || undefined
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
          Manage agency connections, Google multi-service integrations, organization SERP credentials, and project metadata.
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
          <span>SERP Provider (SerpApi)</span>
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
                    SERP Search Provider Configuration
                  </h3>
                  <StatusBadge
                    status={
                      serpConfig?.connection_status === 'connected'
                        ? 'Connected'
                        : serpConfig?.connection_status === 'invalid_key'
                        ? 'Invalid Key'
                        : serpConfig?.connection_status === 'quota_exceeded'
                        ? 'Quota Exceeded'
                        : 'Not Configured'
                    }
                  />
                </div>
                <p className="text-xs text-[#587568] mt-1">
                  Use your organization's SerpApi account for keyword rank tracking and 5x5 Geo-Grid map searches. No Docker service required.
                </p>
              </div>
            </div>

            {serpResultMsg && (
              <div className="p-3.5 bg-[#F1F7F1] border border-[#B8DFC9] rounded-xl text-xs text-[#142820] flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span className="font-medium">{serpResultMsg}</span>
              </div>
            )}

            {serpResultError && (
              <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                <span className="font-semibold">{serpResultError}</span>
              </div>
            )}

            <form onSubmit={handleSaveSerpKey} className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Provider Selection */}
                <div>
                  <label className="block text-xs font-bold text-[#142820] uppercase tracking-wider mb-1.5">
                    SERP Provider
                  </label>
                  <select
                    value={selectedProvider}
                    onChange={(e) => setSelectedProvider(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#B8DFC9] bg-white text-[#142820] text-xs font-semibold focus:ring-2 focus:ring-[#236B4F] focus:outline-none"
                  >
                    <option value="serpapi">SerpApi (Default Cloud Provider)</option>
                    <option value="openserp">OpenSERP (Self-Hosted Web Scraping Engine)</option>
                  </select>
                </div>

                {/* Conditional Inputs */}
                {selectedProvider === 'openserp' ? (
                  <div>
                    <label className="block text-xs font-bold text-[#142820] uppercase tracking-wider mb-1.5">
                      OpenSERP Base URL
                    </label>
                    <input
                      type="url"
                      value={baseUrlInput}
                      onChange={(e) => setBaseUrlInput(e.target.value)}
                      placeholder="http://127.0.0.1:7000"
                      className="w-full px-3.5 py-2.5 rounded-xl border border-[#B8DFC9] bg-white text-[#142820] text-xs font-mono font-medium focus:ring-2 focus:ring-[#236B4F] focus:outline-none"
                    />
                  </div>
                ) : (
                  <div>
                    <label className="block text-xs font-bold text-[#142820] uppercase tracking-wider mb-1.5">
                      SerpApi API Key
                    </label>
                    <div className="relative">
                      <input
                        type="password"
                        value={apiKeyInput}
                        onChange={(e) => setApiKeyInput(e.target.value)}
                        placeholder={
                          serpConfig?.has_key
                            ? `Configured (${serpConfig.masked_key})`
                            : 'Enter your SerpApi API key'
                        }
                        className="w-full px-3.5 py-2.5 rounded-xl border border-[#B8DFC9] bg-white text-[#142820] text-xs font-mono font-medium focus:ring-2 focus:ring-[#236B4F] focus:outline-none pr-10"
                      />
                      <Key className="w-4 h-4 text-[#587568] absolute right-3 top-3 pointer-events-none" />
                    </div>
                  </div>
                )}
              </div>

              {/* Provider Capabilities Note */}
              <div className="p-3 bg-[#F4F9F4] border border-[#C5E3D2] rounded-xl text-xs space-y-1.5">
                <div className="font-bold text-[#142820] flex items-center space-x-1.5">
                  <Info className="w-4 h-4 text-[#236B4F]" />
                  <span>
                    Capabilities for {selectedProvider === 'openserp' ? 'OpenSERP' : 'SerpApi'}:
                  </span>
                </div>
                {selectedProvider === 'openserp' ? (
                  <p className="text-[11px] text-[#4A6358]">
                    • Organic Web Search: <strong className="text-emerald-700">Supported</strong><br/>
                    • Google Maps & Geo-Grid 5x5: <strong className="text-rose-700">Not Supported</strong> (Geo-Grid coordinate search requires SerpApi)
                  </p>
                ) : (
                  <p className="text-[11px] text-[#4A6358]">
                    • Organic Web Search: <strong className="text-emerald-700">Supported</strong><br/>
                    • Google Maps & Geo-Grid 5x5: <strong className="text-emerald-700">Supported</strong> (Full coordinate search enabled)
                  </p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div className="text-[11px] text-[#587568] font-medium">
                  {serpConfig?.has_key ? (
                    <span className="text-emerald-700 font-semibold flex items-center space-x-1">
                      <Check className="w-3.5 h-3.5 inline" />
                      <span>Encrypted API key active for this organization ({serpConfig.masked_key})</span>
                    </span>
                  ) : (
                    <span>No API key currently configured for your organization.</span>
                  )}
                </div>

                <div className="flex items-center space-x-3">
                  <button
                    type="button"
                    onClick={handleTestSerpKey}
                    disabled={isTestingSerpKey}
                    className="btn-secondary-nature px-4 py-2 rounded-xl text-xs flex items-center space-x-2 font-bold"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 text-[#236B4F] ${isTestingSerpKey ? 'animate-spin' : ''}`} />
                    <span>{isTestingSerpKey ? 'Testing...' : 'Test Connection'}</span>
                  </button>

                  <button
                    type="submit"
                    disabled={isSavingSerpKey || !apiKeyInput.trim()}
                    className="btn-primary-nature px-5 py-2 rounded-xl text-xs font-bold shadow-xs hover:shadow-md transition-all flex items-center space-x-2"
                  >
                    <span>{isSavingSerpKey ? 'Saving Key...' : 'Save API Key'}</span>
                  </button>
                </div>
              </div>
            </form>

            {/* Diagnostic Information */}
            <div className="p-4 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-2 text-xs">
              <div className="flex items-center justify-between text-[#142820] font-bold">
                <span>Organization SERP Status</span>
                <span className="text-[11px] font-mono text-[#587568]">
                  {serpConfig?.last_tested_at ? `Last Tested: ${new Date(serpConfig.last_tested_at).toLocaleString()}` : 'Never Tested'}
                </span>
              </div>
              <p className="text-[11px] text-[#587568]">
                {serpConfig?.status_message || 'SERP credentials are encrypted at rest using AES-256 Fernet tokens and used exclusively for your organization.'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* General Project Settings Tab */}
      {activeTab === 'general' && (
        <div className="space-y-6">
          {successMsg && (
            <div className="p-4 rounded-xl bg-[#EAF2EA] border border-[#B8DFC9] text-[#142820] text-xs flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-[#236B4F] shrink-0" />
              <span className="font-semibold">{successMsg}</span>
            </div>
          )}

          {errorMsg && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span className="font-semibold">{errorMsg}</span>
            </div>
          )}

          {!activeProject ? (
            <EmptyState
              icon={Building2}
              badge="Settings"
              title="No Active Project Selected"
              description="Select a project from the top navigation to view or update metadata settings."
            />
          ) : (
            <form onSubmit={handleSave} className="card-nature p-6 space-y-6">
              <div className="border-b border-[#EBF2EB] pb-4">
                <h3 className="text-base font-extrabold text-[#142820] tracking-tight">
                  Project Configuration
                </h3>
                <p className="text-xs text-[#587568] mt-1">
                  Update your canonical project name, domain address, primary category, and location defaults.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="block text-xs font-bold text-[#142820] uppercase tracking-wider mb-1.5">
                    Business / Project Name
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#B8DFC9] bg-white text-[#142820] text-xs font-medium focus:ring-2 focus:ring-[#236B4F] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-[#142820] uppercase tracking-wider mb-1.5">
                    Canonical Website Domain
                  </label>
                  <input
                    type="text"
                    required
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#B8DFC9] bg-white text-[#142820] text-xs font-medium focus:ring-2 focus:ring-[#236B4F] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-[#142820] uppercase tracking-wider mb-1.5">
                    Primary Business Category
                  </label>
                  <input
                    type="text"
                    value={primaryCategory}
                    onChange={(e) => setPrimaryCategory(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#B8DFC9] bg-white text-[#142820] text-xs font-medium focus:ring-2 focus:ring-[#236B4F] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-[#142820] uppercase tracking-wider mb-1.5">
                    Target Country
                  </label>
                  <CountrySelector
                    value={country}
                    onChange={setCountry}
                  />
                </div>
              </div>

              <div className="flex items-center justify-end pt-4 border-t border-[#EBF2EB]">
                <button
                  type="submit"
                  disabled={isSaving}
                  className="btn-primary-nature px-5 py-2.5 rounded-xl text-xs font-bold shadow-xs hover:shadow-md transition-all flex items-center space-x-2"
                >
                  <span>{isSaving ? 'Saving Changes...' : 'Save Project Metadata'}</span>
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
};

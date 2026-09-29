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
  Check,
  Zap,
  CreditCard,
  Calendar,
  Clock,
  ExternalLink,
  ShieldCheck,
  XCircle,
  CheckCircle,
  TrendingUp,
  AlertTriangle
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import { ConnectionsView } from './ConnectionsView';
import { EmptyState } from '../components/ui/EmptyState';
import { StatusBadge } from '../components/ui/StatusBadge';
import api from '../api/client';
import { CountrySelector } from '../components/ui/CountrySelector';
import { getErrorMessage } from '../utils/error';

interface SERPCapabilities {
  organic_search: boolean;
  local_search: boolean;
  maps_search: boolean;
  coordinate_search: boolean;
  local_pack: boolean;
  reviews: boolean;
  geo_grid: boolean;
  desktop: boolean;
  mobile: boolean;
  location_targeting: boolean;
}

interface SERPAccountInfo {
  account_email?: string | null;
  account_id?: string | null;
  plan_name?: string | null;
  plan_id?: string | null;
  renewal_date?: string | null;
  status?: string | null;
  rate_limit?: {
    used?: number | null;
    limit?: number | null;
    unit?: string | null;
  } | null;
  extra_credits?: number | null;
  [key: string]: any;
}

interface SERPUsageInfo {
  model: string;
  used?: number | null;
  limit?: number | null;
  remaining?: number | null;
  percentage_used?: number | null;
  balance?: number | null;
  currency?: string | null;
  unit?: string | null;
  [key: string]: any;
}

interface SERPProviderMeta {
  provider_id: string;
  display_name: string;
  description: string;
  credential_schema: Record<string, {
    label: string;
    type: string;
    placeholder?: string;
    required: boolean;
    help_text?: string;
  }>;
  capabilities: SERPCapabilities;
  usage_model: string;
  supports_account_api: boolean;
}

interface SERPConfig {
  provider: string;
  provider_name: string;
  base_url?: string | null;
  auth_mode: string;
  has_key: boolean;
  masked_key: string | null;
  masked_credentials: Record<string, string>;
  connection_status: string;
  status_message: string;
  capabilities: SERPCapabilities;
  account_info: SERPAccountInfo;
  usage_info: SERPUsageInfo;
  last_tested_at: string | null;
  last_synced_at: string | null;
}

interface ScanAllowance {
  organization_id: number;
  year_month: string;
  used_scans: number;
  allowed_scans: number;
  remaining_scans: number;
  is_byo_serp: boolean;
  last_scan_at: string | null;
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
  const [providers, setProviders] = useState<SERPProviderMeta[]>([]);
  const [allowance, setAllowance] = useState<ScanAllowance | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>('serpapi');
  const [credentialInputs, setCredentialInputs] = useState<Record<string, string>>({});
  const [isSavingSerpKey, setIsSavingSerpKey] = useState(false);
  const [isTestingSerpKey, setIsTestingSerpKey] = useState(false);
  const [isRefreshingUsage, setIsRefreshingUsage] = useState(false);
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
      fetchAllowance();
    }
  }, [activeProject?.id, activeProject?.name, activeProject?.domain, activeProject?.primary_category, activeProject?.country]);

  // Load SERP providers and config on mount
  useEffect(() => {
    fetchProviders();
    fetchSerpConfig();
  }, []);

  const fetchProviders = async () => {
    try {
      const resp = await api.get('/serp/providers');
      setProviders(resp.data || []);
    } catch (err) {
      console.error('Failed to load SERP providers:', err);
    }
  };

  const fetchAllowance = async () => {
    if (!activeProject?.id) return;
    try {
      const resp = await api.get(`/projects/${activeProject.id}/scan-allowance`);
      setAllowance(resp.data);
    } catch {
      setAllowance(null);
    }
  };

  const fetchSerpConfig = async () => {
    try {
      const resp = await api.get('/serp/config');
      setSerpConfig(resp.data);
      if (resp.data?.provider) {
        setSelectedProvider(resp.data.provider);
      }
    } catch {
      setSerpConfig(null);
    }
  };

  const handleCredentialChange = (field: string, value: string) => {
    setCredentialInputs(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSaveSerpKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingSerpKey(true);
    setSerpResultMsg(null);
    setSerpResultError(null);

    try {
      const payload: any = {
        provider: selectedProvider,
        credentials: { ...credentialInputs }
      };
      if (credentialInputs['api_key']) payload.api_key = credentialInputs['api_key'];
      if (credentialInputs['base_url']) payload.base_url = credentialInputs['base_url'];

      const resp = await api.post('/serp/config', payload);
      setSerpConfig(resp.data);
      setCredentialInputs({});
      setSerpResultMsg('SERP provider configuration saved & synchronized successfully.');
      setTimeout(() => setSerpResultMsg(null), 4000);
    } catch (err: any) {
      setSerpResultError(getErrorMessage(err, 'Failed to save SERP provider configuration.'));
    } finally {
      setIsSavingSerpKey(false);
    }
  };

  const handleTestSerpKey = async () => {
    setIsTestingSerpKey(true);
    setSerpResultMsg(null);
    setSerpResultError(null);
    try {
      const payload: any = {
        provider: selectedProvider,
        credentials: { ...credentialInputs }
      };
      if (credentialInputs['api_key']) payload.api_key = credentialInputs['api_key'];
      if (credentialInputs['base_url']) payload.base_url = credentialInputs['base_url'];

      const resp = await api.post('/serp/test-connection', payload);

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

  const handleRefreshUsage = async () => {
    setIsRefreshingUsage(true);
    setSerpResultMsg(null);
    setSerpResultError(null);
    try {
      const resp = await api.post('/serp/refresh-usage');
      setSerpConfig(resp.data);
      setSerpResultMsg('Provider account usage and quotas updated successfully.');
      setTimeout(() => setSerpResultMsg(null), 4000);
    } catch (err: any) {
      setSerpResultError(getErrorMessage(err, 'Unable to refresh provider usage.'));
    } finally {
      setIsRefreshingUsage(false);
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

  const activeProviderMeta = providers.find(p => p.provider_id === selectedProvider) || {
    provider_id: selectedProvider,
    display_name: selectedProvider.toUpperCase(),
    description: '',
    credential_schema: { api_key: { label: 'API Key', type: 'password', required: true } },
    capabilities: {
      organic_search: true,
      local_search: true,
      maps_search: true,
      coordinate_search: true,
      local_pack: true,
      reviews: true,
      geo_grid: true,
      desktop: true,
      mobile: true,
      location_targeting: true
    },
    usage_model: 'monthly_search_quota',
    supports_account_api: true
  };

  const hasEnteredCredentials = Object.values(credentialInputs).some(v => v.trim().length > 0);

  return (
    <div className="max-w-5xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-[#142820] tracking-tight flex items-center space-x-2.5">
          <Settings className="w-6 h-6 text-[#236B4F]" />
          <span>Platform & Infrastructure Settings</span>
        </h1>
        <p className="text-xs text-[#587568] mt-1">
          Manage agency connections, Google multi-service integrations, organization SERP search providers, and project metadata.
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
          <span>SERP Search Provider</span>
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

      {/* SERP Search Provider Tab */}
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
                        : serpConfig?.connection_status === 'invalid_key' || serpConfig?.connection_status === 'invalid_credentials'
                        ? 'Invalid Credentials'
                        : serpConfig?.connection_status === 'quota_exceeded'
                        ? 'Quota Exceeded'
                        : 'Not Configured'
                    }
                  />
                </div>
                <p className="text-xs text-[#587568] mt-1">
                  Use your own {activeProviderMeta.display_name} account for keyword tracking, rankings and supported LocalLift scans. LocalLift does not charge markup on external SERP requests.
                </p>
              </div>
            </div>

            {/* Notification Messages */}
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

            {/* Account Information Panel (When Connected) */}
            {serpConfig?.connection_status === 'connected' && (
              <div className="p-5 rounded-2xl bg-gradient-to-br from-[#F4F9F4] to-[#EBF5EE] border border-[#B8DFC9] space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2.5">
                    <ShieldCheck className="w-5 h-5 text-[#236B4F]" />
                    <span className="text-xs font-black uppercase tracking-wider text-[#142820]">
                      Connected Provider: {serpConfig.provider_name || activeProviderMeta.display_name}
                    </span>
                    {serpConfig.account_info?.plan_name && (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-[#236B4F] text-white shadow-2xs">
                        {serpConfig.account_info.plan_name}
                      </span>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={handleRefreshUsage}
                    disabled={isRefreshingUsage}
                    className="px-3 py-1.5 rounded-xl bg-white border border-[#B8DFC9] hover:bg-[#EAF2EA] text-[11px] font-bold text-[#142820] flex items-center space-x-1.5 transition-all shadow-2xs"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 text-[#236B4F] ${isRefreshingUsage ? 'animate-spin' : ''}`} />
                    <span>{isRefreshingUsage ? 'Refreshing...' : 'Refresh Usage'}</span>
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                  {/* Quota / Balance Stats */}
                  {serpConfig.usage_info?.model === 'monthly_search_quota' && (
                    <>
                      <div className="bg-white/80 backdrop-blur-xs p-3 rounded-xl border border-[#DCE8DC]">
                        <div className="text-[10px] font-bold text-[#587568] uppercase">Monthly Allowance</div>
                        <div className="text-base font-black text-[#142820] mt-0.5">
                          {serpConfig.usage_info.limit?.toLocaleString() || 'Unlimited'} searches
                        </div>
                      </div>
                      <div className="bg-white/80 backdrop-blur-xs p-3 rounded-xl border border-[#DCE8DC]">
                        <div className="text-[10px] font-bold text-[#587568] uppercase">Searches Used</div>
                        <div className="text-base font-black text-[#236B4F] mt-0.5">
                          {serpConfig.usage_info.used?.toLocaleString() || 0}
                          {serpConfig.usage_info.percentage_used !== undefined && (
                            <span className="text-xs font-semibold text-[#587568] ml-1.5">
                              ({serpConfig.usage_info.percentage_used}%)
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="bg-white/80 backdrop-blur-xs p-3 rounded-xl border border-[#DCE8DC]">
                        <div className="text-[10px] font-bold text-[#587568] uppercase">Searches Remaining</div>
                        <div className={`text-base font-black mt-0.5 ${(serpConfig.usage_info.remaining || 0) > 0 ? 'text-emerald-700' : 'text-rose-600'}`}>
                          {serpConfig.usage_info.remaining?.toLocaleString() ?? '—'}
                        </div>
                      </div>
                    </>
                  )}

                  {serpConfig.usage_info?.model === 'account_balance' && (
                    <div className="bg-white/80 backdrop-blur-xs p-3 rounded-xl border border-[#DCE8DC] col-span-2">
                      <div className="text-[10px] font-bold text-[#587568] uppercase">Account Balance</div>
                      <div className="text-lg font-black text-emerald-700 mt-0.5">
                        ${serpConfig.usage_info.balance?.toFixed(2) ?? '0.00'} {serpConfig.usage_info.currency || 'USD'}
                      </div>
                    </div>
                  )}

                  {serpConfig.usage_info?.model === 'credits' && (
                    <>
                      <div className="bg-white/80 backdrop-blur-xs p-3 rounded-xl border border-[#DCE8DC]">
                        <div className="text-[10px] font-bold text-[#587568] uppercase">Credits Used</div>
                        <div className="text-base font-black text-[#142820] mt-0.5">
                          {serpConfig.usage_info.used?.toLocaleString() || 0}
                        </div>
                      </div>
                      <div className="bg-white/80 backdrop-blur-xs p-3 rounded-xl border border-[#DCE8DC]">
                        <div className="text-[10px] font-bold text-[#587568] uppercase">Credits Remaining</div>
                        <div className="text-base font-black text-emerald-700 mt-0.5">
                          {serpConfig.usage_info.remaining?.toLocaleString() ?? '—'}
                        </div>
                      </div>
                    </>
                  )}

                  {serpConfig.usage_info?.model === 'unavailable' && (
                    <div className="bg-white/80 backdrop-blur-xs p-3 rounded-xl border border-[#DCE8DC] col-span-2">
                      <div className="text-[10px] font-bold text-[#587568] uppercase">Usage Model</div>
                      <div className="text-xs font-bold text-[#142820] mt-0.5">
                        Self-hosted / unmetered. No external quota restrictions.
                      </div>
                    </div>
                  )}

                  {/* Renewal Date */}
                  <div className="bg-white/80 backdrop-blur-xs p-3 rounded-xl border border-[#DCE8DC]">
                    <div className="text-[10px] font-bold text-[#587568] uppercase">Renewal / Cycle Date</div>
                    <div className="text-xs font-bold text-[#142820] mt-1 flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 text-[#236B4F]" />
                      <span>{serpConfig.account_info?.renewal_date || 'Standard cycle'}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-[#587568] pt-1">
                  <span className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Last synced: {serpConfig.last_synced_at ? new Date(serpConfig.last_synced_at).toLocaleString() : 'Never'}</span>
                  </span>
                  {serpConfig.account_info?.account_email && (
                    <span>Account: {serpConfig.account_info.account_email}</span>
                  )}
                </div>
              </div>
            )}

            {/* Provider Configuration Form */}
            <form onSubmit={handleSaveSerpKey} className="space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Provider Selection */}
                <div>
                  <label className="block text-xs font-bold text-[#142820] uppercase tracking-wider mb-1.5">
                    SERP Search Provider
                  </label>
                  <select
                    value={selectedProvider}
                    onChange={(e) => {
                      setSelectedProvider(e.target.value);
                      setCredentialInputs({});
                    }}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-[#B8DFC9] bg-white text-[#142820] text-xs font-semibold focus:ring-2 focus:ring-[#236B4F] focus:outline-none"
                  >
                    {providers.map(p => (
                      <option key={p.provider_id} value={p.provider_id}>
                        {p.display_name} {p.provider_id === 'serpapi' ? '(Recommended Cloud Provider)' : ''}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Dynamic Credential Inputs based on selected provider schema */}
                {Object.entries(activeProviderMeta.credential_schema).map(([fieldName, fieldSchema]) => {
                  const isConfigured = serpConfig?.provider === selectedProvider && serpConfig?.has_key;
                  const maskedVal = serpConfig?.masked_credentials?.[fieldName] || serpConfig?.masked_key;

                  return (
                    <div key={fieldName}>
                      <label className="block text-xs font-bold text-[#142820] uppercase tracking-wider mb-1.5">
                        {fieldSchema.label} {fieldSchema.required && <span className="text-rose-600">*</span>}
                      </label>
                      <div className="relative">
                        <input
                          type={fieldSchema.type === 'password' ? 'password' : 'text'}
                          value={credentialInputs[fieldName] || ''}
                          onChange={(e) => handleCredentialChange(fieldName, e.target.value)}
                          placeholder={
                            isConfigured && maskedVal
                              ? `Configured (${maskedVal})`
                              : fieldSchema.placeholder || `Enter ${fieldSchema.label}`
                          }
                          className="w-full px-3.5 py-2.5 rounded-xl border border-[#B8DFC9] bg-white text-[#142820] text-xs font-mono font-medium focus:ring-2 focus:ring-[#236B4F] focus:outline-none pr-10"
                        />
                        {fieldSchema.type === 'password' && (
                          <Key className="w-4 h-4 text-[#587568] absolute right-3 top-3 pointer-events-none" />
                        )}
                      </div>
                      {fieldSchema.help_text && (
                        <p className="text-[10px] text-[#587568] mt-1">{fieldSchema.help_text}</p>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Provider Capabilities Grid */}
              <div className="p-4 bg-[#F4F9F4] border border-[#C5E3D2] rounded-xl text-xs space-y-2.5">
                <div className="font-bold text-[#142820] flex items-center justify-between">
                  <div className="flex items-center space-x-1.5">
                    <Info className="w-4 h-4 text-[#236B4F]" />
                    <span>Feature Capabilities for {activeProviderMeta.display_name}:</span>
                  </div>
                  <span className="text-[10px] font-semibold text-[#587568]">
                    Billing Model: {activeProviderMeta.usage_model.replace(/_/g, ' ').toUpperCase()}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 text-[11px]">
                  <div className="flex items-center space-x-1.5">
                    {activeProviderMeta.capabilities.organic_search ? (
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    )}
                    <span className={activeProviderMeta.capabilities.organic_search ? 'text-[#142820] font-medium' : 'text-slate-400'}>
                      Organic Search
                    </span>
                  </div>

                  <div className="flex items-center space-x-1.5">
                    {activeProviderMeta.capabilities.local_search ? (
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    )}
                    <span className={activeProviderMeta.capabilities.local_search ? 'text-[#142820] font-medium' : 'text-slate-400'}>
                      Local Pack
                    </span>
                  </div>

                  <div className="flex items-center space-x-1.5">
                    {activeProviderMeta.capabilities.maps_search ? (
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    )}
                    <span className={activeProviderMeta.capabilities.maps_search ? 'text-[#142820] font-medium' : 'text-slate-400'}>
                      Google Maps
                    </span>
                  </div>

                  <div className="flex items-center space-x-1.5">
                    {activeProviderMeta.capabilities.geo_grid ? (
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    )}
                    <span className={activeProviderMeta.capabilities.geo_grid ? 'text-[#142820] font-medium' : 'text-slate-400'}>
                      Geo-Grid 5x5
                    </span>
                  </div>

                  <div className="flex items-center space-x-1.5">
                    {activeProviderMeta.capabilities.location_targeting ? (
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    )}
                    <span className={activeProviderMeta.capabilities.location_targeting ? 'text-[#142820] font-medium' : 'text-slate-400'}>
                      Geo Targeting
                    </span>
                  </div>
                </div>

                {!activeProviderMeta.capabilities.geo_grid && (
                  <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-[11px] text-amber-900 flex items-start gap-2 mt-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <span>
                      <strong>Geo-Grid Unavailable:</strong> {activeProviderMeta.display_name} does not support coordinate-based Google Maps searches required for LocalLift Geo-Grid scans. Rank tracking and audits remain active.
                    </span>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div className="text-[11px] text-[#587568] font-medium">
                  {serpConfig?.has_key && serpConfig.provider === selectedProvider ? (
                    <span className="text-emerald-700 font-semibold flex items-center space-x-1">
                      <Check className="w-3.5 h-3.5 inline" />
                      <span>Encrypted credentials active for {activeProviderMeta.display_name}</span>
                    </span>
                  ) : (
                    <span>Enter your {activeProviderMeta.display_name} credentials to authenticate.</span>
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
                    disabled={isSavingSerpKey || (!hasEnteredCredentials && serpConfig?.provider === selectedProvider)}
                    className="btn-primary-nature px-5 py-2 rounded-xl text-xs font-bold shadow-xs hover:shadow-md transition-all flex items-center space-x-2"
                  >
                    <span>{isSavingSerpKey ? 'Saving...' : 'Save Credentials'}</span>
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

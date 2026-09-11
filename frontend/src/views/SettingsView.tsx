import React, { useState, useEffect } from 'react';
import {
  Settings,
  Link2,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Building2,
  Globe,
  Tag,
  Shield,
  Layers,
  Sparkles,
  Info
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import { ConnectionsView } from './ConnectionsView';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';
import { getErrorMessage } from '../utils/error';

export const SettingsView: React.FC = () => {
  const { user } = useAuth();
  const { activeProject, refreshProjects } = useProject();
  const [activeTab, setActiveTab] = useState<'general' | 'connections'>('connections');

  // Form State
  const [name, setName] = useState('');
  const [domain, setDomain] = useState('');
  const [primaryCategory, setPrimaryCategory] = useState('');
  const [country, setCountry] = useState('United States');

  // Request State
  const [isSaving, setIsSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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
      const resp = await api.put(`/projects/${activeProject.id}`, {
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
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
          <Settings className="w-6 h-6 text-purple-600" />
          <span>Platform & Organization Settings</span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Manage agency connections, Google multi-service integrations, project details, and audit execution preferences.
        </p>
      </div>

      {/* Settings Navigation Tabs */}
      <div className="flex items-center space-x-2 border-b border-slate-200 pb-2 text-xs font-bold">
        <button
          onClick={() => setActiveTab('connections')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition-all ${
            activeTab === 'connections'
              ? 'bg-purple-50 text-purple-700 border border-purple-200 shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <Link2 className="w-4 h-4" />
          <span>Connections & Integrations</span>
        </button>

        <button
          onClick={() => setActiveTab('general')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition-all ${
            activeTab === 'general'
              ? 'bg-purple-50 text-purple-700 border border-purple-200 shadow-sm'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <Sliders className="w-4 h-4" />
          <span>General & Project Settings</span>
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'connections' && <ConnectionsView />}

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
                <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center space-x-2 text-xs text-emerald-800 animate-fade-in">
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                  <span className="flex-1 font-medium">{successMsg}</span>
                  <button onClick={() => setSuccessMsg(null)} aria-label="Dismiss notification" className="text-emerald-500 hover:text-emerald-800 text-xs font-bold">✕</button>
                </div>
              )}

              {errorMsg && (
                <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-2 text-xs text-rose-700 animate-fade-in">
                  <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
                  <span className="flex-1 font-medium">{errorMsg}</span>
                  <button onClick={() => setErrorMsg(null)} aria-label="Dismiss error notification" className="text-rose-500 hover:text-rose-800 text-xs font-bold">✕</button>
                </div>
              )}

              <div className="card-vibrant p-6 space-y-6 bg-white border border-slate-200 rounded-2xl shadow-xs">
                <form onSubmit={handleSave} className="space-y-6 text-xs">
                  <div>
                    <h3 className="text-sm font-black text-slate-900 mb-1 flex items-center space-x-2">
                      <Building2 className="w-4 h-4 text-purple-600" />
                      <span>Active Project Configuration</span>
                    </h3>
                    <p className="text-[11px] text-slate-500 mb-4">
                      Update metadata, primary business taxonomy, and domain bindings for the current project.
                    </p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="text-slate-700 font-bold block mb-1">Active Project Name</label>
                        <input
                          type="text"
                          required
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          placeholder="e.g. Apex Electrical Services"
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                        />
                      </div>

                      <div>
                        <label className="text-slate-700 font-bold block mb-1">Target Website Domain</label>
                        <input
                          type="text"
                          required
                          value={domain}
                          onChange={(e) => setDomain(e.target.value)}
                          placeholder="e.g. apexelectrical.com.au"
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                        />
                      </div>

                      <div>
                        <label className="text-slate-700 font-bold block mb-1">Primary Business Category</label>
                        <input
                          type="text"
                          value={primaryCategory}
                          onChange={(e) => setPrimaryCategory(e.target.value)}
                          placeholder="e.g. Electrician, Plumber, Dental Clinic"
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                        />
                      </div>

                      <div>
                        <label className="text-slate-700 font-bold block mb-1">Target Country</label>
                        <input
                          type="text"
                          value={country}
                          onChange={(e) => setCountry(e.target.value)}
                          placeholder="e.g. United States, Australia, United Kingdom"
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-slate-200">
                    <h3 className="text-sm font-black text-slate-900 mb-1 flex items-center space-x-2">
                      <Shield className="w-4 h-4 text-purple-600" />
                      <span>Account & Organization Reference</span>
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3">
                      <div>
                        <label className="text-slate-700 font-bold block mb-1">Account Email</label>
                        <input
                          type="email"
                          disabled
                          value={user?.email || ''}
                          className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-500 font-medium cursor-not-allowed"
                        />
                      </div>
                      <div>
                        <label className="text-slate-700 font-bold block mb-1">User Role</label>
                        <input
                          type="text"
                          disabled
                          value={user?.role || 'Admin'}
                          className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-500 font-medium cursor-not-allowed"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Honest Audit Engine & Architecture Information */}
                  <div className="pt-4 border-t border-slate-200">
                    <h3 className="text-sm font-black text-slate-900 mb-1 flex items-center space-x-2">
                      <Layers className="w-4 h-4 text-purple-600" />
                      <span>Audit & Rank Tracking Engine Status</span>
                    </h3>
                    <p className="text-[11px] text-slate-500 mb-3">
                      LocalLift executes live on-demand website crawling and SERP ranking scans with direct audit verifications.
                    </p>

                    <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5 text-[11px] text-slate-700">
                      <div className="flex items-start space-x-2.5">
                        <Info className="w-4 h-4 text-purple-600 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold text-slate-900">On-Demand Engine: </span>
                          <span>
                            Technical website crawls, NAP consistency audits, Schema validations, and Geo-Grid SERP scans run on-demand via the respective audit tools.
                          </span>
                        </div>
                      </div>
                      <div className="flex items-start space-x-2.5">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold text-slate-900">Data Integrity Safeguard: </span>
                          <span>
                            No fabricated fallback metrics or mock rank scores are used. Incomplete audits honestly report an awaiting status until a live audit is executed.
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-end pt-4 border-t border-slate-200">
                    <button
                      type="submit"
                      disabled={isSaving}
                      className="px-6 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all disabled:opacity-50 flex items-center space-x-2"
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

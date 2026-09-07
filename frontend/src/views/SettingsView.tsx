import React, { useState } from 'react';
import { Settings, Link2, Sliders, CheckCircle2, Store } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import { ConnectionsView } from './ConnectionsView';

export const SettingsView: React.FC = () => {
  const { user } = useAuth();
  const { activeProject } = useProject();
  const [activeTab, setActiveTab] = useState<'general' | 'connections'>('connections');
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
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
          Manage agency connections, Google multi-service integrations, scheduled audits, and account preferences.
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
          <span>General & Audit Schedules</span>
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'connections' && <ConnectionsView />}

      {activeTab === 'general' && (
        <div className="card-vibrant p-6 space-y-6">
          <form onSubmit={handleSave} className="space-y-5 text-xs">
            <div>
              <h3 className="text-sm font-black text-slate-900 mb-3">Organization & Project Details</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-slate-700 font-bold block mb-1">Active Project Name</label>
                  <input
                    type="text"
                    defaultValue={activeProject?.name || ''}
                    placeholder="e.g. My Business"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                  />
                </div>
                <div>
                  <label className="text-slate-700 font-bold block mb-1">Account Email</label>
                  <input
                    type="email"
                    disabled
                    defaultValue={user?.email || ''}
                    placeholder="user@example.com"
                    className="w-full bg-slate-100 border border-slate-200 rounded-xl p-2.5 text-slate-500 font-medium"
                  />
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-200">
              <h3 className="text-sm font-black text-slate-900 mb-3">Automated Scheduled Audits</h3>
              <div className="space-y-2.5">
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input type="checkbox" defaultChecked className="rounded border-slate-300 text-purple-600 focus:ring-purple-500" />
                  <span className="text-slate-800 font-medium">Daily local keyword rank tracking and GBP change monitoring</span>
                </label>
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input type="checkbox" defaultChecked className="rounded border-slate-300 text-purple-600 focus:ring-purple-500" />
                  <span className="text-slate-800 font-medium">Weekly automated website technical crawl & schema validation</span>
                </label>
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input type="checkbox" defaultChecked className="rounded border-slate-300 text-purple-600 focus:ring-purple-500" />
                  <span className="text-slate-800 font-medium">Monthly executive performance PDF report compilation</span>
                </label>
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-slate-200">
              {saved ? (
                <span className="text-xs text-emerald-700 font-bold flex items-center space-x-1">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>Settings saved successfully</span>
                </span>
              ) : <span />}
              <button
                type="submit"
                className="px-6 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all"
              >
                Save Configuration
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};


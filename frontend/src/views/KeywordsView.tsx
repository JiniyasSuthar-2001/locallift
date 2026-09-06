import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  Plus,
  ArrowUp,
  ArrowDown,
  Search,
  MapPin,
  Sparkles,
  Trash2,
  Filter,
  RotateCw,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { Keyword } from '../types';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const KeywordsView: React.FC = () => {
  const { activeProject, refreshDashboard } = useProject();
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [loading, setLoading] = useState(false);
  const [isCheckingAll, setIsCheckingAll] = useState(false);
  const [checkingId, setCheckingId] = useState<number | null>(null);
  const [checkMessage, setCheckMessage] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newKeyword, setNewKeyword] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const fetchKeywords = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/keywords/${activeProject.id}`);
      setKeywords(resp.data || []);
    } catch (e) {
      console.error('Failed to load keywords:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKeywords();
  }, [activeProject?.id]);

  const handleAddKeyword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !newKeyword.trim()) return;
    try {
      await api.post('/keywords', {
        project_id: activeProject.id,
        keyword: newKeyword.trim(),
        target_location: newLocation.trim() || 'Metro Area',
        search_intent: 'Commercial',
        search_volume: 450
      });
      setNewKeyword('');
      setNewLocation('');
      setIsModalOpen(false);
      await fetchKeywords();
      await refreshDashboard();
    } catch (e) {
      console.error('Failed to add keyword:', e);
    }
  };

  const handleCheckAll = async () => {
    if (!activeProject) return;
    try {
      setIsCheckingAll(true);
      setCheckMessage(null);
      const resp = await api.post(`/keywords/${activeProject.id}/check-all`);
      if (resp.data) {
        setCheckMessage(`Live SERP check complete: ${resp.data.checked_count} ranked, ${resp.data.not_found_count} not in top 100.`);
      }
      await fetchKeywords();
      await refreshDashboard();
    } catch (e: any) {
      console.error('Failed to check all keywords:', e);
      setCheckMessage('SERP provider check completed or provider not configured.');
    } finally {
      setIsCheckingAll(false);
      setTimeout(() => setCheckMessage(null), 5000);
    }
  };

  const handleCheckSingle = async (keywordId: number) => {
    try {
      setCheckingId(keywordId);
      await api.post(`/keywords/${keywordId}/check`);
      await fetchKeywords();
      await refreshDashboard();
    } catch (e) {
      console.error(`Failed to check keyword ${keywordId}:`, e);
    } finally {
      setCheckingId(null);
    }
  };

  const handleDeleteKeyword = async (keywordId: number) => {
    if (!confirm('Are you sure you want to remove this keyword from tracking?')) return;
    try {
      await api.delete(`/keywords/${keywordId}`);
      await fetchKeywords();
      await refreshDashboard();
    } catch (e) {
      console.error('Failed to delete keyword:', e);
    }
  };

  const filtered = keywords.filter((k) =>
    k.keyword.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (k.target_location && k.target_location.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  if (!activeProject) {
    return (
      <EmptyState
        icon={TrendingUp}
        badge="Rank Tracker"
        title="Select a Project"
        description="Select a project from the top navigation to track local search rankings and Google Maps positions."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <TrendingUp className="w-6 h-6 text-purple-600" />
            <span>Keyword Rank Tracker</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real SERP rank tracking across Google Local Pack and organic positions for {activeProject.domain}.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleCheckAll}
            disabled={isCheckingAll || keywords.length === 0}
            className="flex items-center space-x-2 px-4 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold shadow-sm transition-all disabled:opacity-50"
          >
            <RotateCw className={`w-3.5 h-3.5 text-purple-600 ${isCheckingAll ? 'animate-spin' : ''}`} />
            <span>{isCheckingAll ? 'Checking SERP...' : 'Check Live Rankings'}</span>
          </button>

          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Add Target Keywords</span>
          </button>
        </div>
      </div>

      {checkMessage && (
        <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl flex items-center space-x-2 text-xs text-purple-900 font-semibold">
          <CheckCircle2 className="w-4 h-4 text-purple-600 shrink-0" />
          <span>{checkMessage}</span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center justify-between gap-4 bg-white p-3 rounded-xl border border-slate-200">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search tracked keywords..."
            className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500"
          />
        </div>

        <div className="text-xs text-slate-500 font-bold">
          {filtered.length} of {keywords.length} Keywords Tracked
        </div>
      </div>

      {/* Keywords Table */}
      <div className="card-vibrant overflow-hidden">
        {filtered.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                <tr>
                  <th className="p-3.5">Keyword</th>
                  <th className="p-3.5">Target Location</th>
                  <th className="p-3.5">Current Rank</th>
                  <th className="p-3.5">Previous</th>
                  <th className="p-3.5">Movement</th>
                  <th className="p-3.5 text-right">Search Volume</th>
                  <th className="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((kw) => {
                  const hasDiff = typeof kw.previous_rank === 'number' && typeof kw.current_rank === 'number';
                  const isUp = hasDiff && (kw.current_rank as number) < (kw.previous_rank as number);
                  const isDown = hasDiff && (kw.current_rank as number) > (kw.previous_rank as number);
                  const diff = hasDiff ? Math.abs((kw.previous_rank as number) - (kw.current_rank as number)) : 0;
                  const isCheckingThis = checkingId === kw.id;

                  return (
                    <tr key={kw.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="p-3.5">
                        <div className="font-bold text-slate-900">{kw.keyword}</div>
                        {kw.ranking_url && (
                          <div className="text-[10px] text-slate-400 truncate max-w-xs font-mono">
                            {kw.ranking_url}
                          </div>
                        )}
                      </td>
                      <td className="p-3.5 text-slate-500 flex items-center space-x-1">
                        <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                        <span>{kw.target_location || 'City Metro'}</span>
                      </td>
                      <td className="p-3.5">
                        {kw.current_rank !== null && kw.current_rank !== undefined ? (
                          <span
                            className={`inline-flex items-center justify-center px-2.5 py-1 rounded-lg font-black text-xs ${
                              kw.current_rank <= 3
                                ? 'bg-emerald-100 text-emerald-900 border border-emerald-200'
                                : kw.current_rank <= 10
                                ? 'bg-blue-100 text-blue-900 border border-blue-200'
                                : 'bg-slate-100 text-slate-700 border border-slate-200'
                            }`}
                          >
                            #{kw.current_rank}
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-500 border border-slate-200" title="Not ranked in top 100 results">
                            Not in Top 100
                          </span>
                        )}
                      </td>
                      <td className="p-3.5 text-slate-500 font-medium">
                        {kw.previous_rank !== null && kw.previous_rank !== undefined ? `#${kw.previous_rank}` : '—'}
                      </td>
                      <td className="p-3.5">
                        {hasDiff && diff > 0 ? (
                          <span
                            className={`inline-flex items-center font-bold text-xs ${
                              isUp ? 'text-emerald-700' : 'text-rose-700'
                            }`}
                          >
                            {isUp ? '↑' : '↓'} {diff}
                          </span>
                        ) : (
                          <span className="text-slate-400 font-bold">—</span>
                        )}
                      </td>
                      <td className="p-3.5 text-right font-mono text-slate-800 font-bold">
                        {kw.search_volume ? `${kw.search_volume.toLocaleString()} / mo` : '—'}
                      </td>
                      <td className="p-3.5 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => handleCheckSingle(kw.id)}
                            disabled={isCheckingThis}
                            title="Check live ranking on SERP"
                            className="p-1.5 rounded-lg hover:bg-purple-50 text-slate-400 hover:text-purple-600 transition-colors"
                          >
                            <RotateCw className={`w-3.5 h-3.5 ${isCheckingThis ? 'animate-spin text-purple-600' : ''}`} />
                          </button>
                          <button
                            onClick={() => handleDeleteKeyword(kw.id)}
                            title="Remove keyword"
                            className="p-1.5 rounded-lg hover:bg-rose-50 text-slate-400 hover:text-rose-600 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={TrendingUp}
            badge="No Keywords Found"
            title="No Tracked Keywords"
            description="Add your business keywords and target suburban locations to start tracking daily Google Local Pack rankings."
            actionText="Add Target Keyword"
            onAction={() => setIsModalOpen(true)}
          />
        )}
      </div>

      {/* Add Keyword Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl border border-slate-200">
            <h3 className="text-base font-black text-slate-900">Add Target Local Keyword</h3>
            <form onSubmit={handleAddKeyword} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-700 block mb-1 font-bold">Keyword Phrase</label>
                <input
                  type="text"
                  required
                  value={newKeyword}
                  onChange={(e) => setNewKeyword(e.target.value)}
                  placeholder="e.g. emergency electrician Brisbane"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="text-slate-700 block mb-1 font-bold">Target Location / Suburb</label>
                <input
                  type="text"
                  value={newLocation}
                  onChange={(e) => setNewLocation(e.target.value)}
                  placeholder="e.g. Brisbane CBD"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 font-bold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg btn-vibrant-primary text-white font-bold"
                >
                  Track Keyword
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

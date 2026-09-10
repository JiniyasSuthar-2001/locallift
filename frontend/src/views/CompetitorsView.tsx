import React, { useState, useEffect } from 'react';
import {
  Flame,
  Plus,
  TrendingUp,
  Star,
  ExternalLink,
  Shield,
  Sparkles,
  Trash2
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { Competitor } from '../types';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const CompetitorsView: React.FC = () => {
  const { activeProject } = useProject();
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [domain, setDomain] = useState('');

  const fetchCompetitors = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/local-seo/competitors/${activeProject.id}`);
      setCompetitors(resp.data || []);
    } catch (e) {
      console.error('Failed to load competitors:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCompetitors();
  }, [activeProject?.id]);

  const handleAddCompetitor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !name.trim()) return;
    try {
      await api.post('/local-seo/competitors', {
        project_id: activeProject.id,
        name: name.trim(),
        domain: domain.trim() || undefined,
        rating: 0.0,
        reviews_count: 0
      });
      setName('');
      setDomain('');
      setIsModalOpen(false);
      await fetchCompetitors();
    } catch (e) {
      console.error('Failed to add competitor:', e);
    }
  };

  const handleDeleteCompetitor = async (competitorId: number) => {
    try {
      await api.delete(`/local-seo/competitors/${competitorId}`);
      setCompetitors((prev) => prev.filter((c) => c.id !== competitorId));
    } catch (e) {
      console.error('Failed to delete competitor:', e);
    }
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={Flame}
        badge="Competitor Benchmark"
        title="Select a Project"
        description="Select a business project to benchmark local rankings, review volume, and domain authority against nearby competitors."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <Flame className="w-6 h-6 text-purple-600" />
            <span>Local Competitor Benchmarking</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Compare Google Maps Local Pack share, review volume, and domain authority against key local competitors.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md self-start transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Add Competitor</span>
        </button>
      </div>

      {/* Competitor Comparison Grid */}
      {competitors.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {competitors.map((comp) => (
            <div
              key={comp.id}
              className="card-vibrant p-5 space-y-4 transition-all relative group"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-extrabold text-slate-900 text-sm">{comp.name}</h3>
                  {comp.domain && (
                    <a
                      href={`https://${comp.domain}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-purple-700 hover:underline flex items-center space-x-1 font-mono mt-0.5"
                    >
                      <span>{comp.domain}</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  )}
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-800 text-[10px] font-bold border border-purple-200">
                    Tracked
                  </span>
                  <button
                    onClick={() => handleDeleteCompetitor(comp.id)}
                    title="Remove competitor"
                    className="p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-[10px] text-slate-500 font-bold block">Avg Maps Rank</span>
                  <span className="text-lg font-black text-slate-900 mt-0.5 block">
                    #{comp.avg_maps_rank ? comp.avg_maps_rank.toFixed(1) : '—'}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <span className="text-[10px] text-slate-500 font-bold block">Reviews & Rating</span>
                  <span className="text-lg font-black text-amber-500 mt-0.5 block">
                    {comp.rating !== null && comp.rating !== undefined ? `${comp.rating} ★` : '—'}{' '}
                    <span className="text-xs text-slate-500 font-normal">({comp.reviews_count ?? (comp as any).total_reviews ?? 0})</span>
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Flame}
          badge="No Competitors"
          title="No Competitors Configured"
          description="Add nearby businesses in your industry to monitor their Google Maps rank movements and review acquisition rates."
          actionText="Add Target Competitor"
          onAction={() => setIsModalOpen(true)}
        />
      )}

      {/* Add Competitor Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl border border-slate-200">
            <h3 className="text-base font-black text-slate-900">Add Local Competitor</h3>
            <form onSubmit={handleAddCompetitor} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-700 block mb-1 font-bold">Business Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Brisbane Elite Electricians"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="text-slate-700 block mb-1 font-bold">Website Domain</label>
                <input
                  type="text"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  placeholder="e.g. brisbaneeliteelectricians.com.au"
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
                  Save Competitor
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

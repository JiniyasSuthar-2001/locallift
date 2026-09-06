import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Plus,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Clock,
  RotateCw,
  Sparkles
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { Citation } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const CitationsView: React.FC = () => {
  const { activeProject } = useProject();
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [directoryName, setDirectoryName] = useState('');
  const [listingUrl, setListingUrl] = useState('');
  const [napStatus, setNapStatus] = useState('match');

  const fetchCitations = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/local-seo/citations/${activeProject.id}`);
      setCitations(resp.data || []);
    } catch (e) {
      console.error('Failed to load citations:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCitations();
  }, [activeProject?.id]);

  const handleAddCitation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !directoryName.trim()) return;
    try {
      await api.post('/local-seo/citations', {
        project_id: activeProject.id,
        directory_name: directoryName.trim(),
        listing_url: listingUrl.trim() || undefined,
        nap_status: napStatus,
        domain_authority: 50
      });
      setDirectoryName('');
      setListingUrl('');
      setIsModalOpen(false);
      await fetchCitations();
    } catch (e) {
      console.error('Failed to add citation:', e);
    }
  };

  const matchingCount = citations.filter(c => c.nap_status === 'match').length;

  if (!activeProject) {
    return (
      <EmptyState
        icon={BookOpen}
        badge="Citations"
        title="Select a Project"
        description="Select a business project to audit local directory citations, YellowPages, Yelp, and Apple Maps listings."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <BookOpen className="w-6 h-6 text-purple-600" />
            <span>Local Citations & Directory Distribution</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Track business listings across core directories, data aggregators, and map networks for {activeProject.domain}.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md self-start transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Add Directory Citation</span>
        </button>
      </div>

      {/* Overview Stat Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card-vibrant p-4 space-y-1">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">Tracked Directories</span>
          <div className="text-2xl font-black text-slate-900">{citations.length}</div>
          <span className="text-[11px] text-slate-500 font-medium">Core platforms scanned</span>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">Matching Listings</span>
          <div className="text-2xl font-black text-emerald-700">{matchingCount}</div>
          <span className="text-[11px] text-slate-500 font-medium">100% NAP verification</span>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">Citation Consistency</span>
          <div className="text-2xl font-black text-purple-700">
            {citations.length > 0 ? Math.round((matchingCount / citations.length) * 100) : 0}%
          </div>
          <span className="text-[11px] text-purple-900 font-semibold">Directory trust score</span>
        </div>
      </div>

      {/* Citations Table */}
      <div className="card-vibrant overflow-hidden">
        {citations.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                <tr>
                  <th className="p-3.5">Directory / Platform</th>
                  <th className="p-3.5">Domain Authority</th>
                  <th className="p-3.5">NAP Status</th>
                  <th className="p-3.5">Listing URL</th>
                  <th className="p-3.5">Last Checked</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {citations.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold text-slate-900">{c.directory_name}</td>
                    <td className="p-3.5">
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[10px] font-bold">
                        DA {c.domain_authority}
                      </span>
                    </td>
                    <td className="p-3.5">
                      <StatusBadge status={c.nap_status || 'missing'} />
                    </td>
                    <td className="p-3.5 max-w-xs truncate">
                      {c.listing_url ? (
                        <a
                          href={c.listing_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-purple-700 hover:underline flex items-center font-mono font-medium truncate"
                        >
                          <span className="truncate">{c.listing_url}</span>
                          <ExternalLink className="w-2.5 h-2.5 ml-1 shrink-0" />
                        </a>
                      ) : (
                        <span className="text-slate-400 font-medium">Unclaimed / Missing</span>
                      )}
                    </td>
                    <td className="p-3.5 text-slate-500 font-mono">
                      {new Date(c.last_checked_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={BookOpen}
            badge="No Citations"
            title="No Directory Citations Added"
            description="Add your business directory listings from Yelp, YellowPages, TrueLocal, and Apple Maps to monitor NAP accuracy."
            actionText="Add First Citation"
            onAction={() => setIsModalOpen(true)}
          />
        )}
      </div>

      {/* Add Citation Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl border border-slate-200">
            <h3 className="text-base font-black text-slate-900">Add Directory Citation</h3>
            <form onSubmit={handleAddCitation} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-700 block mb-1 font-bold">Directory Name</label>
                <input
                  type="text"
                  required
                  value={directoryName}
                  onChange={(e) => setDirectoryName(e.target.value)}
                  placeholder="e.g. YellowPages Australia"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="text-slate-700 block mb-1 font-bold">Listing URL</label>
                <input
                  type="url"
                  value={listingUrl}
                  onChange={(e) => setListingUrl(e.target.value)}
                  placeholder="https://..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="text-slate-700 block mb-1 font-bold">NAP Status</label>
                <select
                  value={napStatus}
                  onChange={(e) => setNapStatus(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium cursor-pointer"
                >
                  <option value="match">Match (100% Consistent)</option>
                  <option value="mismatch">Mismatch (Needs Update)</option>
                  <option value="missing">Missing / Unclaimed</option>
                </select>
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
                  Save Citation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

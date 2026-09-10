import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  Phone,
  MapPin,
  Building,
  Sparkles
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { NAPRecord } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const NAPConsistencyView: React.FC = () => {
  const { activeProject } = useProject();
  const [napRecord, setNapRecord] = useState<NAPRecord | null>(null);
  const [citations, setCitations] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchNAPData = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const [napResp, citResp] = await Promise.allSettled([
        api.get(`/local-seo/nap/${activeProject.id}`),
        api.get(`/local-seo/citations/${activeProject.id}`)
      ]);
      if (napResp.status === 'fulfilled') {
        setNapRecord(napResp.value.data);
      }
      if (citResp.status === 'fulfilled') {
        setCitations(Array.isArray(citResp.value.data) ? citResp.value.data : []);
      }
    } catch (e) {
      console.error('Failed to load NAP records:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNAPData();
  }, [activeProject?.id]);

  const cleanCitations = citations.filter(c => c.nap_status === 'consistent' || c.nap_status === 'match').length;
  const consistencyPct = napRecord?.nap_score ?? (citations.length > 0 ? Math.round((cleanCitations / citations.length) * 100) : (activeProject?.citations_score ?? null));

  if (!activeProject) {
    return (
      <EmptyState
        icon={ShieldCheck}
        badge="NAP Consistency"
        title="Select a Project"
        description="Select a business project to audit Name, Address, and Phone consistency across web directories."
      />
    );
  }

  const primaryLocation = activeProject.locations && activeProject.locations.length > 0 ? activeProject.locations[0] : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <ShieldCheck className="w-6 h-6 text-purple-600" />
            <span>NAP Consistency & Discrepancy Monitor</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Detect Name, Address, and Phone number mismatches between your canonical records and external web directories.
          </p>
        </div>
      </div>

      {/* Canonical Reference Card */}
      <div className="card-vibrant p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <span className="text-xs font-black uppercase tracking-wider text-purple-700">
            Canonical Business Information (Ground Truth)
          </span>
          <span className="text-xs font-bold text-emerald-700 flex items-center space-x-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Master Profile</span>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs">
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1">Legal Name</span>
            <span className="font-extrabold text-slate-900 text-sm">{activeProject.name}</span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1">Target Domain</span>
            <span className="font-mono text-slate-800 font-semibold">{activeProject.domain}</span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1">Canonical Phone</span>
            <span className="font-mono text-slate-800 font-semibold">{primaryLocation?.phone || 'Configured in Location'}</span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1">NAP Uniformity</span>
            <span className="font-black text-purple-700 text-sm">
              {consistencyPct !== null && consistencyPct !== undefined ? `${consistencyPct}% Consistent` : 'Not yet checked'}
            </span>
          </div>
        </div>
      </div>

      {/* NAP Audit Table */}
      <div className="card-vibrant overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-extrabold text-slate-900 tracking-tight">
            Directory Discrepancy Audit Log
          </h3>
          <span className="text-xs text-slate-500 font-bold">
            {cleanCitations} of {citations.length} Clean Listings
          </span>
        </div>

        {citations.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                <tr>
                  <th className="p-3.5">Source / Platform</th>
                  <th className="p-3.5">Listed Business Name</th>
                  <th className="p-3.5">Listed Address</th>
                  <th className="p-3.5">Listed Phone</th>
                  <th className="p-3.5">Audit Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {citations.map((r) => {
                  const isMatch = r.nap_status === 'consistent' || r.nap_status === 'match';
                  return (
                    <tr key={r.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="p-3.5 font-bold text-slate-900">{r.source_name || r.directory_name || 'Directory'}</td>
                      <td className="p-3.5 text-slate-700">{r.found_name || r.listed_name || activeProject.name}</td>
                      <td className="p-3.5 text-slate-700">{r.found_address || r.listed_address || primaryLocation?.address || 'Listed on Directory'}</td>
                      <td className="p-3.5 font-mono text-slate-700">{r.found_phone || r.listed_phone || primaryLocation?.phone || '—'}</td>
                      <td className="p-3.5">
                        <StatusBadge status={isMatch ? 'Consistent' : 'Mismatch'} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={ShieldCheck}
            badge="NAP Verified"
            title="No Directory Discrepancies"
            description="Your business Name, Address, and Phone number are aligned across all tracked directories."
          />
        )}
      </div>
    </div>
  );
};

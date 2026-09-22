import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  Phone,
  MapPin,
  Building,
  Globe,
  XCircle,
  HelpCircle
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

interface FieldComparison {
  expected: string | null;
  found: string | null;
  status: 'match' | 'mismatch' | 'missing' | 'not_evaluated';
}

interface NAPSourceComparison {
  source_type: string;
  source_name: string;
  listing_url: string | null;
  provenance: string;
  is_consistent: boolean;
  name: FieldComparison;
  phone: FieldComparison;
  address: FieldComparison;
  website: FieldComparison;
}

interface NAPComparisonResponse {
  project_id: number;
  canonical_profile: {
    business_name: string;
    website: string | null;
    primary_phone: string | null;
    primary_address: string | null;
    city: string | null;
    state: string | null;
    postal_code: string | null;
    verification_status: string;
  };
  total_sources_evaluated: number;
  consistent_sources_count: number;
  mismatch_sources_count: number;
  nap_consistency_pct: number | null;
  comparisons: NAPSourceComparison[];
}

export const NAPConsistencyView: React.FC = () => {
  const { activeProject } = useProject();
  const [data, setData] = useState<NAPComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchNAPComparison = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/local-seo/nap/comparison/${activeProject.id}`);
      setData(resp.data);
    } catch (e) {
      console.error('Failed to load NAP comparison data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNAPComparison();
  }, [activeProject?.id]);

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

  const profile = data?.canonical_profile;
  const consistencyPct = data?.nap_consistency_pct;
  const comparisons = data?.comparisons || [];
  const totalEvaluated = data?.total_sources_evaluated ?? 0;
  const consistentCount = data?.consistent_sources_count ?? 0;

  const renderFieldCell = (field: FieldComparison, icon: React.ReactNode) => {
    let badgeColor = 'bg-slate-100 text-slate-700';
    if (field.status === 'match') badgeColor = 'bg-emerald-50 text-emerald-700 border-emerald-200';
    else if (field.status === 'mismatch') badgeColor = 'bg-rose-50 text-rose-700 border-rose-200';
    else if (field.status === 'missing') badgeColor = 'bg-amber-50 text-amber-700 border-amber-200';

    return (
      <div className="space-y-1">
        <div className="flex items-center space-x-1.5">
          {icon}
          <span className={`text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded border ${badgeColor}`}>
            {field.status}
          </span>
        </div>
        <div className="text-xs text-slate-800 font-medium">
          {field.found ? field.found : <span className="text-slate-400 italic font-normal">Not detected</span>}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <ShieldCheck className="w-6 h-6 text-purple-600" />
            <span>NAP Consistency & Ground Truth Monitor</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Detect Name, Address, and Phone number mismatches between your Canonical Business Profile and external directories.
          </p>
        </div>
        <button
          onClick={fetchNAPComparison}
          disabled={loading}
          className="btn-secondary text-xs flex items-center space-x-1.5 self-start sm:self-auto"
        >
          <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Comparison</span>
        </button>
      </div>

      {/* Canonical Ground Truth Reference Card */}
      <div className="card-vibrant p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <span className="text-xs font-black uppercase tracking-wider text-purple-700">
            Canonical Business Information (Ground Truth)
          </span>
          <span className="text-xs font-bold text-emerald-700 flex items-center space-x-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{profile?.verification_status || 'CANONICAL'}</span>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs">
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1">Legal Name</span>
            <span className="font-extrabold text-slate-900 text-sm">
              {profile?.business_name || activeProject.name}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1">Target Website</span>
            <span className="font-mono text-slate-800 font-semibold truncate block">
              {profile?.website || (activeProject.domain ? `https://${activeProject.domain}` : '—')}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1">Canonical Phone</span>
            <span className="font-mono text-slate-800 font-semibold">
              {profile?.primary_phone || '—'}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1">NAP Uniformity</span>
            <span className="font-black text-purple-700 text-sm">
              {consistencyPct !== null && consistencyPct !== undefined
                ? `${consistencyPct}% Uniform`
                : 'NOT_SCANNED'}
            </span>
          </div>
        </div>
      </div>

      {/* NAP Audit Table */}
      <div className="card-vibrant overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-extrabold text-slate-900 tracking-tight">
            External Directory & Profile Discrepancies
          </h3>
          <span className="text-xs text-slate-500 font-bold">
            {totalEvaluated > 0
              ? `${consistentCount} of ${totalEvaluated} Aligned Sources`
              : 'No sources evaluated'}
          </span>
        </div>

        {comparisons.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                <tr>
                  <th className="p-3.5">Source & Provenance</th>
                  <th className="p-3.5">Listed Business Name</th>
                  <th className="p-3.5">Listed Address</th>
                  <th className="p-3.5">Listed Phone</th>
                  <th className="p-3.5">Overall Alignment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {comparisons.map((c, idx) => (
                  <tr key={idx} className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 space-y-1">
                      <div className="font-bold text-slate-900">{c.source_name}</div>
                      <div className="flex items-center space-x-1.5">
                        <span className="text-[10px] font-bold uppercase px-1.5 py-0.2 rounded bg-purple-50 text-purple-700 border border-purple-200">
                          {c.provenance}
                        </span>
                        <span className="text-[10px] text-slate-400 font-medium">({c.source_type})</span>
                      </div>
                    </td>
                    <td className="p-3.5">
                      {renderFieldCell(c.name, <Building className="w-3 h-3 text-slate-400" />)}
                    </td>
                    <td className="p-3.5">
                      {renderFieldCell(c.address, <MapPin className="w-3 h-3 text-slate-400" />)}
                    </td>
                    <td className="p-3.5">
                      {renderFieldCell(c.phone, <Phone className="w-3 h-3 text-slate-400" />)}
                    </td>
                    <td className="p-3.5">
                      <StatusBadge
                        status={c.is_consistent ? 'Aligned' : 'Mismatch'}
                        variant={c.is_consistent ? 'green' : 'red'}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={ShieldCheck}
            badge="NAP Status"
            title="No NAP Audit Records Collected"
            description="Run a Central Intelligence Scan or connect citation directories to evaluate Name, Address, and Phone consistency against external listings."
          />
        )}
      </div>
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  MapPin,
  TrendingUp,
  Store,
  Star,
  PhoneCall,
  BookOpen,
  AlertTriangle,
  CheckSquare,
  ChevronRight,
  BarChart3,
  Target,
  Eye,
  XCircle,
  Sparkles,
  Globe,
  HelpCircle,
  Activity
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { useProjectScan } from '../context/ScanContext';
import { Link } from 'react-router-dom';
import { EmptyState } from '../components/ui/EmptyState';
import { FindingCard } from '../components/audit/FindingCard';
import api from '../api/client';
import type { LocalIntelligenceSummary, LocalAuditFinding } from '../types';

export const Dashboard: React.FC = () => {
  const { activeProject } = useProject();
  const { isScanning, activeScan, startScan, openProgressModal } = useProjectScan();
  const [intel, setIntel] = useState<LocalIntelligenceSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Flush stale data on project switch
    setIntel(null);
    setError(null);

    if (!activeProject) return;

    const loadIntelligence = async () => {
      try {
        setLoading(true);
        const resp = await api.get(`/projects/${activeProject.id}/local-intelligence-summary`);
        setIntel(resp.data);
      } catch (e: any) {
        console.error('Failed to load intelligence summary:', e);
        setError('Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    loadIntelligence();
  }, [activeProject?.id]);

  if (!activeProject) {
    return (
      <EmptyState
        icon={BarChart3}
        badge="Dashboard"
        title="Select a Project"
        description="Select or create a project to view your Local SEO intelligence dashboard."
      />
    );
  }

  if (loading && !intel) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-[#236B4F] border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-slate-500 font-medium">Loading intelligence data...</p>
        </div>
      </div>
    );
  }

  const auditScore = intel?.audit?.overall_score;
  const geoVisibility = intel?.geo_visibility?.local_visibility_pct;
  const geoAvgRank = intel?.geo_visibility?.average_rank;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-[#142820] tracking-tight">
            Local SEO Intelligence
          </h1>
          <p className="text-xs text-[#587568] mt-1">
            {activeProject.name} — {activeProject.domain}
          </p>
        </div>

        {isScanning ? (
          <button
            onClick={openProgressModal}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-purple-700 bg-purple-50 border border-purple-300 hover:bg-purple-100 transition-all shadow-xs animate-pulse self-start sm:self-auto"
          >
            <Activity className="w-4 h-4 text-purple-600 animate-spin" />
            <span>Scanning ({activeScan?.progress_pct || 0}%) — View Live Progress</span>
          </button>
        ) : (
          <button
            onClick={startScan}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-[#236B4F] hover:bg-[#1D5A42] transition-all shadow-sm self-start sm:self-auto"
          >
            <Activity className="w-4 h-4 text-white" />
            <span>Run Full Local SEO Scan</span>
          </button>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 font-medium">
          {error}
        </div>
      )}

      {/* ─── PRIMARY METRICS ROW ─── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Local SEO Score */}
        <MetricCard
          icon={ShieldCheck}
          label="Local SEO Health"
          value={auditScore != null ? `${auditScore}` : null}
          suffix={auditScore != null ? '/100' : undefined}
          subtext={intel?.audit ? `Last audit: ${formatDate(intel.audit.completed_at)}` : 'No audit run'}
          color="emerald"
          linkTo="/audits/local"
        />

        {/* Geo Visibility */}
        <MetricCard
          icon={MapPin}
          label="Geo Visibility"
          value={geoVisibility != null ? `${geoVisibility.toFixed(0)}%` : null}
          subtext={geoAvgRank != null ? `Avg rank: ${geoAvgRank.toFixed(1)}` : 'No scan data'}
          color="blue"
          linkTo="/rankings/grid"
        />

        {/* Tracked Keywords */}
        <MetricCard
          icon={TrendingUp}
          label="Keywords Tracked"
          value={intel?.keywords?.total != null ? `${intel.keywords.total}` : null}
          subtext={intel?.keywords?.average_rank != null ? `Avg rank: ${intel.keywords.average_rank}` : 'No rank data'}
          color="purple"
          linkTo="/rankings/keywords"
        />

        {/* Reviews */}
        <MetricCard
          icon={Star}
          label="Reviews"
          value={intel?.reviews?.total != null ? `${intel.reviews.total}` : null}
          subtext={intel?.reviews?.average_rating != null
            ? `${intel.reviews.average_rating.toFixed(1)}★ avg · ${intel.reviews.unanswered} unanswered`
            : 'No reviews'}
          color="amber"
          linkTo="/local/reviews"
        />
      </div>

      {/* ─── SECONDARY METRICS ROW ─── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {/* GBP Health */}
        <SmallMetricCard
          icon={Store}
          label="GBP"
          value={intel?.gbp?.connected ? 'Connected' : 'Not connected'}
          status={intel?.gbp?.connected ? 'good' : 'neutral'}
          linkTo="/google/gbp"
        />

        {/* NAP Consistency */}
        <SmallMetricCard
          icon={PhoneCall}
          label="NAP"
          value={intel?.citations?.nap_conflicts != null
            ? (intel.citations.nap_conflicts === 0 ? 'Consistent' : `${intel.citations.nap_conflicts} conflicts`)
            : null}
          status={intel?.citations?.nap_conflicts === 0 ? 'good' : intel?.citations?.nap_conflicts ? 'warning' : 'neutral'}
          linkTo="/local/nap"
        />

        {/* Citations */}
        <SmallMetricCard
          icon={BookOpen}
          label="Citations"
          value={intel?.citations?.total != null ? `${intel.citations.total}` : null}
          status="neutral"
          linkTo="/local/citations"
        />

        {/* Open Issues */}
        <SmallMetricCard
          icon={AlertTriangle}
          label="Open Issues"
          value={intel?.open_issues != null ? `${intel.open_issues}` : null}
          status={intel?.open_issues && intel.open_issues > 0 ? 'warning' : 'good'}
          linkTo="/tasks"
        />

        {/* Active Tasks */}
        <SmallMetricCard
          icon={CheckSquare}
          label="Active Tasks"
          value={intel?.active_tasks != null ? `${intel.active_tasks}` : null}
          status="neutral"
          linkTo="/tasks"
        />
      </div>

      {/* ─── AUDIT CATEGORY SCORES ─── */}
      {intel?.audit?.category_scores && Object.keys(intel.audit.category_scores).length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-black text-[#142820] uppercase tracking-wider">
              Category Scores
            </h2>
            <Link to="/audits/local" className="text-[11px] font-bold text-[#236B4F] hover:underline flex items-center gap-1">
              View Full Audit <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
            {Object.entries(intel.audit.category_scores).map(([key, score]) => (
              <CategoryScorePill key={key} categoryKey={key} score={score} />
            ))}
          </div>
        </div>
      )}

      {/* ─── PRIORITY FINDINGS ─── */}
      {intel?.priority_findings && intel.priority_findings.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-black text-[#142820] uppercase tracking-wider">
              Priority Actions
            </h2>
            <Link to="/audits/local" className="text-[11px] font-bold text-[#236B4F] hover:underline flex items-center gap-1">
              All Findings <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {intel.priority_findings.slice(0, 6).map((f) => (
              <FindingCard
                key={f.id}
                finding={f as any}
                compact
              />
            ))}
          </div>
        </div>
      )}

      {/* ─── BUSINESS PROFILE STATUS ─── */}
      {intel?.business_profile && (
        <div className="rounded-2xl border border-[#DCE8DC] bg-white p-5 space-y-3">
          <h2 className="text-sm font-black text-[#142820] uppercase tracking-wider">
            Business Profile
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <ProfileField label="Business Name" value={intel.business_profile.business_name} />
            <ProfileField label="Category" value={intel.business_profile.primary_category} />
            <ProfileField label="Coordinates" value={intel.business_profile.has_coordinates ? '✓ Set' : 'Not set'} ok={intel.business_profile.has_coordinates} />
            <ProfileField label="Phone" value={intel.business_profile.has_phone ? '✓ Set' : 'Not set'} ok={intel.business_profile.has_phone} />
            <ProfileField label="Address" value={intel.business_profile.has_address ? '✓ Set' : 'Not set'} ok={intel.business_profile.has_address} />
            <ProfileField label="Verification" value={intel.business_profile.verification_status.replace(/_/g, ' ')} />
          </div>
        </div>
      )}

      {/* No data state */}
      {!intel?.audit && !intel?.geo_visibility && (
        <div className="rounded-2xl border border-[#DCE8DC] bg-[#F7FAF7] p-8 text-center space-y-3">
          <Sparkles className="w-8 h-8 text-[#236B4F] mx-auto" />
          <h3 className="text-sm font-bold text-[#142820]">Get Started with Local SEO Intelligence</h3>
          <p className="text-xs text-[#587568] max-w-md mx-auto">
            Run your first Local SEO audit and Geo-Grid scan to populate your intelligence dashboard with real data.
          </p>
          <div className="flex items-center justify-center gap-3 pt-2">
            <Link
              to="/audits/local"
              className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-[#236B4F] hover:bg-[#1D5A42] transition-colors"
            >
              Run Local Audit
            </Link>
            <Link
              to="/rankings/grid"
              className="px-4 py-2 rounded-xl text-xs font-bold text-[#236B4F] bg-white border border-[#B8DFC9] hover:bg-[#F1F7F1] transition-colors"
            >
              Run Geo-Grid Scan
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};

// ─── Helper Components ───

interface MetricCardProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | null;
  suffix?: string;
  subtext: string;
  color: 'emerald' | 'blue' | 'purple' | 'amber';
  linkTo: string;
}

const COLOR_MAP = {
  emerald: { bg: 'bg-emerald-50', border: 'border-emerald-200', icon: 'text-emerald-600', value: 'text-emerald-800' },
  blue: { bg: 'bg-blue-50', border: 'border-blue-200', icon: 'text-blue-600', value: 'text-blue-800' },
  purple: { bg: 'bg-violet-50', border: 'border-violet-200', icon: 'text-violet-600', value: 'text-violet-800' },
  amber: { bg: 'bg-amber-50', border: 'border-amber-200', icon: 'text-amber-600', value: 'text-amber-800' },
};

const MetricCard: React.FC<MetricCardProps> = ({ icon: Icon, label, value, suffix, subtext, color, linkTo }) => {
  const c = COLOR_MAP[color];
  return (
    <Link
      to={linkTo}
      className={`rounded-2xl border ${c.border} bg-white p-4 space-y-2 hover:shadow-md transition-all group`}
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">{label}</span>
        <div className={`w-7 h-7 rounded-lg ${c.bg} flex items-center justify-center`}>
          <Icon className={`w-4 h-4 ${c.icon}`} />
        </div>
      </div>
      <div className="flex items-baseline gap-1">
        <span className={`text-2xl font-black ${value != null ? c.value : 'text-slate-400'}`}>
          {value ?? 'N/A'}
        </span>
        {suffix && <span className="text-xs font-semibold text-slate-400">{suffix}</span>}
      </div>
      <div className="text-[11px] text-[#587568] font-medium">{subtext}</div>
    </Link>
  );
};

interface SmallMetricCardProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | null;
  status: 'good' | 'warning' | 'neutral';
  linkTo: string;
}

const SmallMetricCard: React.FC<SmallMetricCardProps> = ({ icon: Icon, label, value, status, linkTo }) => {
  const statusColors = {
    good: 'text-emerald-700 bg-emerald-50 border-emerald-200',
    warning: 'text-amber-700 bg-amber-50 border-amber-200',
    neutral: 'text-slate-600 bg-slate-50 border-slate-200',
  };

  return (
    <Link
      to={linkTo}
      className="rounded-xl border border-[#DCE8DC] bg-white p-3 hover:shadow-sm transition-all flex items-center gap-3"
    >
      <Icon className="w-4 h-4 text-[#587568] shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#587568]">{label}</div>
        <div className={`text-xs font-bold mt-0.5 ${value != null ? 'text-slate-900' : 'text-slate-400'}`}>
          {value ?? 'N/A'}
        </div>
      </div>
    </Link>
  );
};

const CategoryScorePill: React.FC<{ categoryKey: string; score: number | null | any }> = ({ categoryKey, score }) => {
  const label = categoryKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  const actualScore: number | null = typeof score === 'object' && score !== null ? (score.score ?? null) : (typeof score === 'number' ? score : null);
  const getColor = (s: number | null) => {
    if (s === null) return 'bg-slate-100 text-slate-500 border-slate-200';
    if (s >= 80) return 'bg-emerald-50 text-emerald-800 border-emerald-200';
    if (s >= 60) return 'bg-amber-50 text-amber-800 border-amber-200';
    if (s >= 40) return 'bg-orange-50 text-orange-800 border-orange-200';
    return 'bg-rose-50 text-rose-800 border-rose-200';
  };

  return (
    <div className={`rounded-xl border px-3 py-2 ${getColor(actualScore)}`}>
      <div className="text-[10px] font-medium truncate">{label}</div>
      <div className="text-sm font-black">{actualScore != null ? actualScore : '—'}</div>
    </div>
  );
};

const ProfileField: React.FC<{ label: string; value: string | null; ok?: boolean }> = ({ label, value, ok }) => (
  <div className="space-y-0.5">
    <div className="text-[10px] font-bold uppercase tracking-wider text-[#587568]">{label}</div>
    <div className={`text-xs font-semibold ${ok === false ? 'text-amber-700' : ok === true ? 'text-emerald-700' : 'text-slate-900'}`}>
      {value || 'N/A'}
    </div>
  </div>
);

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return 'N/A';
  }
}

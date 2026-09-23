import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  RotateCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  History,
  ChevronDown,
  Filter
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import { FindingCard } from '../components/audit/FindingCard';
import { CategoryScoreCard } from '../components/audit/CategoryScoreCard';
import api from '../api/client';
import type {
  LocalAuditRun,
  LocalAuditFinding,
  AuditCategoryKey,
  AUDIT_CATEGORY_LABELS as LABELS
} from '../types';
import { AUDIT_CATEGORY_LABELS } from '../types';

type FilterTab = 'all' | 'fail' | 'partial' | 'pass' | 'not_verified';

export const LocalSEOAuditView: React.FC = () => {
  const { activeProject } = useProject();
  const [auditRun, setAuditRun] = useState<LocalAuditRun | null>(null);
  const [history, setHistory] = useState<LocalAuditRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [isAuditing, setIsAuditing] = useState(false);
  const [filterTab, setFilterTab] = useState<FilterTab>('all');
  const [viewMode, setViewMode] = useState<'categories' | 'findings'>('categories');

  useEffect(() => {
    setAuditRun(null);
    setHistory([]);
    if (!activeProject?.id) return;

    const loadAudit = async () => {
      try {
        setLoading(true);
        const [latestResp, historyResp] = await Promise.allSettled([
          api.get(`/audits/${activeProject.id}/local/latest`),
          api.get(`/audits/${activeProject.id}/local/history?limit=10`),
        ]);

        if (latestResp.status === 'fulfilled' && latestResp.value.data) {
          setAuditRun(latestResp.value.data);
        }
        if (historyResp.status === 'fulfilled' && Array.isArray(historyResp.value.data)) {
          setHistory(historyResp.value.data);
        }
      } catch (e) {
        console.error('Failed to load audit:', e);
      } finally {
        setLoading(false);
      }
    };

    loadAudit();
  }, [activeProject?.id]);

  const handleRunAudit = async () => {
    if (!activeProject) return;
    try {
      setIsAuditing(true);
      const resp = await api.post(`/audits/${activeProject.id}/local/run`);
      if (resp.data) {
        setAuditRun(resp.data);
        // Refresh history
        const hResp = await api.get(`/audits/${activeProject.id}/local/history?limit=10`);
        if (Array.isArray(hResp.data)) setHistory(hResp.data);
      }
    } catch (e) {
      console.error('Audit failed:', e);
    } finally {
      setIsAuditing(false);
    }
  };

  const handleSelectRun = async (runId: number) => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/audits/${activeProject.id}/local/runs/${runId}`);
      if (resp.data) setAuditRun(resp.data);
    } catch (e) {
      console.error('Failed to load audit run:', e);
    } finally {
      setLoading(false);
    }
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={ShieldCheck}
        badge="Local SEO Audit"
        title="Select a Project"
        description="Select an active project to run a comprehensive 20-category Local SEO audit."
      />
    );
  }

  const findings: LocalAuditFinding[] = auditRun?.findings || [];
  const filteredFindings = filterTab === 'all'
    ? findings
    : findings.filter(f => f.status === filterTab.toUpperCase());

  // Group findings by category
  const categoryGroups: Record<string, LocalAuditFinding[]> = {};
  for (const f of filteredFindings) {
    if (!categoryGroups[f.category]) categoryGroups[f.category] = [];
    categoryGroups[f.category].push(f);
  }

  const overallScore = auditRun?.overall_score;
  const summary = auditRun?.findings_summary || {};

  const passCount = summary.pass || 0;
  const failCount = summary.fail || 0;
  const partialCount = summary.partial || 0;
  const notVerifiedCount = summary.not_verified || 0;
  const totalCount = summary.total || findings.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-[#142820] tracking-tight flex items-center gap-2">
            <ShieldCheck className="w-6 h-6 text-[#236B4F]" />
            Local SEO Audit
          </h1>
          <p className="text-xs text-[#587568] mt-1">
            Comprehensive 20-category audit with evidence-backed findings and provenance tracking.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* History selector */}
          {history.length > 1 && (
            <div className="flex items-center gap-1.5 bg-white border border-[#DCE8DC] rounded-xl px-3 py-1.5">
              <History className="w-3.5 h-3.5 text-[#587568]" />
              <select
                value={auditRun?.id || ''}
                onChange={(e) => handleSelectRun(parseInt(e.target.value))}
                className="text-xs font-semibold text-[#142820] bg-transparent focus:outline-none cursor-pointer"
              >
                {history.map((run) => (
                  <option key={run.id} value={run.id}>
                    Run #{run.id} — {formatDate(run.executed_at)}
                    {run.overall_score != null ? ` (${run.overall_score}/100)` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={handleRunAudit}
            disabled={isAuditing}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-[#236B4F] hover:bg-[#1D5A42] disabled:opacity-50 transition-colors shadow-sm"
          >
            <RotateCw className={`w-4 h-4 ${isAuditing ? 'animate-spin' : ''}`} />
            {isAuditing ? 'Running Audit...' : 'Run Audit'}
          </button>
        </div>
      </div>

      {loading && !auditRun && (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-4 border-[#236B4F] border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {!loading && !auditRun && (
        <EmptyState
          icon={ShieldCheck}
          badge="20 Categories"
          title="No Audit Run Yet"
          description="Run your first Local SEO audit to evaluate your business across 20 ranking factor categories with traceable evidence."
          actionText="Run First Audit"
          onAction={handleRunAudit}
        />
      )}

      {auditRun && (
        <>
          {/* ─── OVERALL SCORE ─── */}
          <div className="rounded-2xl border border-[#DCE8DC] bg-white p-6">
            <div className="flex flex-col sm:flex-row sm:items-center gap-6">
              {/* Score ring */}
              <div className="flex items-center gap-5">
                <div className={`w-20 h-20 rounded-2xl flex items-center justify-center ${getScoreBg(overallScore)} border-2 ${getScoreBorder(overallScore)}`}>
                  <span className={`text-3xl font-black ${getScoreColor(overallScore)}`}>
                    {overallScore != null ? overallScore : '—'}
                  </span>
                </div>
                <div>
                  <div className="text-lg font-black text-[#142820]">
                    {overallScore != null ? 'Local SEO Score' : 'Score Not Available'}
                  </div>
                  <div className="text-xs text-[#587568] mt-0.5">
                    {overallScore != null
                      ? `Based on ${totalCount} checks across 20 categories`
                      : 'Insufficient verified data to calculate score'}
                  </div>
                </div>
              </div>

              {/* Summary counters */}
              <div className="flex items-center gap-4 sm:ml-auto">
                <SummaryBadge icon={CheckCircle2} label="Pass" count={passCount} color="emerald" />
                <SummaryBadge icon={XCircle} label="Fail" count={failCount} color="rose" />
                <SummaryBadge icon={AlertTriangle} label="Partial" count={partialCount} color="amber" />
                <SummaryBadge icon={HelpCircle} label="Not Verified" count={notVerifiedCount} color="slate" />
              </div>
            </div>
          </div>

          {/* ─── VIEW TOGGLE & FILTER ─── */}
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setViewMode('categories')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                  viewMode === 'categories'
                    ? 'bg-[#236B4F] text-white'
                    : 'bg-white text-[#587568] border border-[#DCE8DC] hover:bg-[#F1F7F1]'
                }`}
              >
                By Category
              </button>
              <button
                onClick={() => setViewMode('findings')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                  viewMode === 'findings'
                    ? 'bg-[#236B4F] text-white'
                    : 'bg-white text-[#587568] border border-[#DCE8DC] hover:bg-[#F1F7F1]'
                }`}
              >
                All Findings
              </button>
            </div>

            <div className="flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-[#587568]" />
              {(['all', 'fail', 'partial', 'pass', 'not_verified'] as FilterTab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setFilterTab(tab)}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-colors ${
                    filterTab === tab
                      ? 'bg-[#EAF2EA] text-[#142820] border border-[#B8DFC9]'
                      : 'text-[#587568] hover:bg-[#F1F7F1]'
                  }`}
                >
                  {tab === 'all' ? 'All' : tab === 'not_verified' ? 'Not Verified' : tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* ─── CATEGORY VIEW ─── */}
          {viewMode === 'categories' && (
            <div className="space-y-3">
              {Object.keys(AUDIT_CATEGORY_LABELS).map((key) => {
                const catKey = key as AuditCategoryKey;
                const catScore = auditRun.category_scores?.[catKey] ?? null;
                const catFindings = categoryGroups[catKey] || [];

                // Skip categories with no findings in filtered view
                if (filterTab !== 'all' && catFindings.length === 0) return null;

                return (
                  <CategoryScoreCard
                    key={catKey}
                    categoryKey={catKey}
                    score={catScore}
                    findings={catFindings}
                  />
                );
              })}
            </div>
          )}

          {/* ─── FINDINGS LIST VIEW ─── */}
          {viewMode === 'findings' && (
            <div className="space-y-3">
              {filteredFindings.length > 0 ? (
                filteredFindings.map((f) => (
                  <FindingCard key={f.id} finding={f} />
                ))
              ) : (
                <div className="text-center py-10 text-sm text-[#587568]">
                  No findings match the current filter.
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

// ─── Helper Components ───

const SummaryBadge: React.FC<{
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  count: number;
  color: string;
}> = ({ icon: Icon, label, count, color }) => {
  const colorMap: Record<string, string> = {
    emerald: 'text-emerald-700 bg-emerald-50',
    rose: 'text-rose-700 bg-rose-50',
    amber: 'text-amber-700 bg-amber-50',
    slate: 'text-slate-600 bg-slate-100',
  };
  const c = colorMap[color] || colorMap.slate;

  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg ${c}`}>
      <Icon className="w-3.5 h-3.5" />
      <span className="text-xs font-bold">{count}</span>
      <span className="text-[10px] font-medium hidden sm:inline">{label}</span>
    </div>
  );
};

function getScoreColor(s: number | null | undefined): string {
  if (s == null) return 'text-slate-500';
  if (s >= 80) return 'text-emerald-700';
  if (s >= 60) return 'text-amber-700';
  if (s >= 40) return 'text-orange-700';
  return 'text-rose-700';
}

function getScoreBg(s: number | null | undefined): string {
  if (s == null) return 'bg-slate-50';
  if (s >= 80) return 'bg-emerald-50';
  if (s >= 60) return 'bg-amber-50';
  if (s >= 40) return 'bg-orange-50';
  return 'bg-rose-50';
}

function getScoreBorder(s: number | null | undefined): string {
  if (s == null) return 'border-slate-200';
  if (s >= 80) return 'border-emerald-200';
  if (s >= 60) return 'border-amber-200';
  if (s >= 40) return 'border-orange-200';
  return 'border-rose-200';
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return 'N/A';
  }
}

import React, { useState } from 'react';
import {
  Store,
  Star,
  Play,
  RotateCw,
  Search,
  FileText,
  CheckCircle2,
  ArrowRight,
  AlertCircle
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import api from '../../api/client';

export const RightInsightsPanel: React.FC = () => {
  const { activeProject, dashboard, refreshDashboard } = useProject();
  const navigate = useNavigate();
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const handleRunAudit = async () => {
    if (!activeProject) return;
    try {
      setActionLoading('audit');
      await api.post(`/audits/crawl/${activeProject.id}`, {
        url: `https://${activeProject.domain}`,
        max_pages: 10
      });
      setTimeout(async () => {
        await refreshDashboard();
        setActionLoading(null);
        setActionSuccess('Audit Complete!');
        setTimeout(() => setActionSuccess(null), 3000);
      }, 2000);
    } catch (e) {
      console.error(e);
      setActionLoading(null);
    }
  };

  const handleSyncGBP = async () => {
    if (!activeProject) return;
    try {
      setActionLoading('gbp');
      await api.post(`/gbp/${activeProject.id}/sync`);
      await refreshDashboard();
      setActionLoading(null);
      setActionSuccess('GBP Synced!');
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (e) {
      console.error(e);
      setActionLoading(null);
    }
  };

  const gbpData = dashboard?.gbp_summary;
  const issuesList = dashboard?.recent_issues || [];
  const criticalCount = issuesList.filter((i: any) => i.severity?.toLowerCase() === 'critical').length;
  const importantCount = issuesList.filter((i: any) => i.severity?.toLowerCase() === 'important').length;
  const moderateCount = issuesList.filter((i: any) => i.severity?.toLowerCase() === 'moderate').length;
  const lowCount = issuesList.filter((i: any) => i.severity?.toLowerCase() === 'low' || i.severity?.toLowerCase() === 'info').length;
  const totalIssues = issuesList.length;

  return (
    <aside className="w-[290px] xl:w-[315px] bg-white border-l border-slate-200 flex flex-col shrink-0 h-screen sticky top-0 z-10 overflow-y-auto p-4 space-y-5 select-none">
      {/* 1. Google Business Profile Real Insights */}
      <div className="card-vibrant p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-7 h-7 rounded-lg gradient-blue-cyan text-white flex items-center justify-center font-bold text-xs shadow-sm">
              <Store className="w-4 h-4" />
            </div>
            <span className="text-xs font-bold text-slate-900">Google Business Profile</span>
          </div>
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
              gbpData?.connected
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                : 'bg-slate-100 text-slate-600 border border-slate-200'
            }`}
          >
            {gbpData?.connected ? 'Live' : 'Ready'}
          </span>
        </div>

        {gbpData?.connected ? (
          <div className="space-y-3">
            <div className="flex items-baseline justify-between pt-1">
              <div>
                <div className="flex items-center space-x-1.5">
                  <span className="text-2xl font-black text-slate-900">
                    {gbpData.completeness_score !== null && gbpData.completeness_score !== undefined
                      ? `${gbpData.completeness_score}%`
                      : '—'}
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5 font-medium">Profile Completeness</div>
              </div>

              <div className="text-right">
                <span className="inline-block text-xs font-bold px-2 py-0.5 rounded-md bg-purple-50 text-purple-800 border border-purple-200">
                  {gbpData.search_impressions ? `${gbpData.search_impressions} views` : 'Synced'}
                </span>
                <div className="text-[10px] text-slate-400 mt-0.5 font-medium">Monthly Reach</div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs pt-1">
              <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-[10px] text-slate-400 font-bold block">Calls</span>
                <span className="text-sm font-bold text-slate-900">{gbpData.calls || 0}</span>
              </div>
              <div className="p-2 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-[10px] text-slate-400 font-bold block">Clicks</span>
                <span className="text-sm font-bold text-slate-900">{gbpData.website_clicks || 0}</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="py-2 text-center space-y-2">
            <p className="text-xs text-slate-500 font-medium">
              Connect Google Business Profile to track live calls, discovery searches, and map impressions.
            </p>
          </div>
        )}

        <Link
          to="/google/gbp"
          className="w-full py-2 px-3 btn-vibrant-secondary rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 transition-colors shadow-sm"
        >
          <span>View GBP Insights</span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
        </Link>
      </div>

      {/* 2. SEO Issues Real Breakdown Donut */}
      <div className="card-vibrant p-4 space-y-3.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-extrabold text-slate-900">SEO Issues Breakdown</span>
          <span className="text-[11px] font-bold text-slate-500">
            {totalIssues} {totalIssues === 1 ? 'Issue' : 'Issues'}
          </span>
        </div>

        {totalIssues > 0 ? (
          <div className="flex items-center space-x-3 py-1">
            <div className="relative w-20 h-20 shrink-0 flex items-center justify-center">
              <svg viewBox="0 0 36 36" className="w-20 h-20 transform -rotate-90">
                <path
                  className="text-slate-100"
                  strokeWidth="4"
                  stroke="currentColor"
                  fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                {criticalCount > 0 && (
                  <path
                    className="text-rose-500"
                    strokeDasharray={`${(criticalCount / totalIssues) * 100}, 100`}
                    strokeWidth="4.5"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                )}
                {importantCount > 0 && (
                  <path
                    className="text-amber-500"
                    strokeDasharray={`${(importantCount / totalIssues) * 100}, 100`}
                    strokeDashoffset={`-${(criticalCount / totalIssues) * 100}`}
                    strokeWidth="4.5"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                )}
              </svg>
              <div className="absolute flex flex-col items-center justify-center text-center">
                <span className="text-lg font-black text-slate-900 leading-none">{totalIssues}</span>
                <span className="text-[8px] font-bold text-slate-400 uppercase tracking-tighter mt-0.5">Total</span>
              </div>
            </div>

            {/* Severity Legend with readable text */}
            <div className="space-y-1 text-xs flex-1">
              <div className="flex items-center justify-between">
                <span className="flex items-center space-x-1.5 text-slate-600 font-medium">
                  <span className="w-2 h-2 rounded-full bg-rose-500" />
                  <span>Critical</span>
                </span>
                <span className="font-bold text-slate-900">{criticalCount}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center space-x-1.5 text-slate-600 font-medium">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  <span>Important</span>
                </span>
                <span className="font-bold text-slate-900">{importantCount}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center space-x-1.5 text-slate-600 font-medium">
                  <span className="w-2 h-2 rounded-full bg-blue-500" />
                  <span>Moderate</span>
                </span>
                <span className="font-bold text-slate-900">{moderateCount}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center space-x-1.5 text-slate-600 font-medium">
                  <span className="w-2 h-2 rounded-full bg-purple-500" />
                  <span>Low</span>
                </span>
                <span className="font-bold text-slate-900">{lowCount}</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-3">
            <span className="text-xs text-emerald-700 font-semibold flex items-center justify-center space-x-1">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>Zero issues detected</span>
            </span>
          </div>
        )}

        <Link
          to="/audits/website"
          className="text-[11px] font-bold text-purple-700 hover:text-purple-800 flex items-center justify-center space-x-1 pt-0.5"
        >
          <span>Review Audit Diagnostics</span>
          <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      {/* 3. Quick Actions Live Triggers */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
            Quick Actions
          </span>
          {actionSuccess && (
            <span className="text-[11px] font-bold text-emerald-700 flex items-center space-x-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>{actionSuccess}</span>
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 gap-2">
          {/* Action 1: Run Website Audit */}
          <button
            onClick={handleRunAudit}
            disabled={actionLoading === 'audit'}
            className="w-full text-left p-2.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 hover:border-purple-300 flex items-center justify-between text-xs font-bold text-slate-800 transition-all shadow-sm group"
          >
            <div className="flex items-center space-x-2.5">
              <div className="w-7 h-7 rounded-lg bg-purple-50 text-purple-700 flex items-center justify-center">
                <Play className={`w-3.5 h-3.5 fill-current ${actionLoading === 'audit' ? 'animate-spin text-purple-600' : ''}`} />
              </div>
              <span>{actionLoading === 'audit' ? 'Running Crawl...' : 'Run Website Audit'}</span>
            </div>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-purple-600 transition-colors" />
          </button>

          {/* Action 2: Check Rankings */}
          <button
            onClick={() => navigate('/rankings/grid')}
            className="w-full text-left p-2.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 hover:border-purple-300 flex items-center justify-between text-xs font-bold text-slate-800 transition-all shadow-sm group"
          >
            <div className="flex items-center space-x-2.5">
              <div className="w-7 h-7 rounded-lg bg-pink-50 text-pink-700 flex items-center justify-center">
                <Search className="w-3.5 h-3.5 stroke-[2.5]" />
              </div>
              <span>Check 5x5 Geo-Grid</span>
            </div>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-purple-600 transition-colors" />
          </button>

          {/* Action 3: Sync GBP Data */}
          <button
            onClick={handleSyncGBP}
            disabled={actionLoading === 'gbp'}
            className="w-full text-left p-2.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 hover:border-purple-300 flex items-center justify-between text-xs font-bold text-slate-800 transition-all shadow-sm group"
          >
            <div className="flex items-center space-x-2.5">
              <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center">
                <RotateCw className={`w-3.5 h-3.5 ${actionLoading === 'gbp' ? 'animate-spin text-blue-600' : ''}`} />
              </div>
              <span>{actionLoading === 'gbp' ? 'Syncing...' : 'Sync GBP Data'}</span>
            </div>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-purple-600 transition-colors" />
          </button>

          {/* Action 4: Generate Report */}
          <button
            onClick={() => navigate('/reports')}
            className="w-full text-left p-2.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 hover:border-purple-300 flex items-center justify-between text-xs font-bold text-slate-800 transition-all shadow-sm group"
          >
            <div className="flex items-center space-x-2.5">
              <div className="w-7 h-7 rounded-lg bg-orange-50 text-orange-700 flex items-center justify-center">
                <FileText className="w-3.5 h-3.5 stroke-[2.2]" />
              </div>
              <span>Executive Report</span>
            </div>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-purple-600 transition-colors" />
          </button>
        </div>
      </div>
    </aside>
  );
};

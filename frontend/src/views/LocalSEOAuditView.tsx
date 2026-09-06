import React, { useState, useEffect } from 'react';
import {
  MapPin,
  Play,
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  FileCode2,
  PhoneCall,
  Search,
  Sparkles
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { SEOIssue } from '../types';
import { IssueCard } from '../components/ui/IssueCard';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const LocalSEOAuditView: React.FC = () => {
  const { activeProject, refreshDashboard } = useProject();
  const [issues, setIssues] = useState<SEOIssue[]>([]);
  const [loading, setLoading] = useState(false);
  const [isAuditing, setIsAuditing] = useState(false);

  const fetchLocalIssues = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/audits/issues/${activeProject.id}?category=Local SEO`);
      setIssues(resp.data || []);
    } catch (err) {
      console.error('Failed to load local SEO issues:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLocalIssues();
  }, [activeProject?.id]);

  const handleRunLocalAudit = async () => {
    if (!activeProject) return;
    try {
      setIsAuditing(true);
      await api.post(`/audits/crawl/${activeProject.id}`, {
        url: `https://${activeProject.domain}`,
        max_pages: 10
      });
      await fetchLocalIssues();
      await refreshDashboard();
    } catch (err) {
      console.error('Local audit failed:', err);
    } finally {
      setIsAuditing(false);
    }
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={MapPin}
        badge="Local SEO"
        title="Select a Project"
        description="Select an active business project to audit local signals, NAP consistency, and schema structured data."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <MapPin className="w-6 h-6 text-purple-600" />
            <span>Local SEO Signals & Proximity Audit</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Auditing localized landing pages, NAP schema markup, geo-coordinates, city keyword targeting, and local pack signals.
          </p>
        </div>

        <button
          onClick={handleRunLocalAudit}
          disabled={isAuditing}
          className="flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md self-start transition-all"
        >
          <RotateCw className={`w-4 h-4 ${isAuditing ? 'animate-spin' : ''}`} />
          <span>{isAuditing ? 'Evaluating Signals...' : 'Recheck Local Signals'}</span>
        </button>
      </div>

      {/* Local Checklist Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card-vibrant p-4 space-y-1.5">
          <div className="text-[11px] font-black uppercase tracking-wider text-slate-500 flex items-center justify-between">
            <span>Schema.org Markup</span>
            <FileCode2 className="w-4 h-4 text-purple-600" />
          </div>
          <div className="text-xl font-black text-slate-900">LocalBusiness JSON-LD</div>
          <p className="text-[11px] text-slate-500">Structured data validation for search engines</p>
        </div>

        <div className="card-vibrant p-4 space-y-1.5">
          <div className="text-[11px] font-black uppercase tracking-wider text-slate-500 flex items-center justify-between">
            <span>Canonical NAP</span>
            <PhoneCall className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-xl font-black text-slate-900">Address & Phone Matching</div>
          <p className="text-[11px] text-slate-500">Direct alignment with Google Business listing</p>
        </div>

        <div className="card-vibrant p-4 space-y-1.5">
          <div className="text-[11px] font-black uppercase tracking-wider text-slate-500 flex items-center justify-between">
            <span>City Pages</span>
            <MapPin className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-xl font-black text-slate-900">Suburban Coverage</div>
          <p className="text-[11px] text-slate-500">Target localized suburb keywords</p>
        </div>
      </div>

      {/* Detected Local SEO Issues */}
      <div className="space-y-3">
        <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
          Detected Local Signal Recommendations ({issues.length})
        </h3>

        {issues.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {issues.map((issue) => (
              <IssueCard key={issue.id} issue={issue} onConvertedToTask={fetchLocalIssues} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={CheckCircle2}
            badge="Signals Strong"
            title="All Local SEO Rules Passed"
            description="Your landing pages contain verified localized content, NAP structured data, and geographic coordinates."
            actionText="Run Deep Local Scan"
            onAction={handleRunLocalAudit}
          />
        )}
      </div>
    </div>
  );
};

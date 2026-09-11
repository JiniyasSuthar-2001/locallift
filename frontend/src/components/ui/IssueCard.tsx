import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  CheckCircle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  ExternalLink,
  Plus
} from 'lucide-react';
import { SEOIssue } from '../../types';
import { StatusBadge } from './StatusBadge';
import api from '../../api/client';
import { getErrorMessage } from '../../utils/error';
import { normalizeExternalUrl } from '../../utils/url';

interface IssueCardProps {
  issue: SEOIssue;
  onConvertedToTask?: () => void;
  onTaskCreated?: () => void;
}

export const IssueCard: React.FC<IssueCardProps> = ({ issue, onConvertedToTask, onTaskCreated }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isConverting, setIsConverting] = useState(false);
  const [converted, setConverted] = useState(issue.status === 'in_task' || issue.status === 'resolved');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleConvertToTask = async () => {
    try {
      setIsConverting(true);
      setErrorMsg(null);
      setSuccessMsg(null);
      await api.post(`/tasks/convert-issue/${issue.id}`, { priority: 'medium' });
      setConverted(true);
      setSuccessMsg('Task created successfully');
      if (onConvertedToTask) {
        onConvertedToTask();
      }
      if (onTaskCreated) {
        onTaskCreated();
      }
    } catch (err: any) {
      console.error('Failed to convert issue to task:', err);
      setErrorMsg(getErrorMessage(err, 'Failed to convert issue to task.'));
    } finally {
      setIsConverting(false);
    }
  };

  const safeAffectedUrl = issue.affected_url ? normalizeExternalUrl(issue.affected_url) : null;

  return (
    <div className="card-vibrant p-4 space-y-3 transition-all">
      {/* Top Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <StatusBadge status={issue.severity} />
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              {issue.category}
            </span>
          </div>
          <h4 className="text-sm font-extrabold text-slate-900 leading-snug">
            {issue.title}
          </h4>
        </div>

        <button
          onClick={() => setIsExpanded(!isExpanded)}
          aria-label={isExpanded ? 'Collapse issue details' : 'Expand issue details'}
          className="p-1 text-slate-400 hover:text-slate-800 rounded-lg transition-colors shrink-0"
        >
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Evidence Summary */}
      {issue.evidence && (
        <div className="text-xs text-slate-700 bg-slate-50/80 p-3 rounded-xl border border-slate-200/60 font-mono">
          <span className="text-slate-400 font-sans font-bold text-[10px] uppercase block mb-0.5">
            Detected Evidence:
          </span>
          {issue.evidence}
        </div>
      )}

      {/* Expanded Reasoning & Solution Accordion */}
      {isExpanded && (
        <div className="space-y-3 pt-2 border-t border-slate-100 text-xs animate-fade-in">
          {issue.why_it_matters && (
            <div className="space-y-1">
              <span className="font-bold text-slate-900 flex items-center space-x-1">
                <HelpCircle className="w-3.5 h-3.5 text-purple-600" />
                <span>Why This Impacts Local Rankings:</span>
              </span>
              <p className="text-slate-600 leading-relaxed pl-4">
                {issue.why_it_matters}
              </p>
            </div>
          )}

          {issue.recommended_solution && (
            <div className="space-y-1 bg-purple-50/60 border border-purple-100 p-3 rounded-xl">
              <span className="font-bold text-purple-900 flex items-center space-x-1">
                <CheckCircle className="w-3.5 h-3.5 text-purple-600" />
                <span>AI Recommended Remediation:</span>
              </span>
              <p className="text-slate-800 leading-relaxed font-medium">
                {issue.recommended_solution}
              </p>
            </div>
          )}

          {issue.affected_url && (
            <div className="flex items-center space-x-1 text-[11px] text-slate-500">
              <span>Target URL:</span>
              {safeAffectedUrl ? (
                <a
                  href={safeAffectedUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-purple-700 hover:underline flex items-center font-mono font-medium truncate max-w-sm"
                >
                  <span>{issue.affected_url}</span>
                  <ExternalLink className="w-2.5 h-2.5 ml-1" />
                </a>
              ) : (
                <span className="font-mono text-slate-600">{issue.affected_url}</span>
              )}
            </div>
          )}
        </div>
      )}

      {errorMsg && (
        <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center space-x-2 animate-fade-in">
          <AlertTriangle className="w-3.5 h-3.5 text-rose-600 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center space-x-2 animate-fade-in">
          <CheckCircle className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Action Footer */}
      <div className="pt-2 flex items-center justify-between border-t border-slate-100 flex-wrap gap-2">
        <div className="text-[11px] font-semibold text-slate-500">
          Status: <span className="font-bold capitalize text-slate-800">{converted ? 'in_task' : issue.status}</span>
        </div>

        <div className="flex items-center space-x-2">
          {(() => {
            const text = (issue.title + ' ' + issue.category + ' ' + (issue.recommended_solution || '')).toLowerCase();
            let templateSlug = null;
            if (text.includes('schema') || text.includes('json-ld')) templateSlug = 'localbusiness-schema-standard';
            else if (text.includes('citation') || text.includes('directory') || text.includes('nap')) templateSlug = 'citation-nap-correction-task';
            else if (text.includes('landing page') || text.includes('suburb') || text.includes('location page')) templateSlug = 'service-location-page-blueprint';
            else if (text.includes('review') || text.includes('reputation')) templateSlug = 'positive-review-response';
            else if (text.includes('google business') || text.includes('gbp') || text.includes('post')) templateSlug = 'gbp-weekly-update-post';

            if (!templateSlug) return null;

            return (
              <Link
                to={`/templates?apply=${templateSlug}`}
                className="inline-flex items-center space-x-1 px-2.5 py-1.5 bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200 rounded-lg text-xs font-bold transition-all"
              >
                <ArrowRight className="w-3.5 h-3.5" />
                <span>Apply Template</span>
              </Link>
            );
          })()}

          {converted ? (
            <span className="inline-flex items-center space-x-1 text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
              <CheckCircle className="w-3.5 h-3.5" />
              <span>Task Created</span>
            </span>
          ) : (
            <button
              onClick={handleConvertToTask}
              disabled={isConverting}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 btn-vibrant-primary rounded-lg text-xs font-bold shadow-sm transition-all disabled:opacity-50"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>{isConverting ? 'Creating...' : 'Convert to Task'}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

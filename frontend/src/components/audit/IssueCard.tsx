import React, { useState } from 'react';
import { AlertCircle, AlertTriangle, Lightbulb, CheckCircle, ArrowRight, Check, ListPlus } from 'lucide-react';
import { SEOIssue } from '../../types';
import { StatusBadge } from '../ui/StatusBadge';
import api from '../../api/client';

interface IssueCardProps {
  issue: SEOIssue;
  onTaskCreated?: () => void;
}

export const IssueCard: React.FC<IssueCardProps> = ({ issue, onTaskCreated }) => {
  const [isCreatingTask, setIsCreatingTask] = useState(false);
  const [taskCreated, setTaskCreated] = useState(issue.status === 'in_task' || issue.status === 'resolved');

  const handleConvertToTask = async () => {
    try {
      setIsCreatingTask(true);
      await api.post(`/tasks/convert-issue/${issue.id}`, { priority: 'high' });
      setTaskCreated(true);
      if (onTaskCreated) onTaskCreated();
    } catch (e) {
      console.error('Failed to convert issue to task:', e);
    } finally {
      setIsCreatingTask(false);
    }
  };

  const getSeverityIcon = () => {
    switch (issue.severity) {
      case 'critical':
        return <AlertCircle className="w-5 h-5 text-rose-400" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-amber-400" />;
      case 'opportunity':
        return <Lightbulb className="w-5 h-5 text-emerald-400" />;
      default:
        return <AlertCircle className="w-5 h-5 text-sky-400" />;
    }
  };

  return (
    <div className="glass-panel rounded-xl p-5 border border-[#1f293d] hover:border-gray-700 transition-all space-y-4">
      {/* Header: Severity, Category, Title, Status */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start space-x-3">
          <div className="mt-0.5">{getSeverityIcon()}</div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[11px] font-semibold tracking-wider uppercase text-gray-400">
                {issue.category}
              </span>
              <StatusBadge status={issue.severity} />
            </div>
            <h4 className="text-sm font-bold text-white mt-1">{issue.title}</h4>
            {issue.affected_url && (
              <div className="text-xs text-gray-400 font-mono mt-0.5 truncate max-w-lg">
                {issue.affected_url}
              </div>
            )}
          </div>
        </div>

        <div>
          {taskCreated ? (
            <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-emerald-950/70 border border-emerald-800 text-emerald-400 text-xs font-semibold">
              <Check className="w-3.5 h-3.5" />
              <span>In Tasks</span>
            </span>
          ) : (
            <button
              onClick={handleConvertToTask}
              disabled={isCreatingTask}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/20 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-600/30 text-xs font-semibold transition-colors shadow-sm"
            >
              <ListPlus className="w-3.5 h-3.5" />
              <span>{isCreatingTask ? 'Creating...' : 'Convert to Task'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Structured Diagnostics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 border-t border-gray-800/60 text-xs">
        {/* Evidence */}
        <div className="bg-gray-900/60 p-3 rounded-lg border border-gray-800/80">
          <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1">
            Evidence
          </div>
          <div className="text-gray-300 leading-relaxed">
            {issue.evidence || 'Detected during automated SEO crawl.'}
          </div>
        </div>

        {/* Why It Matters */}
        <div className="bg-gray-900/60 p-3 rounded-lg border border-gray-800/80">
          <div className="text-[10px] font-bold text-amber-400 uppercase tracking-wider mb-1">
            Why It Matters
          </div>
          <div className="text-gray-300 leading-relaxed">
            {issue.why_it_matters || 'Impacts search visibility and local crawl authority.'}
          </div>
        </div>

        {/* Recommended Solution */}
        <div className="bg-emerald-950/20 p-3 rounded-lg border border-emerald-900/30">
          <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1">
            AI Recommended Solution
          </div>
          <div className="text-gray-200 leading-relaxed">
            {issue.recommended_solution || 'Apply standard SEO remediation procedures.'}
          </div>
        </div>
      </div>
    </div>
  );
};

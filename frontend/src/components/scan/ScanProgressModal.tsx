import React from 'react';
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  XCircle,
  HelpCircle,
  Clock,
  Minimize2,
  X
} from 'lucide-react';
import { useProjectScan, ScanStageInfo } from '../../context/ScanContext';
import { useProject } from '../../context/ProjectContext';

export const ScanProgressModal: React.FC = () => {
  const { activeScan, isProgressModalOpen, closeProgressModal } = useProjectScan();
  const { activeProject } = useProject();

  if (!isProgressModalOpen || !activeScan) return null;

  const stages = activeScan.stages ? Object.values(activeScan.stages) : [];
  const completedCount = activeScan.completed_stages_count || 0;
  const totalCount = activeScan.total_stages_count || 13;
  const progressPct = activeScan.progress_pct || Math.round((completedCount / totalCount) * 100);

  const getStageIcon = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />;
      case 'RUNNING':
        return <RotateCw className="w-4 h-4 text-purple-600 animate-spin shrink-0" />;
      case 'PARTIAL':
        return <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />;
      case 'FAILED':
        return <XCircle className="w-4 h-4 text-rose-500 shrink-0" />;
      case 'NOT_CONFIGURED':
        return <HelpCircle className="w-4 h-4 text-slate-400 shrink-0" />;
      default:
        return <div className="w-3.5 h-3.5 rounded-full border-2 border-slate-300 shrink-0" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">Done</span>;
      case 'RUNNING':
        return <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">Scanning</span>;
      case 'PARTIAL':
        return <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">Notice</span>;
      case 'FAILED':
        return <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">Error</span>;
      case 'NOT_CONFIGURED':
        return <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200">Not Configured</span>;
      default:
        return <span className="text-[10px] font-medium text-slate-400">Waiting</span>;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="p-5 border-b border-slate-100 bg-gradient-to-r from-purple-50 via-indigo-50/50 to-white flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-purple-600 text-white flex items-center justify-center shadow-md shadow-purple-600/20">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 tracking-tight flex items-center space-x-2">
                <span>Running Local SEO Intelligence Scan</span>
              </h2>
              <p className="text-xs text-slate-500 font-medium truncate max-w-xs">
                {activeProject?.name} {activeProject?.domain ? `(${activeProject.domain})` : ''}
              </p>
            </div>
          </div>
          <button
            onClick={closeProgressModal}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            title="Minimize and run in background"
          >
            <Minimize2 className="w-4 h-4" />
          </button>
        </div>

        {/* Progress Bar & Current Stage Banner */}
        <div className="p-5 border-b border-slate-100 bg-slate-50/50 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center space-x-2 font-bold text-slate-800">
              <RotateCw className="w-3.5 h-3.5 text-purple-600 animate-spin" />
              <span className="truncate">{activeScan.current_stage_label || 'Executing Local SEO modules...'}</span>
            </div>
            <span className="font-mono font-black text-purple-700">
              {completedCount} / {totalCount} ({progressPct}%)
            </span>
          </div>

          <div className="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
            <div
              className="bg-gradient-to-r from-purple-600 to-indigo-600 h-full rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {/* Stage Checklist */}
        <div className="p-5 overflow-y-auto space-y-2 flex-1 divide-y divide-slate-100">
          {stages.map((st: ScanStageInfo) => (
            <div key={st.key} className="pt-2 first:pt-0 flex items-start justify-between gap-3 text-xs">
              <div className="flex items-start space-x-2.5">
                <div className="mt-0.5">{getStageIcon(st.status)}</div>
                <div className="space-y-0.5">
                  <div className="font-bold text-slate-900">{st.label}</div>
                  <div className="text-[11px] text-slate-500 font-medium">
                    {st.message}
                  </div>
                </div>
              </div>
              <div className="shrink-0">{getStatusBadge(st.status)}</div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-xs">
          <span className="text-slate-500">
            Scan continues automatically in the background.
          </span>
          <button
            onClick={closeProgressModal}
            className="btn-secondary text-xs px-4 py-2"
          >
            Run in Background
          </button>
        </div>
      </div>
    </div>
  );
};

import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Sparkles,
  ArrowRight,
  RotateCw,
  X
} from 'lucide-react';
import { useProjectScan, ScanStageInfo } from '../../context/ScanContext';
import { useProject } from '../../context/ProjectContext';

export const ScanCompleteModal: React.FC = () => {
  const { activeScan, isCompleteModalOpen, closeCompleteModal, refreshAllProjectData } = useProjectScan();
  const { activeProject } = useProject();

  if (!isCompleteModalOpen || !activeScan) return null;

  const stages = activeScan.stages ? Object.values(activeScan.stages) : [];
  const successfulStages = stages.filter(s => s.status === 'SUCCESS').length;
  const partialStages = stages.filter(s => s.status === 'PARTIAL').length;
  const failedStages = stages.filter(s => s.status === 'FAILED').length;
  const notConfiguredStages = stages.filter(s => s.status === 'NOT_CONFIGURED').length;

  const isSuccess = activeScan.status === 'COMPLETED';
  const isPartial = activeScan.status === 'PARTIAL';

  const handleRefreshAndClose = async () => {
    await refreshAllProjectData();
    closeCompleteModal();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className={`p-5 border-b border-slate-100 flex items-center justify-between ${
          isSuccess ? 'bg-emerald-50/50' : 'bg-amber-50/50'
        }`}>
          <div className="flex items-center space-x-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shadow-md ${
              isSuccess ? 'bg-emerald-600 text-white shadow-emerald-600/20' : 'bg-amber-500 text-white shadow-amber-500/20'
            }`}>
              {isSuccess ? <CheckCircle2 className="w-6 h-6" /> : <AlertTriangle className="w-6 h-6" />}
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 tracking-tight">
                {isSuccess
                  ? 'Local SEO Intelligence Scan Complete'
                  : 'Scan Finished with Partial Warnings'}
              </h2>
              <p className="text-xs text-slate-500 font-medium">
                {activeProject?.name} • Refreshed evidence across {stages.length} modules
              </p>
            </div>
          </div>
          <button
            onClick={closeCompleteModal}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-white/60 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Summary Stat Badges */}
        <div className="p-4 border-b border-slate-100 bg-slate-50/70 grid grid-cols-4 gap-2 text-center text-xs">
          <div className="p-2 rounded-xl bg-white border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-emerald-600 block">Complete</span>
            <span className="text-lg font-black text-slate-900">{successfulStages}</span>
          </div>
          <div className="p-2 rounded-xl bg-white border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-amber-600 block">Partial</span>
            <span className="text-lg font-black text-slate-900">{partialStages}</span>
          </div>
          <div className="p-2 rounded-xl bg-white border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block">Unconfigured</span>
            <span className="text-lg font-black text-slate-900">{notConfiguredStages}</span>
          </div>
          <div className="p-2 rounded-xl bg-white border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-rose-600 block">Failed</span>
            <span className="text-lg font-black text-slate-900">{failedStages}</span>
          </div>
        </div>

        {/* Module Breakdown */}
        <div className="p-5 overflow-y-auto space-y-2.5 flex-1 divide-y divide-slate-100">
          {stages.map((st: ScanStageInfo) => (
            <div key={st.key} className="pt-2 first:pt-0 flex items-start justify-between gap-3 text-xs">
              <div className="space-y-0.5">
                <div className="font-bold text-slate-900">{st.label}</div>
                <div className="text-[11px] text-slate-500">
                  {st.message}
                </div>
              </div>
              <div className="shrink-0">
                {st.status === 'SUCCESS' && (
                  <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                    Verified
                  </span>
                )}
                {st.status === 'PARTIAL' && (
                  <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
                    Notice
                  </span>
                )}
                {st.status === 'NOT_CONFIGURED' && (
                  <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                    Not Configured
                  </span>
                )}
                {st.status === 'FAILED' && (
                  <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">
                    Error
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Action Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-xs">
          <span className="text-slate-500">
            All workspaces updated with latest collected metrics.
          </span>
          <button
            onClick={handleRefreshAndClose}
            className="btn-primary text-xs px-5 py-2.5 flex items-center space-x-2"
          >
            <span>Apply & View Refreshed Data</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};

import React from 'react';
import {
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  BookOpen,
  ShieldCheck,
  Check,
  Clock,
  Search,
  ExternalLink,
  Layers
} from 'lucide-react';
import { Modal } from '../ui/Modal';

export interface CitationScanResultData {
  project_id?: number;
  queries_executed?: number;
  candidates_found?: number;
  verified_citations?: number;
  rejected_candidates?: number;
  new_citations_added?: number;
  existing_citations_updated?: number;
  elapsed_seconds?: number;
  scan_status?: string;
  scan_errors?: string[];
  rejection_summary?: Array<{
    url: string;
    reason: string;
    verification_status: string;
  }>;
  total_nap_matches?: number;
}

export interface CitationScanModalProps {
  isOpen: boolean;
  onClose: () => void;
  status: 'idle' | 'running' | 'success' | 'partial' | 'error';
  result: CitationScanResultData | null;
  error: string | null;
  businessName?: string;
  city?: string;
}

export const CitationScanModal: React.FC<CitationScanModalProps> = ({
  isOpen,
  onClose,
  status,
  result,
  error,
  businessName,
  city
}) => {
  if (!isOpen || status === 'idle') return null;

  const isRunning = status === 'running';
  const isSuccess = status === 'success';
  const isPartial = status === 'partial';
  const isError = status === 'error';

  // Determine modal title & subtitle based on state machine
  let modalTitle = 'Scanning Local Citations';
  let modalSubtitle = 'Your citation and NAP discovery scan is currently running.';
  let modalIcon = <RotateCw className="w-5 h-5 text-[#236B4F] animate-spin" />;

  if (isSuccess) {
    modalTitle = 'Citation Scan Complete';
    modalSubtitle = 'Your scan finished successfully.';
    modalIcon = <CheckCircle2 className="w-5 h-5 text-emerald-600" />;
  } else if (isPartial) {
    modalTitle = 'Citation Scan Complete with Notices';
    modalSubtitle = 'Some results were saved before the scan stopped.';
    modalIcon = <AlertTriangle className="w-5 h-5 text-amber-600" />;
  } else if (isError) {
    modalTitle = 'Scan Could Not Be Completed';
    modalSubtitle = 'The citation scan encountered an issue.';
    modalIcon = <AlertCircle className="w-5 h-5 text-rose-600" />;
  }

  // Real data metrics from backend response
  const verifiedCount = result?.verified_citations;
  const candidatesCount = result?.candidates_found;
  const rejectedCount = result?.rejected_candidates;
  const napMatches = result?.total_nap_matches ?? result?.verified_citations;
  const elapsed = result?.elapsed_seconds;
  const newAdded = result?.new_citations_added;
  const existingUpdated = result?.existing_citations_updated;
  const queriesCount = result?.queries_executed;

  const hasPartialData = Boolean(
    result &&
    ((result.new_citations_added && result.new_citations_added > 0) ||
      (result.verified_citations && result.verified_citations > 0) ||
      result.scan_status === 'completed_with_errors')
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={modalTitle}
      subtitle={modalSubtitle}
      icon={modalIcon}
      maxWidth="md"
      closeOnBackdropClick={!isRunning}
      closeOnEscape={!isRunning}
      showCloseButton={!isRunning}
      zIndex={10000}
    >
      <div className="space-y-5">
        {/* ─── STATE 1: SCAN IN PROGRESS ─── */}
        {isRunning && (
          <div className="space-y-5 py-2">
            <div className="text-center space-y-3">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-[#EAF2EA] border border-[#B8DFC9] text-[#236B4F] shadow-xs">
                <RotateCw className="w-7 h-7 animate-spin" />
              </div>
              <div>
                <h4 className="text-base font-extrabold text-[#142820]">
                  Scanning Local Citations
                </h4>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Your citation and NAP discovery scan is currently running. Please keep this window open.
                </p>
              </div>
            </div>

            {/* Target Business Context */}
            {(businessName || city) && (
              <div className="p-3 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2 text-slate-700">
                  <BookOpen className="w-4 h-4 text-[#236B4F]" />
                  <span className="font-semibold">{businessName || 'Business Profile'}</span>
                </div>
                {city && (
                  <span className="text-[11px] font-bold text-slate-500 bg-white px-2 py-0.5 rounded-md border border-[#DCE8DC]">
                    {city}
                  </span>
                )}
              </div>
            )}

            {/* Supported Pipeline Stages (Real Stages) */}
            <div className="space-y-2 rounded-xl bg-slate-50 p-4 border border-slate-200">
              <div className="text-[11px] font-extrabold uppercase tracking-wider text-slate-600 mb-2">
                Active Scan Pipeline
              </div>
              <div className="space-y-2.5 text-xs text-slate-600">
                <div className="flex items-center space-x-2.5">
                  <div className="w-2 h-2 rounded-full bg-[#236B4F] animate-ping" />
                  <span>Discovering citation sources across search engines</span>
                </div>
                <div className="flex items-center space-x-2.5">
                  <div className="w-2 h-2 rounded-full bg-slate-300" />
                  <span>Checking business directory listings & URLs</span>
                </div>
                <div className="flex items-center space-x-2.5">
                  <div className="w-2 h-2 rounded-full bg-slate-300" />
                  <span>Verifying live NAP information & business identity</span>
                </div>
                <div className="flex items-center space-x-2.5">
                  <div className="w-2 h-2 rounded-full bg-slate-300" />
                  <span>Saving verified citations to database</span>
                </div>
              </div>
            </div>

            <div className="text-center">
              <span className="inline-flex items-center text-[11px] font-medium text-slate-400">
                <Clock className="w-3.5 h-3.5 mr-1" />
                This live multi-query search & NAP verification usually takes 10–25 seconds.
              </span>
            </div>
          </div>
        )}

        {/* ─── STATE 2: SCAN COMPLETED (SUCCESS or PARTIAL) ─── */}
        {(isSuccess || isPartial) && (
          <div className="space-y-4">
            <div className={`p-3.5 rounded-xl border flex items-center space-x-3 text-xs ${
              isPartial
                ? 'bg-amber-50 border-amber-200 text-amber-900'
                : 'bg-emerald-50 border-emerald-200 text-emerald-900'
            }`}>
              {isPartial ? (
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              )}
              <div className="flex-1">
                <span className="font-extrabold">
                  {isPartial ? 'Scan completed with notices' : 'Scan completed successfully'}
                </span>
                {isPartial && hasPartialData && (
                  <p className="text-[11px] text-amber-800 mt-0.5">
                    Some results were saved before the scan stopped.
                  </p>
                )}
              </div>
            </div>

            {/* Real Metrics Grid */}
            <div className="grid grid-cols-2 gap-3">
              {typeof verifiedCount === 'number' && (
                <div className="p-3.5 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC]">
                  <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
                    Verified Citations
                  </div>
                  <div className="text-2xl font-black text-[#236B4F] mt-1">
                    {verifiedCount}
                  </div>
                </div>
              )}

              {typeof napMatches === 'number' && (
                <div className="p-3.5 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC]">
                  <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
                    NAP Matches
                  </div>
                  <div className="text-2xl font-black text-slate-800 mt-1">
                    {napMatches}
                  </div>
                </div>
              )}

              {typeof candidatesCount === 'number' && (
                <div className="p-3.5 rounded-xl bg-white border border-slate-200">
                  <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
                    Candidates Checked
                  </div>
                  <div className="text-lg font-extrabold text-slate-800 mt-1">
                    {candidatesCount}
                  </div>
                </div>
              )}

              {typeof rejectedCount === 'number' && (
                <div className="p-3.5 rounded-xl bg-white border border-slate-200">
                  <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">
                    Unverified / Skipped
                  </div>
                  <div className="text-lg font-extrabold text-slate-600 mt-1">
                    {rejectedCount}
                  </div>
                </div>
              )}
            </div>

            {/* Additional Real Data Info */}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-1 text-xs text-slate-600">
              {typeof elapsed === 'number' && (
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Scan Duration:</span>
                  <span className="font-semibold text-slate-700">{elapsed}s</span>
                </div>
              )}
              {typeof queriesCount === 'number' && (
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Search Queries:</span>
                  <span className="font-semibold text-slate-700">{queriesCount}</span>
                </div>
              )}
              {(typeof newAdded === 'number' || typeof existingUpdated === 'number') && (
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Database Index:</span>
                  <span className="font-semibold text-slate-700">
                    {newAdded ?? 0} new, {existingUpdated ?? 0} updated
                  </span>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="pt-2 flex items-center justify-end space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-white border border-[#DCE8DC] hover:bg-[#F7FAF7] text-slate-700 rounded-xl text-xs font-bold transition-all cursor-pointer"
              >
                Close
              </button>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-[#236B4F] hover:bg-[#1D5A42] text-white rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer"
              >
                View Citations
              </button>
            </div>
          </div>
        )}

        {/* ─── STATE 3: ERROR STATE ─── */}
        {isError && (
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 space-y-1.5">
              <div className="flex items-center space-x-2">
                <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
                <span className="text-sm font-extrabold text-rose-950">
                  Scan Could Not Be Completed
                </span>
              </div>
              <p className="text-xs text-rose-800 pl-7 leading-relaxed">
                {error || 'Unable to reach the citation provider or complete the scan.'}
              </p>
            </div>

            {hasPartialData && (
              <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>Some results were saved before the scan stopped.</span>
              </div>
            )}

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-[11px] text-slate-500 space-y-1">
              <p className="font-semibold text-slate-600">Possible troubleshooting steps:</p>
              <ul className="list-disc pl-4 space-y-0.5">
                <li>Verify SERP provider configuration in Settings</li>
                <li>Check your provider API quota and connection status</li>
                <li>Ensure business canonical NAP profile is populated</li>
              </ul>
            </div>

            {/* Action Buttons */}
            <div className="pt-2 flex items-center justify-end space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-bold transition-all cursor-pointer"
              >
                Close
              </button>
              {hasPartialData && (
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 bg-[#236B4F] hover:bg-[#1D5A42] text-white rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer"
                >
                  View Available Results
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};

import React from 'react';
import {
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  TrendingUp,
  MapPin,
  Globe,
  Search,
  Clock,
  ExternalLink,
  Layers
} from 'lucide-react';
import { Modal } from '../ui/Modal';

export interface KeywordScanTarget {
  type: 'all' | 'single';
  keyword?: string;
  location?: string;
  provider?: string;
  totalKeywords?: number;
}

export interface KeywordScanResultData {
  type: 'all' | 'single';
  keyword?: string;
  location?: string;
  provider?: string;
  current_rank?: number | null;
  organic_rank?: number | null;
  local_pack_rank?: number | null;
  maps_rank?: number | null;
  ranking_url?: string | null;
  ranking_title?: string | null;
  serp_type?: string;
  status?: string; // 'checked' | 'not_in_top_100' | 'not_found' | 'error' | ...
  error_message?: string | null;
  // Batch metrics
  total_scanned?: number;
  checked_count?: number; // ranked
  not_found_count?: number; // not in top 100
  error_count?: number;
  organic_count?: number;
  local_pack_count?: number;
  results?: any[];
}

export interface KeywordScanModalProps {
  isOpen: boolean;
  onClose: () => void;
  status: 'idle' | 'running' | 'success' | 'partial' | 'error';
  target: KeywordScanTarget | null;
  result: KeywordScanResultData | null;
  error: string | null;
  onRunInBackground?: () => void;
  onCancelScan?: () => void;
}

export const KeywordScanModal: React.FC<KeywordScanModalProps> = ({
  isOpen,
  onClose,
  status,
  target,
  result,
  error,
  onRunInBackground,
  onCancelScan
}) => {
  if (!isOpen || status === 'idle') return null;

  const isRunning = status === 'running';
  const isSuccess = status === 'success';
  const isPartial = status === 'partial';
  const isError = status === 'error';

  // Check if single keyword was not found in top 100 (which is a valid SUCCESS state, not an error)
  const isSingleNotFound =
    result?.type === 'single' &&
    (result.status === 'not_in_top_100' || result.status === 'not_found' || result.current_rank === null);

  let modalTitle = 'Scanning Keyword Rankings';
  let modalSubtitle = 'Your keyword rankings are being checked. This may take a moment.';
  let modalIcon = <RotateCw className="w-5 h-5 text-[#236B4F] animate-spin" />;

  if (isSuccess) {
    modalTitle = 'Keyword Scan Complete';
    modalSubtitle = 'Your scan finished successfully.';
    modalIcon = <CheckCircle2 className="w-5 h-5 text-emerald-600" />;
  } else if (isPartial) {
    modalTitle = 'Keyword Scan Complete with Notices';
    modalSubtitle = 'Some keywords were checked, but some encountered provider issues.';
    modalIcon = <AlertTriangle className="w-5 h-5 text-amber-600" />;
  } else if (isError) {
    modalTitle = 'Keyword Scan Could Not Be Completed';
    modalSubtitle = 'The ranking lookup could not be completed.';
    modalIcon = <AlertCircle className="w-5 h-5 text-rose-600" />;
  }

  const effectiveProvider = result?.provider || target?.provider || 'Google SERP Provider';
  const effectiveLocation = result?.location || target?.location || 'Target Location';

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
                  Scanning Keyword Rankings
                </h4>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Your keyword rankings are being checked. This may take a moment.
                </p>
              </div>
            </div>

            {/* Real Search Context Details */}
            <div className="rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] p-4 space-y-2.5 text-xs">
              {target?.type === 'single' ? (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 font-medium">Keyword:</span>
                    <span className="font-extrabold text-slate-900 bg-white px-2.5 py-1 rounded-lg border border-[#DCE8DC]">
                      "{target.keyword}"
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 font-medium">Location:</span>
                    <span className="font-semibold text-slate-800 flex items-center">
                      <MapPin className="w-3.5 h-3.5 text-[#236B4F] mr-1" />
                      {effectiveLocation}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 font-medium">Provider:</span>
                    <span className="font-semibold text-slate-800 capitalize">
                      {effectiveProvider}
                    </span>
                  </div>
                  <div className="flex items-center justify-between pt-1 border-t border-[#E8F0E8]">
                    <span className="text-slate-500 font-medium">Status:</span>
                    <span className="text-[#236B4F] font-bold flex items-center">
                      <RotateCw className="w-3 h-3 animate-spin mr-1.5" />
                      Scanning Google search results...
                    </span>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 font-medium">Target:</span>
                    <span className="font-extrabold text-slate-900 bg-white px-2.5 py-1 rounded-lg border border-[#DCE8DC]">
                      All Tracked Keywords ({target?.totalKeywords ?? 0})
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 font-medium">Location:</span>
                    <span className="font-semibold text-slate-800 flex items-center">
                      <MapPin className="w-3.5 h-3.5 text-[#236B4F] mr-1" />
                      {effectiveLocation}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 font-medium">Provider:</span>
                    <span className="font-semibold text-slate-800 capitalize">
                      {effectiveProvider}
                    </span>
                  </div>
                  <div className="flex items-center justify-between pt-1 border-t border-[#E8F0E8]">
                    <span className="text-slate-500 font-medium">Status:</span>
                    <span className="text-[#236B4F] font-bold flex items-center">
                      <RotateCw className="w-3 h-3 animate-spin mr-1.5" />
                      Checking Google Local Pack and organic positions...
                    </span>
                  </div>
                </>
              )}
            </div>

            <div className="flex items-center justify-between border-t border-[#E8F0E8] pt-3">
              <span className="inline-flex items-center text-[11px] font-medium text-slate-500">
                <Clock className="w-3.5 h-3.5 mr-1 text-[#236B4F]" />
                Live SERP lookup in progress.
              </span>
              <div className="flex items-center space-x-2">
                {onRunInBackground && (
                  <button
                    type="button"
                    onClick={onRunInBackground}
                    className="px-3.5 py-1.5 rounded-xl text-xs font-bold text-[#236B4F] bg-[#F1F7F1] border border-[#B8DFC9] hover:bg-[#EAF2EA] transition-all cursor-pointer shadow-2xs"
                  >
                    Run in Background
                  </button>
                )}
                {onCancelScan && (
                  <button
                    type="button"
                    onClick={onCancelScan}
                    className="px-3 py-1.5 rounded-xl text-xs font-bold text-rose-700 bg-rose-50 border border-rose-200 hover:bg-rose-100 transition-all cursor-pointer"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ─── STATE 2: SCAN COMPLETED (SUCCESS or PARTIAL) ─── */}
        {(isSuccess || isPartial) && result && (
          <div className="space-y-4">
            {/* Success / Notice Banner */}
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
                  {isPartial ? 'Scan finished with notices' : 'Scan completed successfully'}
                </span>
                {isSingleNotFound && (
                  <p className="text-[11px] text-emerald-800 mt-0.5 font-medium">
                    Your business was not found in the tracked result range (Top 100).
                  </p>
                )}
                {isPartial && result.error_count && result.error_count > 0 && (
                  <p className="text-[11px] text-amber-800 mt-0.5">
                    {result.error_count} keyword(s) encountered provider lookup errors.
                  </p>
                )}
              </div>
            </div>

            {/* SINGLE KEYWORD RESULT */}
            {result.type === 'single' ? (
              <div className="space-y-3">
                <div className="p-4 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] space-y-3 text-xs">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500 font-medium">Keyword:</span>
                    <span className="font-black text-slate-900 text-sm">
                      "{result.keyword}"
                    </span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-slate-500 font-medium">Ranking Status:</span>
                    {result.current_rank ? (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-black bg-emerald-100 text-emerald-800 border border-emerald-300">
                        Rank #{result.current_rank}
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-bold bg-slate-100 text-slate-700 border border-slate-300">
                        Not in Top 100
                      </span>
                    )}
                  </div>

                  {/* Surface Breakdown */}
                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[#E8F0E8]">
                    <div className="p-2.5 rounded-lg bg-white border border-[#DCE8DC]">
                      <div className="text-[10px] font-bold text-slate-500 uppercase">
                        Organic Rank
                      </div>
                      <div className="text-sm font-extrabold text-slate-800 mt-0.5">
                        {result.organic_rank ? `#${result.organic_rank}` : 'Not Ranked'}
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-white border border-[#DCE8DC]">
                      <div className="text-[10px] font-bold text-slate-500 uppercase">
                        Local Pack Rank
                      </div>
                      <div className="text-sm font-extrabold text-slate-800 mt-0.5">
                        {result.local_pack_rank ? `#${result.local_pack_rank}` : 'Not Ranked'}
                      </div>
                    </div>
                  </div>

                  {result.ranking_url && (
                    <div className="pt-2 border-t border-[#E8F0E8] flex items-center justify-between text-[11px]">
                      <span className="text-slate-500">Ranking URL:</span>
                      <a
                        href={result.ranking_url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-[#236B4F] hover:underline flex items-center max-w-[240px] truncate"
                      >
                        <span className="truncate">{result.ranking_url}</span>
                        <ExternalLink className="w-3 h-3 ml-1 shrink-0" />
                      </a>
                    </div>
                  )}

                  <div className="flex justify-between items-center text-[11px] text-slate-500 pt-1">
                    <span>Provider: <span className="font-semibold text-slate-700 capitalize">{effectiveProvider}</span></span>
                    <span>Location: <span className="font-semibold text-slate-700">{effectiveLocation}</span></span>
                  </div>
                </div>
              </div>
            ) : (
              /* ALL KEYWORDS (BATCH) RESULT */
              <div className="space-y-3">
                {/* Metric Summary Grid */}
                <div className="grid grid-cols-3 gap-2.5">
                  <div className="p-3 rounded-xl bg-white border border-slate-200 text-center">
                    <div className="text-[10px] font-bold text-slate-500 uppercase">
                      Keywords Scanned
                    </div>
                    <div className="text-xl font-black text-slate-900 mt-0.5">
                      {result.total_scanned ?? 0}
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] text-center">
                    <div className="text-[10px] font-bold text-[#236B4F] uppercase">
                      Rankings Found
                    </div>
                    <div className="text-xl font-black text-[#236B4F] mt-0.5">
                      {result.checked_count ?? 0}
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-center">
                    <div className="text-[10px] font-bold text-slate-500 uppercase">
                      Not in Top 100
                    </div>
                    <div className="text-xl font-black text-slate-700 mt-0.5">
                      {result.not_found_count ?? 0}
                    </div>
                  </div>
                </div>

                {/* Surface Breakdown (Organic vs Local Pack) */}
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2 text-xs">
                  <div className="text-[11px] font-extrabold uppercase tracking-wider text-slate-600">
                    Ranking Surfaces
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-slate-200">
                      <span className="text-slate-600 font-medium">Organic Rankings:</span>
                      <span className="font-extrabold text-slate-900">
                        {result.organic_count ?? 0}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-slate-200">
                      <span className="text-slate-600 font-medium">Local Pack:</span>
                      <span className="font-extrabold text-[#236B4F]">
                        {result.local_pack_count ?? 0}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                    <span>Provider: <span className="font-semibold text-slate-700 capitalize">{effectiveProvider}</span></span>
                    <span>Location: <span className="font-semibold text-slate-700">{effectiveLocation}</span></span>
                  </div>
                </div>
              </div>
            )}

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
                View Rankings
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
                  Keyword Scan Could Not Be Completed
                </span>
              </div>
              <p className="text-xs text-rose-800 pl-7 leading-relaxed">
                {error || 'An unexpected error occurred while communicating with the ranking provider.'}
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-2">
              <p className="font-semibold text-slate-700">Identified error details:</p>
              <div className="p-2.5 rounded-lg bg-white border border-slate-200 text-[11px] font-mono text-slate-700 break-words">
                {error || 'Provider request failure'}
              </div>
              <p className="text-[11px] text-slate-500">
                Note: This request failed at the provider or network level. It does not indicate that your keyword is unranked.
              </p>
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
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};

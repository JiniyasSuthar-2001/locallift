import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  TrendingUp,
  Plus,
  ArrowUp,
  ArrowDown,
  Search,
  MapPin,
  Sparkles,
  Trash2,
  Filter,
  RotateCw,
  CheckCircle2,
  AlertCircle,
  Settings,
  ExternalLink,
  HelpCircle,
  Clock,
  Globe
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { useTaskManager } from '../context/TaskManagerContext';
import { Keyword } from '../types';
import { EmptyState } from '../components/ui/EmptyState';
import { Modal } from '../components/ui/Modal';
import { KeywordScanModal, KeywordScanTarget, KeywordScanResultData } from '../components/scan/KeywordScanModal';
import api from '../api/client';
import { getErrorMessage } from '../utils/error';

interface SerpConfigData {
  provider: string;
  connection_status: string;
  has_key?: boolean;
  capabilities?: {
    organic_search?: boolean;
    local_search?: boolean;
    maps_search?: boolean;
    coordinate_search?: boolean;
    geo_grid?: boolean;
  };
}

export const KeywordsView: React.FC = () => {
  const { activeProject, refreshDashboard } = useProject();
  const { notifyJobCreated, runInBackground, cancelTask, refreshTasks } = useTaskManager();
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [loading, setLoading] = useState(false);
  const [isCheckingAll, setIsCheckingAll] = useState(false);
  const [checkingId, setCheckingId] = useState<number | null>(null);
  const [checkMessage, setCheckMessage] = useState<string | null>(null);
  const [serpError, setSerpError] = useState<{ type: 'not_configured' | 'invalid_key' | 'quota_exceeded' | 'timeout' | 'error'; message: string } | null>(null);
  const [serpConfig, setSerpConfig] = useState<SerpConfigData | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newKeyword, setNewKeyword] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Scan State Machine (idle | running | success | partial | error)
  const [scanStatus, setScanStatus] = useState<'idle' | 'running' | 'success' | 'partial' | 'error'>('idle');
  const [scanModalOpen, setScanModalOpen] = useState(false);
  const [scanTarget, setScanTarget] = useState<KeywordScanTarget | null>(null);
  const [scanResult, setScanResult] = useState<KeywordScanResultData | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const pollTimerRef = React.useRef<any>(null);

  // Provider-agnostic configuration check
  const checkSerpStatus = async () => {
    try {
      const resp = await api.get('/serp/config');
      const data: SerpConfigData = resp.data;
      setSerpConfig(data);

      const provider = (data?.provider || '').toLowerCase();
      const isConnected = data?.connection_status === 'connected';
      // OpenSERP does not use an API key; SerpApi requires a key
      const isConfigured = provider === 'openserp' ? isConnected : (isConnected && Boolean(data?.has_key));

      if (!isConfigured && data?.connection_status === 'not_configured') {
        setSerpError({
          type: 'not_configured',
          message: 'SERP provider not configured. Connect your SERP provider in Settings to enable live keyword rank tracking.'
        });
      } else if (data?.connection_status === 'invalid_key') {
        setSerpError({
          type: 'invalid_key',
          message: 'SERP provider rejected your API key. Please check your credentials in Settings.'
        });
      } else if (data?.connection_status === 'quota_exceeded') {
        setSerpError({
          type: 'quota_exceeded',
          message: 'Your SERP provider account search quota has been reached.'
        });
      } else {
        setSerpError(null);
      }
    } catch (e) {
      console.warn('Failed to fetch SERP status:', e);
    }
  };

  const fetchKeywords = async (showLoading = true) => {
    if (!activeProject) return;
    try {
      if (showLoading) setLoading(true);
      const resp = await api.get(`/keywords/${activeProject.id}`);
      setKeywords(resp.data || []);
    } catch (e) {
      console.error('Failed to load keywords:', e);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchKeywords(true);
    checkSerpStatus();
  }, [activeProject?.id]);

  const handleAddKeyword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !newKeyword.trim()) return;
    try {
      await api.post('/keywords', {
        project_id: activeProject.id,
        keyword: newKeyword.trim(),
        target_location: newLocation.trim() || undefined,
        search_intent: 'Commercial',
        search_volume: null
      });
      setNewKeyword('');
      setNewLocation('');
      setIsModalOpen(false);
      await fetchKeywords(false);
      await refreshDashboard();
    } catch (e) {
      console.error('Failed to add keyword:', e);
    }
  };

  // Cleanup polling timer on unmount or project switch
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [activeProject?.id]);

  const handleRunInBackground = () => {
    if (activeJobId) {
      runInBackground(activeJobId);
    }
    setScanModalOpen(false);
  };

  const handleCancelScan = async () => {
    if (activeJobId && activeProject) {
      await cancelTask(activeJobId, 'keyword_rank');
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
      setIsCheckingAll(false);
      setActiveJobId(null);
      setScanStatus('idle');
      setScanModalOpen(false);
    }
  };

  const handleCheckAll = async () => {
    if (!activeProject) return;
    // Duplicate-scan protection
    if (scanStatus === 'running' || isCheckingAll || checkingId !== null) return;

    const targetLoc = (activeProject as any)?.city || activeProject?.country || 'Configured Locations';
    const targetProv = serpConfig?.provider || 'Google SERP Provider';

    try {
      setIsCheckingAll(true);
      setScanStatus('running');
      setScanTarget({
        type: 'all',
        totalKeywords: keywords.length,
        location: targetLoc,
        provider: targetProv
      });
      setScanResult(null);
      setScanError(null);
      setScanModalOpen(true);
      setCheckMessage(null);
      setSerpError(null);

      // Start asynchronous scan job (Part 6 & 7: 30-40 keywords background execution)
      const startResp = await api.post(`/projects/${activeProject.id}/keywords/start-scan`);
      const jobId = startResp.data.job_id;
      setActiveJobId(jobId);

      // Notify global task manager (Part 10 & 12)
      notifyJobCreated({
        id: jobId,
        project_id: activeProject.id,
        project_name: activeProject.name,
        job_type: 'keyword_rank',
        status: 'RUNNING',
        progress: 0,
        total: startResp.data.total_items || keywords.length,
        processed: 0,
        successful: 0,
        failed: 0,
        not_found: 0,
        errors: 0,
        current_stage: startResp.data.current_stage || 'Initializing ranking scan...',
      });

      // Polling loop for active job
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      pollTimerRef.current = setInterval(async () => {
        try {
          const pollResp = await api.get(`/projects/${activeProject.id}/jobs/${jobId}`);
          const job = pollResp.data;

          if (job.status === 'COMPLETED' || job.status === 'COMPLETED_WITH_ERRORS') {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            setIsCheckingAll(false);
            setActiveJobId(null);

            const allResultData: KeywordScanResultData = {
              type: 'all',
              total_scanned: job.processed_items,
              checked_count: job.successful_items,
              not_found_count: job.not_found_items,
              error_count: job.error_count,
              organic_count: job.summary_data?.organic_count || 0,
              local_pack_count: job.summary_data?.local_pack_count || 0,
              provider: targetProv,
              location: targetLoc,
            };

            if (job.status === 'COMPLETED_WITH_ERRORS') {
              setScanStatus('partial');
              setScanResult(allResultData);
              setCheckMessage(`Live SERP check complete with notices: ${job.successful_items} ranked, ${job.not_found_items} not in Top 100, ${job.error_count} errors.`);
            } else {
              setScanStatus('success');
              setScanResult(allResultData);
              setCheckMessage(`Live SERP check complete: ${job.successful_items} ranked, ${job.not_found_items} not in Top 100.`);
            }

            await fetchKeywords(false);
            await refreshDashboard();
          } else if (job.status === 'FAILED' || job.status === 'EXPIRED') {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            setIsCheckingAll(false);
            setActiveJobId(null);
            setScanStatus('error');
            setScanError(job.error_details || 'Keyword scan job failed.');
          } else if (job.status === 'CANCELLED') {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            setIsCheckingAll(false);
            setActiveJobId(null);
            setScanStatus('idle');
            setScanModalOpen(false);
          }
        } catch (pollErr) {
          console.warn('Job polling error:', pollErr);
        }
      }, 1500);

    } catch (e: any) {
      console.error('Failed to check all keywords:', e);
      const errMsg = getErrorMessage(e, 'SERP check failed.');
      setScanStatus('error');
      setScanError(errMsg);
      setIsCheckingAll(false);
      setActiveJobId(null);
      if (errMsg.includes('SERP_PROVIDER_NOT_CONFIGURED') || errMsg.includes('not configured')) {
        setSerpError({
          type: 'not_configured',
          message: 'SERP provider not configured. Connect your SERP provider in Settings to enable keyword tracking.'
        });
      } else {
        setSerpError({
          type: 'error',
          message: errMsg
        });
      }
    }
  };

  const handleCheckSingle = async (keywordId: number) => {
    // Duplicate-scan protection
    if (scanStatus === 'running' || isCheckingAll || checkingId !== null) return;

    const targetKw = keywords.find((k) => k.id === keywordId);
    const kwLocation = targetKw?.target_location || (activeProject as any)?.city || activeProject?.country || 'Target Location';
    const kwProvider = serpConfig?.provider || 'Google SERP Provider';

    try {
      setCheckingId(keywordId);
      setScanStatus('running');
      setScanTarget({
        type: 'single',
        keyword: targetKw?.keyword || 'Selected Keyword',
        location: kwLocation,
        provider: kwProvider
      });
      setScanResult(null);
      setScanError(null);
      setScanModalOpen(true);
      setSerpError(null);

      const resp = await api.post(`/keywords/${keywordId}/check`);
      const st = resp.data?.status;
      const isNotFound = st === 'not_in_top_100' || st === 'not_found' || (st === 'checked' && resp.data?.current_rank === null);
      const isProviderErr = st === 'provider_error' || st === 'timeout' || st === 'location_error' || st === 'error';
      const isNotConfig = st === 'not_configured';

      if (isNotConfig) {
        setScanStatus('error');
        const msg = resp.data?.error_message || 'SERP provider not configured. Connect your SERP provider in Settings.';
        setScanError(msg);
        setSerpError({ type: 'not_configured', message: msg });
      } else if (isProviderErr) {
        setScanStatus('error');
        const userErr = resp.data?.error_message || (st === 'timeout' ? 'Provider timeout: Search provider took too long to respond.' : st === 'location_error' ? 'Invalid location: Search provider could not resolve target location.' : 'SERP lookup failed with provider error.');
        setScanError(userErr);
        setSerpError({ type: 'error', message: userErr });
      } else if (isNotFound) {
        // IMPORTANT: Not in top 100 is SUCCESS (completed search), NOT an error!
        setScanStatus('success');
        setScanResult({
          type: 'single',
          keyword: targetKw?.keyword || resp.data?.keyword,
          location: kwLocation,
          provider: resp.data?.provider || kwProvider,
          current_rank: null,
          organic_rank: null,
          local_pack_rank: null,
          status: 'not_in_top_100'
        });
      } else {
        // Successfully ranked
        setScanStatus('success');
        setScanResult({
          type: 'single',
          keyword: targetKw?.keyword || resp.data?.keyword,
          location: kwLocation,
          provider: resp.data?.provider || kwProvider,
          current_rank: resp.data?.current_rank,
          organic_rank: resp.data?.organic_rank,
          local_pack_rank: resp.data?.local_pack_rank,
          maps_rank: resp.data?.maps_rank,
          ranking_url: resp.data?.ranking_url,
          ranking_title: resp.data?.ranking_title,
          status: 'checked'
        });
      }

      // Always refetch fresh database state
      await fetchKeywords(false);
      await refreshDashboard();
    } catch (e: any) {
      console.error(`Failed to check keyword ${keywordId}:`, e);
      const errMsg = getErrorMessage(e, 'Failed to check keyword ranking.');
      setScanStatus('error');
      setScanError(errMsg);
      if (errMsg.includes('SERP_PROVIDER_NOT_CONFIGURED') || errMsg.includes('not configured')) {
        setSerpError({
          type: 'not_configured',
          message: 'SERP provider not configured. Connect your SERP provider in Settings to enable keyword tracking.'
        });
      } else {
        setSerpError({
          type: 'error',
          message: errMsg
        });
      }
    } finally {
      setCheckingId(null);
    }
  };

  const handleDeleteKeyword = async (keywordId: number) => {
    if (!confirm('Are you sure you want to remove this keyword from tracking?')) return;
    try {
      await api.delete(`/keywords/${keywordId}`);
      await fetchKeywords(false);
      await refreshDashboard();
    } catch (e) {
      console.error('Failed to delete keyword:', e);
    }
  };

  // Reliable search filter by keyword, target location, ranking URL, or ranking title
  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return keywords;
    const q = searchQuery.trim().toLowerCase();
    return keywords.filter((k) =>
      (k.keyword && k.keyword.toLowerCase().includes(q)) ||
      (k.target_location && k.target_location.toLowerCase().includes(q)) ||
      (k.ranking_url && k.ranking_url.toLowerCase().includes(q)) ||
      (k.ranking_title && k.ranking_title.toLowerCase().includes(q))
    );
  }, [keywords, searchQuery]);

  if (!activeProject) {
    return (
      <EmptyState
        icon={TrendingUp}
        badge="Rank Tracker"
        title="Select a Project"
        description="Select a project from the top navigation to track local search rankings and Google Maps positions."
      />
    );
  }

  // Capability check
  const supportsLocalPack = serpConfig?.capabilities?.local_search ?? true;

  return (
    <div className="space-y-6">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <TrendingUp className="w-6 h-6 text-[#236B4F]" />
            <span>Keyword Rank Tracker</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real SERP rank tracking across Google Local Pack and organic positions for <span className="font-semibold text-slate-700">{activeProject.domain}</span>.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={handleCheckAll}
            disabled={scanStatus === 'running' || isCheckingAll || checkingId !== null || keywords.length === 0}
            className="flex items-center space-x-2 px-4 py-2 rounded-xl border border-[#DCE8DC] bg-white hover:bg-[#F7FAF7] text-[#236B4F] text-xs font-bold shadow-xs transition-all disabled:opacity-50 cursor-pointer"
          >
            <RotateCw className={`w-3.5 h-3.5 ${scanStatus === 'running' && scanTarget?.type === 'all' ? 'animate-spin' : ''}`} />
            <span>{scanStatus === 'running' && scanTarget?.type === 'all' ? 'Checking SERP...' : 'Check Live Rankings'}</span>
          </button>

          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-[#236B4F] hover:bg-[#1D5A42] text-white rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Add Target Keywords</span>
          </button>
        </div>
      </div>

      {serpError && (
        <div className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
          serpError.type === 'not_configured'
            ? 'bg-amber-50/80 border-amber-200 text-amber-900'
            : 'bg-rose-50/80 border-rose-200 text-rose-900'
        }`}>
          <div className="flex items-start space-x-2.5">
            <AlertCircle className={`w-4 h-4 shrink-0 mt-0.5 ${
              serpError.type === 'not_configured' ? 'text-amber-600' : 'text-rose-600'
            }`} />
            <div>
              <div className="font-bold">
                {serpError.type === 'not_configured'
                  ? 'SERP Provider Not Configured'
                  : serpError.type === 'invalid_key'
                  ? 'Invalid SERP API Key'
                  : serpError.type === 'quota_exceeded'
                  ? 'SERP Provider Quota Limit'
                  : 'SERP Rank Tracking Error'}
              </div>
              <div className="mt-0.5 text-slate-600">{serpError.message}</div>
            </div>
          </div>
          <Link
            to="/settings"
            className={`inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-lg font-bold text-xs shrink-0 self-start sm:self-auto transition-all shadow-2xs ${
              serpError.type === 'not_configured'
                ? 'bg-amber-600 hover:bg-amber-700 text-white'
                : 'bg-rose-600 hover:bg-rose-700 text-white'
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
            <span>Open SERP Settings</span>
            <ExternalLink className="w-3 h-3 ml-0.5" />
          </Link>
        </div>
      )}

      {checkMessage && (
        <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center space-x-2 text-xs text-emerald-900 font-semibold">
          <CheckCircle2 className="w-4 h-4 text-[#236B4F] shrink-0" />
          <span>{checkMessage}</span>
        </div>
      )}

      {/* Surface Clarification Notice */}
      <div className="p-3.5 bg-[#F7FAF7] border border-[#DCE8DC] rounded-xl flex items-center justify-between gap-3 text-xs text-slate-600">
        <div className="flex items-center gap-2">
          <MapPin className="w-4 h-4 text-[#236B4F] shrink-0" />
          <span>
            <b>Live SERP Surfaces:</b> Google Organic and 3-Pack rankings are monitored directly from search engine result pages. For 5x5 coordinate grid positions, view{' '}
            <Link to="/rankings/grid" className="text-[#236B4F] font-bold hover:underline">
              Local Geo-Grid Rankings →
            </Link>
          </span>
        </div>
      </div>

      {/* Filter & Count Bar */}
      <div className="flex items-center justify-between gap-4 bg-white p-3.5 rounded-xl border border-[#DCE8DC] shadow-xs">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search tracked keywords by phrase, location, or URL..."
            className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-[#236B4F]"
          />
        </div>

        <div className="text-xs text-slate-500 font-bold">
          {filtered.length} of {keywords.length} Keywords Tracked
        </div>
      </div>

      {/* Keywords Table */}
      <div className="rounded-2xl border border-[#DCE8DC] bg-white overflow-hidden shadow-xs">
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-400">
            <RotateCw className="w-8 h-8 animate-spin text-[#236B4F] mb-3" />
            <p className="text-xs font-bold text-slate-700">Loading tracked keywords...</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Fetching live SERP positions & historical rankings</p>
          </div>
        ) : filtered.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-[#F7FAF7] text-[#587568] uppercase text-[10px] font-black tracking-wider border-b border-[#EBF2EB]">
                <tr>
                  <th className="p-4">Keyword Phrase</th>
                  <th className="p-4">Target Location</th>
                  <th className="p-4">Google Organic</th>
                  <th className="p-4">Google Local Pack</th>
                  <th className="p-4">Movement</th>
                  <th className="p-4 text-right">Search Volume</th>
                  <th className="p-4 text-right">Last Checked</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EBF2EB]">
                {filtered.map((kw) => {
                  const isCheckingThis = checkingId === kw.id;
                  const rankStatusNorm = (kw.rank_status || '').toUpperCase();

                  // Correct Display Priority for Google Organic:
                  // 1. Checking / Loading
                  // 2. PROVIDER_ERROR
                  // 3. NOT_CONFIGURED
                  // 4. TIMEOUT / LOCATION_ERROR
                  // 5. NOT_IN_TOP_100
                  // 6. Successful Organic Rank
                  // 7. NOT_CHECKED / Default
                  const renderOrganicRank = () => {
                    if (isCheckingThis || isCheckingAll) {
                      return (
                        <span className="inline-flex items-center text-xs text-[#236B4F] font-bold">
                          <RotateCw className="w-3 h-3 mr-1 animate-spin" /> Checking...
                        </span>
                      );
                    }
                    if (rankStatusNorm === 'PROVIDER_ERROR') {
                      return (
                        <div className="space-y-0.5">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-extrabold bg-rose-50 text-rose-700 border border-rose-200">
                            SERP error
                          </span>
                          {kw.previous_rank && (
                            <span className="text-[10px] text-slate-400 block">Last: #{kw.previous_rank}</span>
                          )}
                        </div>
                      );
                    }
                    if (rankStatusNorm === 'NOT_CONFIGURED') {
                      return (
                        <div className="space-y-0.5">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-extrabold bg-amber-50 text-amber-700 border border-amber-200">
                            Not configured
                          </span>
                        </div>
                      );
                    }
                    if (rankStatusNorm === 'TIMEOUT') {
                      return (
                        <div className="space-y-0.5">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-extrabold bg-amber-50 text-amber-700 border border-amber-200">
                            Timeout
                          </span>
                          {kw.previous_rank && (
                            <span className="text-[10px] text-slate-400 block">Last: #{kw.previous_rank}</span>
                          )}
                        </div>
                      );
                    }
                    if (rankStatusNorm === 'LOCATION_ERROR') {
                      return (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-extrabold bg-rose-50 text-rose-700 border border-rose-200">
                          Location error
                        </span>
                      );
                    }
                    if (rankStatusNorm === 'NOT_IN_TOP_100') {
                      return (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-extrabold bg-slate-100 text-slate-600 border border-slate-200">
                          Not in Top 100
                        </span>
                      );
                    }
                    if (kw.organic_rank !== null && kw.organic_rank !== undefined) {
                      return (
                        <span
                          className={`inline-flex items-center justify-center px-2.5 py-1 rounded-lg font-black text-xs ${
                            kw.organic_rank <= 3
                              ? 'bg-emerald-100 text-emerald-900 border border-emerald-200'
                              : kw.organic_rank <= 10
                              ? 'bg-blue-100 text-blue-900 border border-blue-200'
                              : 'bg-slate-100 text-slate-700 border border-slate-200'
                          }`}
                        >
                          #{kw.organic_rank}
                        </span>
                      );
                    }
                    if (kw.current_rank !== null && kw.current_rank !== undefined && rankStatusNorm === 'RANKED') {
                      return (
                        <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-lg font-black text-xs bg-slate-100 text-slate-700 border border-slate-200">
                          #{kw.current_rank}
                        </span>
                      );
                    }
                    return (
                      <span className="text-slate-400 text-[11px] font-medium italic">Not checked</span>
                    );
                  };

                  // Correct Display Priority for Google Local Pack:
                  // 1. Checking
                  // 2. Provider Error / Not Configured / Timeout
                  // 3. Provider does not support local pack -> "Not supported"
                  // 4. Successful Local Pack Rank -> "Pack #X"
                  // 5. Confirmed Not in 3-Pack -> "Not in 3-Pack"
                  // 6. Not checked -> "—"
                  const renderLocalPackRank = () => {
                    if (isCheckingThis || isCheckingAll) {
                      return <span className="text-slate-400 text-xs">—</span>;
                    }
                    if (['PROVIDER_ERROR', 'NOT_CONFIGURED', 'TIMEOUT', 'LOCATION_ERROR'].includes(rankStatusNorm)) {
                      return <span className="text-slate-400 text-xs">—</span>;
                    }
                    if (!supportsLocalPack) {
                      return (
                        <span className="text-slate-400 text-[10px] font-medium" title="Current SERP provider does not support local 3-pack extraction">
                          Not supported
                        </span>
                      );
                    }
                    if (kw.local_pack_rank !== null && kw.local_pack_rank !== undefined) {
                      return (
                        <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-lg font-black text-xs bg-emerald-100 text-emerald-900 border border-emerald-300">
                          Pack #{kw.local_pack_rank}
                        </span>
                      );
                    }
                    if (rankStatusNorm === 'RANKED' || rankStatusNorm === 'NOT_IN_TOP_100') {
                      return (
                        <span className="text-slate-400 text-[10px] font-semibold">Not in 3-Pack</span>
                      );
                    }
                    return (
                      <span className="text-slate-400 text-[11px] font-medium">—</span>
                    );
                  };

                  // Movement Calculation Display:
                  const renderMovement = () => {
                    if (['PROVIDER_ERROR', 'NOT_CONFIGURED', 'TIMEOUT', 'LOCATION_ERROR'].includes(rankStatusNorm)) {
                      return <span className="text-slate-400 text-[11px] font-medium">Check failed</span>;
                    }
                    if (kw.movement_label && kw.movement_label !== '—') {
                      const isUp = kw.movement_label.includes('+') || kw.movement_label.toLowerCase().includes('improved') || kw.movement_label.toLowerCase().includes('entered');
                      const isDown = kw.movement_label.includes('-') || kw.movement_label.toLowerCase().includes('declined') || kw.movement_label.toLowerCase().includes('lost');
                      return (
                        <span className={`inline-flex items-center font-bold text-[11px] ${
                          isUp ? 'text-emerald-700' : isDown ? 'text-rose-700' : 'text-slate-600'
                        }`}>
                          {kw.movement_label}
                        </span>
                      );
                    }
                    if (typeof kw.previous_rank === 'number' && typeof kw.current_rank === 'number') {
                      const diff = kw.previous_rank - kw.current_rank;
                      if (diff > 0) return <span className="font-bold text-xs text-emerald-700">+{diff} improved</span>;
                      if (diff < 0) return <span className="font-bold text-xs text-rose-700">{diff} declined</span>;
                      return <span className="text-slate-400 text-xs">No change</span>;
                    }
                    return <span className="text-slate-400 font-medium">—</span>;
                  };

                  return (
                    <tr key={kw.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="p-4">
                        <div className="font-extrabold text-slate-900 text-sm">{kw.keyword}</div>
                        {kw.ranking_url ? (
                          <a
                            href={kw.ranking_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-[#236B4F] hover:underline truncate max-w-xs font-mono block mt-0.5 flex items-center"
                            title={kw.ranking_url}
                          >
                            <span className="truncate">{kw.ranking_url}</span>
                            <ExternalLink className="w-2.5 h-2.5 ml-1 shrink-0" />
                          </a>
                        ) : null}
                      </td>
                      <td className="p-4 text-slate-600">
                        <div className="flex items-center space-x-1 font-medium">
                          <MapPin className="w-3 h-3 text-[#236B4F] shrink-0" />
                          <span>{kw.target_location || 'Project Location'}</span>
                        </div>
                      </td>
                      <td className="p-4">
                        {renderOrganicRank()}
                      </td>
                      <td className="p-4">
                        {renderLocalPackRank()}
                      </td>
                      <td className="p-4">
                        {renderMovement()}
                      </td>
                      <td className="p-4 text-right font-mono text-slate-600">
                        {kw.search_volume !== null && kw.search_volume !== undefined ? (
                          <span className="font-bold text-slate-900">{kw.search_volume.toLocaleString()} / mo</span>
                        ) : (
                          <span className="text-slate-400 text-[10px] italic" title="Keyword search volume unavailable from current SERP provider">
                            Unavailable
                          </span>
                        )}
                      </td>
                      <td className="p-4 text-right text-[11px] text-slate-500 font-medium whitespace-nowrap">
                        {kw.last_successful_check_at ? (
                          <div>
                            <span>
                              {new Date(kw.last_successful_check_at).toLocaleDateString(undefined, {
                                month: 'short',
                                day: 'numeric'
                              })}
                            </span>
                            {['PROVIDER_ERROR', 'TIMEOUT'].includes(rankStatusNorm) && (
                              <span className="block text-[9px] text-rose-500 font-bold">Latest: Failed</span>
                            )}
                          </div>
                        ) : kw.last_checked_at ? (
                          <span>
                            {new Date(kw.last_checked_at).toLocaleDateString(undefined, {
                              month: 'short',
                              day: 'numeric'
                            })}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="p-4 text-right space-x-1 whitespace-nowrap">
                        <button
                          onClick={() => handleCheckSingle(kw.id)}
                          disabled={scanStatus === 'running' || isCheckingAll || checkingId !== null}
                          title="Check live ranking on SERP"
                          className="p-1.5 rounded-lg hover:bg-[#F0F6F2] text-slate-400 hover:text-[#236B4F] transition-colors cursor-pointer disabled:opacity-50"
                        >
                          <RotateCw className={`w-3.5 h-3.5 ${checkingId === kw.id ? 'animate-spin text-[#236B4F]' : ''}`} />
                        </button>
                        <button
                          onClick={() => handleDeleteKeyword(kw.id)}
                          title="Remove keyword"
                          className="p-1.5 rounded-lg hover:bg-rose-50 text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={TrendingUp}
            badge="No Keywords"
            title={searchQuery ? 'No Matching Keywords' : 'No Tracked Keywords'}
            description={
              searchQuery
                ? 'No tracked keywords match your search query.'
                : 'Add target search terms to track Google Organic and Local 3-Pack positions.'
            }
            actionText={searchQuery ? undefined : 'Add Target Keywords'}
            onAction={searchQuery ? undefined : () => setIsModalOpen(true)}
          />
        )}
      </div>

      {/* Add Keyword Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        maxWidth="md"
        title="Add Target Keywords"
        description="Track search rankings on Google for this business"
      >
        <form onSubmit={handleAddKeyword} className="space-y-4 text-xs">
          <div>
            <label className="text-slate-700 block mb-1 font-bold">Keyword Phrase *</label>
            <input
              type="text"
              required
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              placeholder="e.g. seafood restaurant melbourne, emergency plumber"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-[#236B4F] font-medium"
            />
          </div>

          <div>
            <label className="text-slate-700 block mb-1 font-bold">Target Location (Optional)</label>
            <input
              type="text"
              value={newLocation}
              onChange={(e) => setNewLocation(e.target.value)}
              placeholder="e.g. Melbourne, Victoria or leave blank for project city"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-[#236B4F] font-medium"
            />
            <p className="text-[10px] text-slate-400 mt-1">If blank, the project's primary city/metro will be used for SERP queries.</p>
          </div>

          <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 font-bold"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-[#236B4F] hover:bg-[#1D5A42] text-white font-bold shadow-xs cursor-pointer"
            >
              Add Keyword
            </button>
          </div>
        </form>
      </Modal>

      {/* ─── Keyword Scan Progress & Completion Modal (Part 9) ─── */}
      <KeywordScanModal
        isOpen={scanModalOpen}
        onClose={() => {
          setScanModalOpen(false);
          if (scanStatus !== 'running') {
            setScanStatus('idle');
          }
        }}
        status={scanStatus}
        target={scanTarget}
        result={scanResult}
        error={scanError}
        onRunInBackground={handleRunInBackground}
        onCancelScan={handleCancelScan}
      />
    </div>
  );
};

export default KeywordsView;

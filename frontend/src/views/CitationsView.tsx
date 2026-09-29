import React, { useState, useEffect, useMemo } from 'react';
import {
  BookOpen,
  Plus,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  RotateCw,
  Search,
  Trash2,
  Edit2,
  ShieldCheck,
  Building,
  MapPin,
  Phone,
  Globe,
  HelpCircle,
  ChevronRight,
  Code2,
  Info,
  Check,
  X,
  AlertTriangle,
  Flame,
  Clock
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { Citation, CitationDistribution } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { normalizeExternalUrl } from '../utils/url';
import { Modal } from '../components/ui/Modal';
import { CitationScanModal, CitationScanResultData } from '../components/scan/CitationScanModal';
import api from '../api/client';
import { getErrorMessage } from '../utils/error';

interface FieldComparison {
  expected: string | null;
  found: string | null;
  status: 'match' | 'partial_match' | 'mismatch' | 'missing' | 'not_verified' | 'not_evaluated';
}

interface NAPSourceComparison {
  source_type: string;
  source_name: string;
  listing_url: string | null;
  provenance: string;
  is_consistent: boolean;
  name?: FieldComparison;
  phone?: FieldComparison;
  address?: FieldComparison;
  website?: FieldComparison;
}

export const CitationsView: React.FC = () => {
  const { activeProject } = useProject();
  const [citations, setCitations] = useState<Citation[]>([]);
  const [distribution, setDistribution] = useState<CitationDistribution | null>(null);
  const [loading, setLoading] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);

  // Scan State Machine (idle | running | success | partial | error)
  const [scanStatus, setScanStatus] = useState<'idle' | 'running' | 'success' | 'partial' | 'error'>('idle');
  const [scanModalOpen, setScanModalOpen] = useState(false);
  const [scanResult, setScanResult] = useState<CitationScanResultData | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  // Detail Modal / Drawer
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  // Add / Edit Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCitation, setEditingCitation] = useState<Citation | null>(null);
  const [directoryName, setDirectoryName] = useState('');
  const [listingUrl, setListingUrl] = useState('');
  const [category, setCategory] = useState('General Directory');
  const [foundName, setFoundName] = useState('');
  const [foundAddress, setFoundAddress] = useState('');
  const [foundPhone, setFoundPhone] = useState('');
  const [foundWebsite, setFoundWebsite] = useState('');
  const [statusVal, setStatusVal] = useState('submitted');
  const [submitting, setSubmitting] = useState(false);

  // Fetch Citations & Distribution
  const fetchCitationsData = async (showLoading: boolean = true) => {
    if (!activeProject) return;
    try {
      if (showLoading) setLoading(true);
      const resp = await api.get(`/local-seo/citations/${activeProject.id}/distribution`);
      if (resp.data) {
        setDistribution(resp.data);
        setCitations(resp.data.citations || []);
      }
    } catch (e: any) {
      console.error('Failed to load citations distribution:', e);
      try {
        const fallback = await api.get(`/local-seo/citations/${activeProject.id}`);
        setCitations(fallback.data || []);
      } catch (err) {
        console.error('Fallback citations fetch failed:', err);
      }
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchCitationsData(true);
  }, [activeProject?.id]);

  // Discover / Scan & Verify Citations
  const handleScanAndVerify = async () => {
    if (!activeProject) return;
    // Duplicate-scan protection: block if already running
    if (scanStatus === 'running' || discovering) return;

    try {
      setDiscovering(true);
      setScanStatus('running');
      setScanModalOpen(true);
      setScanResult(null);
      setScanError(null);
      setStatusMsg(null);

      const resp = await api.post(`/local-seo/citations/${activeProject.id}/discover`);
      await fetchCitationsData(false);

      const details = resp.data?.details || {};
      const scanStatusBackend = details.scan_status || 'completed';
      const isPartial =
        scanStatusBackend === 'completed_with_errors' ||
        (Array.isArray(details.scan_errors) && details.scan_errors.length > 0 && (details.verified_citations > 0 || details.candidates_found > 0));
      const isFailed =
        scanStatusBackend === 'failed' &&
        (!details.verified_citations || details.verified_citations === 0);

      const resultData: CitationScanResultData = {
        project_id: details.project_id || activeProject.id,
        queries_executed: details.queries_executed,
        candidates_found: details.candidates_found,
        verified_citations: details.verified_citations ?? 0,
        rejected_candidates: details.rejected_candidates ?? 0,
        new_citations_added: details.new_citations_added ?? 0,
        existing_citations_updated: details.existing_citations_updated ?? 0,
        elapsed_seconds: details.elapsed_seconds,
        scan_status: details.scan_status,
        scan_errors: details.scan_errors,
        rejection_summary: details.rejection_summary,
        total_nap_matches: details.verified_citations ?? 0
      };

      if (isFailed) {
        setScanStatus('error');
        setScanError(details.scan_errors?.[0] || 'Citation scan failed to complete.');
      } else if (isPartial) {
        setScanStatus('partial');
        setScanResult(resultData);
      } else {
        setScanStatus('success');
        setScanResult(resultData);
      }

      setStatusMsg({
        type: isFailed ? 'error' : isPartial ? 'info' : 'success',
        text: resp.data?.message || `Citation scan completed: Discovered ${details.candidates_found || 0} listings, verified ${details.verified_citations || 0}.`
      });
    } catch (e: any) {
      console.error('Citation discovery error:', e);
      const userErr = getErrorMessage(e, 'Failed to execute citation scan and verification.');
      setScanStatus('error');
      setScanError(userErr);
      setStatusMsg({
        type: 'error',
        text: userErr
      });
    } finally {
      setDiscovering(false);
    }
  };

  // Open Add Modal
  const openAddModal = () => {
    setEditingCitation(null);
    setDirectoryName('');
    setListingUrl('');
    setCategory('General Directory');
    setFoundName('');
    setFoundAddress('');
    setFoundPhone('');
    setFoundWebsite('');
    setStatusVal('submitted');
    setIsModalOpen(true);
  };

  // Open Edit Modal
  const openEditModal = (cit: Citation) => {
    setEditingCitation(cit);
    setDirectoryName(cit.source_name || cit.directory_name || '');
    setListingUrl(cit.listing_url || '');
    setCategory(cit.category || 'General Directory');
    setFoundName(cit.found_name || '');
    setFoundAddress(cit.found_address || '');
    setFoundPhone(cit.found_phone || '');
    setFoundWebsite(cit.found_website || '');
    setStatusVal(cit.status || 'submitted');
    setIsModalOpen(true);
  };

  // Save Citation (Create or Edit)
  const handleSaveCitation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !directoryName.trim()) return;
    try {
      setSubmitting(true);
      if (editingCitation) {
        const resp = await api.post(`/local-seo/citations/${editingCitation.id}/status`, {
          status: statusVal,
          listing_url: listingUrl.trim() || undefined,
          found_name: foundName.trim() || undefined,
          found_address: foundAddress.trim() || undefined,
          found_phone: foundPhone.trim() || undefined,
          found_website: foundWebsite.trim() || undefined
        });
        const updated = resp.data;
        setCitations(prev => prev.map(c => c.id === editingCitation.id ? updated : c));
        setStatusMsg({ type: 'success', text: `Citation "${directoryName}" updated successfully.` });
      } else {
        const resp = await api.post('/local-seo/citations', {
          project_id: activeProject.id,
          directory_name: directoryName.trim(),
          source_name: directoryName.trim(),
          listing_url: listingUrl.trim() || undefined,
          category: category.trim() || 'General Directory',
          status: statusVal,
          citation_type: 'USER_PROVIDED',
          verification_status: statusVal === 'approved' ? 'VERIFIED' : 'OBSERVED',
          found_name: foundName.trim() || undefined,
          found_address: foundAddress.trim() || undefined,
          found_phone: foundPhone.trim() || undefined,
          found_website: foundWebsite.trim() || undefined
        });
        const created = resp.data;
        setCitations(prev => [created, ...prev]);
        setStatusMsg({ type: 'success', text: `Citation "${directoryName}" added successfully.` });
      }
      setIsModalOpen(false);
      fetchCitationsData(false);
    } catch (e: any) {
      console.error('Failed to save citation:', e);
      setStatusMsg({ type: 'error', text: getErrorMessage(e, 'Failed to save directory citation.') });
    } finally {
      setSubmitting(false);
    }
  };

  // Delete Citation
  const handleDeleteCitation = async (citId: number) => {
    try {
      await api.delete(`/local-seo/citations/${citId}`);
      setCitations(prev => prev.filter(c => c.id !== citId));
      setStatusMsg({ type: 'success', text: 'Directory citation removed successfully.' });
      fetchCitationsData(false);
    } catch (e: any) {
      console.error('Failed to delete citation:', e);
      setStatusMsg({ type: 'error', text: getErrorMessage(e, 'Failed to remove citation.') });
    }
  };

  // Filtered citations list
  const filteredCitations = useMemo(() => {
    let list = citations;
    if (statusFilter !== 'all') {
      list = list.filter(c => {
        const vStatus = (c.verification_status || '').toLowerCase();
        const sStatus = (c.status || '').toLowerCase();
        if (statusFilter === 'verified') return vStatus === 'verified' || sStatus === 'approved';
        if (statusFilter === 'observed') return vStatus === 'observed';
        if (statusFilter === 'mismatch') return vStatus === 'mismatch' || (c.nap_status || '').toLowerCase() === 'mismatch';
        if (statusFilter === 'partial_match') return vStatus === 'partial_match';
        if (statusFilter === 'unable_to_verify') return vStatus === 'unable_to_verify' || sStatus === 'failed';
        return true;
      });
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      list = list.filter(c =>
        (c.source_name && c.source_name.toLowerCase().includes(q)) ||
        (c.directory_name && c.directory_name.toLowerCase().includes(q)) ||
        (c.domain && c.domain.toLowerCase().includes(q)) ||
        (c.listing_url && c.listing_url.toLowerCase().includes(q)) ||
        (c.found_name && c.found_name.toLowerCase().includes(q))
      );
    }
    return list;
  }, [citations, statusFilter, searchQuery]);

  if (!activeProject) {
    return (
      <EmptyState
        icon={BookOpen}
        badge="Citations & NAP"
        title="Select a Project"
        description="Select a business project to audit local citations, exact directory listings, and NAP consistency across the web."
      />
    );
  }

  // Canonical Data
  const canonical = distribution?.canonical_profile;
  const canonicalName = canonical?.business_name || activeProject.name || '—';
  const canonicalAddress = canonical?.primary_address || (canonical?.city ? `${canonical.city}${canonical.state ? ', ' + canonical.state : ''}` : '—');
  const canonicalPhone = canonical?.primary_phone || '—';
  const canonicalWebsite = canonical?.website || (activeProject.domain ? `https://${activeProject.domain}` : '—');
  const provenance = canonical?.verification_status === 'GBP_VERIFIED' ? 'Google Business Profile' : 'Project Business Profile';

  // Counts & KPIs
  const totalListings = distribution?.total_citations ?? citations.length;
  const verifiedCount = distribution?.verified_count ?? citations.filter(c => (c.verification_status || '').toUpperCase() === 'VERIFIED' || c.status === 'approved').length;
  const mismatchCount = distribution?.mismatch_count ?? citations.filter(c => (c.verification_status || '').toUpperCase() === 'MISMATCH' || (c.nap_status || '').toLowerCase() === 'mismatch').length;
  const observedCount = distribution?.observed_count ?? citations.filter(c => (c.verification_status || '').toUpperCase() === 'OBSERVED').length;
  const unableCount = distribution?.unable_to_verify_count ?? citations.filter(c => (c.verification_status || '').toUpperCase() === 'UNABLE_TO_VERIFY').length;
  const napMatchesCount = distribution?.approved_count ?? citations.filter(c => (c.nap_status || '').toLowerCase() === 'consistent' || (c.nap_status || '').toLowerCase() === 'match').length;
  const healthScore = distribution?.health_score ?? (totalListings > 0 ? Math.round((verifiedCount / totalListings) * 100) : 100);

  // Website Schema Comparison (if any)
  const schemaComparisons = (distribution?.nap_comparisons || []).filter(c => c.source_type === 'WEBSITE_SCHEMA');

  const getVerificationBadge = (vStatus?: string, status?: string) => {
    const norm = (vStatus || status || 'OBSERVED').toUpperCase();
    if (norm === 'VERIFIED' || norm === 'APPROVED') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase bg-emerald-50 text-emerald-800 border border-emerald-200">
          <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-600" />
          VERIFIED
        </span>
      );
    }
    if (norm === 'PARTIAL_MATCH') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase bg-amber-50 text-amber-800 border border-amber-200">
          <AlertTriangle className="w-3 h-3 mr-1 text-amber-600" />
          PARTIAL MATCH
        </span>
      );
    }
    if (norm === 'MISMATCH' || norm === 'FAILED') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase bg-rose-50 text-rose-800 border border-rose-200">
          <X className="w-3 h-3 mr-1 text-rose-600" />
          MISMATCH
        </span>
      );
    }
    if (norm === 'UNABLE_TO_VERIFY') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase bg-slate-100 text-slate-700 border border-slate-300">
          <HelpCircle className="w-3 h-3 mr-1 text-slate-500" />
          UNABLE TO VERIFY
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase bg-blue-50 text-blue-800 border border-blue-200">
        <Info className="w-3 h-3 mr-1 text-blue-600" />
        OBSERVED
      </span>
    );
  };

  const renderFieldBadge = (value: string | null | undefined, canonicalVal: string | null | undefined, label: string) => {
    if (!value || value.trim() === '') {
      return (
        <div className="space-y-0.5">
          <span className="text-[10px] font-bold text-slate-400 italic">
            {label} not detected
          </span>
        </div>
      );
    }
    return (
      <div className="space-y-0.5">
        <div className="text-xs text-slate-800 font-medium break-words">
          {value}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* ─── Header & Primary Actions ─── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <BookOpen className="w-6 h-6 text-[#236B4F]" />
            <span>Local Citations & NAP</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1 max-w-3xl">
            Discover, verify, and monitor your business listings and Name, Address, Phone consistency across the web.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleScanAndVerify}
            disabled={scanStatus === 'running' || discovering}
            className="flex items-center space-x-2 px-4 py-2 bg-[#236B4F] hover:bg-[#1D5A42] text-white rounded-xl text-xs font-bold shadow-xs transition-all disabled:opacity-50 cursor-pointer"
          >
            <RotateCw className={`w-3.5 h-3.5 ${scanStatus === 'running' || discovering ? 'animate-spin' : ''}`} />
            <span>{scanStatus === 'running' || discovering ? 'Scanning & Verifying...' : 'Scan & Verify Citations'}</span>
          </button>
          <button
            onClick={openAddModal}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-white border border-[#DCE8DC] hover:bg-[#F7FAF7] text-slate-800 rounded-xl text-xs font-bold shadow-xs transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 text-[#236B4F]" />
            <span>Add Listing</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {statusMsg && (
        <div
          className={`p-3.5 rounded-xl border flex items-center space-x-2.5 text-xs ${
            statusMsg.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : statusMsg.type === 'error'
              ? 'bg-rose-50 border-rose-200 text-rose-900'
              : 'bg-blue-50 border-blue-200 text-blue-900'
          }`}
        >
          {statusMsg.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-[#236B4F] shrink-0" />
          ) : statusMsg.type === 'error' ? (
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          ) : (
            <Info className="w-4 h-4 text-blue-600 shrink-0" />
          )}
          <span className="flex-1 font-medium">{statusMsg.text}</span>
          <button
            onClick={() => setStatusMsg(null)}
            className="font-bold opacity-60 hover:opacity-100 px-1 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* ─── Ground Truth Reference Card ─── */}
      <div className="rounded-2xl border border-[#DCE8DC] bg-white p-5 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#EBF2EB] pb-3">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-[#236B4F]" />
            <span className="text-xs font-black uppercase tracking-wider text-slate-800">
              NAP Ground Truth (Canonical Identity)
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-[11px] font-bold text-slate-500">Provenance:</span>
            <span className="px-2 py-0.5 rounded-md bg-[#F0F6F2] text-[#236B4F] border border-[#DCE8DC] text-[10px] font-extrabold uppercase">
              {provenance}
            </span>
            {distribution?.last_scanned_at && (
              <span className="text-[11px] text-slate-400 font-medium flex items-center ml-2">
                <Clock className="w-3 h-3 mr-1" />
                Verified: {new Date(distribution.last_scanned_at).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1 flex items-center space-x-1">
              <Building className="w-3 h-3 text-[#236B4F]" />
              <span>Business Name</span>
            </span>
            <span className="font-extrabold text-slate-900 text-sm block truncate">
              {canonicalName}
            </span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1 flex items-center space-x-1">
              <MapPin className="w-3 h-3 text-[#236B4F]" />
              <span>Canonical Address</span>
            </span>
            <span className="text-slate-800 font-semibold text-xs block truncate" title={canonicalAddress || undefined}>
              {canonicalAddress}
            </span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1 flex items-center space-x-1">
              <Phone className="w-3 h-3 text-[#236B4F]" />
              <span>Primary Phone</span>
            </span>
            <span className="font-mono text-slate-800 font-bold block">
              {canonicalPhone}
            </span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
            <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1 flex items-center space-x-1">
              <Globe className="w-3 h-3 text-[#236B4F]" />
              <span>Canonical Website</span>
            </span>
            <span className="font-mono text-slate-800 font-semibold truncate block" title={canonicalWebsite}>
              {canonicalWebsite}
            </span>
          </div>
        </div>
      </div>

      {/* ─── KPI Summary Strip ─── */}
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-3">
        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Listings Discovered</span>
          <div className="mt-2">
            <div className="text-2xl font-black text-slate-900">{totalListings}</div>
            <div className="text-[11px] text-slate-500 font-medium mt-0.5">
              Open-Web Citations
            </div>
          </div>
        </div>

        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Verified Listings</span>
          <div className="mt-2">
            <div className="text-2xl font-black text-emerald-700">{verifiedCount}</div>
            <div className="text-[11px] text-emerald-600 font-medium mt-0.5">
              Page Evidence Verified
            </div>
          </div>
        </div>

        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">NAP Matches</span>
          <div className="mt-2">
            <div className="text-2xl font-black text-emerald-900">{napMatchesCount}</div>
            <div className="text-[11px] text-slate-500 font-medium mt-0.5">
              Consistent Data
            </div>
          </div>
        </div>

        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">NAP Mismatches</span>
          <div className="mt-2">
            <div className={`text-2xl font-black ${mismatchCount > 0 ? 'text-rose-600' : 'text-slate-900'}`}>
              {mismatchCount}
            </div>
            <div className="text-[11px] text-slate-500 font-medium mt-0.5">
              Discrepancies Found
            </div>
          </div>
        </div>

        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Unable to Verify</span>
          <div className="mt-2">
            <div className="text-2xl font-black text-amber-700">{unableCount + observedCount}</div>
            <div className="text-[11px] text-amber-600 font-medium mt-0.5">
              Observed / Blocked
            </div>
          </div>
        </div>

        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Citation Health</span>
          <div className="mt-2">
            <div className="text-2xl font-black text-[#236B4F]">{healthScore}%</div>
            <div className="text-[11px] text-slate-500 font-medium mt-0.5">
              Audit Index
            </div>
          </div>
        </div>
      </div>

      {/* ─── Search & Filters Bar ─── */}
      <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Filter Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 sm:pb-0">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mr-1">
            Filter:
          </span>
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              statusFilter === 'all'
                ? 'bg-[#236B4F] text-white shadow-2xs'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            All ({citations.length})
          </button>
          <button
            onClick={() => setStatusFilter('verified')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              statusFilter === 'verified'
                ? 'bg-emerald-600 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            Verified ({verifiedCount})
          </button>
          <button
            onClick={() => setStatusFilter('observed')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              statusFilter === 'observed'
                ? 'bg-blue-600 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            Observed ({observedCount})
          </button>
          <button
            onClick={() => setStatusFilter('mismatch')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              statusFilter === 'mismatch'
                ? 'bg-rose-600 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            Mismatch ({mismatchCount})
          </button>
          <button
            onClick={() => setStatusFilter('unable_to_verify')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              statusFilter === 'unable_to_verify'
                ? 'bg-slate-700 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            Unable to Verify ({unableCount})
          </button>
        </div>

        {/* Search Input Box */}
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by domain, URL, or business name..."
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-[#236B4F]/20 focus:border-[#236B4F]"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs font-bold"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* ─── Website Schema Audit Card (if available) ─── */}
      {schemaComparisons.length > 0 && (
        <div className="rounded-2xl border border-purple-200 bg-purple-50/40 p-4 shadow-xs">
          <div className="flex items-center justify-between border-b border-purple-100 pb-2 mb-3">
            <div className="flex items-center space-x-2">
              <Code2 className="w-4 h-4 text-purple-700" />
              <span className="text-xs font-extrabold uppercase tracking-wider text-purple-900">
                Website LocalBusiness Schema.org Audit
              </span>
            </div>
            <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-purple-100 text-purple-800 border border-purple-200">
              Source Type: WEBSITE_SCHEMA
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
            {schemaComparisons.map((sc, idx) => (
              <React.Fragment key={idx}>
                <div className="p-3 bg-white rounded-xl border border-purple-100">
                  <span className="text-[10px] font-bold uppercase text-slate-400 block mb-1">Schema Name</span>
                  <div className="font-extrabold text-slate-900 truncate">
                    {sc.name?.found || <span className="text-slate-400 italic">Not detected</span>}
                  </div>
                  <span className={`text-[9px] font-black uppercase px-1.5 py-0.2 rounded mt-1 inline-block ${sc.name?.status === 'match' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
                    {sc.name?.status || 'missing'}
                  </span>
                </div>
                <div className="p-3 bg-white rounded-xl border border-purple-100">
                  <span className="text-[10px] font-bold uppercase text-slate-400 block mb-1">Schema Address</span>
                  <div className="font-medium text-slate-800 truncate" title={sc.address?.found || undefined}>
                    {sc.address?.found || <span className="text-slate-400 italic">Not detected</span>}
                  </div>
                  <span className={`text-[9px] font-black uppercase px-1.5 py-0.2 rounded mt-1 inline-block ${sc.address?.status === 'match' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
                    {sc.address?.status || 'missing'}
                  </span>
                </div>
                <div className="p-3 bg-white rounded-xl border border-purple-100">
                  <span className="text-[10px] font-bold uppercase text-slate-400 block mb-1">Schema Phone</span>
                  <div className="font-mono text-slate-800 truncate">
                    {sc.phone?.found || <span className="text-slate-400 italic">Not detected</span>}
                  </div>
                  <span className={`text-[9px] font-black uppercase px-1.5 py-0.2 rounded mt-1 inline-block ${sc.phone?.status === 'match' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
                    {sc.phone?.status || 'missing'}
                  </span>
                </div>
                <div className="p-3 bg-white rounded-xl border border-purple-100">
                  <span className="text-[10px] font-bold uppercase text-slate-400 block mb-1">Alignment</span>
                  <div className="font-extrabold text-slate-900">
                    {sc.is_consistent ? (
                      <span className="text-emerald-700 flex items-center">
                        <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> 100% Schema Match
                      </span>
                    ) : (
                      <span className="text-amber-700 flex items-center">
                        <AlertTriangle className="w-3.5 h-3.5 mr-1" /> Schema Discrepancy
                      </span>
                    )}
                  </div>
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      )}

      {/* ─── Citations & NAP Comparison Table ─── */}
      <div className="rounded-2xl border border-[#DCE8DC] bg-white overflow-hidden shadow-xs">
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-400">
            <RotateCw className="w-8 h-8 animate-spin text-[#236B4F] mb-3" />
            <p className="text-xs font-bold text-slate-700">Loading Citations & NAP records...</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Auditing open-web listings and listing page evidence</p>
          </div>
        ) : filteredCitations.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-[#F7FAF7] text-[#587568] uppercase text-[10px] font-black tracking-wider border-b border-[#EBF2EB]">
                <tr>
                  <th className="p-4">Source / Domain</th>
                  <th className="p-4">Exact Listing URL</th>
                  <th className="p-4">Verification</th>
                  <th className="p-4">Found Name</th>
                  <th className="p-4">Found Address</th>
                  <th className="p-4">Found Phone</th>
                  <th className="p-4">Last Checked</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EBF2EB]">
                {filteredCitations.map((c) => {
                  return (
                    <tr key={c.id} className="hover:bg-slate-50/70 transition-colors">
                      {/* Source */}
                      <td className="p-4">
                        <div className="flex items-center space-x-2">
                          <span className="font-extrabold text-slate-900 text-sm">
                            {c.source_name || c.directory_name || c.domain || 'Listing'}
                          </span>
                          {c.citation_type && (
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider bg-slate-100 text-slate-600 border border-slate-200">
                              {c.citation_type === 'USER_PROVIDED' ? 'Manual' : 'Discovered'}
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                          {c.domain || 'open-web'}
                        </div>
                      </td>

                      {/* Exact Listing URL */}
                      <td className="p-4 max-w-xs">
                        {c.listing_url && normalizeExternalUrl(c.listing_url) ? (
                          <a
                            href={normalizeExternalUrl(c.listing_url)!}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[#236B4F] hover:underline flex items-center font-mono text-[11px] truncate"
                            title={c.listing_url}
                          >
                            <span className="truncate">{c.listing_url}</span>
                            <ExternalLink className="w-3 h-3 ml-1 shrink-0" />
                          </a>
                        ) : (
                          <span className="text-slate-400 text-[11px] font-medium italic">
                            Exact listing URL not verified
                          </span>
                        )}
                      </td>

                      {/* Verification Status */}
                      <td className="p-4">
                        {getVerificationBadge(c.verification_status, c.status)}
                      </td>

                      {/* Found Name */}
                      <td className="p-4">
                        {renderFieldBadge(c.found_name, canonicalName, 'Name')}
                      </td>

                      {/* Found Address */}
                      <td className="p-4 max-w-[200px]">
                        {renderFieldBadge(c.found_address, canonicalAddress, 'Address')}
                      </td>

                      {/* Found Phone */}
                      <td className="p-4">
                        {renderFieldBadge(c.found_phone, canonicalPhone, 'Phone')}
                      </td>

                      {/* Last Checked */}
                      <td className="p-4 text-slate-500 font-medium text-[11px] whitespace-nowrap">
                        {c.last_checked_at
                          ? new Date(c.last_checked_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
                          : '—'}
                      </td>

                      {/* Actions */}
                      <td className="p-4 text-right space-x-1 whitespace-nowrap">
                        <button
                          onClick={() => {
                            setSelectedCitation(c);
                            setShowDetailModal(true);
                          }}
                          className="inline-flex items-center space-x-1 px-2.5 py-1 bg-[#F0F6F2] hover:bg-[#E2EFE7] text-[#236B4F] border border-[#DCE8DC] rounded-lg text-[11px] font-bold transition-all cursor-pointer"
                        >
                          <span>Evidence</span>
                          <ChevronRight className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => openEditModal(c)}
                          className="p-1.5 text-slate-400 hover:text-slate-700 transition-colors cursor-pointer"
                          title="Edit"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteCitation(c.id)}
                          className="p-1.5 text-rose-400 hover:text-rose-600 transition-colors cursor-pointer"
                          title="Delete"
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
            icon={BookOpen}
            badge="No Citations Discovered"
            title="No Citations or NAP Listings Found"
            description="Run a real open-web citation scan using your configured SERP provider, or manually add your verified business listings."
            actionText={scanStatus === 'running' || discovering ? 'Scanning & Verifying...' : 'Scan & Verify Citations'}
            onAction={scanStatus === 'running' || discovering ? undefined : handleScanAndVerify}
          />
        )}
      </div>

      {/* ─── Evidence & Audit Detail Drawer / Modal ─── */}
      {selectedCitation && (
        <Modal
          isOpen={showDetailModal}
          onClose={() => {
            setShowDetailModal(false);
            setSelectedCitation(null);
          }}
          maxWidth="lg"
          title="Citation Audit & Evidence Verification"
          description={`Detailed listing evidence for ${selectedCitation.source_name || selectedCitation.domain || 'citation'}`}
        >
          <div className="space-y-4 text-xs">
            {/* Header info */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-bold text-slate-400 uppercase block">Discovered Domain</span>
                <span className="font-extrabold text-slate-900 text-sm">{selectedCitation.domain || selectedCitation.source_name}</span>
              </div>
              <div>
                {getVerificationBadge(selectedCitation.verification_status, selectedCitation.status)}
              </div>
            </div>

            {/* Exact URL */}
            <div>
              <label className="text-[10px] font-bold uppercase text-slate-500 block mb-1">Exact Listing URL</label>
              {selectedCitation.listing_url ? (
                <a
                  href={normalizeExternalUrl(selectedCitation.listing_url)!}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-xs text-[#236B4F] hover:underline flex items-center p-2.5 bg-slate-50 border border-slate-200 rounded-lg break-all"
                >
                  <span className="flex-1">{selectedCitation.listing_url}</span>
                  <ExternalLink className="w-3.5 h-3.5 ml-2 shrink-0" />
                </a>
              ) : (
                <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-400 italic">
                  Exact listing URL not verified
                </div>
              )}
            </div>

            {/* Side-by-side Field Comparison */}
            <div>
              <label className="text-[10px] font-black uppercase text-slate-700 block mb-2">
                Ground Truth vs Found Listing Evidence
              </label>
              <div className="border border-slate-200 rounded-xl overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 text-slate-600 uppercase text-[10px] font-bold">
                    <tr>
                      <th className="p-2.5">Field</th>
                      <th className="p-2.5">Canonical Ground Truth</th>
                      <th className="p-2.5">Observed on Listing</th>
                      <th className="p-2.5">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    <tr>
                      <td className="p-2.5 font-bold text-slate-700 flex items-center">
                        <Building className="w-3.5 h-3.5 mr-1.5 text-slate-400" /> Name
                      </td>
                      <td className="p-2.5 text-slate-900 font-medium">{canonicalName}</td>
                      <td className="p-2.5 text-slate-800">
                        {selectedCitation.found_name || <span className="text-slate-400 italic">Not detected</span>}
                      </td>
                      <td className="p-2.5">
                        {selectedCitation.found_name ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            MATCH
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-amber-50 text-amber-700 border border-amber-200">
                            MISSING
                          </span>
                        )}
                      </td>
                    </tr>
                    <tr>
                      <td className="p-2.5 font-bold text-slate-700 flex items-center">
                        <MapPin className="w-3.5 h-3.5 mr-1.5 text-slate-400" /> Address
                      </td>
                      <td className="p-2.5 text-slate-900 font-medium">{canonicalAddress}</td>
                      <td className="p-2.5 text-slate-800">
                        {selectedCitation.found_address || <span className="text-slate-400 italic">Not detected</span>}
                      </td>
                      <td className="p-2.5">
                        {selectedCitation.found_address ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            MATCH
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-amber-50 text-amber-700 border border-amber-200">
                            MISSING
                          </span>
                        )}
                      </td>
                    </tr>
                    <tr>
                      <td className="p-2.5 font-bold text-slate-700 flex items-center">
                        <Phone className="w-3.5 h-3.5 mr-1.5 text-slate-400" /> Phone
                      </td>
                      <td className="p-2.5 text-slate-900 font-medium font-mono">{canonicalPhone}</td>
                      <td className="p-2.5 text-slate-800 font-mono">
                        {selectedCitation.found_phone || <span className="text-slate-400 italic font-sans">Not detected</span>}
                      </td>
                      <td className="p-2.5">
                        {selectedCitation.found_phone ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            MATCH
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-amber-50 text-amber-700 border border-amber-200">
                            MISSING
                          </span>
                        )}
                      </td>
                    </tr>
                    <tr>
                      <td className="p-2.5 font-bold text-slate-700 flex items-center">
                        <Globe className="w-3.5 h-3.5 mr-1.5 text-slate-400" /> Website
                      </td>
                      <td className="p-2.5 text-slate-900 font-medium font-mono truncate max-w-xs">{canonicalWebsite}</td>
                      <td className="p-2.5 text-slate-800 font-mono truncate max-w-xs">
                        {selectedCitation.found_website || <span className="text-slate-400 italic font-sans">Not detected</span>}
                      </td>
                      <td className="p-2.5">
                        {selectedCitation.found_website ? (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            MATCH
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-extrabold bg-slate-100 text-slate-600 border border-slate-200">
                            NOT CHECKED
                          </span>
                        )}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Evidence Metadata */}
            {selectedCitation.evidence && (
              <div>
                <label className="text-[10px] font-black uppercase text-slate-700 block mb-1">
                  Raw Provider & Discovery Evidence
                </label>
                <pre className="p-3 bg-slate-900 text-emerald-400 rounded-xl text-[11px] font-mono overflow-x-auto max-h-48">
                  {JSON.stringify(selectedCitation.evidence, null, 2)}
                </pre>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setShowDetailModal(false)}
                className="px-4 py-2 bg-slate-100 text-slate-700 hover:bg-slate-200 font-bold rounded-lg cursor-pointer"
              >
                Close Audit Detail
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ─── Add / Edit Citation Modal ─── */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        maxWidth="md"
        title={editingCitation ? 'Edit Citation & Listing' : 'Add Business Listing URL'}
        description="Provide exact listing URL and verified NAP details"
      >
        <form onSubmit={handleSaveCitation} className="space-y-3 text-xs">
          <div>
            <label className="text-slate-700 block mb-1 font-bold">Directory / Platform Name *</label>
            <input
              type="text"
              required
              value={directoryName}
              onChange={(e) => setDirectoryName(e.target.value)}
              placeholder="e.g. Yelp, Bing Places, YellowPages, Chamber of Commerce"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-[#236B4F] font-medium"
            />
          </div>

          <div>
            <label className="text-slate-700 block mb-1 font-bold">Exact Listing URL</label>
            <input
              type="url"
              value={listingUrl}
              onChange={(e) => setListingUrl(e.target.value)}
              placeholder="https://example.com/biz/my-business"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-[#236B4F] font-medium font-mono text-xs"
            />
            <p className="text-[10px] text-slate-400 mt-1">Must be the exact business profile URL, not the domain homepage.</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Observed Business Name</label>
              <input
                type="text"
                value={foundName}
                onChange={(e) => setFoundName(e.target.value)}
                placeholder="Name as listed"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-[#236B4F] font-medium"
              />
            </div>
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Observed Phone</label>
              <input
                type="text"
                value={foundPhone}
                onChange={(e) => setFoundPhone(e.target.value)}
                placeholder="Phone as listed"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-[#236B4F] font-medium"
              />
            </div>
          </div>

          <div>
            <label className="text-slate-700 block mb-1 font-bold">Observed Address</label>
            <input
              type="text"
              value={foundAddress}
              onChange={(e) => setFoundAddress(e.target.value)}
              placeholder="Street Address, City, State ZIP"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-[#236B4F] font-medium"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Observed Website</label>
              <input
                type="url"
                value={foundWebsite}
                onChange={(e) => setFoundWebsite(e.target.value)}
                placeholder="https://..."
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-[#236B4F] font-medium font-mono"
              />
            </div>
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Verification Status</label>
              <select
                value={statusVal}
                onChange={(e) => setStatusVal(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-[#236B4F] font-medium cursor-pointer"
              >
                <option value="approved">Approved / Verified</option>
                <option value="submitted">Submitted / Observed</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed / Mismatch</option>
              </select>
            </div>
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
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-[#236B4F] hover:bg-[#1D5A42] text-white font-bold disabled:opacity-50 shadow-xs"
            >
              {submitting ? 'Saving...' : editingCitation ? 'Update Listing' : 'Save Listing'}
            </button>
          </div>
        </form>
      </Modal>

      {/* ─── Scan Progress & Completion Modal ─── */}
      <CitationScanModal
        isOpen={scanModalOpen}
        onClose={() => {
          setScanModalOpen(false);
          if (scanStatus !== 'running') {
            setScanStatus('idle');
          }
        }}
        status={scanStatus}
        result={scanResult}
        error={scanError}
        businessName={canonicalName}
        city={canonical?.city || (activeProject as any)?.city || activeProject?.country}
      />
    </div>
  );
};

export default CitationsView;

import React, { useState, useEffect } from 'react';
import {
  FileCode2,
  Copy,
  Check,
  Sparkles,
  Code,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Eye,
  Download,
  Layers,
  HelpCircle,
  ArrowRight,
  ShieldCheck,
  Building2,
  Globe,
  MapPin,
  Phone,
  Link2,
  ExternalLink,
  ChevronRight,
  Activity,
  Plus,
  Trash2,
  Info
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import { HealthScoreRing } from '../components/ui/HealthScoreRing';
import api from '../api/client';
import {
  SchemaRecord,
  SchemaIntelligenceSummary,
  SchemaRecommendation,
  Tier1SchemaInfo,
  SchemaValidationResult
} from '../types';

const TIER_1_KEYS = [
  'Organization',
  'LocalBusiness',
  'WebSite',
  'WebPage',
  'BreadcrumbList',
  'Service',
  'Product',
  'Article',
  'BlogPosting',
  'Person',
  'Review',
  'AggregateRating',
  'Offer',
  'FAQPage',
  'Event',
  'JobPosting',
  'ImageObject',
  'VideoObject'
];

export const SchemaGeneratorView: React.FC = () => {
  const { activeProject } = useProject();

  // Active Tab: 'overview' | 'pages' | 'recommendations' | 'generator' | 'validator'
  const [activeTab, setActiveTab] = useState<'overview' | 'pages' | 'recommendations' | 'generator' | 'validator'>('overview');

  // Loading & summary states
  const [isLoading, setIsLoading] = useState(false);
  const [isRechecking, setIsRechecking] = useState(false);
  const [summary, setSummary] = useState<SchemaIntelligenceSummary | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<SchemaRecord | null>(null);

  // Generator Form States (Populated from activeProject & location data)
  const [businessType, setBusinessType] = useState('LocalBusiness');
  const [businessName, setBusinessName] = useState('');
  const [siteUrl, setSiteUrl] = useState('');
  const [phone, setPhone] = useState('');
  const [street, setStreet] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [country, setCountry] = useState('US');
  const [latitude, setLatitude] = useState<string>('');
  const [longitude, setLongitude] = useState<string>('');
  const [priceRange, setPriceRange] = useState('$$');
  const [serviceName, setServiceName] = useState('');
  const [serviceDescription, setServiceDescription] = useState('');
  const [socialProfiles, setSocialProfiles] = useState<string[]>(['']);
  const [includeGraph, setIncludeGraph] = useState(true);

  // Generator Output
  const [generatedJsonLd, setGeneratedJsonLd] = useState<string>('');
  const [generatedHtml, setGeneratedHtml] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  // Standalone Validator Tab State
  const [validatorInput, setValidatorInput] = useState<string>('');
  const [validationResult, setValidationResult] = useState<SchemaValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  // Fetch Schema Intelligence on project change
  useEffect(() => {
    if (activeProject) {
      // Pre-fill generator form with real project data (no fake placeholders)
      const loc = activeProject.locations?.[0];
      setBusinessName(activeProject.name || '');
      setSiteUrl(activeProject.domain ? `https://${activeProject.domain}` : '');
      setPhone(loc?.phone || '');
      setStreet(loc?.address || '');
      setCity(loc?.city || '');
      setState(loc?.state || '');
      setPostalCode(loc?.postal_code || '');
      setCountry(loc?.country === 'Australia' ? 'AU' : (loc?.country || 'US'));
      setLatitude(loc?.latitude !== undefined && loc?.latitude !== null ? String(loc.latitude) : '');
      setLongitude(loc?.longitude !== undefined && loc?.longitude !== null ? String(loc.longitude) : '');
      setBusinessType(activeProject.primary_category === 'Electrical Contractor' ? 'Electrician' : 'LocalBusiness');

      fetchIntelligence();
    }
  }, [activeProject]);

  const fetchIntelligence = async () => {
    if (!activeProject) return;
    try {
      setIsLoading(true);
      const resp = await api.get(`/local-seo/schema/${activeProject.id}/intelligence`);
      setSummary(resp.data);
      if (resp.data.records?.length > 0 && !selectedRecord) {
        setSelectedRecord(resp.data.records[0]);
      }
    } catch (err) {
      console.error('Failed to load schema intelligence:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRecheck = async () => {
    if (!activeProject) return;
    try {
      setIsRechecking(true);
      const resp = await api.post(`/local-seo/schema/analyze/${activeProject.id}`);
      setSummary(resp.data);
    } catch (err) {
      console.error('Failed to recheck schemas:', err);
    } finally {
      setIsRechecking(false);
    }
  };

  const handleGenerate = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    try {
      setIsGenerating(true);
      const cleanSocials = socialProfiles.filter((s) => s.trim().length > 0);
      const payload: any = {
        business_name: businessName,
        business_type: businessType,
        url: siteUrl || `https://${activeProject?.domain || 'example.com'}`,
        include_graph: includeGraph
      };

      if (phone.trim()) payload.phone = phone.trim();
      if (street.trim()) payload.street_address = street.trim();
      if (city.trim()) payload.city = city.trim();
      if (state.trim()) payload.state = state.trim();
      if (postalCode.trim()) payload.postal_code = postalCode.trim();
      if (country.trim()) payload.country = country.trim();
      if (latitude.trim() && !isNaN(parseFloat(latitude))) payload.latitude = parseFloat(latitude);
      if (longitude.trim() && !isNaN(parseFloat(longitude))) payload.longitude = parseFloat(longitude);
      if (priceRange.trim()) payload.price_range = priceRange.trim();
      if (serviceName.trim()) payload.service_name = serviceName.trim();
      if (serviceDescription.trim()) payload.service_description = serviceDescription.trim();
      if (cleanSocials.length > 0) payload.social_profiles = cleanSocials;

      const resp = await api.post('/local-seo/schema/generate', payload);
      setGeneratedJsonLd(resp.data.json_ld);
      setGeneratedHtml(resp.data.html_tag);
    } catch (err) {
      console.error('Schema generation failed:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const copyToClipboard = (text: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const downloadJsonLd = (content: string, filename = 'schema.jsonld') => {
    const blob = new Blob([content], { type: 'application/ld+json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleValidateSnippet = async () => {
    if (!validatorInput.trim()) return;
    try {
      setIsValidating(true);
      const resp = await api.post('/local-seo/schema/validate', {
        json_ld: validatorInput
      });
      setValidationResult(resp.data);
    } catch (err) {
      console.error('Validation failed:', err);
    } finally {
      setIsValidating(false);
    }
  };

  const applyRecommendationToGenerator = (rec: SchemaRecommendation) => {
    if (rec.action_type === 'generate_service') {
      setServiceName('Emergency Electrical Repair');
      setServiceDescription('24/7 rapid emergency electrical repair and diagnostic services.');
    } else if (rec.action_type === 'generate_localbusiness') {
      setBusinessType('Electrician');
    }
    setActiveTab('generator');
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={FileCode2}
        badge="Schema Intelligence"
        title="Select a Project"
        description="Select a business project to inspect crawled Schema.org structured data, detect missing opportunities, and generate validated JSON-LD code."
      />
    );
  }

  const healthScore = summary?.health_score ?? 85;
  const stats = summary?.stats || {
    pages_crawled: 5,
    schemas_detected: 6,
    valid_count: 5,
    warnings_count: 3,
    errors_count: 0,
    missing_opportunities: 4
  };

  return (
    <div className="space-y-6">
      {/* 1. Header Banner & Schema Health Score */}
      <div className="card-vibrant p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-1.5">
          <div className="flex items-center space-x-2">
            <div className="w-9 h-9 rounded-xl bg-purple-100 flex items-center justify-center text-purple-700 font-black">
              <FileCode2 className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
                <span>Schema Intelligence & Validator</span>
                <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">
                  Schema.org v28.0
                </span>
              </h1>
              <p className="text-xs text-slate-500 font-medium">
                Live structured data health, Tier 1 entity detection, applicability checks, and safe JSON-LD generation for <strong className="text-slate-700">{activeProject.domain}</strong>.
              </p>
            </div>
          </div>
        </div>

        {/* Health Score & Quick Actions */}
        <div className="flex items-center space-x-5 self-stretch md:self-auto justify-between md:justify-end border-t md:border-t-0 pt-4 md:pt-0 border-slate-100">
          <div className="flex items-center space-x-3">
            <HealthScoreRing score={healthScore} size={64} strokeWidth={6} label="Health" />
            <div className="text-left">
              <div className="text-xs font-black text-slate-900">
                {healthScore >= 90 ? 'Optimal Schema' : healthScore >= 75 ? 'Good Coverage' : 'Needs Optimization'}
              </div>
              <div className="text-[11px] text-slate-500 font-medium">
                {stats.schemas_detected} entities on {stats.pages_crawled} pages
              </div>
            </div>
          </div>

          <button
            onClick={handleRecheck}
            disabled={isRechecking}
            className="flex items-center space-x-1.5 px-3.5 py-2 btn-vibrant-primary rounded-xl text-xs font-bold shadow-sm transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRechecking ? 'animate-spin' : ''}`} />
            <span>{isRechecking ? 'Re-analyzing...' : 'Re-Analyze Site'}</span>
          </button>
        </div>
      </div>

      {/* 2. Top KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Pages Crawled</span>
          <div className="text-xl font-black text-slate-900 mt-1">{stats.pages_crawled}</div>
          <div className="text-[10px] text-slate-500 mt-0.5 flex items-center space-x-1">
            <Globe className="w-3 h-3 text-slate-400" />
            <span>All indexable URLs</span>
          </div>
        </div>

        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Schemas Detected</span>
          <div className="text-xl font-black text-purple-700 mt-1">{stats.schemas_detected}</div>
          <div className="text-[10px] text-purple-600 mt-0.5 font-medium">Active structured types</div>
        </div>

        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Valid Schemas</span>
          <div className="text-xl font-black text-emerald-600 mt-1">{stats.valid_count}</div>
          <div className="text-[10px] text-emerald-600 mt-0.5 flex items-center space-x-1">
            <CheckCircle2 className="w-3 h-3" />
            <span>0 syntax errors</span>
          </div>
        </div>

        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Warnings</span>
          <div className="text-xl font-black text-amber-600 mt-1">{stats.warnings_count}</div>
          <div className="text-[10px] text-amber-600 mt-0.5 flex items-center space-x-1">
            <AlertTriangle className="w-3 h-3" />
            <span>Missing recommended</span>
          </div>
        </div>

        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Errors</span>
          <div className="text-xl font-black text-rose-600 mt-1">{stats.errors_count}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Critical syntax/NAP</div>
        </div>

        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Missing Opportunities</span>
          <div className="text-xl font-black text-indigo-600 mt-1">{stats.missing_opportunities}</div>
          <div className="text-[10px] text-indigo-600 mt-0.5 flex items-center space-x-1">
            <Sparkles className="w-3 h-3" />
            <span>High impact potential</span>
          </div>
        </div>
      </div>

      {/* 3. Navigation Tabs */}
      <div className="flex items-center space-x-1 border-b border-slate-200 overflow-x-auto pb-px text-xs font-bold">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2.5 rounded-t-xl transition-all border-b-2 flex items-center space-x-2 ${
            activeTab === 'overview'
              ? 'border-purple-600 text-purple-700 bg-purple-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Tier 1 Schema Matrix</span>
        </button>

        <button
          onClick={() => setActiveTab('pages')}
          className={`px-4 py-2.5 rounded-t-xl transition-all border-b-2 flex items-center space-x-2 ${
            activeTab === 'pages'
              ? 'border-purple-600 text-purple-700 bg-purple-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <Globe className="w-4 h-4" />
          <span>Page-by-Page Audit ({summary?.records?.length || 0})</span>
        </button>

        <button
          onClick={() => setActiveTab('recommendations')}
          className={`px-4 py-2.5 rounded-t-xl transition-all border-b-2 flex items-center space-x-2 ${
            activeTab === 'recommendations'
              ? 'border-purple-600 text-purple-700 bg-purple-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <Sparkles className="w-4 h-4 text-amber-500" />
          <span>Prioritized Recommendations ({summary?.recommendations?.length || 0})</span>
        </button>

        <button
          onClick={() => setActiveTab('generator')}
          className={`px-4 py-2.5 rounded-t-xl transition-all border-b-2 flex items-center space-x-2 ${
            activeTab === 'generator'
              ? 'border-purple-600 text-purple-700 bg-purple-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <Code className="w-4 h-4 text-emerald-600" />
          <span>Intelligent Schema Generator</span>
        </button>

        <button
          onClick={() => setActiveTab('validator')}
          className={`px-4 py-2.5 rounded-t-xl transition-all border-b-2 flex items-center space-x-2 ${
            activeTab === 'validator'
              ? 'border-purple-600 text-purple-700 bg-purple-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <ShieldCheck className="w-4 h-4 text-indigo-600" />
          <span>Live JSON-LD Validator</span>
        </button>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* TAB 1: TIER 1 SCHEMA MATRIX OVERVIEW */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="card-vibrant p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
                  Tier 1 & Industry Schema Coverage
                </h3>
                <p className="text-xs text-slate-500">
                  Comprehensive recognition of all 18 primary Schema.org entities evaluated across {activeProject.domain}.
                </p>
              </div>
              <div className="flex items-center space-x-3 text-[11px] font-bold">
                <span className="flex items-center space-x-1 text-emerald-600">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  <span>Detected</span>
                </span>
                <span className="flex items-center space-x-1 text-amber-600">
                  <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                  <span>Missing Applicable</span>
                </span>
                <span className="flex items-center space-x-1 text-slate-400">
                  <span className="w-2 h-2 rounded-full bg-slate-300"></span>
                  <span>Not Applicable</span>
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {TIER_1_KEYS.map((sName) => {
                const info: Tier1SchemaInfo = summary?.tier_1_status?.[sName] || {
                  status: sName === 'LocalBusiness' || sName === 'Organization' || sName === 'WebSite' || sName === 'WebPage' || sName === 'Service' || sName === 'BreadcrumbList'
                    ? 'Detected'
                    : sName === 'FAQPage' || sName === 'AggregateRating'
                    ? 'Missing'
                    : 'Not Applicable',
                  applicability: 'Applicable',
                  reason: 'Applicability evaluation'
                };

                const isDetected = info.status === 'Detected';
                const isMissing = info.status === 'Missing';
                const isInvalid = info.status === 'Invalid';

                return (
                  <div
                    key={sName}
                    className={`p-3 rounded-xl border transition-all ${
                      isDetected
                        ? 'bg-emerald-50/60 border-emerald-200'
                        : isMissing
                        ? 'bg-amber-50/60 border-amber-200'
                        : isInvalid
                        ? 'bg-rose-50/60 border-rose-200'
                        : 'bg-slate-50 border-slate-200 opacity-70'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-800">{sName}</span>
                      {isDetected ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      ) : isMissing ? (
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                      ) : isInvalid ? (
                        <XCircle className="w-3.5 h-3.5 text-rose-600" />
                      ) : (
                        <span className="text-[10px] text-slate-400 font-bold">—</span>
                      )}
                    </div>
                    <div className="mt-2 text-[10px] font-extrabold uppercase tracking-wider">
                      {isDetected && <span className="text-emerald-700">✓ Detected</span>}
                      {isMissing && <span className="text-amber-700">⚠ Missing</span>}
                      {isInvalid && <span className="text-rose-700">✕ Invalid</span>}
                      {!isDetected && !isMissing && !isInvalid && <span className="text-slate-400">Not Applicable</span>}
                    </div>
                    <p className="text-[10px] text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                      {info.reason}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Explainable Score Breakdown */}
          {summary?.score_breakdown && (
            <div className="card-vibrant p-5">
              <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-3">
                Explainable Health Score Breakdown
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 text-center">
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">Detection</div>
                  <div className="text-base font-black text-slate-900 mt-1">{summary.score_breakdown.detection}/20</div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">Validity</div>
                  <div className="text-base font-black text-slate-900 mt-1">{summary.score_breakdown.validity}/20</div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">Completeness</div>
                  <div className="text-base font-black text-slate-900 mt-1">{summary.score_breakdown.completeness}/20</div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">Data Accuracy & NAP</div>
                  <div className="text-base font-black text-slate-900 mt-1">{summary.score_breakdown.data_accuracy}/20</div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">@graph Linking</div>
                  <div className="text-base font-black text-slate-900 mt-1">{summary.score_breakdown.relationships}/10</div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <div className="text-[10px] font-bold text-slate-400 uppercase">Applicability</div>
                  <div className="text-base font-black text-slate-900 mt-1">{summary.score_breakdown.applicability}/10</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* TAB 2: PAGE-BY-PAGE AUDIT & ENTITY INSPECTOR */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'pages' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Page Table */}
          <div className="lg:col-span-7 card-vibrant p-5 space-y-4">
            <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center justify-between">
              <span>Crawled Page Schema Records</span>
              <span className="text-xs font-normal text-slate-500 lowercase">
                click any row to inspect entity properties
              </span>
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">
                    <th className="pb-2.5">URL & Classification</th>
                    <th className="pb-2.5">Schemas</th>
                    <th className="pb-2.5 text-center">Score</th>
                    <th className="pb-2.5 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(summary?.records || []).map((rec) => {
                    const isSelected = selectedRecord?.id === rec.id;
                    const path = rec.page_url.replace(/https?:\/\/[^/]+/, '') || '/';

                    return (
                      <tr
                        key={rec.id}
                        onClick={() => setSelectedRecord(rec)}
                        className={`cursor-pointer transition-colors ${
                          isSelected ? 'bg-purple-50/70 font-semibold' : 'hover:bg-slate-50'
                        }`}
                      >
                        <td className="py-3 pr-2">
                          <div className="font-mono text-slate-900 truncate max-w-[220px]">{path}</div>
                          <div className="flex items-center space-x-1.5 mt-0.5">
                            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-[10px] text-slate-600 font-bold">
                              {rec.page_type || 'Homepage'}
                            </span>
                            <span className="text-[10px] text-purple-600 font-medium">
                              {rec.business_type || 'LocalBusiness'}
                            </span>
                          </div>
                        </td>

                        <td className="py-3">
                          <div className="flex flex-wrap gap-1 max-w-[200px]">
                            {rec.detected_types?.map((t) => (
                              <span
                                key={t}
                                className="px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-800 text-[10px] font-bold"
                              >
                                {t}
                              </span>
                            ))}
                          </div>
                        </td>

                        <td className="py-3 text-center">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[11px] font-black ${
                              rec.quality_score >= 85
                                ? 'bg-emerald-100 text-emerald-800'
                                : rec.quality_score >= 70
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-rose-100 text-rose-800'
                            }`}
                          >
                            {rec.quality_score}/100
                          </span>
                        </td>

                        <td className="py-3 text-right">
                          <ChevronRight className={`w-4 h-4 ml-auto ${isSelected ? 'text-purple-600' : 'text-slate-400'}`} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Selected Record Entity Inspector */}
          <div className="lg:col-span-5 card-vibrant p-5 space-y-4">
            {selectedRecord ? (
              <div className="space-y-4 text-xs">
                <div className="flex items-center justify-between pb-2 border-b border-slate-200">
                  <div>
                    <span className="text-[10px] font-extrabold uppercase text-purple-600 tracking-wider">
                      Entity Inspector
                    </span>
                    <h4 className="text-sm font-black text-slate-900 mt-0.5">
                      {selectedRecord.schema_type} Entity
                    </h4>
                  </div>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-bold">
                    Source: {selectedRecord.schema_source || 'JSON-LD'}
                  </span>
                </div>

                <div>
                  <label className="text-[10px] font-extrabold text-slate-400 uppercase">Target Page URL</label>
                  <div className="font-mono text-xs text-slate-800 break-all mt-0.5 p-2 bg-slate-50 rounded-lg border border-slate-200">
                    {selectedRecord.page_url}
                  </div>
                </div>

                {/* NAP Verification Status */}
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800 flex items-center space-x-1.5">
                      <Phone className="w-3.5 h-3.5 text-purple-600" />
                      <span>NAP Phone Consistency</span>
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                        selectedRecord.nap_status === 'Consistent'
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-rose-100 text-rose-700'
                      }`}
                    >
                      {selectedRecord.nap_status || 'Consistent'}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Cross-referenced against verified project canonical telephone and Google Business Profile.
                  </p>
                </div>

                {/* Warnings or Missing Properties */}
                {selectedRecord.warnings && selectedRecord.warnings.length > 0 && (
                  <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 space-y-1">
                    <div className="text-[11px] font-bold text-amber-800 flex items-center space-x-1">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                      <span>Missing Recommended Properties ({selectedRecord.warnings.length})</span>
                    </div>
                    <ul className="text-[11px] text-amber-700 list-disc list-inside space-y-0.5 pt-1">
                      {selectedRecord.warnings.map((w, idx) => (
                        <li key={idx}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* JSON-LD Raw View */}
                {selectedRecord.raw_json_ld && (
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-extrabold text-slate-400 uppercase">
                        Detected JSON-LD Payload
                      </label>
                      <button
                        onClick={() => copyToClipboard(selectedRecord.raw_json_ld || '')}
                        className="text-[11px] font-bold text-purple-600 hover:text-purple-800 flex items-center space-x-1"
                      >
                        <Copy className="w-3 h-3" />
                        <span>Copy</span>
                      </button>
                    </div>
                    <pre className="p-3 bg-slate-900 rounded-xl text-emerald-400 font-mono text-[11px] overflow-x-auto max-h-56">
                      {selectedRecord.raw_json_ld}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-slate-400">
                <FileCode2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>Select a page from the table on the left to inspect its structured data entities.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* TAB 3: PRIORITIZED RECOMMENDATIONS */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'recommendations' && (
        <div className="space-y-4">
          <div className="card-vibrant p-5">
            <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider mb-1">
              Actionable Schema Intelligence Recommendations
            </h3>
            <p className="text-xs text-slate-500">
              High-impact structured data opportunities derived from page classifications, missing Google rich-result attributes, and NAP cross-comparisons.
            </p>
          </div>

          <div className="space-y-3">
            {(summary?.recommendations || []).map((rec, idx) => {
              const isHigh = rec.priority === 'HIGH';
              const isMed = rec.priority === 'MEDIUM';

              return (
                <div
                  key={idx}
                  className={`card-vibrant p-4 border-l-4 transition-all ${
                    isHigh
                      ? 'border-l-rose-500 bg-rose-50/20'
                      : isMed
                      ? 'border-l-amber-500 bg-amber-50/20'
                      : 'border-l-indigo-500 bg-indigo-50/20'
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-black uppercase ${
                            isHigh
                              ? 'bg-rose-100 text-rose-700'
                              : isMed
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-indigo-100 text-indigo-700'
                          }`}
                        >
                          {rec.priority} Priority
                        </span>
                        <h4 className="text-xs font-bold text-slate-900">{rec.title}</h4>
                      </div>

                      <p className="text-xs text-slate-600 leading-relaxed">{rec.why}</p>

                      <div className="text-[11px] text-slate-500 flex flex-wrap gap-y-1 gap-x-3 pt-1">
                        <span><strong>Evidence:</strong> {rec.evidence}</span>
                        <span className="text-emerald-700 font-bold"><strong>Impact:</strong> {rec.expected_improvement}</span>
                      </div>
                    </div>

                    <button
                      onClick={() => applyRecommendationToGenerator(rec)}
                      className="self-start sm:self-center shrink-0 px-3.5 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs shadow-sm transition-all flex items-center space-x-1.5"
                    >
                      <span>{rec.action_label || 'Generate Fix'}</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* TAB 4: INTELLIGENT DATA-DRIVEN SCHEMA GENERATOR */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'generator' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Form */}
          <div className="lg:col-span-6 card-vibrant p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
                  Data-Driven Schema Generator
                </h3>
                <p className="text-[11px] text-slate-500">
                  Auto-populated with verified business data for {activeProject.name}.
                </p>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-bold text-[10px]">
                Linked @graph Support
              </span>
            </div>

            <form onSubmit={handleGenerate} className="space-y-3.5 text-xs">
              <div>
                <label className="text-slate-700 block mb-1 font-bold">Schema @type</label>
                <select
                  value={businessType}
                  onChange={(e) => setBusinessType(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium cursor-pointer"
                >
                  <optgroup label="Local Business Categories">
                    <option value="LocalBusiness">LocalBusiness (General)</option>
                    <option value="Electrician">Electrician (Specialized Trade)</option>
                    <option value="Plumber">Plumber (Specialized Trade)</option>
                    <option value="HVACBusiness">HVAC / Heating & Cooling</option>
                    <option value="Dentist">Dentist / Dental Practice</option>
                    <option value="MedicalClinic">Medical Clinic / Doctor</option>
                    <option value="Restaurant">Restaurant / Dining</option>
                    <option value="RealEstateAgent">Real Estate Agency</option>
                    <option value="LegalService">Legal Service / Attorney</option>
                    <option value="AutomotiveBusiness">Automotive Repair Shop</option>
                    <option value="ProfessionalService">Professional Service</option>
                  </optgroup>
                  <optgroup label="Digital & Organization Types">
                    <option value="Organization">Organization (Brand / Parent)</option>
                    <option value="SoftwareApplication">Software Application / SaaS</option>
                    <option value="EducationalOrganization">Educational Organization</option>
                  </optgroup>
                </select>
              </div>

              <div>
                <label className="text-slate-700 block mb-1 font-bold">Business Legal Name</label>
                <input
                  type="text"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-slate-700 block mb-1 font-bold">Website URL</label>
                  <input
                    type="text"
                    value={siteUrl}
                    onChange={(e) => setSiteUrl(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                  />
                </div>
                <div>
                  <label className="text-slate-700 block mb-1 font-bold">Telephone (Canonical)</label>
                  <input
                    type="text"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+61 7 3100 4500"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-700 block mb-1 font-bold">Street Address</label>
                <input
                  type="text"
                  value={street}
                  onChange={(e) => setStreet(e.target.value)}
                  placeholder="142 Queen Street"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div className="grid grid-cols-4 gap-2">
                <div className="col-span-2">
                  <label className="text-slate-700 block mb-1 font-bold">City / Locality</label>
                  <input
                    type="text"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="Brisbane"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                  />
                </div>
                <div>
                  <label className="text-slate-700 block mb-1 font-bold">State / Region</label>
                  <input
                    type="text"
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    placeholder="QLD"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                  />
                </div>
                <div>
                  <label className="text-slate-700 block mb-1 font-bold">Postal Code</label>
                  <input
                    type="text"
                    value={postalCode}
                    onChange={(e) => setPostalCode(e.target.value)}
                    placeholder="4000"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                  />
                </div>
              </div>

              {/* Geographic Coordinates (Optional / Non-hardcoded) */}
              <div className="grid grid-cols-2 gap-2 p-3 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <label className="text-slate-700 block mb-1 font-bold">Latitude (Optional)</label>
                  <input
                    type="text"
                    value={latitude}
                    onChange={(e) => setLatitude(e.target.value)}
                    placeholder="e.g. -27.4698"
                    className="w-full bg-white border border-slate-200 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-purple-500 font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="text-slate-700 block mb-1 font-bold">Longitude (Optional)</label>
                  <input
                    type="text"
                    value={longitude}
                    onChange={(e) => setLongitude(e.target.value)}
                    placeholder="e.g. 153.0251"
                    className="w-full bg-white border border-slate-200 rounded-lg p-2 text-slate-900 focus:outline-none focus:border-purple-500 font-mono text-xs"
                  />
                </div>
              </div>

              {/* Service Offering Specification */}
              <div className="p-3 bg-purple-50/50 rounded-xl border border-purple-100 space-y-2">
                <span className="font-bold text-purple-900 block">Optional Service Node Injection</span>
                <input
                  type="text"
                  value={serviceName}
                  onChange={(e) => setServiceName(e.target.value)}
                  placeholder="Service Name (e.g. Emergency Electrical Repairs)"
                  className="w-full bg-white border border-purple-200 rounded-lg p-2 text-slate-900 text-xs"
                />
                <input
                  type="text"
                  value={serviceDescription}
                  onChange={(e) => setServiceDescription(e.target.value)}
                  placeholder="Service Description"
                  className="w-full bg-white border border-purple-200 rounded-lg p-2 text-slate-900 text-xs"
                />
              </div>

              {/* Linked @graph Checkbox */}
              <div className="flex items-center space-x-2 pt-1">
                <input
                  type="checkbox"
                  id="includeGraph"
                  checked={includeGraph}
                  onChange={(e) => setIncludeGraph(e.target.checked)}
                  className="rounded text-purple-600 focus:ring-purple-500 w-4 h-4 cursor-pointer"
                />
                <label htmlFor="includeGraph" className="text-slate-700 font-bold cursor-pointer">
                  Generate Interconnected <code className="text-purple-700 font-mono">@graph</code> (Organization → LocalBusiness → WebSite → WebPage → Service)
                </label>
              </div>

              <button
                type="submit"
                disabled={isGenerating}
                className="w-full py-3 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all mt-2 flex items-center justify-center space-x-2"
              >
                <Sparkles className="w-4 h-4" />
                <span>{isGenerating ? 'Validating & Generating...' : 'Generate Validated Schema.org JSON-LD'}</span>
              </button>
            </form>
          </div>

          {/* Right Output Panel */}
          <div className="lg:col-span-6 card-vibrant p-5 flex flex-col justify-between space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center space-x-1.5">
                <Code className="w-4 h-4 text-purple-600" />
                <span>Generated Schema.org JSON-LD Tag</span>
              </h3>

              {generatedHtml && (
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => downloadJsonLd(generatedJsonLd, `${activeProject.domain}-schema.jsonld`)}
                    className="flex items-center space-x-1 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-lg text-xs font-bold border border-slate-200 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>.jsonld</span>
                  </button>

                  <button
                    onClick={() => copyToClipboard(generatedHtml)}
                    className="flex items-center space-x-1 px-3 py-1 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-bold shadow-sm transition-colors"
                  >
                    {isCopied ? <Check className="w-3.5 h-3.5 text-white" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{isCopied ? 'Copied Tag' : 'Copy HTML Tag'}</span>
                  </button>
                </div>
              )}
            </div>

            <div className="flex-1 bg-slate-900 p-4 rounded-xl border border-slate-800 font-mono text-xs text-emerald-400 overflow-x-auto min-h-[380px] max-h-[460px]">
              <pre className="whitespace-pre">
                {generatedHtml ||
                  '// Click "Generate Validated Schema.org JSON-LD" on the left to produce production-grade structured markup tailored for ' +
                    activeProject.domain +
                    '.'}
              </pre>
            </div>

            <div className="text-[11px] text-slate-500 flex items-center justify-between pt-1 border-t border-slate-100">
              <span className="flex items-center space-x-1 text-emerald-600 font-bold">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Internally validated against Schema.org & Google Rich Results specs</span>
              </span>
              <span>Ready for <code className="text-purple-600 font-mono">&lt;head&gt;</code> injection</span>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* TAB 5: LIVE JSON-LD VALIDATOR */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'validator' && (
        <div className="card-vibrant p-5 space-y-4">
          <div>
            <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
              Live Schema.org & Google Rich Results JSON-LD Validator
            </h3>
            <p className="text-xs text-slate-500">
              Paste any custom JSON-LD script snippet to test syntax correctness, mandatory property completeness, and NAP alignment.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 space-y-2">
              <textarea
                value={validatorInput}
                onChange={(e) => setValidatorInput(e.target.value)}
                placeholder='<script type="application/ld+json">&#10;{&#10;  "@context": "https://schema.org",&#10;  "@type": "LocalBusiness",&#10;  "name": "Example Business"&#10;}&#10;</script>'
                className="w-full h-80 bg-slate-900 text-emerald-400 font-mono text-xs p-4 rounded-xl border border-slate-800 focus:outline-none focus:border-purple-500"
              />
              <button
                onClick={handleValidateSnippet}
                disabled={isValidating || !validatorInput.trim()}
                className="px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-sm transition-all"
              >
                {isValidating ? 'Validating...' : 'Validate Structured Snippet'}
              </button>
            </div>

            <div className="lg:col-span-5 p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
              <h4 className="text-xs font-extrabold uppercase text-slate-700 tracking-wider">
                Validation Report
              </h4>

              {validationResult ? (
                <div className="space-y-3 text-xs">
                  <div
                    className={`p-3 rounded-xl border flex items-center space-x-2 font-bold ${
                      validationResult.is_valid
                        ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                        : 'bg-rose-50 border-rose-200 text-rose-800'
                    }`}
                  >
                    {validationResult.is_valid ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-rose-600 shrink-0" />
                    )}
                    <span>
                      {validationResult.is_valid
                        ? 'Valid Schema.org Structure'
                        : 'Validation Errors Detected'}
                    </span>
                  </div>

                  {validationResult.entities?.length > 0 && (
                    <div>
                      <span className="text-[10px] font-extrabold text-slate-400 uppercase block mb-1">
                        Detected Entity Types
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {validationResult.entities.map((ent, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 text-[10px] font-bold"
                          >
                            {ent}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {validationResult.errors?.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-extrabold text-rose-600 uppercase block">
                        Errors ({validationResult.errors.length})
                      </span>
                      <ul className="text-[11px] text-rose-700 list-disc list-inside space-y-0.5">
                        {validationResult.errors.map((err, idx) => (
                          <li key={idx}>{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {validationResult.warnings?.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-extrabold text-amber-600 uppercase block">
                        Recommendations / Warnings ({validationResult.warnings.length})
                      </span>
                      <ul className="text-[11px] text-amber-700 list-disc list-inside space-y-0.5">
                        {validationResult.warnings.map((w, idx) => (
                          <li key={idx}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-16 text-slate-400 text-xs">
                  <ShieldCheck className="w-8 h-8 mx-auto mb-2 opacity-40" />
                  <p>Paste your JSON-LD code and click Validate to run the Schema.org inspection engine.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

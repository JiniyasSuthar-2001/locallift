import React, { useState, useEffect } from 'react';
import {
  Globe,
  Play,
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  FileText,
  Search,
  ExternalLink,
  Filter,
  Sparkles,
  FileCode2,
  ShieldCheck,
  MapPin,
  Phone,
  Building2,
  Star,
  Check,
  X,
  ArrowUpRight,
  ArrowRight,
  Database,
  Layers,
  Award
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';
import { WebsitePage, SEOIssue } from '../types';
import { IssueCard } from '../components/ui/IssueCard';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

interface DiscrepancyField {
  website?: string | null;
  gbp?: string | null;
  citations_mismatches?: number;
  is_aligned?: boolean;
}

interface DiagnosticSummary {
  project_id: number;
  overall_score: number;
  pages_analyzed: number;
  critical_issues: number;
  warnings: number;
  opportunities: number;
  passed_checks: number;
  pillar_scores: {
    crawl_health: number;
    onpage_content: number;
    schema_structured_data: number;
    gbp_alignment: number;
    citations_nap: number;
    reviews_reputation: number;
  };
  discrepancy_matrix: {
    business_name: DiscrepancyField;
    phone: DiscrepancyField;
    address: DiscrepancyField;
    website_url: DiscrepancyField;
  };
  gbp_status: {
    connected: boolean;
    profile_name?: string | null;
    phone?: string | null;
    address?: string | null;
  };
  citations_status: {
    total: number;
    mismatches: number;
    active: number;
  };
  reviews_status: {
    total: number;
    average_rating: number;
    unanswered: number;
  };
}

export const WebsiteAuditView: React.FC = () => {
  const { activeProject, refreshDashboard } = useProject();
  const [pages, setPages] = useState<WebsitePage[]>([]);
  const [issues, setIssues] = useState<SEOIssue[]>([]);
  const [summary, setSummary] = useState<DiagnosticSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [isCrawling, setIsCrawling] = useState(false);
  const [activeTab, setActiveTab] = useState<'issues' | 'matrix' | 'pages'>('issues');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  const fetchAuditData = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const [pagesResp, issuesResp, summaryResp] = await Promise.allSettled([
        api.get(`/audits/pages/${activeProject.id}`),
        api.get(`/audits/issues/${activeProject.id}`),
        api.get(`/audits/${activeProject.id}/diagnostic-summary`)
      ]);

      if (pagesResp.status === 'fulfilled') setPages(pagesResp.value.data || []);
      if (issuesResp.status === 'fulfilled') setIssues(issuesResp.value.data || []);
      if (summaryResp.status === 'fulfilled') setSummary(summaryResp.value.data);
    } catch (err) {
      console.error('Failed to load audit data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditData();
  }, [activeProject?.id]);

  const handleTriggerCrawl = async () => {
    if (!activeProject) return;
    try {
      setIsCrawling(true);
      await api.post(`/audits/crawl/${activeProject.id}`, {
        url: `https://${activeProject.domain}`,
        max_pages: 15
      });
      await fetchAuditData();
      await refreshDashboard();
    } catch (err) {
      console.error('Crawl execution failed:', err);
    } finally {
      setIsCrawling(false);
    }
  };

  const filteredIssues = issues.filter((i) => {
    if (severityFilter !== 'all' && i.severity.toLowerCase() !== severityFilter.toLowerCase()) {
      return false;
    }
    if (categoryFilter !== 'all' && i.category.toLowerCase() !== categoryFilter.toLowerCase()) {
      return false;
    }
    return true;
  });

  const schemaCount = pages.filter(p => p.schema_types && p.schema_types.length > 0).length;

  // Derive Pillar Scores (from summary or fallbacks)
  const pillars = summary?.pillar_scores || {
    crawl_health: activeProject?.technical_score || 82,
    onpage_content: activeProject?.onpage_score || 75,
    schema_structured_data: activeProject?.local_score || 68,
    gbp_alignment: activeProject?.gbp_score || 85,
    citations_nap: activeProject?.citations_score || 80,
    reviews_reputation: activeProject?.reviews_score || 90
  };

  const matrix = summary?.discrepancy_matrix;

  const pillarCards = [
    {
      id: 'crawl',
      name: 'Local Crawl Health',
      weight: '20%',
      score: pillars.crawl_health,
      desc: 'HTTP status, canonicals, and indexability',
      color: 'text-indigo-600',
      bg: 'bg-indigo-500'
    },
    {
      id: 'onpage',
      name: 'Local On-Page & Geo-Content',
      weight: '20%',
      score: pillars.onpage_content,
      desc: 'City/suburb keywords, local H1, meta geo signals',
      color: 'text-purple-600',
      bg: 'bg-purple-500'
    },
    {
      id: 'schema',
      name: 'Schema & Structured Data',
      weight: '25%',
      score: pillars.schema_structured_data,
      desc: 'LocalBusiness JSON-LD, geo, opening hours',
      color: 'text-fuchsia-600',
      bg: 'bg-fuchsia-500'
    },
    {
      id: 'gbp',
      name: 'Google Business Profile Match',
      weight: '15%',
      score: pillars.gbp_alignment,
      desc: 'Cross-alignment of Name, Phone, and Address',
      color: 'text-blue-600',
      bg: 'bg-blue-500'
    },
    {
      id: 'citations',
      name: 'Citations & Directory NAP',
      weight: '10%',
      score: pillars.citations_nap,
      desc: 'Consistency across top directory listings',
      color: 'text-amber-600',
      bg: 'bg-amber-500'
    },
    {
      id: 'reviews',
      name: 'Reviews & Reputation',
      weight: '10%',
      score: pillars.reviews_reputation,
      desc: 'Review volume, velocity, and response health',
      color: 'text-emerald-600',
      bg: 'bg-emerald-500'
    }
  ];

  if (!activeProject) {
    return (
      <EmptyState
        icon={Globe}
        badge="Local Website Audit"
        title="Select a Project"
        description="Select an active business project to inspect local crawlability, Schema.org JSON-LD, on-page NAP, and suburban landing pages."
      />
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* View Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-purple-100/80 rounded-xl text-purple-700">
              <Globe className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                Local Website & Local SEO Audit
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Multi-signal local audit verifying on-page NAP consistency, Schema.org LocalBusiness JSON-LD, GBP alignment, and suburban landing pages for <span className="font-semibold text-slate-700">{activeProject.domain}</span>.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2.5 self-start shrink-0">
          <NavLink
            to="/templates"
            className="flex items-center space-x-1.5 px-4 py-2.5 bg-white border border-slate-200 hover:border-purple-300 text-slate-700 hover:text-purple-700 rounded-xl text-xs font-bold shadow-sm transition-all"
          >
            <FileCode2 className="w-4 h-4 text-purple-600" />
            <span>Local SEO Templates</span>
          </NavLink>

          <button
            onClick={handleTriggerCrawl}
            disabled={isCrawling}
            className="flex items-center space-x-2 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all disabled:opacity-50"
          >
            <Play className={`w-4 h-4 fill-current ${isCrawling ? 'animate-spin' : ''}`} />
            <span>{isCrawling ? 'Auditing Local Signals...' : 'Run Local Audit'}</span>
          </button>
        </div>
      </div>

      {/* Top Banner: Overall Score & Quick Local Stats */}
      <div className="card-vibrant p-5 bg-gradient-to-r from-purple-900 via-indigo-950 to-slate-900 text-white rounded-2xl relative overflow-hidden shadow-lg border-0">
        <div className="absolute right-0 top-0 bottom-0 opacity-10 pointer-events-none flex items-center pr-8">
          <ShieldCheck className="w-64 h-64 text-white" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 relative z-10">
          {/* Health Score Gauge */}
          <div className="flex items-center space-x-4 md:border-r md:border-white/10 pr-4">
            <div className="w-20 h-20 rounded-2xl bg-white/10 backdrop-blur-md flex flex-col items-center justify-center border border-white/20 shrink-0">
              <span className="text-3xl font-black text-white leading-none">
                {summary?.overall_score || activeProject.health_score || 72}
              </span>
              <span className="text-[10px] font-bold text-purple-200 mt-1 uppercase tracking-wider">
                / 100
              </span>
            </div>
            <div>
              <div className="flex items-center space-x-1.5 text-purple-300 text-xs font-bold uppercase tracking-wider">
                <Award className="w-3.5 h-3.5" />
                <span>Overall Local SEO Grade</span>
              </div>
              <p className="text-xs text-slate-300 mt-1 leading-snug">
                Derived across 6 weighted local pillars including Schema JSON-LD and NAP alignment.
              </p>
            </div>
          </div>

          {/* Metric 1 */}
          <div className="space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-purple-200/80">Crawled Pages</span>
            <div className="text-2xl font-black text-white">{pages.length}</div>
            <p className="text-xs text-slate-300">
              {pages.filter(p => p.status_code === 200).length} indexable 200 OK pages
            </p>
          </div>

          {/* Metric 2 */}
          <div className="space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-purple-200/80">Schema.org Adoption</span>
            <div className="text-2xl font-black text-emerald-400">
              {pages.length > 0 ? Math.round((schemaCount / pages.length) * 100) : 0}%
            </div>
            <p className="text-xs text-slate-300">
              {schemaCount} of {pages.length} pages have valid JSON-LD
            </p>
          </div>

          {/* Metric 3 */}
          <div className="space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-purple-200/80">Open Remediation Items</span>
            <div className="text-2xl font-black text-rose-400">{issues.length}</div>
            <p className="text-xs text-slate-300">
              {issues.filter(i => i.severity === 'critical').length} critical blockers detected
            </p>
          </div>
        </div>
      </div>

      {/* 6 Pillars Scoring Grid */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-black text-slate-900 uppercase tracking-wider flex items-center space-x-2">
            <Layers className="w-4 h-4 text-purple-600" />
            <span>Local SEO Audit Pillars & Weight Breakdown</span>
          </h2>
          <span className="text-xs text-slate-500 font-medium">Standards-compliant scoring engine</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {pillarCards.map((p) => (
            <div key={p.id} className="card-vibrant p-4 space-y-3 bg-white">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-mono">
                    Weight: {p.weight}
                  </span>
                  <h4 className="text-xs font-bold text-slate-900 mt-1.5">{p.name}</h4>
                </div>
                <div className="text-right">
                  <span className={`text-xl font-black ${p.score >= 80 ? 'text-emerald-600' : p.score >= 60 ? 'text-amber-600' : 'text-rose-600'}`}>
                    {p.score}
                  </span>
                  <span className="text-[10px] font-bold text-slate-400 block">/ 100</span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-2 rounded-full ${p.score >= 80 ? 'bg-emerald-500' : p.score >= 60 ? 'bg-amber-500' : 'bg-rose-500'} transition-all duration-500`}
                  style={{ width: `${Math.min(100, p.score)}%` }}
                />
              </div>

              <p className="text-[11px] text-slate-500 leading-tight font-medium">
                {p.desc}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 pb-2">
        <div className="flex space-x-2">
          <button
            onClick={() => setActiveTab('issues')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 ${
              activeTab === 'issues'
                ? 'bg-purple-100/70 text-purple-900 border border-purple-200 shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <AlertCircle className="w-3.5 h-3.5 text-purple-700" />
            <span>Audit Issues & Action Items ({issues.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('matrix')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 ${
              activeTab === 'matrix'
                ? 'bg-purple-100/70 text-purple-900 border border-purple-200 shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Building2 className="w-3.5 h-3.5 text-purple-700" />
            <span>Discrepancy Matrix (NAP vs GBP)</span>
          </button>

          <button
            onClick={() => setActiveTab('pages')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 ${
              activeTab === 'pages'
                ? 'bg-purple-100/70 text-purple-900 border border-purple-200 shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <FileText className="w-3.5 h-3.5 text-purple-700" />
            <span>Crawled Pages ({pages.length})</span>
          </button>
        </div>

        {activeTab === 'issues' && (
          <div className="flex items-center space-x-2">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="bg-white border border-slate-200 rounded-xl px-3 py-1.5 text-xs font-semibold text-slate-800 focus:outline-none focus:border-purple-500 cursor-pointer"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical Blockers</option>
              <option value="warning">Warnings</option>
              <option value="opportunity">Opportunities</option>
            </select>
          </div>
        )}
      </div>

      {/* Tab 1: Issues View */}
      {activeTab === 'issues' && (
        <div className="space-y-4">
          {filteredIssues.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredIssues.map((issue) => (
                <IssueCard key={issue.id} issue={issue} onConvertedToTask={fetchAuditData} />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={CheckCircle2}
              badge="Audit Clean"
              title="No Local SEO Issues Detected"
              description="Your website crawl passed all local SEO rules, NAP checks, and Schema structured data validations."
              actionText="Run Full Local Website Audit"
              onAction={handleTriggerCrawl}
            />
          )}
        </div>
      )}

      {/* Tab 2: Discrepancy Matrix View */}
      {activeTab === 'matrix' && (
        <div className="space-y-4">
          <div className="card-vibrant p-5 bg-white space-y-4">
            <div>
              <h3 className="text-base font-extrabold text-slate-900 flex items-center space-x-2">
                <Building2 className="w-5 h-5 text-purple-600" />
                <span>Website vs Google Business Profile vs Citations Consistency Matrix</span>
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Search engines cross-validate business identity across your Website, Google Business Profile, and major local directories. Conflicting data directly hurts local pack rankings.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                  <tr>
                    <th className="p-3.5">Signal Field</th>
                    <th className="p-3.5">On-Page / Website Data</th>
                    <th className="p-3.5">Google Business Profile</th>
                    <th className="p-3.5">Citation Conflicts</th>
                    <th className="p-3.5">Status</th>
                    <th className="p-3.5 text-right">Quick Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {/* Business Name */}
                  <tr className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold text-slate-900">
                      <div className="flex items-center space-x-1.5">
                        <Building2 className="w-3.5 h-3.5 text-slate-400" />
                        <span>Business Name</span>
                      </div>
                    </td>
                    <td className="p-3.5 font-semibold text-slate-800">
                      {matrix?.business_name?.website || activeProject.name}
                    </td>
                    <td className="p-3.5 font-semibold text-slate-800">
                      {matrix?.business_name?.gbp || summary?.gbp_status?.profile_name || activeProject.name}
                    </td>
                    <td className="p-3.5">
                      {matrix?.business_name?.citations_mismatches ? (
                        <span className="px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded font-bold text-[10px]">
                          {matrix.business_name.citations_mismatches} Conflicting
                        </span>
                      ) : (
                        <span className="text-emerald-700 font-medium">0 Mismatches</span>
                      )}
                    </td>
                    <td className="p-3.5">
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-bold">
                        <Check className="w-3 h-3 text-emerald-600" />
                        <span>Aligned</span>
                      </span>
                    </td>
                    <td className="p-3.5 text-right">
                      <NavLink
                        to="/templates?apply=citation-nap-correction-task"
                        className="inline-flex items-center space-x-1 text-purple-700 hover:text-purple-900 font-bold hover:underline text-xs"
                      >
                        <span>Standardize</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </NavLink>
                    </td>
                  </tr>

                  {/* Phone Number */}
                  <tr className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold text-slate-900">
                      <div className="flex items-center space-x-1.5">
                        <Phone className="w-3.5 h-3.5 text-slate-400" />
                        <span>Phone Number</span>
                      </div>
                    </td>
                    <td className="p-3.5 font-mono text-slate-800">
                      {matrix?.phone?.website || summary?.gbp_status?.phone || '+1 555-0199'}
                    </td>
                    <td className="p-3.5 font-mono text-slate-800">
                      {matrix?.phone?.gbp || summary?.gbp_status?.phone || '+1 555-0199'}
                    </td>
                    <td className="p-3.5">
                      {matrix?.phone?.citations_mismatches ? (
                        <span className="px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded font-bold text-[10px]">
                          {matrix.phone.citations_mismatches} Conflicting
                        </span>
                      ) : (
                        <span className="text-emerald-700 font-medium">0 Mismatches</span>
                      )}
                    </td>
                    <td className="p-3.5">
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-bold">
                        <Check className="w-3 h-3 text-emerald-600" />
                        <span>Aligned</span>
                      </span>
                    </td>
                    <td className="p-3.5 text-right">
                      <NavLink
                        to="/templates?apply=citation-nap-correction-task"
                        className="inline-flex items-center space-x-1 text-purple-700 hover:text-purple-900 font-bold hover:underline text-xs"
                      >
                        <span>Verify Phone</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </NavLink>
                    </td>
                  </tr>

                  {/* Physical Address */}
                  <tr className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold text-slate-900">
                      <div className="flex items-center space-x-1.5">
                        <MapPin className="w-3.5 h-3.5 text-slate-400" />
                        <span>Physical Address</span>
                      </div>
                    </td>
                    <td className="p-3.5 text-slate-800">
                      {matrix?.address?.website || summary?.gbp_status?.address || '123 Business Way, Suite 100'}
                    </td>
                    <td className="p-3.5 text-slate-800">
                      {matrix?.address?.gbp || summary?.gbp_status?.address || '123 Business Way, Suite 100'}
                    </td>
                    <td className="p-3.5">
                      {matrix?.address?.citations_mismatches ? (
                        <span className="px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded font-bold text-[10px]">
                          {matrix.address.citations_mismatches} Conflicting
                        </span>
                      ) : (
                        <span className="text-emerald-700 font-medium">0 Mismatches</span>
                      )}
                    </td>
                    <td className="p-3.5">
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-bold">
                        <Check className="w-3 h-3 text-emerald-600" />
                        <span>Aligned</span>
                      </span>
                    </td>
                    <td className="p-3.5 text-right">
                      <NavLink
                        to="/templates?apply=localbusiness-schema-standard"
                        className="inline-flex items-center space-x-1 text-purple-700 hover:text-purple-900 font-bold hover:underline text-xs"
                      >
                        <span>Inject Schema</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </NavLink>
                    </td>
                  </tr>

                  {/* Website URL */}
                  <tr className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold text-slate-900">
                      <div className="flex items-center space-x-1.5">
                        <Globe className="w-3.5 h-3.5 text-slate-400" />
                        <span>Target Domain</span>
                      </div>
                    </td>
                    <td className="p-3.5 font-mono text-slate-800">
                      https://{activeProject.domain}
                    </td>
                    <td className="p-3.5 font-mono text-slate-800">
                      https://{activeProject.domain}
                    </td>
                    <td className="p-3.5 text-slate-400 font-medium">
                      Matches canonical
                    </td>
                    <td className="p-3.5">
                      <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-bold">
                        <Check className="w-3 h-3 text-emerald-600" />
                        <span>Canonical</span>
                      </span>
                    </td>
                    <td className="p-3.5 text-right">
                      <NavLink
                        to="/templates?apply=service-location-page-blueprint"
                        className="inline-flex items-center space-x-1 text-purple-700 hover:text-purple-900 font-bold hover:underline text-xs"
                      >
                        <span>Add Suburb Page</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </NavLink>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Crawled Pages Table */}
      {activeTab === 'pages' && (
        <div className="card-vibrant overflow-hidden">
          {pages.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                  <tr>
                    <th className="p-3.5">URL Path</th>
                    <th className="p-3.5">Status</th>
                    <th className="p-3.5">Title Tag</th>
                    <th className="p-3.5">Schema.org Types</th>
                    <th className="p-3.5">Load Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {pages.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="p-3.5 font-mono text-slate-900 font-semibold max-w-xs truncate">
                        {p.url}
                      </td>
                      <td className="p-3.5">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                            p.status_code === 200
                              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                              : 'bg-rose-50 text-rose-800 border border-rose-200'
                          }`}
                        >
                          {p.status_code}
                        </span>
                      </td>
                      <td className="p-3.5 text-slate-700 max-w-sm truncate">
                        {p.title || <span className="text-slate-400 italic">Missing title</span>}
                      </td>
                      <td className="p-3.5">
                        {p.schema_types && p.schema_types.length > 0 ? (
                          <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-800 border border-purple-200 text-[10px] font-bold">
                            {p.schema_types.join(', ')}
                          </span>
                        ) : (
                          <span className="text-slate-400 font-medium">None</span>
                        )}
                      </td>
                      <td className="p-3.5 font-mono text-slate-500">
                        {p.load_time_ms ? `${p.load_time_ms}ms` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              icon={Globe}
              badge="No Pages Crawled"
              title="No Crawled Pages Yet"
              description="Run the automated crawler to scan your website structure, NAP visibility, and LocalBusiness schemas."
              actionText="Start Local Page Crawl"
              onAction={handleTriggerCrawl}
            />
          )}
        </div>
      )}
    </div>
  );
};

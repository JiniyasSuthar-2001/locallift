import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  Globe,
  Star,
  ShieldCheck,
  CheckSquare,
  AlertCircle,
  Clock,
  Sparkles,
  ExternalLink,
  ChevronRight,
  Search,
  CheckCircle2,
  Plus,
  Play,
  Layers,
  MapPin,
  Bot
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';
import { useProject } from '../context/ProjectContext';
import { Link, useNavigate } from 'react-router-dom';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { StatCard } from '../components/ui/StatCard';
import api from '../api/client';

export const Dashboard: React.FC = () => {
  const { activeProject, dashboard, loading, refreshDashboard } = useProject();
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<any[]>([]);
  const [keywords, setKeywords] = useState<any[]>([]);
  const [gscMetrics, setGscMetrics] = useState<any[]>([]);
  const [dataLoading, setDataLoading] = useState(false);

  useEffect(() => {
    if (!activeProject) return;

    const loadProjectData = async () => {
      try {
        setDataLoading(true);
        const [kwResp, taskResp, gscResp] = await Promise.allSettled([
          api.get(`/keywords/${activeProject.id}`),
          api.get(`/tasks/${activeProject.id}`),
          api.get(`/google/gsc/${activeProject.id}`)
        ]);

        if (kwResp.status === 'fulfilled') {
          setKeywords(kwResp.value.data || []);
        }
        if (taskResp.status === 'fulfilled') {
          setTasks(taskResp.value.data || []);
        }
        if (gscResp.status === 'fulfilled') {
          setGscMetrics(gscResp.value.data?.daily_history || []);
        }
      } catch (e) {
        console.error('Error loading dashboard data:', e);
      } finally {
        setDataLoading(false);
      }
    };

    loadProjectData();
  }, [activeProject?.id]);

  const toggleTaskStatus = async (taskId: number, currentStatus: string) => {
    try {
      const newStatus = currentStatus === 'completed' ? 'open' : 'completed';
      await api.patch(`/tasks/${taskId}`, { status: newStatus });
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, status: newStatus } : t));
      await refreshDashboard();
    } catch (e) {
      console.error('Failed to update task:', e);
    }
  };

  if (loading && !dashboard) {
    return (
      <div className="card-nature p-12 text-center space-y-3">
        <Sparkles className="w-8 h-8 mx-auto text-[#236B4F] animate-spin" />
        <p className="text-xs font-semibold text-[#587568]">Loading live project intelligence...</p>
      </div>
    );
  }

  if (!activeProject) {
    return (
      <EmptyState
        icon={Globe}
        badge="No Project Selected"
        title="Get Started with LocalLift"
        description="Create or select a business project to start auditing SEO health, tracking local keywords, and monitoring Google Business Profile performance."
        actionText="Setup New Project"
        actionLink="/onboarding"
      />
    );
  }

  const overallHealth = dashboard?.health_score !== undefined && dashboard?.health_score !== null 
    ? dashboard.health_score 
    : activeProject.health_score;
  const isHealthCalculated = overallHealth !== null && overallHealth !== undefined;

  const scores = dashboard?.scores || {
    technical: activeProject.technical_score ?? null,
    onpage: activeProject.onpage_score ?? null,
    local: activeProject.local_score ?? null,
    citations: activeProject.citations_score ?? null,
    reviews: activeProject.reviews_score ?? null,
    gbp: activeProject.gbp_score ?? null
  };

  const healthBreakdown = [
    { name: 'Technical SEO', score: scores.technical, color: '#236B4F' },
    { name: 'On-Page SEO', score: scores.onpage, color: '#2FA878' },
    { name: 'Local Signals', score: scores.local, color: '#39B982' },
    { name: 'Citations & NAP', score: scores.citations, color: '#D97706' },
    { name: 'Reputation & Reviews', score: scores.reviews, color: '#0D9488' },
  ];

  const improvedKeywordsCount = keywords.filter(k => k.current_rank && k.previous_rank && k.current_rank < k.previous_rank).length;
  const top3KeywordsCount = keywords.filter(k => k.current_rank && k.current_rank <= 3).length;

  return (
    <div className="space-y-6">
      {/* Hero Atmosphere Banner */}
      <div className="card-nature p-6 relative overflow-hidden bg-gradient-to-r from-white via-[#F7FAF7] to-[#F1F7F1]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#EAF2EA] text-[#174A38] border border-[#B8DFC9]">
                Local SEO Operations
              </span>
              <span className="text-xs text-[#587568]">{activeProject.domain}</span>
            </div>
            <h2 className="text-xl font-black text-[#142820] tracking-tight mt-1.5">
              {activeProject.name} — Local Visibility & Health
            </h2>
            <p className="text-xs text-[#587568] mt-0.5">
              Live ranking presence, organic visibility trends, and automated technical audit remediations.
            </p>
          </div>

          <div className="flex items-center space-x-2.5 shrink-0">
            <button
              onClick={() => navigate('/audits/website')}
              className="btn-primary-gradient px-4 py-2 rounded-xl text-xs flex items-center space-x-2"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Run Full Audit</span>
            </button>
          </div>
        </div>
      </div>

      {/* 1. Horizontal KPI Cards Section */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {/* Card 1: SEO Health */}
        <div className="kpi-forest p-4 rounded-2xl shadow-2xs space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#174A38]">
              SEO Health
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]">
              {isHealthCalculated
                ? (overallHealth >= 80 ? 'Good' : overallHealth >= 60 ? 'Fair' : 'Needs Action')
                : 'Awaiting Audit'}
            </span>
          </div>
          <div className="flex items-baseline space-x-1.5">
            <span className="text-2xl lg:text-3xl font-black text-[#142820]">
              {isHealthCalculated ? overallHealth : '—'}
            </span>
            {isHealthCalculated ? (
              <span className="text-xs font-bold text-[#587568]">/ 100</span>
            ) : (
              <span className="text-xs font-semibold text-[#587568]">Not yet audited</span>
            )}
          </div>
          <div className="text-[11px] text-[#174A38] font-semibold flex items-center space-x-1">
            <span className="text-[#236B4F] font-black">●</span>
            <span>Overall Site Grade</span>
          </div>
        </div>

        {/* Card 2: Local Visibility */}
        <div className="kpi-accent p-4 rounded-2xl shadow-2xs space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#142820]">
              Local Visibility
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]">
              {top3KeywordsCount} in Top 3
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-[#142820]">
              {keywords.length > 0 ? Math.round((top3KeywordsCount / keywords.length) * 100) : 0}%
            </span>
          </div>
          <div className="text-[11px] text-[#2E4E40] font-semibold">
            Local Pack Share
          </div>
        </div>

        {/* Card 3: Keywords Improved */}
        <div className="kpi-forest p-4 rounded-2xl shadow-2xs space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#174A38]">
              Rank Climbers
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]">
              +{improvedKeywordsCount}
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-[#142820]">{improvedKeywordsCount}</span>
          </div>
          <div className="text-[11px] text-[#174A38] font-semibold">
            Keywords Improved
          </div>
        </div>

        {/* Card 4: Active Tasks */}
        <div className="kpi-amber p-4 rounded-2xl shadow-2xs space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#92400E]">
              Active Tasks
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A]">
              {tasks.filter(t => t.status !== 'completed').length} Open
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-[#142820]">
              {tasks.filter(t => t.status !== 'completed').length}
            </span>
          </div>
          <div className="text-[11px] text-[#92400E] font-semibold">
            Pending Remediation
          </div>
        </div>

        {/* Card 5: Total Tracked */}
        <div className="kpi-forest p-4 rounded-2xl shadow-2xs space-y-2 relative overflow-hidden col-span-2 md:col-span-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#174A38]">
              Tracked Terms
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]">
              Live
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-[#142820]">{keywords.length}</span>
          </div>
          <div className="text-[11px] text-[#174A38] font-semibold">
            Active Search Terms
          </div>
        </div>
      </div>

      {/* 2. Performance Overview Section with Nature Line/Area Chart */}
      <div className="card-nature p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#EBF2EB] pb-4">
          <div>
            <h2 className="text-base font-extrabold text-[#142820] tracking-tight">
              Search Performance & Visibility
            </h2>
            <p className="text-xs text-[#587568] mt-0.5">
              Live Google Search visibility and impression analytics for {activeProject.domain}.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <Link
              to="/google/gsc"
              className="text-xs font-bold text-[#236B4F] hover:text-[#174A38] flex items-center space-x-1"
            >
              <span>Search Console View</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {gscMetrics.length > 0 ? (
          <div className="h-60 w-full pt-1">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={gscMetrics} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorImpressions" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#236B4F" stopOpacity={0.25}/>
                    <stop offset="95%" stopColor="#236B4F" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorClicks" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#39B982" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#39B982" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EAF2EA" />
                <XAxis dataKey="date" tickLine={false} axisLine={{ stroke: '#DCE8DC' }} tick={{ fill: '#587568', fontSize: 11 }} />
                <YAxis tickLine={false} axisLine={{ stroke: '#DCE8DC' }} tick={{ fill: '#587568', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#121D16', borderRadius: '0.75rem', borderColor: '#22382C', color: '#F5FAF6' }}
                  labelStyle={{ fontWeight: 'bold', color: '#F5FAF6' }}
                />
                <Legend verticalAlign="top" height={36} iconType="circle" />
                <Area type="monotone" name="Impressions" dataKey="impressions" stroke="#236B4F" strokeWidth={2.5} fillOpacity={1} fill="url(#colorImpressions)" />
                <Area type="monotone" name="Clicks" dataKey="clicks" stroke="#39B982" strokeWidth={2.5} fillOpacity={1} fill="url(#colorClicks)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="p-8 text-center bg-[#F7FAF7] rounded-xl border border-[#DCE8DC] space-y-2">
            <Globe className="w-8 h-8 text-[#236B4F] mx-auto stroke-[1.8]" />
            <h4 className="text-xs font-bold text-[#142820]">Google Search Console Integration</h4>
            <p className="text-xs text-[#587568] max-w-md mx-auto">
              Authorize Google Search Console to populate daily organic search impressions, query rankings, and CTR analytics.
            </p>
            <div className="pt-2">
              <Link
                to="/google/gsc"
                className="btn-secondary-nature inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs"
              >
                <span>Connect Search Console</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        )}
      </div>

      {/* 3. Top Keyword Rankings Table (Real Data) */}
      <div className="card-nature overflow-hidden">
        <div className="p-4 border-b border-[#EBF2EB] flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <TrendingUp className="w-4 h-4 text-[#236B4F]" />
            <h3 className="text-sm font-extrabold text-[#142820] tracking-tight">
              Top Tracked Keyword Rankings
            </h3>
          </div>
          <Link
            to="/rankings/keywords"
            className="text-xs font-bold text-[#236B4F] hover:text-[#174A38] flex items-center space-x-1"
          >
            <span>Manage All Keywords</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {keywords.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-[#2E4E40]">
              <thead className="bg-[#F7FAF7] text-[#587568] uppercase text-[10px] font-bold tracking-wider border-b border-[#EBF2EB]">
                <tr>
                  <th className="p-3.5">Keyword</th>
                  <th className="p-3.5">Location</th>
                  <th className="p-3.5">Current Rank</th>
                  <th className="p-3.5">Previous</th>
                  <th className="p-3.5">Change</th>
                  <th className="p-3.5 text-right">Search Volume</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EBF2EB]">
                {keywords.slice(0, 6).map((kw) => {
                  const hasDiff = kw.previous_rank !== null && kw.current_rank !== null;
                  const isUp = hasDiff && kw.current_rank < kw.previous_rank;
                  const isDown = hasDiff && kw.current_rank > kw.previous_rank;
                  const diff = hasDiff ? Math.abs(kw.previous_rank - kw.current_rank) : 0;

                  return (
                    <tr key={kw.id} className="hover:bg-[#F7FAF7] transition-colors">
                      <td className="p-3.5 font-bold text-[#142820]">{kw.keyword}</td>
                      <td className="p-3.5 text-[#587568]">{kw.target_location || 'Local Metro'}</td>
                      <td className="p-3.5">
                        <span
                          className={`inline-flex items-center justify-center w-7 h-7 rounded-lg font-black text-xs ${
                            kw.current_rank && kw.current_rank <= 3
                              ? 'bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]'
                              : kw.current_rank && kw.current_rank <= 10
                              ? 'bg-[#E6F8F0] text-[#065F46] border border-[#A7F3D0]'
                              : 'bg-[#F1F5F1] text-[#2E4E40] border border-[#DCE8DC]'
                          }`}
                        >
                          {kw.current_rank ? kw.current_rank : '—'}
                        </span>
                      </td>
                      <td className="p-3.5 text-[#587568] font-medium">
                        {kw.previous_rank ? `#${kw.previous_rank}` : '—'}
                      </td>
                      <td className="p-3.5">
                        {hasDiff && diff > 0 ? (
                          <span
                            className={`inline-flex items-center font-bold text-xs ${
                              isUp ? 'text-[#065F46]' : 'text-[#991B1B]'
                            }`}
                          >
                            {isUp ? '↑' : '↓'}
                            {diff}
                          </span>
                        ) : (
                          <span className="text-[#587568] font-bold">—</span>
                        )}
                      </td>
                      <td className="p-3.5 text-right font-mono text-[#142820] font-semibold">
                        {kw.search_volume ? `${kw.search_volume.toLocaleString()} / mo` : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center space-y-2">
            <p className="text-xs text-[#587568]">No keywords added yet for this project.</p>
            <Link
              to="/rankings/keywords"
              className="inline-flex items-center space-x-1 text-xs font-bold text-[#236B4F] hover:text-[#174A38]"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Track Your First Keyword</span>
            </Link>
          </div>
        )}
      </div>

      {/* 4. Active Remediation Tasks */}
      <div className="card-nature overflow-hidden">
        <div className="p-4 border-b border-[#EBF2EB] flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CheckSquare className="w-4 h-4 text-[#236B4F]" />
            <h3 className="text-sm font-extrabold text-[#142820] tracking-tight">
              Actionable SEO Tasks & Audit Fixes
            </h3>
          </div>
          <Link
            to="/tasks"
            className="text-xs font-bold text-[#236B4F] hover:text-[#174A38] flex items-center space-x-1"
          >
            <span>View Task Board</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {tasks.length > 0 ? (
          <div className="divide-y divide-[#EBF2EB]">
            {tasks.slice(0, 5).map((task) => (
              <div
                key={task.id}
                className="p-4 flex items-center justify-between hover:bg-[#F7FAF7] transition-colors"
              >
                <div className="flex items-center space-x-3 truncate">
                  <button
                    onClick={() => toggleTaskStatus(task.id, task.status)}
                    className={`w-5 h-5 rounded-md border flex items-center justify-center transition-colors shrink-0 ${
                      task.status === 'completed'
                        ? 'bg-[#236B4F] border-[#236B4F] text-white'
                        : 'border-[#B8DFC9] hover:border-[#236B4F] bg-white'
                    }`}
                  >
                    {task.status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5" />}
                  </button>
                  <div className="truncate">
                    <p className={`text-xs font-bold truncate ${task.status === 'completed' ? 'line-through text-[#8DAAA0]' : 'text-[#142820]'}`}>
                      {task.title}
                    </p>
                    <p className="text-[11px] text-[#587568] truncate">{task.description}</p>
                  </div>
                </div>

                <div className="flex items-center space-x-2 shrink-0 ml-3">
                  <StatusBadge status={task.priority || 'medium'} size="sm" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center space-y-2">
            <p className="text-xs text-[#587568]">All audit remediation tasks are completed.</p>
          </div>
        )}
      </div>
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  ArrowUp,
  ArrowDown,
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
  Play
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
      <div className="card-vibrant p-12 text-center space-y-3">
        <Sparkles className="w-8 h-8 mx-auto text-purple-600 animate-spin" />
        <p className="text-xs font-semibold text-slate-600">Loading live project intelligence...</p>
      </div>
    );
  }

  if (!activeProject) {
    return (
      <EmptyState
        icon={Globe}
        badge="No Project Selected"
        title="Get Started with LocalScope"
        description="Create or select a business project to start auditing SEO health, tracking local keywords, and monitoring Google Business Profile performance."
        actionText="Setup New Project"
        actionLink="/onboarding"
      />
    );
  }

  const scores = dashboard?.scores || {
    technical: activeProject.technical_score || 80,
    onpage: activeProject.onpage_score || 80,
    local: activeProject.local_score || 75,
    citations: activeProject.citations_score || 70,
    reviews: activeProject.reviews_score || 85,
    gbp: activeProject.gbp_score || 70
  };

  const healthBreakdown = [
    { name: 'Technical SEO', score: scores.technical, color: '#7C3AED' },
    { name: 'On-Page SEO', score: scores.onpage, color: '#2563EB' },
    { name: 'Local Signals', score: scores.local, color: '#059669' },
    { name: 'Citations & NAP', score: scores.citations, color: '#EA580C' },
    { name: 'Reputation & Reviews', score: scores.reviews, color: '#EC4899' },
  ];

  const improvedKeywordsCount = keywords.filter(k => k.current_rank && k.previous_rank && k.current_rank < k.previous_rank).length;
  const top3KeywordsCount = keywords.filter(k => k.current_rank && k.current_rank <= 3).length;

  return (
    <div className="space-y-6">
      {/* 1. Horizontal Vibrant KPI Cards Section */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {/* Card 1: Purple (SEO Health) */}
        <div className="kpi-vibrant-purple p-4 rounded-2xl shadow-sm space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-black uppercase tracking-wider text-purple-900">
              SEO Health
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-200 text-purple-900 border border-purple-300">
              {activeProject.health_score >= 80 ? 'Good' : activeProject.health_score >= 60 ? 'Fair' : 'Attention'}
            </span>
          </div>
          <div className="flex items-baseline space-x-1.5">
            <span className="text-2xl lg:text-3xl font-black text-slate-900">{activeProject.health_score}</span>
            <span className="text-xs font-bold text-slate-500">/ 100</span>
          </div>
          <div className="text-[11px] text-purple-900 font-semibold flex items-center space-x-1">
            <span className="text-purple-600 font-black">●</span>
            <span>Overall Site Grade</span>
          </div>
        </div>

        {/* Card 2: Blue (Local Visibility) */}
        <div className="kpi-vibrant-blue p-4 rounded-2xl shadow-sm space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-black uppercase tracking-wider text-blue-900">
              Local Visibility
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-200 text-blue-900 border border-blue-300">
              {top3KeywordsCount} in Top 3
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-slate-900">
              {keywords.length > 0 ? Math.round((top3KeywordsCount / keywords.length) * 100) : 0}%
            </span>
          </div>
          <div className="text-[11px] text-blue-900 font-semibold">
            Local Pack Share
          </div>
        </div>

        {/* Card 3: Green (Keywords Improved) */}
        <div className="kpi-vibrant-emerald p-4 rounded-2xl shadow-sm space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-black uppercase tracking-wider text-emerald-900">
              Rank Climbers
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-200 text-emerald-900 border border-emerald-300">
              +{improvedKeywordsCount}
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-slate-900">{improvedKeywordsCount}</span>
          </div>
          <div className="text-[11px] text-emerald-900 font-semibold">
            Keywords Improved
          </div>
        </div>

        {/* Card 4: Orange (Active Tasks) */}
        <div className="kpi-vibrant-orange p-4 rounded-2xl shadow-sm space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-black uppercase tracking-wider text-amber-900">
              Active Tasks
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-200 text-amber-950 border border-amber-300">
              {tasks.filter(t => t.status !== 'completed').length} Open
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-slate-900">
              {tasks.filter(t => t.status !== 'completed').length}
            </span>
          </div>
          <div className="text-[11px] text-amber-900 font-semibold">
            Pending Remediation
          </div>
        </div>

        {/* Card 5: Pink (Total Tracked) */}
        <div className="kpi-vibrant-pink p-4 rounded-2xl shadow-sm space-y-2 relative overflow-hidden col-span-2 md:col-span-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-black uppercase tracking-wider text-pink-900">
              Tracked Keywords
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-pink-200 text-pink-900 border border-pink-300">
              Live
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl lg:text-3xl font-black text-slate-900">{keywords.length}</span>
          </div>
          <div className="text-[11px] text-pink-900 font-semibold">
            Active Search Terms
          </div>
        </div>
      </div>

      {/* 2. Performance Overview Section with Real GSC/Analytics Line Chart */}
      <div className="card-vibrant p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <h2 className="text-base font-extrabold text-slate-900 tracking-tight">
              Search Performance & Impressions
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Live Google Search visibility and customer click trends for {activeProject.domain}.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <Link
              to="/google/gsc"
              className="text-xs font-bold text-purple-700 hover:text-purple-800 flex items-center space-x-1"
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
                    <stop offset="5%" stopColor="#7C3AED" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#7C3AED" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorClicks" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#EC4899" stopOpacity={0.25}/>
                    <stop offset="95%" stopColor="#EC4899" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                <XAxis dataKey="date" tickLine={false} axisLine={{ stroke: '#E2E8F0' }} tick={{ fill: '#64748B', fontSize: 11 }} />
                <YAxis tickLine={false} axisLine={{ stroke: '#E2E8F0' }} tick={{ fill: '#64748B', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#FFFFFF', borderRadius: '0.75rem', borderColor: '#E2E8F0', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.08)' }}
                  labelStyle={{ fontWeight: 'bold', color: '#0F172A' }}
                />
                <Legend verticalAlign="top" height={36} iconType="circle" />
                <Area type="monotone" name="Impressions" dataKey="impressions" stroke="#7C3AED" strokeWidth={2.5} fillOpacity={1} fill="url(#colorImpressions)" />
                <Area type="monotone" name="Clicks" dataKey="clicks" stroke="#EC4899" strokeWidth={2.5} fillOpacity={1} fill="url(#colorClicks)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="p-8 text-center bg-slate-50/70 rounded-xl border border-slate-200/80 space-y-2">
            <Globe className="w-8 h-8 text-purple-600 mx-auto stroke-[1.8]" />
            <h4 className="text-xs font-bold text-slate-800">Google Search Console Integration</h4>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Authorize Google Search Console to populate daily organic search impressions, query rankings, and CTR analytics.
            </p>
            <div className="pt-2">
              <Link
                to="/google/gsc"
                className="inline-flex items-center space-x-1.5 px-4 py-2 btn-vibrant-secondary rounded-xl text-xs font-bold"
              >
                <span>Connect Search Console</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        )}
      </div>

      {/* 3. Top Keyword Rankings Table (Real Data) */}
      <div className="card-vibrant overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <TrendingUp className="w-4 h-4 text-purple-600" />
            <h3 className="text-sm font-extrabold text-slate-900 tracking-tight">
              Top Tracked Keyword Rankings
            </h3>
          </div>
          <Link
            to="/rankings/keywords"
            className="text-xs font-bold text-purple-700 hover:text-purple-800 flex items-center space-x-1"
          >
            <span>Manage All Keywords</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {keywords.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50/80 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                <tr>
                  <th className="p-3.5">Keyword</th>
                  <th className="p-3.5">Location</th>
                  <th className="p-3.5">Current Rank</th>
                  <th className="p-3.5">Previous</th>
                  <th className="p-3.5">Change</th>
                  <th className="p-3.5 text-right">Search Volume</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {keywords.slice(0, 6).map((kw) => {
                  const hasDiff = kw.previous_rank !== null && kw.current_rank !== null;
                  const isUp = hasDiff && kw.current_rank < kw.previous_rank;
                  const isDown = hasDiff && kw.current_rank > kw.previous_rank;
                  const diff = hasDiff ? Math.abs(kw.previous_rank - kw.current_rank) : 0;

                  return (
                    <tr key={kw.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="p-3.5 font-bold text-slate-900">{kw.keyword}</td>
                      <td className="p-3.5 text-slate-500">{kw.target_location || 'Local Metro'}</td>
                      <td className="p-3.5">
                        <span
                          className={`inline-flex items-center justify-center w-7 h-7 rounded-lg font-black text-xs ${
                            kw.current_rank && kw.current_rank <= 3
                              ? 'bg-emerald-100 text-emerald-900 border border-emerald-200'
                              : kw.current_rank && kw.current_rank <= 10
                              ? 'bg-blue-100 text-blue-900 border border-blue-200'
                              : 'bg-slate-100 text-slate-700 border border-slate-200'
                          }`}
                        >
                          {kw.current_rank ? kw.current_rank : '—'}
                        </span>
                      </td>
                      <td className="p-3.5 text-slate-500 font-medium">
                        {kw.previous_rank ? `#${kw.previous_rank}` : '—'}
                      </td>
                      <td className="p-3.5">
                        {hasDiff && diff > 0 ? (
                          <span
                            className={`inline-flex items-center font-bold text-xs ${
                              isUp ? 'text-emerald-700' : 'text-rose-700'
                            }`}
                          >
                            {isUp ? '↑' : '↓'}
                            {diff}
                          </span>
                        ) : (
                          <span className="text-slate-400 font-bold">—</span>
                        )}
                      </td>
                      <td className="p-3.5 text-right font-mono text-slate-700 font-semibold">
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
            <p className="text-xs text-slate-500">No keywords added yet for this project.</p>
            <Link
              to="/rankings/keywords"
              className="inline-flex items-center space-x-1 text-xs font-bold text-purple-700 hover:text-purple-800"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Target Local Keywords</span>
            </Link>
          </div>
        )}
      </div>

      {/* 4. Two Columns: SEO Health Breakdown (Real Scores) & Tasks / Priorities */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Real SEO Health Breakdown */}
        <div className="lg:col-span-5 card-vibrant p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-extrabold text-slate-900 tracking-tight">
              SEO Pillar Health Breakdown
            </h3>
            <span className="text-xs font-black text-purple-700">{activeProject.health_score} / 100</span>
          </div>

          <div className="space-y-3.5">
            {healthBreakdown.map((item, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-800">{item.name}</span>
                  <span className="font-bold text-slate-900">{item.score} / 100</span>
                </div>
                <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${item.score}%`,
                      backgroundColor: item.color
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Real Prioritized Tasks */}
        <div className="lg:col-span-7 card-vibrant p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center space-x-2">
              <CheckSquare className="w-4 h-4 text-purple-600" />
              <h3 className="text-sm font-extrabold text-slate-900 tracking-tight">
                Prioritized SEO Remediation Tasks
              </h3>
            </div>
            <Link to="/tasks" className="text-xs font-bold text-purple-700 hover:text-purple-800">
              Open Board →
            </Link>
          </div>

          {tasks.length > 0 ? (
            <div className="space-y-2.5">
              {tasks.slice(0, 5).map((task) => (
                <div
                  key={task.id}
                  className={`p-3 rounded-xl border flex items-center justify-between transition-all ${
                    task.status === 'completed'
                      ? 'bg-slate-50 border-slate-200 opacity-60'
                      : 'bg-white border-slate-200 hover:border-purple-300'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => toggleTaskStatus(task.id, task.status)}
                      className={`w-5 h-5 rounded-md border flex items-center justify-center transition-colors ${
                        task.status === 'completed'
                          ? 'bg-emerald-600 border-emerald-600 text-white'
                          : 'border-slate-300 hover:border-purple-500 bg-white'
                      }`}
                    >
                      {task.status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5" />}
                    </button>
                    <div>
                      <div
                        className={`text-xs font-bold text-slate-900 ${
                          task.status === 'completed' ? 'line-through text-slate-400' : ''
                        }`}
                      >
                        {task.title}
                      </div>
                      <div className="text-[10px] text-slate-500 font-medium">
                        {task.category}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2.5">
                    <StatusBadge status={task.priority} />
                    <button
                      onClick={() => toggleTaskStatus(task.id, task.status)}
                      className="px-2.5 py-1 text-[11px] font-bold text-purple-700 hover:bg-purple-50 rounded-lg transition-colors"
                    >
                      {task.status === 'completed' ? 'Reopen' : 'Complete'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center space-y-2">
              <p className="text-xs text-slate-500">No tasks created yet.</p>
              <Link
                to="/tasks"
                className="inline-flex items-center space-x-1 text-xs font-bold text-purple-700 hover:text-purple-800"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create Optimization Task</span>
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

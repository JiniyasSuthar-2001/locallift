import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, Link, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Globe,
  Search,
  Cpu,
  Activity,
  Layers,
  HeartPulse,
  Bell,
  FileText,
  ShieldAlert,
  Settings,
  ArrowLeft,
  Search as SearchIcon,
  AlertTriangle,
  CheckCircle2,
  Lock,
  ExternalLink,
  RefreshCw,
  Power
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../api/client';

export const MasterPlaceLayout: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showSearchModal, setShowSearchModal] = useState(false);
  const [aiKillStatus, setAiKillStatus] = useState<boolean | null>(null);

  // Check platform permission
  const isPlatformOperator = Boolean(
    user?.is_superuser ||
    (user?.platform_role && ['super_admin', 'platform_admin', 'operations', 'support', 'finance', 'viewer'].includes(user.platform_role.toLowerCase()))
  );

  useEffect(() => {
    if (!isPlatformOperator) return;

    // Fetch kill switch status for top bar indicator
    api.get('/masterplace/overview')
      .then((res) => {
        if (res.data?.kpis) {
          setAiKillStatus(res.data.kpis.global_ai_enabled);
        }
      })
      .catch(() => {});
  }, [isPlatformOperator]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearchLoading(true);
    setShowSearchModal(true);
    try {
      const res = await api.get('/masterplace/search', { params: { q: searchQuery.trim() } });
      setSearchResults(res.data.results);
    } catch (err) {
      setSearchResults(null);
    } finally {
      setSearchLoading(false);
    }
  };

  if (!isPlatformOperator) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-white">
        <div className="max-w-md w-full bg-slate-900 border border-red-500/30 rounded-2xl p-8 text-center space-y-6 shadow-2xl">
          <div className="w-16 h-16 bg-red-500/10 border border-red-500/30 rounded-2xl flex items-center justify-center mx-auto text-red-400">
            <Lock className="w-8 h-8" />
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-black tracking-tight text-white">403 Forbidden</h1>
            <p className="text-sm font-semibold text-red-400">MasterPlace Platform Control Plane</p>
            <p className="text-xs text-slate-400 leading-relaxed">
              Access to this internal control plane is restricted to authorized platform operators and administrators. Your account does not possess platform-level permissions.
            </p>
          </div>
          <div className="pt-2">
            <button
              onClick={() => navigate('/')}
              className="w-full inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-sm transition-colors shadow-lg shadow-purple-600/20"
            >
              <ArrowLeft className="w-4 h-4" />
              Return to Project Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  const navItems = [
    { label: 'Overview', path: '/masterplace', icon: LayoutDashboard, end: true },
    { label: 'Customers', path: '/masterplace/customers', icon: Users },
    { label: 'Websites', path: '/masterplace/websites', icon: Globe },
    { label: 'Google APIs', path: '/masterplace/google', icon: Layers },
    { label: 'SERP Providers', path: '/masterplace/serp', icon: Search },
    { label: 'AI Providers', path: '/masterplace/ai', icon: Cpu },
    { label: 'Scan Jobs', path: '/masterplace/jobs', icon: Activity },
    { label: 'System Health', path: '/masterplace/health', icon: HeartPulse },
    { label: 'Alerts', path: '/masterplace/alerts', icon: Bell },
    { label: 'Audit Logs', path: '/masterplace/audit', icon: FileText },
    { label: 'Security', path: '/masterplace/security', icon: ShieldAlert },
    { label: 'Settings', path: '/masterplace/settings', icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header Bar */}
      <header className="h-16 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md sticky top-0 z-40 px-6 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-600 to-blue-500 flex items-center justify-center text-white font-black text-lg shadow-lg shadow-purple-600/30">
              L
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-black text-sm tracking-wider text-white">LOCALLIFT</span>
                <span className="px-2 py-0.5 text-[10px] font-black uppercase tracking-wider rounded-md bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  MASTERPLACE
                </span>
              </div>
              <span className="text-[11px] font-medium text-slate-400 block -mt-0.5">Platform Owner Command Center</span>
            </div>
          </div>

          {/* Quick return link */}
          <Link
            to="/"
            className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700/60 text-xs font-semibold text-slate-300 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Project Dashboard
          </Link>
        </div>

        {/* Global Search Bar */}
        <div className="flex-1 max-w-md mx-6 hidden sm:block">
          <form onSubmit={handleSearch} className="relative">
            <SearchIcon className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search customers, websites, jobs, domains..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-1.5 text-xs rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all"
            />
          </form>
        </div>

        {/* Header Right Status Badges */}
        <div className="flex items-center gap-3">
          {/* AI Kill Switch Indicator */}
          {aiKillStatus !== null && (
            <div
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold border ${
                aiKillStatus
                  ? 'bg-emerald-950/60 border-emerald-500/30 text-emerald-400'
                  : 'bg-red-950/60 border-red-500/30 text-red-400 animate-pulse'
              }`}
            >
              <Power className="w-3.5 h-3.5" />
              <span>AI {aiKillStatus ? 'ENABLED' : 'KILL SWITCH ACTIVE'}</span>
            </div>
          )}

          {/* Operator Badge */}
          <div className="flex items-center gap-2 pl-3 border-l border-slate-800">
            <div className="w-8 h-8 rounded-full bg-purple-600/30 border border-purple-500/40 flex items-center justify-center text-xs font-bold text-purple-300">
              {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'O'}
            </div>
            <div className="hidden lg:block text-left">
              <div className="text-xs font-bold text-white truncate max-w-[120px]">{user?.full_name || user?.email}</div>
              <div className="text-[10px] font-semibold text-purple-400 uppercase tracking-wider">
                {user?.is_superuser ? 'SUPER ADMIN' : (user?.platform_role || 'OPERATOR')}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Body with Sidebar + Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* MasterPlace Sidebar */}
        <aside className="w-60 border-r border-slate-800/80 bg-slate-900/60 flex flex-col shrink-0">
          <nav className="p-3 space-y-1 overflow-y-auto">
            <div className="px-3 py-2 text-[10px] font-black uppercase tracking-wider text-slate-500">
              CONTROL PLANE
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.end}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                      isActive
                        ? 'bg-purple-600/20 text-purple-300 border border-purple-500/30 shadow-sm'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>

          <div className="p-4 mt-auto border-t border-slate-800/80 text-[11px] text-slate-500 space-y-1">
            <div className="font-semibold text-slate-400">LocalLift v1.0 Owner Plane</div>
            <div>Authoritative telemetry mode</div>
          </div>
        </aside>

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto bg-slate-950 p-6 md:p-8">
          <Outlet />
        </main>
      </div>

      {/* Global Search Results Modal */}
      {showSearchModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center pt-20 p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <SearchIcon className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-bold text-white">Global Search: &quot;{searchQuery}&quot;</h3>
              </div>
              <button
                onClick={() => setShowSearchModal(false)}
                className="text-xs font-bold text-slate-400 hover:text-white"
              >
                ✕ Close
              </button>
            </div>

            {searchLoading ? (
              <div className="py-8 text-center text-xs text-slate-400">Searching platform database...</div>
            ) : !searchResults ? (
              <div className="py-8 text-center text-xs text-slate-400">No results found for query.</div>
            ) : (
              <div className="space-y-4 max-h-96 overflow-y-auto pr-1">
                {/* Customers */}
                {searchResults.customers?.length > 0 && (
                  <div>
                    <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">Customers ({searchResults.customers.length})</h4>
                    <div className="space-y-1.5">
                      {searchResults.customers.map((c: any) => (
                        <div
                          key={c.id}
                          onClick={() => {
                            setShowSearchModal(false);
                            navigate(`/masterplace/customers`);
                          }}
                          className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80 hover:border-purple-500/50 cursor-pointer flex items-center justify-between"
                        >
                          <div>
                            <span className="text-xs font-bold text-white">{c.name}</span>
                            <span className="ml-2 text-[10px] text-slate-400">Plan: {c.plan}</span>
                          </div>
                          <span className={`text-[10px] px-2 py-0.5 rounded font-semibold ${c.status === 'active' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'}`}>
                            {c.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Projects */}
                {searchResults.projects?.length > 0 && (
                  <div>
                    <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">Projects ({searchResults.projects.length})</h4>
                    <div className="space-y-1.5">
                      {searchResults.projects.map((p: any) => (
                        <div
                          key={p.id}
                          className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80 flex items-center justify-between"
                        >
                          <div>
                            <span className="text-xs font-bold text-white">{p.name}</span>
                            <span className="ml-2 text-[11px] text-purple-400">{p.domain}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Websites */}
                {searchResults.websites?.length > 0 && (
                  <div>
                    <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">Websites ({searchResults.websites.length})</h4>
                    <div className="space-y-1.5">
                      {searchResults.websites.map((w: any) => (
                        <div
                          key={w.id}
                          onClick={() => {
                            setShowSearchModal(false);
                            navigate(`/masterplace/websites`);
                          }}
                          className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80 hover:border-purple-500/50 cursor-pointer flex items-center justify-between"
                        >
                          <span className="text-xs font-bold text-white">{w.url}</span>
                          <span className="text-[11px] text-slate-400">{w.project_name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Jobs */}
                {searchResults.jobs?.length > 0 && (
                  <div>
                    <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">Scan Jobs ({searchResults.jobs.length})</h4>
                    <div className="space-y-1.5">
                      {searchResults.jobs.map((j: any) => (
                        <div
                          key={j.id}
                          onClick={() => {
                            setShowSearchModal(false);
                            navigate(`/masterplace/jobs`);
                          }}
                          className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80 hover:border-purple-500/50 cursor-pointer flex items-center justify-between"
                        >
                          <span className="text-xs font-bold text-white">Job #{j.id} ({j.job_type})</span>
                          <span className="text-[10px] px-2 py-0.5 rounded font-semibold bg-purple-500/20 text-purple-300">{j.status}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

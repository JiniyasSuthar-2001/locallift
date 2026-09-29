import React, { useState } from 'react';
import {
  Building2,
  ChevronDown,
  Calendar,
  RotateCw,
  Sparkles,
  Plus,
  Check,
  Activity,
  Layers,
  X,
  ExternalLink,
  Shield,
  LayoutGrid,
  LayoutDashboard
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useProject } from '../../context/ProjectContext';
import { useProjectScan } from '../../context/ScanContext';
import { useTaskManager } from '../../context/TaskManagerContext';
import { useLocation, useNavigate, Link } from 'react-router-dom';

interface HeaderProps {
  onOpenAI: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onOpenAI }) => {
  const { user } = useAuth();
  const { projects, activeProject, setActiveProject, refreshDashboard } = useProject();
  const { isScanning, activeScan, startScan, openProgressModal } = useProjectScan();
  const { activeTasks, activeCount, cancelTask } = useTaskManager();
  const location = useLocation();
  const navigate = useNavigate();
  const [isProjectDropdownOpen, setIsProjectDropdownOpen] = useState(false);
  const [isTasksDropdownOpen, setIsTasksDropdownOpen] = useState(false);
  const [dateRange, setDateRange] = useState('Last 30 Days');
  const [isSyncing, setIsSyncing] = useState(false);

  // Derive page title from path
  const getPageTitle = () => {
    const path = location.pathname;

    if (path.startsWith('/projects/')) return 'Project Details';
    if (path.startsWith('/team/')) return 'Team Member Profile';

    switch (path) {
      case '/':
        return activeProject ? `${activeProject.name} — Dashboard` : 'Project Dashboard';
      case '/dashboard':
      case '/central-dashboard':
        return 'Main Dashboard — All My Projects';
      case '/projects':
        return 'My Projects';
      case '/rankings/keywords':
        return 'Keyword Rank Tracker';
      case '/rankings/grid':
        return '5x5 Geo-Grid Rankings';
      case '/audits/local':
        return 'Local SEO Signals Audit';
      case '/google/gbp':
        return 'Google Business Profile Hub';
      case '/google/gsc':
        return 'Google Search Console Telemetry';
      case '/google/ga4':
        return 'Google Analytics 4 Intelligence';
      case '/connections':
      case '/integrations':
        return 'Integrations & API Connections';
      case '/audits/website':
        return 'Technical Website Audit';
      case '/local/reviews':
        return 'Reviews & AI Reputation';
      case '/local/citations':
        return 'Citations Directory';
      case '/local/nap':
        return 'NAP Consistency Monitor';
      case '/local/competitors':
        return 'Local Competitors';
      case '/seo/schema':
        return 'Schema.org JSON-LD Generator';
      case '/seo/content-gaps':
        return 'Content & Landing Page Opportunities';
      case '/tasks':
        return 'SEO Task Operations';
      case '/team':
        return 'Team Directory';
      case '/agency/clients':
        return 'Agency Clients Directory';
      case '/templates':
        return 'Templates Hub';
      case '/reports':
        return 'Executive Performance Reports';
      case '/ai-assistant':
        return 'AI Diagnostic Studio';
      case '/settings':
        return 'Platform Settings';
      case '/onboarding':
        return 'New Project Setup';
      default:
        return 'Overview';
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    await refreshDashboard();
    setTimeout(() => setIsSyncing(false), 600);
  };

  const isCentralDashboard = location.pathname === '/dashboard' || location.pathname === '/central-dashboard';
  const isMasterPlace = location.pathname.startsWith('/masterplace');
  const isPlatformOwner = Boolean(user?.is_superuser || user?.platform_role);

  return (
    <header className="h-16 bg-white border-b border-[#DCE8DC] px-6 flex items-center justify-between sticky top-0 z-30 shadow-2xs">
      {/* Left: Page Title */}
      <div className="flex items-center space-x-3">
        <h1 className="text-xl font-black text-[#142820] tracking-tight">
          {getPageTitle()}
        </h1>
        {activeProject && !isCentralDashboard && !isMasterPlace && (
          <span className="hidden lg:inline-block text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-[#EAF2EA] text-[#174A38] border border-[#B8DFC9]">
            {activeProject.domain}
          </span>
        )}
      </div>

      {/* Right Controls: Business Selector, Date Range, Refresh, AI Diagnostic */}
      <div className="flex items-center space-x-3">
        {/* Global Background Tasks Indicator */}
        {activeCount > 0 && (
          <div className="relative">
            <button
              onClick={() => setIsTasksDropdownOpen(!isTasksDropdownOpen)}
              className="flex items-center space-x-2 px-3 py-1.5 rounded-xl bg-purple-50 border border-purple-200 hover:bg-purple-100 text-xs font-bold text-purple-800 transition-all shadow-2xs"
            >
              <Activity className="w-3.5 h-3.5 text-purple-600 animate-spin" />
              <span>Background Tasks</span>
              <span className="px-1.5 py-0.2 rounded-full bg-purple-600 text-white text-[10px]">
                {activeCount}
              </span>
              <ChevronDown className="w-3 h-3 text-purple-600" />
            </button>

            {isTasksDropdownOpen && (
              <div className="absolute right-0 mt-2 w-80 rounded-2xl bg-white border border-[#DCE8DC] shadow-xl p-3 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                <div className="flex items-center justify-between pb-2 border-b border-[#EBF2EB] mb-2">
                  <span className="text-[11px] font-black uppercase tracking-wider text-[#142820]">
                    Active Background Operations ({activeCount})
                  </span>
                  <button
                    onClick={() => setIsTasksDropdownOpen(false)}
                    className="p-1 text-slate-400 hover:text-slate-600 rounded-md"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {activeTasks.map((t) => (
                    <div
                      key={t.id}
                      className="p-2.5 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] text-xs space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-[#142820] flex items-center gap-1.5">
                          <Activity className="w-3 h-3 text-[#236B4F] animate-spin" />
                          {t.job_type === 'keyword_rank'
                            ? 'Keyword Scan'
                            : t.job_type === 'geo_grid'
                            ? 'Geo-Grid Scan'
                            : t.job_type}
                        </span>
                        <button
                          onClick={() => cancelTask(t.id, t.job_type)}
                          className="text-[10px] font-bold text-rose-600 hover:text-rose-800 px-1.5 py-0.5 rounded bg-rose-50 border border-rose-200"
                        >
                          Cancel
                        </button>
                      </div>
                      <div className="text-[10px] text-[#587568]">
                        Project: <span className="font-semibold text-[#142820]">{t.project_name}</span>
                      </div>
                      <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-[#236B4F] h-full transition-all duration-300"
                          style={{ width: `${t.progress}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-[#587568]">
                        <span>{t.current_stage || 'Processing...'}</span>
                        <span className="font-bold">{t.processed} / {t.total} ({t.progress}%)</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Improved Business / Project & Dashboard Selector */}
        <div className="relative">
          <button
            onClick={() => setIsProjectDropdownOpen(!isProjectDropdownOpen)}
            className={`flex items-center space-x-2 px-3 py-1.5 rounded-xl border transition-all shadow-2xs ${
              isMasterPlace
                ? 'bg-purple-950/40 border-purple-800 text-purple-200 hover:border-purple-600'
                : isCentralDashboard
                ? 'bg-[#EAF2EA] border-[#B8DFC9] text-[#142820] font-bold'
                : 'bg-[#F7FAF7] border-[#DCE8DC] hover:border-[#B8DFC9] text-[#142820]'
            } text-xs font-bold`}
          >
            {isMasterPlace ? (
              <Shield className="w-3.5 h-3.5 text-purple-400" />
            ) : isCentralDashboard ? (
              <LayoutGrid className="w-3.5 h-3.5 text-[#236B4F]" />
            ) : (
              <Building2 className="w-3.5 h-3.5 text-[#236B4F]" />
            )}
            <span className="max-w-[140px] truncate">
              {isMasterPlace
                ? 'MasterPlace'
                : isCentralDashboard
                ? 'Main Dashboard'
                : activeProject
                ? activeProject.name
                : 'Select Project'}
            </span>
            <ChevronDown className={`w-3 h-3 ${isMasterPlace ? 'text-purple-400' : 'text-[#587568]'}`} />
          </button>

          {isProjectDropdownOpen && (
            <div className="absolute right-0 mt-2 w-80 rounded-2xl bg-white border border-[#DCE8DC] shadow-xl py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150 overflow-hidden">
              <div className="px-3.5 py-1.5 text-[10px] font-black uppercase tracking-wider text-[#587568] border-b border-[#EBF2EB] flex items-center justify-between">
                <span>Select Active Project</span>
                <span className="text-[9px] text-[#7A9988] font-semibold">{projects.length} Available</span>
              </div>
              <div className="max-h-60 overflow-y-auto py-1 divide-y divide-[#F1F7F1]">
                {projects.map((proj) => {
                  const loc = proj.locations && proj.locations.length > 0 ? proj.locations[0] : null;
                  const locLabel = loc
                    ? [loc.city, loc.country].filter(Boolean).join(', ')
                    : proj.country || '';
                  const isSelected = !isMasterPlace && !isCentralDashboard && activeProject?.id === proj.id;

                  return (
                    <button
                      key={proj.id}
                      onClick={() => {
                        setActiveProject(proj);
                        setIsProjectDropdownOpen(false);
                        navigate('/');
                      }}
                      className={`w-full text-left px-3.5 py-2.5 text-xs flex items-center justify-between hover:bg-[#F1F7F1] transition-colors ${
                        isSelected ? 'bg-[#EAF2EA] text-[#142820]' : 'text-[#2E4E40]'
                      }`}
                    >
                      <div className="min-w-0 flex-1 pr-2">
                        <div className="font-bold truncate text-xs text-[#142820]">{proj.name}</div>
                        <div className="text-[10px] text-[#587568] truncate font-medium">{proj.domain}</div>
                        {locLabel && (
                          <div className="text-[9px] text-[#7A9988] truncate mt-0.5">{locLabel}</div>
                        )}
                      </div>
                      {isSelected && (
                        <Check className="w-4 h-4 text-[#236B4F] shrink-0 ml-2" />
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Add New Project */}
              <div className="p-2 border-t border-[#EBF2EB]">
                <button
                  onClick={() => {
                    setIsProjectDropdownOpen(false);
                    navigate('/onboarding');
                  }}
                  className="w-full flex items-center justify-center space-x-1.5 py-1.5 rounded-xl bg-[#F1F7F1] hover:bg-[#EAF2EA] text-xs font-bold text-[#236B4F] transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add New Project</span>
                </button>
              </div>

              {/* MAIN DASHBOARD (User Central Dashboard - All My Projects) */}
              <div className="p-2 border-t border-[#DCE8DC] bg-[#F7FAF7]">
                <button
                  onClick={() => {
                    setIsProjectDropdownOpen(false);
                    navigate('/dashboard');
                  }}
                  className={`w-full text-left p-2.5 rounded-xl transition-all flex items-center gap-3 group ${
                    isCentralDashboard
                      ? 'bg-[#EAF2EA] border border-[#B8DFC9] text-[#142820]'
                      : 'bg-white hover:bg-[#F1F7F1] border border-[#DCE8DC] text-[#142820]'
                  }`}
                >
                  <div className="w-8 h-8 rounded-lg bg-[#EAF2EA] border border-[#B8DFC9] flex items-center justify-center shrink-0">
                    <LayoutGrid className="w-4 h-4 text-[#236B4F]" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-black tracking-tight text-[#142820] flex items-center justify-between">
                      <span>MAIN DASHBOARD</span>
                      <span className="px-1.5 py-0.2 text-[8px] font-black rounded-sm bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]">
                        ALL PROJECTS
                      </span>
                    </div>
                    <div className="text-[10px] text-[#587568] font-medium truncate mt-0.5">
                      Centralized multi-project overview
                    </div>
                  </div>
                  {isCentralDashboard && (
                    <Check className="w-4 h-4 text-[#236B4F] shrink-0" />
                  )}
                </button>
              </div>

              {/* Master Dashboard (Platform Owner Command Center) - Rendered ONLY for Platform Owners */}
              {isPlatformOwner && (
                <div className="p-2 border-t border-slate-800 bg-slate-950">
                  <button
                    onClick={() => {
                      setIsProjectDropdownOpen(false);
                      navigate('/masterplace');
                    }}
                    className={`w-full text-left p-2.5 rounded-xl transition-all flex items-center gap-3 group ${
                      isMasterPlace
                        ? 'bg-purple-900/50 border border-purple-500/50 text-white'
                        : 'bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-200 hover:text-white'
                    }`}
                  >
                    <div className="w-8 h-8 rounded-lg bg-purple-600/30 border border-purple-500/40 flex items-center justify-center shrink-0">
                      <Shield className="w-4 h-4 text-purple-300 group-hover:text-purple-200" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-black tracking-tight text-white flex items-center gap-1.5">
                        <span>MASTERPLACE</span>
                        <span className="px-1.5 py-0.2 text-[8px] font-black rounded-sm bg-purple-500/30 text-purple-300 border border-purple-500/40">OWNER ONLY</span>
                      </div>
                      <div className="text-[10px] text-slate-400 font-medium truncate mt-0.5">
                        Platform Owner Command Center
                      </div>
                    </div>
                    {isMasterPlace && (
                      <Check className="w-4 h-4 text-purple-400 shrink-0" />
                    )}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Date Range Selector */}
        <div className="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] text-xs font-semibold text-[#2E4E40]">
          <Calendar className="w-3.5 h-3.5 text-[#587568]" />
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="bg-transparent border-none text-xs font-bold text-[#142820] focus:ring-0 cursor-pointer p-0 pr-1 outline-none"
          >
            <option value="Last 7 Days">Last 7 Days</option>
            <option value="Last 30 Days">Last 30 Days</option>
            <option value="Last 90 Days">Last 90 Days</option>
            <option value="Year to Date">Year to Date</option>
          </select>
        </div>

        {/* Full Local SEO Scan Action */}
        {isScanning ? (
          <button
            onClick={openProgressModal}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl bg-purple-50 border border-purple-300 text-xs font-bold text-purple-700 hover:bg-purple-100 transition-all shadow-xs animate-pulse"
          >
            <Activity className="w-3.5 h-3.5 text-purple-600 animate-spin" />
            <span>Scanning ({activeScan?.progress_pct || 0}%)</span>
          </button>
        ) : (
          <button
            onClick={startScan}
            disabled={!activeProject}
            title={activeProject ? "Run full intelligence scan across all 13 Local SEO modules" : "Select a project first"}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#236B4F] text-white hover:bg-[#1D5A42] text-xs font-bold transition-all shadow-xs disabled:opacity-50"
          >
            <Activity className="w-3.5 h-3.5 text-white" />
            <span className="hidden md:inline">Scan Project</span>
          </button>
        )}

        {/* Manual Data Refresh Button */}
        <button
          onClick={handleSync}
          disabled={isSyncing}
          title="Refresh Active Project Metrics"
          className="p-2 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] hover:border-[#B8DFC9] hover:bg-[#F1F7F1] text-[#2E4E40] transition-all shadow-2xs disabled:opacity-50"
        >
          <RotateCw className={`w-3.5 h-3.5 text-[#236B4F] ${isSyncing ? 'animate-spin' : ''}`} />
        </button>

        {/* AI Diagnostic CTA (Botanical Modern Gradient) */}
        <button
          onClick={onOpenAI}
          className="btn-primary-gradient flex items-center space-x-2 px-3.5 py-1.5 rounded-xl text-xs shadow-sm"
        >
          <Sparkles className="w-3.5 h-3.5 text-white animate-pulse" />
          <span className="font-bold">AI Diagnostic</span>
        </button>

        {/* MasterPlace Owner Control Center Shortcut */}
        {Boolean(user?.is_superuser || user?.platform_role) && (
          <Link
            to="/masterplace"
            title="Open Platform Owner Control Plane"
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-purple-950/80 border border-purple-500/40 text-purple-300 hover:bg-purple-900 text-xs font-bold transition-all shadow-xs"
          >
            <Shield className="w-3.5 h-3.5 text-purple-400" />
            <span className="hidden lg:inline">MasterPlace</span>
          </Link>
        )}
      </div>
    </header>
  );
};

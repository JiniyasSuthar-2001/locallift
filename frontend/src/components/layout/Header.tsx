import React, { useState } from 'react';
import {
  Building2,
  ChevronDown,
  Calendar,
  RotateCw,
  Bell,
  Sparkles,
  Bot,
  Plus
} from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { useLocation, useNavigate } from 'react-router-dom';

interface HeaderProps {
  onOpenAI: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onOpenAI }) => {
  const { projects, activeProject, setActiveProject, refreshDashboard } = useProject();
  const location = useLocation();
  const navigate = useNavigate();
  const [isProjectDropdownOpen, setIsProjectDropdownOpen] = useState(false);
  const [dateRange, setDateRange] = useState('Last 30 Days');
  const [isSyncing, setIsSyncing] = useState(false);

  // Derive page title from path
  const getPageTitle = () => {
    switch (location.pathname) {
      case '/':
        return 'Overview Dashboard';
      case '/rankings/keywords':
        return 'Keyword Rank Tracker';
      case '/rankings/grid':
        return '5x5 Geo-Grid Rankings';
      case '/audits/local':
        return 'Local SEO Signals Audit';
      case '/google/gbp':
        return 'Google Business Profile Hub';
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

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between sticky top-0 z-10 select-none">
      {/* Left: Page Title */}
      <div className="flex items-center space-x-3">
        <h1 className="text-xl font-black text-slate-900 tracking-tight">
          {getPageTitle()}
        </h1>
        {activeProject && (
          <span className="hidden lg:inline-block text-[11px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
            {activeProject.domain}
          </span>
        )}
      </div>

      {/* Right Controls: Business Selector, Date Range, Refresh, Notifications, AI */}
      <div className="flex items-center space-x-3">
        {/* Business / Client Selector */}
        <div className="relative">
          <button
            onClick={() => setIsProjectDropdownOpen(!isProjectDropdownOpen)}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 hover:border-purple-300 text-xs font-bold text-slate-800 transition-all shadow-sm"
          >
            <Building2 className="w-3.5 h-3.5 text-purple-600" />
            <span className="max-w-[140px] truncate">{activeProject ? activeProject.name : 'Select Project'}</span>
            <ChevronDown className="w-3 h-3 text-slate-400" />
          </button>

          {isProjectDropdownOpen && (
            <div className="absolute right-0 mt-2 w-64 bg-white border border-slate-200 rounded-xl shadow-xl py-2 z-50">
              <div className="px-3 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                <span>Select Project</span>
                <button
                  onClick={() => {
                    setIsProjectDropdownOpen(false);
                    navigate('/onboarding');
                  }}
                  className="text-purple-600 hover:text-purple-700 font-bold flex items-center space-x-0.5"
                >
                  <Plus className="w-3 h-3" />
                  <span>New</span>
                </button>
              </div>

              <div className="max-h-56 overflow-y-auto mt-1">
                {projects.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setActiveProject(p);
                      setIsProjectDropdownOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-slate-50 transition-colors ${
                      activeProject?.id === p.id ? 'bg-purple-50 text-purple-900 font-bold' : 'text-slate-700'
                    }`}
                  >
                    <div className="truncate pr-2">
                      <div className="truncate font-semibold">{p.name}</div>
                      <div className="text-[10px] text-slate-400 truncate">{p.domain}</div>
                    </div>
                    <span className="text-[10px] font-black px-1.5 py-0.5 rounded bg-purple-100 text-purple-800">
                      {p.health_score !== null && p.health_score !== undefined ? p.health_score : '—'}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Date Range Selector */}
        <div className="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200 text-xs font-medium text-slate-700">
          <Calendar className="w-3.5 h-3.5 text-slate-500" />
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="bg-transparent border-none text-xs font-bold text-slate-800 focus:outline-none cursor-pointer"
          >
            <option>Last 30 Days</option>
            <option>Last 7 Days</option>
            <option>Last 90 Days</option>
            <option>Year to Date</option>
          </select>
        </div>

        {/* Refresh Icon */}
        <button
          onClick={handleSync}
          disabled={isSyncing}
          className="p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition-all border border-slate-200 bg-slate-50 shadow-sm"
          title="Refresh Data"
        >
          <RotateCw className={`w-4 h-4 ${isSyncing ? 'animate-spin text-purple-600' : ''}`} />
        </button>

        {/* AI Assistant Button */}
        <button
          onClick={onOpenAI}
          className="flex items-center space-x-1.5 px-3.5 py-1.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all"
        >
          <Bot className="w-3.5 h-3.5" />
          <span className="hidden md:inline">AI Diagnostic</span>
        </button>
      </div>
    </header>
  );
};

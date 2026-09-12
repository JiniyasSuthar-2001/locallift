import React, { useState } from 'react';
import {
  Building2,
  ChevronDown,
  Calendar,
  RotateCw,
  Sparkles,
  Bot,
  Plus,
  Check
} from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { useLocation, useNavigate, Link } from 'react-router-dom';

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

  return (
    <header className="h-16 bg-white border-b border-[#DCE8DC] px-6 flex items-center justify-between sticky top-0 z-10 shadow-2xs">
      {/* Left: Page Title */}
      <div className="flex items-center space-x-3">
        <h1 className="text-xl font-black text-[#142820] tracking-tight">
          {getPageTitle()}
        </h1>
        {activeProject && (
          <span className="hidden lg:inline-block text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-[#EAF2EA] text-[#174A38] border border-[#B8DFC9]">
            {activeProject.domain}
          </span>
        )}
      </div>

      {/* Right Controls: Business Selector, Date Range, Refresh, AI Diagnostic */}
      <div className="flex items-center space-x-3">
        {/* Business / Client Selector */}
        <div className="relative">
          <button
            onClick={() => setIsProjectDropdownOpen(!isProjectDropdownOpen)}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-xl bg-[#F7FAF7] border border-[#DCE8DC] hover:border-[#B8DFC9] text-xs font-bold text-[#142820] transition-all shadow-2xs"
          >
            <Building2 className="w-3.5 h-3.5 text-[#236B4F]" />
            <span className="max-w-[140px] truncate">{activeProject ? activeProject.name : 'Select Project'}</span>
            <ChevronDown className="w-3 h-3 text-[#587568]" />
          </button>

          {isProjectDropdownOpen && (
            <div className="absolute right-0 mt-2 w-64 rounded-xl bg-white border border-[#DCE8DC] shadow-xl py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
              <div className="px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-wider text-[#587568] border-b border-[#EBF2EB]">
                Select Active Project
              </div>
              <div className="max-h-60 overflow-y-auto py-1">
                {projects.map((proj) => (
                  <button
                    key={proj.id}
                    onClick={() => {
                      setActiveProject(proj);
                      setIsProjectDropdownOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-[#F1F7F1] transition-colors ${
                      activeProject?.id === proj.id ? 'bg-[#EAF2EA] font-bold text-[#142820]' : 'text-[#2E4E40]'
                    }`}
                  >
                    <div className="truncate">
                      <div className="font-semibold truncate">{proj.name}</div>
                      <div className="text-[10px] text-[#587568] truncate">{proj.domain}</div>
                    </div>
                    {activeProject?.id === proj.id && (
                      <Check className="w-4 h-4 text-[#236B4F] shrink-0 ml-2" />
                    )}
                  </button>
                ))}
              </div>
              <div className="p-2 border-t border-[#EBF2EB]">
                <button
                  onClick={() => {
                    setIsProjectDropdownOpen(false);
                    navigate('/onboarding');
                  }}
                  className="w-full flex items-center justify-center space-x-1.5 py-1.5 rounded-lg bg-[#F1F7F1] hover:bg-[#EAF2EA] text-xs font-bold text-[#236B4F] transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add New Project</span>
                </button>
              </div>
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
      </div>
    </header>
  );
};

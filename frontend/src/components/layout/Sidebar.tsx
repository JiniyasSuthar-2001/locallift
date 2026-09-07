import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  TrendingUp,
  MapPin,
  Store,
  Globe,
  Star,
  BookOpen,
  Flame,
  CheckSquare,
  FileText,
  Bot,
  Settings,
  ChevronDown,
  Compass,
  FileCode2,
  Sparkles,
  Layers,
  Search,
  Users2,
  FolderKanban
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface NavGroup {
  title: string;
  items: {
    name: string;
    path: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: string;
  }[];
}

export const Sidebar: React.FC = () => {
  const location = useLocation();
  const { user } = useAuth();

  const navGroups: NavGroup[] = [
    {
      title: 'Overview',
      items: [
        { name: 'Dashboard', path: '/', icon: LayoutDashboard },
        { name: 'My Projects', path: '/projects', icon: FolderKanban },
        { name: 'AI Diagnostic', path: '/ai-assistant', icon: Bot, badge: 'AI' },
      ]
    },
    {
      title: 'Rankings & Visibility',
      items: [
        { name: 'Keyword Tracker', path: '/rankings/keywords', icon: TrendingUp },
        { name: '5x5 Geo-Grid Map', path: '/rankings/grid', icon: MapPin },
        { name: 'Google Business Profile', path: '/google/gbp', icon: Store },
      ]
    },
    {
      title: 'Auditing & Tools',
      items: [
        { name: 'Local Website Audit', path: '/audits/website', icon: Globe },
        { name: 'Local SEO Signals', path: '/audits/local', icon: Layers },
        { name: 'Schema Generator', path: '/seo/schema', icon: FileCode2 },
        { name: 'Content Opportunities', path: '/seo/content-gaps', icon: Sparkles },
      ]
    },
    {
      title: 'Reputation & Off-Page',
      items: [
        { name: 'Customer Reviews', path: '/local/reviews', icon: Star },
        { name: 'Citations & NAP', path: '/local/citations', icon: BookOpen },
        { name: 'Competitor Intel', path: '/local/competitors', icon: Flame },
      ]
    },
    {
      title: 'Operations & Assets',
      items: [
        { name: 'SEO Task Board', path: '/tasks', icon: CheckSquare },
        { name: 'Team Directory', path: '/team', icon: Users2 },
        { name: 'Templates Hub', path: '/templates', icon: FileCode2, badge: 'New' },
        { name: 'Executive Reports', path: '/reports', icon: FileText },
        { name: 'Settings', path: '/settings', icon: Settings },
      ]
    }
  ];


  return (
    <aside className="w-[245px] bg-white border-r border-slate-200 flex flex-col shrink-0 h-screen sticky top-0 z-20 select-none">
      {/* Brand Logo Header */}
      <div className="h-16 px-5 border-b border-slate-100 flex items-center shrink-0">
        <NavLink to="/" className="flex items-center space-x-2.5 group">
          <div className="w-8 h-8 rounded-xl gradient-brand flex items-center justify-center text-white font-black shadow-md shadow-purple-500/20 group-hover:scale-105 transition-transform">
            <Compass className="w-5 h-5 text-white stroke-[2.2]" />
          </div>
          <div className="flex flex-col">
            <span className="font-black text-lg tracking-tight text-slate-900 leading-none">
              Local<span className="bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">Scope</span>
            </span>
            <span className="text-[10px] text-slate-400 font-semibold tracking-tight mt-0.5">
              Local SEO Platform
            </span>
          </div>
        </NavLink>
      </div>

      {/* Compartmentalized Navigation Groups */}
      <nav className="flex-1 px-3 py-3 overflow-y-auto space-y-4">
        {navGroups.map((group, gIdx) => (
          <div key={gIdx} className="space-y-0.5">
            {/* Section Header */}
            <div className="px-3 pt-1 pb-1 text-[10px] font-black uppercase tracking-wider text-slate-400">
              {group.title}
            </div>

            {/* Section Links */}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive =
                  location.pathname === item.path ||
                  (item.path === '/' && location.pathname === '');

                return (
                  <NavLink
                    key={item.name}
                    to={item.path}
                    className={`flex items-center justify-between px-3 py-2 text-xs font-semibold rounded-xl transition-all duration-150 ${
                      isActive
                        ? 'bg-gradient-to-r from-purple-50 to-pink-50 text-purple-900 font-bold border border-purple-200/80 shadow-sm'
                        : 'text-slate-700 hover:text-slate-900 hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center space-x-2.5 truncate">
                      <Icon
                        className={`w-4 h-4 transition-colors shrink-0 ${
                          isActive ? 'text-purple-600 stroke-[2.4]' : 'text-slate-400'
                        }`}
                      />
                      <span className="truncate">{item.name}</span>
                    </div>

                    {item.badge && (
                      <span className="text-[9px] font-black px-1.5 py-0.2 rounded-md bg-purple-100 text-purple-800 border border-purple-200">
                        {item.badge}
                      </span>
                    )}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom User Profile */}
      <div className="p-3 border-t border-slate-100 bg-slate-50/80 shrink-0">
        <div className="flex items-center justify-between p-2 rounded-xl bg-white border border-slate-200/80 shadow-sm hover:border-purple-300 transition-all cursor-pointer">
          <div className="flex items-center space-x-2.5 truncate">
            <div className="w-8 h-8 rounded-full gradient-brand text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-sm">
              {user?.full_name ? user.full_name[0] : 'A'}
            </div>
            <div className="truncate text-left">
              <div className="text-xs font-bold text-slate-900 truncate leading-tight">
                {user?.full_name || 'Admin User'}
              </div>
              <div className="text-[10px] text-slate-500 font-medium truncate capitalize">
                {user?.role || 'Account Owner'}
              </div>
            </div>
          </div>
          <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0 ml-1" />
        </div>
      </div>
    </aside>
  );
};

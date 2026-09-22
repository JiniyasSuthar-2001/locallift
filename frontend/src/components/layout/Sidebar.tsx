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
  Users2,
  FolderKanban,
  ShieldCheck,
  PhoneCall,
  BarChart3,
  History,
  Search
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
      ]
    },
    {
      title: 'Local SEO',
      items: [
        { name: 'Local SEO Audit', path: '/audits/local', icon: ShieldCheck },
        { name: 'Google Business', path: '/google/gbp', icon: Store },
        { name: 'Reviews', path: '/local/reviews', icon: Star },
        { name: 'NAP Consistency', path: '/local/nap', icon: PhoneCall },
        { name: 'Citations', path: '/local/citations', icon: BookOpen },
        { name: 'Schema', path: '/seo/schema', icon: FileCode2 },
      ]
    },
    {
      title: 'Rankings',
      items: [
        { name: 'Keywords', path: '/rankings/keywords', icon: TrendingUp },
        { name: 'Geo-Grid', path: '/rankings/grid', icon: MapPin },
      ]
    },
    {
      title: 'Competitors',
      items: [
        { name: 'Competitor Intel', path: '/local/competitors', icon: Flame },
      ]
    },
    {
      title: 'Website',
      items: [
        { name: 'Website Audit', path: '/audits/website', icon: Globe },
        { name: 'Content Gaps', path: '/seo/content-gaps', icon: Sparkles },
      ]
    },
    {
      title: 'Operations',
      items: [
        { name: 'Tasks', path: '/tasks', icon: CheckSquare },
        { name: 'Reports', path: '/reports', icon: FileText },
        { name: 'AI Assistant', path: '/ai-assistant', icon: Bot, badge: 'AI' },
        { name: 'Templates', path: '/templates', icon: FileCode2 },
        { name: 'Team', path: '/team', icon: Users2 },
        { name: 'Integrations', path: '/connections', icon: Layers },
        { name: 'Settings', path: '/settings', icon: Settings },
      ]
    }
  ];

  return (
    <aside className="w-[245px] bg-[#FFFFFF] border-r border-[#DCE8DC] flex flex-col shrink-0 h-screen sticky top-0 z-20">
      {/* Brand Logo Header */}
      <div className="h-16 px-5 border-b border-[#EBF2EB] flex items-center shrink-0 bg-[#F7FAF7]">
        <NavLink to="/" className="flex items-center space-x-2.5 group">
          <div className="w-8 h-8 rounded-xl gradient-brand flex items-center justify-center text-white font-black shadow-md shadow-[#236B4F]/20 group-hover:scale-105 transition-transform">
            <Compass className="w-5 h-5 text-white stroke-[2.2]" />
          </div>
          <div className="flex flex-col">
            <span className="font-black text-lg tracking-tight text-[#142820] leading-none">
              Local<span className="bg-gradient-to-r from-[#236B4F] via-[#2FA878] to-[#39B982] bg-clip-text text-transparent">Lift</span>
            </span>
            <span className="text-[10px] text-[#587568] font-semibold tracking-tight mt-0.5">
              Local SEO Intelligence
            </span>
          </div>
        </NavLink>
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 px-3 py-3 overflow-y-auto space-y-4">
        {navGroups.map((group, gIdx) => (
          <div key={gIdx} className="space-y-0.5">
            {/* Section Header */}
            <div className="px-3 pt-1 pb-1 text-[10px] font-extrabold uppercase tracking-wider text-[#587568]">
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
                        ? 'bg-[#EAF2EA] text-[#142820] font-bold border border-[#B8DFC9] shadow-xs'
                        : 'text-[#2E4E40] hover:text-[#142820] hover:bg-[#F1F7F1]'
                    }`}
                  >
                    <div className="flex items-center space-x-2.5 truncate">
                      <Icon
                        className={`w-4 h-4 transition-colors shrink-0 ${
                          isActive ? 'text-[#236B4F] stroke-[2.4]' : 'text-[#587568]'
                        }`}
                      />
                      <span className="truncate">{item.name}</span>
                    </div>

                    {item.badge && (
                      <span className="text-[9px] font-black px-1.5 py-0.5 rounded-md bg-[#DDEFE5] text-[#174A38] border border-[#B8DFC9]">
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
      <div className="p-3 border-t border-[#EBF2EB] bg-[#F7FAF7] shrink-0">
        <NavLink
          to="/settings"
          className="flex items-center justify-between p-2 rounded-xl bg-white border border-[#DCE8DC] shadow-xs hover:border-[#B8DFC9] transition-all"
        >
          <div className="flex items-center space-x-2.5 truncate">
            <div className="w-8 h-8 rounded-full gradient-brand text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-xs">
              {user?.full_name ? user.full_name[0] : 'A'}
            </div>
            <div className="truncate text-left">
              <div className="text-xs font-bold text-[#142820] truncate leading-tight">
                {user?.full_name || 'Admin User'}
              </div>
              <div className="text-[10px] text-[#587568] font-medium truncate capitalize">
                {user?.role || 'Account Owner'}
              </div>
            </div>
          </div>
          <ChevronDown className="w-3.5 h-3.5 text-[#587568] shrink-0 ml-1" />
        </NavLink>
      </div>
    </aside>
  );
};

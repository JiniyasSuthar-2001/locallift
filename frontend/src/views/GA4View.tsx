import React, { useState, useEffect } from 'react';
import { Activity, Users, MousePointerClick, TrendingUp, Sparkles } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const GA4View: React.FC = () => {
  const { activeProject } = useProject();
  const [ga4Data, setGa4Data] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchGA4 = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/google/ga4/${activeProject.id}`);
      setGa4Data(resp.data);
    } catch (e) {
      console.error('Failed to load GA4 data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGA4();
  }, [activeProject?.id]);

  if (!activeProject) {
    return (
      <EmptyState
        icon={Activity}
        badge="Analytics"
        title="Select a Project"
        description="Select a business project to view Google Analytics 4 organic traffic, conversions, and landing page sessions."
      />
    );
  }

  const landingPages = ga4Data?.landing_pages || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <Activity className="w-6 h-6 text-purple-600" />
            <span>Google Analytics 4 Engagement</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Track organic user sessions, engagement rates, phone calls, and local landing page conversions for {activeProject.domain}.
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Organic Users</div>
          <div className="text-2xl font-black text-slate-900 mt-1">{ga4Data?.organic_users || 0}</div>
          <div className="text-[11px] text-purple-700 font-bold">Search visitors</div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Total Sessions</div>
          <div className="text-2xl font-black text-slate-900 mt-1">{ga4Data?.sessions || 0}</div>
          <div className="text-[11px] text-slate-500 font-medium">Browse sessions</div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Engagement Rate</div>
          <div className="text-2xl font-black text-emerald-700 mt-1">{ga4Data?.engagement_rate ? `${ga4Data.engagement_rate}%` : '0%'}</div>
          <div className="text-[11px] text-slate-500 font-medium">Active interactions</div>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Local Conversions</div>
          <div className="text-2xl font-black text-purple-700 mt-1">{ga4Data?.conversions || 0}</div>
          <div className="text-[11px] text-purple-900 font-bold">Calls & Quote requests</div>
        </div>
      </div>

      {/* Landing Pages Table */}
      <div className="card-vibrant overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-900">
            Top Landing Pages by Organic Engagement
          </h3>
          <span className="text-xs text-slate-500 font-bold">{landingPages.length} Pages</span>
        </div>

        {landingPages.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
                <tr>
                  <th className="p-3.5">Landing Page URL</th>
                  <th className="p-3.5">Organic Sessions</th>
                  <th className="p-3.5">Engagement Rate</th>
                  <th className="p-3.5">Conversions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {landingPages.map((lp: any, idx: number) => (
                  <tr key={idx} className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3.5 font-bold font-mono text-slate-900">{lp.path}</td>
                    <td className="p-3.5 font-black text-purple-700">{lp.sessions}</td>
                    <td className="p-3.5 text-slate-700 font-semibold">{lp.engagement_rate}%</td>
                    <td className="p-3.5 font-black text-emerald-700">{lp.conversions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={Activity}
            badge="GA4 Landing Pages"
            title="No GA4 Landing Pages"
            description="Connect Google Analytics 4 property to track localized landing page session analytics and conversions."
          />
        )}
      </div>
    </div>
  );
};

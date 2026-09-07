import React, { useState, useEffect } from 'react';
import { Sparkles, MapPin, Layers, Target, ArrowRight, BookOpen } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { ContentOpportunity } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const ContentGapsView: React.FC = () => {
  const { activeProject } = useProject();
  const [opportunities, setOpportunities] = useState<ContentOpportunity[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchOpportunities = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/ai/content-opportunities/${activeProject.id}`);
      setOpportunities(resp.data || []);
    } catch (e) {
      console.error('Failed to load content opportunities:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOpportunities();
  }, [activeProject?.id]);

  if (!activeProject) {
    return (
      <EmptyState
        icon={Sparkles}
        badge="Content Gaps"
        title="Select a Project"
        description="Select a business project to discover missing suburban location landing pages and high-value service topics."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
          <Sparkles className="w-6 h-6 text-purple-600" />
          <span>Content & Landing Page Opportunities</span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Recommendations for new service pages, suburban location landing pages, and commercial guide topics for {activeProject.domain}.
        </p>
      </div>

      {opportunities.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {opportunities.map((opp, idx) => (
            <div
              key={idx}
              className="card-vibrant p-5 space-y-4 flex flex-col justify-between transition-all"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-purple-700">
                    {opp.page_type}
                  </span>
                  <StatusBadge status={opp.business_value + ' Value'} variant="green" />
                </div>
                <h3 className="font-extrabold text-slate-900 text-sm">{opp.topic}</h3>
                <div className="text-xs text-slate-500 font-mono">Suggested URL: {opp.target_slug}</div>
              </div>

              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Primary Keyword:</span>
                  <span className="font-bold text-slate-900">{opp.primary_keyword}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 font-medium">Search Volume:</span>
                  <span className="font-mono text-purple-700 font-bold text-[11px]">
                    {opp.search_volume !== null && opp.search_volume !== undefined
                      ? `${opp.search_volume} searches / mo`
                      : (opp.search_volume_status || 'Unavailable — connect keyword data provider')}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500 font-medium">Search Intent:</span>
                  <span className="text-slate-700 font-semibold">{opp.search_intent}</span>
                </div>
              </div>

              <div className="space-y-1.5 text-[11px] text-slate-500">
                <span className="font-bold text-slate-700">Secondary Keywords to include:</span>
                <div className="flex flex-wrap gap-1">
                  {opp.secondary_keywords.map((sk, sIdx) => (
                    <span key={sIdx} className="px-2 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200 font-medium">
                      {sk}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Sparkles}
          badge="No Content Gaps"
          title="No Content Gaps Identified"
          description="Your current landing page architecture covers all detected local keyword clusters."
        />
      )}
    </div>
  );
};

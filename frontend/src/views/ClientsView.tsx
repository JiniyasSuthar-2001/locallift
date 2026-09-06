import React, { useState, useEffect } from 'react';
import { Users2, Plus, Building2, ExternalLink, Mail, Phone, Sparkles } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const ClientsView: React.FC = () => {
  const { projects } = useProject();
  const [clients, setClients] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchClients = async () => {
    try {
      setLoading(true);
      const resp = await api.get('/organizations/clients');
      setClients(resp.data || []);
    } catch (e) {
      console.error('Failed to load clients:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClients();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <Users2 className="w-6 h-6 text-purple-600" />
            <span>Agency & Client Portfolio</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Manage multiple client accounts, assign team permissions, and oversee multi-location local health scores.
          </p>
        </div>
      </div>

      {/* Clients Grid */}
      {clients.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {clients.map((c) => (
            <div
              key={c.id}
              className="card-vibrant p-5 space-y-4 transition-all"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-extrabold text-slate-900 text-base">{c.name}</h3>
                  <div className="text-xs text-slate-500">{c.projects_count} Managed Project(s)</div>
                </div>
                <span className="px-2 py-0.5 rounded bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold">
                  Active Client
                </span>
              </div>

              <div className="space-y-1.5 text-xs text-slate-700">
                {c.contact_email && (
                  <div className="flex items-center space-x-2">
                    <Mail className="w-3.5 h-3.5 text-slate-400" />
                    <span className="font-medium">{c.contact_email}</span>
                  </div>
                )}
                {c.phone && (
                  <div className="flex items-center space-x-2">
                    <Phone className="w-3.5 h-3.5 text-slate-400" />
                    <span className="font-mono font-medium">{c.phone}</span>
                  </div>
                )}
              </div>

              {c.projects && c.projects.length > 0 && (
                <div className="pt-2 border-t border-slate-100 space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Associated SEO Projects
                  </span>
                  {c.projects.map((p: any) => (
                    <div
                      key={p.id}
                      className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs"
                    >
                      <span className="text-slate-900 font-bold">{p.name}</span>
                      <span className="font-black text-purple-700">{p.health_score} / 100</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Users2}
          badge="Agency Roster"
          title="No Clients Created"
          description="Create client accounts to manage permissions and group multi-location business projects."
        />
      )}
    </div>
  );
};

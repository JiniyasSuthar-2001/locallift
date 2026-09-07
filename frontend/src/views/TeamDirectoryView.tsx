import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Users2,
  Mail,
  Shield,
  FolderKanban,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
  Search
} from 'lucide-react';
import api from '../api/client';
import { getErrorMessage } from '../utils/error';
import { TeamDirectoryMember } from '../types';

export const TeamDirectoryView: React.FC = () => {
  const { memberId } = useParams<{ memberId?: string }>();
  const [members, setMembers] = useState<TeamDirectoryMember[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchDirectory = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.get<TeamDirectoryMember[]>('/team');
      setMembers(res.data);
    } catch (err: any) {
      setErrorMsg(getErrorMessage(err, 'Failed to load team directory.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDirectory();
  }, []);

  const filteredMembers = members.filter((m) => {
    return (
      m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.global_role.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  const selectedMember = memberId
    ? members.find((m) => String(m.user_id) === String(memberId))
    : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center p-16 text-xs text-slate-500 space-x-2">
        <RefreshCw className="w-4 h-4 animate-spin text-purple-600" />
        <span>Loading team directory...</span>
      </div>
    );
  }

  return (
    <div className="max-w-5xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2.5">
          <Users2 className="w-6 h-6 text-purple-600" />
          <span>Team Directory & Project Assignments</span>
        </h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Centralized directory of all organization members, project collaborators, and their active project permissions.
        </p>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-2 text-xs text-rose-700">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span className="flex-1">{errorMsg}</span>
        </div>
      )}

      {/* Search Bar */}
      <div className="bg-white p-3.5 border border-slate-200/80 rounded-2xl shadow-xs max-w-md">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search collaborators by name or email..."
            className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
          />
        </div>
      </div>

      {/* Directory Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {filteredMembers.map((member) => (
          <div
            key={member.user_id}
            className="card-vibrant p-5 border border-slate-200/80 rounded-2xl bg-white shadow-xs space-y-4"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-purple-600 to-indigo-600 text-white font-bold text-sm flex items-center justify-center shadow-xs">
                  {member.name[0]}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-sm font-black text-slate-900">{member.name}</h3>
                    <span className="text-[10px] font-bold px-2 py-0.2 rounded-md bg-purple-50 text-purple-700 border border-purple-200">
                      {member.global_role}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">{member.email}</div>
                </div>
              </div>

              <span className="text-[11px] font-bold text-slate-400">
                {member.project_count} Project{member.project_count === 1 ? '' : 's'}
              </span>
            </div>

            {/* Assigned Projects */}
            <div className="pt-3 border-t border-slate-100 space-y-2">
              <span className="text-[11px] font-bold text-slate-700 block">Assigned Projects & Permissions:</span>
              {member.projects.length === 0 ? (
                <div className="text-[11px] text-slate-400 italic">No specific project assignments yet.</div>
              ) : (
                <div className="space-y-2">
                  {member.projects.map((p) => (
                    <div
                      key={p.id}
                      className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/60 text-xs flex flex-col space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <Link
                          to={`/projects/${p.id}`}
                          className="font-bold text-slate-800 hover:text-purple-600 flex items-center space-x-1"
                        >
                          <span>{p.name}</span>
                          <ExternalLink className="w-3 h-3 text-slate-400" />
                        </Link>
                        <span className="text-[10px] font-bold px-2 py-0.2 rounded bg-purple-100 text-purple-800">
                          {p.role}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {p.permissions.slice(0, 4).map((perm) => (
                          <span
                            key={perm}
                            className="text-[9px] font-medium px-1.5 py-0.2 rounded bg-white border border-slate-200 text-slate-600"
                          >
                            {perm.replace('_', ' ')}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

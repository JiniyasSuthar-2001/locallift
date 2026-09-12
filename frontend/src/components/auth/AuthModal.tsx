import React, { useState } from 'react';
import { Globe, Lock, Mail, User, Building, ArrowRight, Sparkles, ShieldCheck } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { getErrorMessage } from '../../utils/error';

export const AuthModal: React.FC = () => {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [orgName, setOrgName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        if (!email.trim() || !password.trim() || !fullName.trim()) {
          setError('Please fill out all required fields.');
          setLoading(false);
          return;
        }
        await register(email.trim(), password.trim(), fullName.trim(), orgName.trim());
      } else {
        if (!email.trim() || !password.trim()) {
          setError('Please enter your email and password.');
          setLoading(false);
          return;
        }
        await login(email.trim(), password.trim());
      }
    } catch (err: any) {
      setError(getErrorMessage(err, 'Authentication error. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-md p-4">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-2xl border border-slate-100 overflow-hidden animate-in fade-in zoom-in duration-200">
        {/* Header */}
        <div className="gradient-primary p-6 text-white text-center space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-white/15 backdrop-blur-sm mx-auto flex items-center justify-center border border-white/20 shadow-inner">
            <Globe className="w-6 h-6 text-white" />
          </div>
          <h2 className="text-xl font-black tracking-tight">LocalLift</h2>
          <p className="text-xs text-purple-100 font-medium">
            Local SEO Automation & Intelligence Platform
          </p>
        </div>

        {/* Form */}
        <div className="p-6 sm:p-8 space-y-6">
          <div className="flex border-b border-slate-100 pb-2">
            <button
              type="button"
              onClick={() => { setIsRegister(false); setError(null); }}
              className={`flex-1 text-center py-2 text-xs font-bold transition-colors ${
                !isRegister ? 'text-purple-700 border-b-2 border-purple-600 -mb-2.5' : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => { setIsRegister(true); setError(null); }}
              className={`flex-1 text-center py-2 text-xs font-bold transition-colors ${
                isRegister ? 'text-purple-700 border-b-2 border-purple-600 -mb-2.5' : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              Create Account
            </button>
          </div>

          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs font-semibold flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-rose-500 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <>
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-700 uppercase tracking-wider block">
                    Full Name
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                    <input
                      type="text"
                      required
                      placeholder="Jane Doe"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2.5 text-xs text-slate-900 font-medium focus:outline-none focus:border-purple-500 focus:bg-white transition-all"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-slate-700 uppercase tracking-wider block">
                    Agency or Business Name
                  </label>
                  <div className="relative">
                    <Building className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                    <input
                      type="text"
                      placeholder="e.g. Apex Local Growth"
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2.5 text-xs text-slate-900 font-medium focus:outline-none focus:border-purple-500 focus:bg-white transition-all"
                    />
                  </div>
                </div>
              </>
            )}

            <div className="space-y-1">
              <label className="text-[11px] font-bold text-slate-700 uppercase tracking-wider block">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="email"
                  required
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2.5 text-xs text-slate-900 font-medium focus:outline-none focus:border-purple-500 focus:bg-white transition-all"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-bold text-slate-700 uppercase tracking-wider block">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2.5 text-xs text-slate-900 font-medium focus:outline-none focus:border-purple-500 focus:bg-white transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 btn-vibrant-primary rounded-xl text-xs font-extrabold flex items-center justify-center space-x-2 shadow-lg shadow-purple-500/20 transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50"
            >
              {loading ? (
                <Sparkles className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <span>{isRegister ? 'Register & Start Tracking' : 'Sign In to Dashboard'}</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

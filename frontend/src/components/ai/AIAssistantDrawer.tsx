import React, { useState } from 'react';
import {
  X,
  Bot,
  Send,
  Sparkles,
  HelpCircle,
  ArrowRight,
  ShieldAlert,
  CheckCircle2,
  TrendingDown
} from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { AIAnalysisResponse } from '../../types';
import { StatusBadge } from '../ui/StatusBadge';
import api from '../../api/client';

interface AIAssistantDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AIAssistantDrawer: React.FC<AIAssistantDrawerProps> = ({ isOpen, onClose }) => {
  const { activeProject } = useProject();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<AIAnalysisResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const quickPrompts = [
    'Why did my local ranking drop in the main metro area?',
    'What schema markup is missing on our service pages?',
    'How do I improve my Google Maps Local Pack share?',
    'Analyze our recent Google customer review sentiments'
  ];

  const handleDiagnose = async (customQuery?: string) => {
    const q = customQuery || query;
    if (!activeProject || !q.trim()) return;

    try {
      setLoading(true);
      setErrorMessage(null);
      setQuery(q);
      const resp = await api.post('/ai/diagnostic', {
        project_id: activeProject.id,
        query: q
      });
      setAnalysis(resp.data);
    } catch (err: any) {
      console.error('AI Diagnostic failed:', err);
      const detail = err?.response?.data?.detail || err?.message || 'AI diagnostic analysis failed.';
      setErrorMessage(detail);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden select-none">
      <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity" onClick={onClose} />

      <div className="fixed inset-y-0 right-0 pl-10 max-w-full flex">
        <div className="w-screen max-w-md bg-white border-l border-slate-200 flex flex-col shadow-2xl">
          {/* Drawer Header */}
          <div className="p-5 border-b border-slate-100 flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-xl gradient-brand flex items-center justify-center text-white shadow-sm">
                <Bot className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-black text-sm text-slate-900">AI SEO Diagnostic Studio</h3>
                <p className="text-[11px] text-slate-500 font-medium">Root-cause SEO intelligence</p>
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {/* Quick Prompts */}
            <div className="space-y-2">
              <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">
                Diagnostic Quick-Prompts
              </span>
              <div className="space-y-1.5">
                {quickPrompts.map((p, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleDiagnose(p)}
                    className="w-full text-left p-2.5 rounded-xl bg-slate-50 hover:bg-purple-50 hover:border-purple-200 border border-slate-200 text-xs font-semibold text-slate-700 hover:text-purple-900 transition-colors flex items-center justify-between group"
                  >
                    <span className="truncate pr-2">{p}</span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-purple-600 shrink-0" />
                  </button>
                ))}
              </div>
            </div>

            {errorMessage && (
              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start space-x-2.5">
                <div className="font-bold shrink-0">⚠️ AI Notice:</div>
                <div>
                  <div className="font-semibold">{errorMessage}</div>
                  {errorMessage.includes('AI_NOT_CONFIGURED') && (
                    <div className="mt-1 text-slate-600 text-[11px]">
                      Configure <code className="bg-amber-100 px-1 py-0.5 rounded font-mono">AI_API_KEY</code> in your backend environment to activate AI diagnostics.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Loading State */}
            {loading && (
              <div className="p-8 text-center space-y-3 bg-purple-50/50 rounded-2xl border border-purple-100">
                <Sparkles className="w-7 h-7 text-purple-600 mx-auto animate-spin" />
                <p className="text-xs text-purple-950 font-bold">
                  Synthesizing rank shifts, GBP changes, reviews, crawl signals, and NAP citations...
                </p>
              </div>
            )}

            {/* Analysis Result Output */}
            {analysis && !loading && (
              <div className="space-y-5 animate-fade-in">
                {/* Summary Box */}
                <div className="p-4 rounded-2xl bg-purple-50 border border-purple-200 space-y-1.5">
                  <span className="text-[10px] font-black text-purple-900 uppercase tracking-wider flex items-center space-x-1">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Executive Summary</span>
                  </span>
                  <p className="text-xs text-slate-900 leading-relaxed font-semibold">
                    {analysis.summary}
                  </p>
                </div>

                {/* Likely Causes */}
                <div className="space-y-2.5">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-wider">
                    Identified Causes
                  </span>
                  <div className="space-y-2">
                    {analysis.likely_causes.map((cause, cIdx) => (
                      <div
                        key={cIdx}
                        className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-slate-900">{cause.category}</span>
                          <StatusBadge status={cause.confidence} />
                        </div>
                        <p className="text-[11px] text-slate-600 leading-relaxed font-medium">
                          {cause.description}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Recommended Actions */}
                <div className="space-y-2.5">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-wider">
                    Recommended Action Plan
                  </span>
                  <div className="space-y-2">
                    {analysis.recommended_actions.map((act, aIdx) => (
                      <div
                        key={aIdx}
                        className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-slate-800 font-medium flex items-start space-x-2"
                      >
                        <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" />
                        <span>{act}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Drawer Footer Input */}
          <div className="p-4 border-t border-slate-100 bg-slate-50">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleDiagnose();
              }}
              className="flex items-center space-x-2"
            >
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask specific root-cause question..."
                className="flex-1 bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500 font-medium"
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="p-2.5 btn-vibrant-primary rounded-xl text-white shadow-md disabled:opacity-50"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

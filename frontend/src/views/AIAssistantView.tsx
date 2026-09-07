import React, { useState } from 'react';
import { Bot, Send, Sparkles, CheckCircle2, ArrowRight } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { AIAnalysisResponse } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const AIAssistantView: React.FC = () => {
  const { activeProject } = useProject();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<AIAnalysisResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const quickPrompts = [
    'Why did my local ranking drop in the primary metro area?',
    'How do I improve my Google Maps Local Pack share?',
    'What schema markup is missing on our service landing pages?',
    'Analyze our recent Google customer review sentiments'
  ];

  const handleAsk = async (question: string) => {
    if (!activeProject || !question.trim()) return;
    try {
      setLoading(true);
      setErrorMessage(null);
      setQuery(question);
      const resp = await api.post('/ai/diagnostic', {
        project_id: activeProject.id,
        query: question
      });
      setAnalysis(resp.data);
    } catch (e: any) {
      console.error('AI Diagnostic failed:', e);
      const detail = e?.response?.data?.detail || e?.message || 'AI diagnostic analysis failed.';
      setErrorMessage(detail);
    } finally {
      setLoading(false);
    }
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={Bot}
        badge="AI Diagnostic"
        title="Select a Project"
        description="Select a business project to run AI root-cause diagnostics on keyword rank movements and technical signals."
      />
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
          <Bot className="w-6 h-6 text-purple-600" />
          <span>AI SEO Assistant & Diagnostic Studio</span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Root-cause SEO intelligence synthesizing keyword rank movements, GBP changes, customer reviews, and technical health signals for {activeProject.domain}.
        </p>
      </div>

      {errorMessage && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start space-x-3">
          <div className="font-bold shrink-0">⚠️ AI Configuration Notice:</div>
          <div>
            <div className="font-semibold">{errorMessage}</div>
            {errorMessage.includes('AI_NOT_CONFIGURED') && (
              <div className="mt-1 text-slate-600">
                To activate AI diagnostics, configure <code className="bg-amber-100 px-1.5 py-0.5 rounded font-mono text-[11px]">AI_API_KEY</code> in your backend environment variables or <code className="bg-amber-100 px-1.5 py-0.5 rounded font-mono text-[11px]">.env</code> file.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Query Bar */}
      <div className="card-vibrant p-5 space-y-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk(query);
          }}
          className="flex items-center space-x-2"
        >
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask AI about local rank shifts, competitor gaps, or schema diagnostics..."
            className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500 font-medium"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="px-5 py-3 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all flex items-center space-x-1.5"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Analyze</span>
          </button>
        </form>

        {/* Quick Prompts */}
        <div className="space-y-1.5">
          <span className="text-[10px] font-black text-slate-500 uppercase tracking-wider">
            Quick Diagnostic Questions
          </span>
          <div className="flex flex-wrap gap-2">
            {quickPrompts.map((p, idx) => (
              <button
                key={idx}
                onClick={() => handleAsk(p)}
                className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-purple-50 hover:text-purple-900 hover:border-purple-200 border border-transparent text-slate-700 text-xs font-semibold transition-colors"
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="card-vibrant p-10 text-center space-y-3">
          <Sparkles className="w-8 h-8 mx-auto text-purple-600 animate-spin" />
          <p className="text-xs text-slate-600 font-bold">
            Synthesizing rank shifts, GBP changes, reviews, crawl signals, and NAP citations...
          </p>
        </div>
      )}

      {/* Analysis Output */}
      {analysis && !loading && (
        <div className="card-vibrant p-6 space-y-6">
          <div className="bg-purple-50 border border-purple-200 p-4 rounded-xl space-y-1">
            <span className="text-[10px] font-black text-purple-900 uppercase tracking-wider">
              Diagnostic Summary
            </span>
            <p className="text-xs text-slate-900 leading-relaxed font-semibold">
              {analysis.summary}
            </p>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-black text-slate-900 uppercase tracking-wider">
              Identified Causes (Confidence Level)
            </h3>
            <div className="space-y-2.5">
              {analysis.likely_causes.map((cause, cIdx) => (
                <div key={cIdx} className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/50 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">{cause.category}</span>
                    <StatusBadge status={cause.confidence} />
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed font-medium">{cause.description}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-black text-slate-900 uppercase tracking-wider">
              Recommended Action Plan
            </h3>
            <div className="space-y-2">
              {analysis.recommended_actions.map((act, aIdx) => (
                <div key={aIdx} className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-slate-800 font-medium flex items-start space-x-2.5">
                  <ArrowRight className="w-4 h-4 text-emerald-700 mt-0.5 shrink-0" />
                  <span>{act}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

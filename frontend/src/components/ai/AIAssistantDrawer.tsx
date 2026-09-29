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
import { Drawer } from '../ui/Drawer';
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

  const footerContent = (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        handleDiagnose();
      }}
      className="flex items-center space-x-2 w-full"
    >
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Ask specific root-cause question..."
        className="flex-1 bg-white border border-[#DCE8DC] rounded-xl px-3 py-2 text-xs text-[#142820] placeholder-[#587568] focus:outline-none focus:border-[#236B4F] font-medium shadow-2xs"
      />
      <button
        type="submit"
        disabled={loading || !query.trim()}
        className="p-2.5 btn-primary-gradient rounded-xl text-white shadow-md disabled:opacity-50 cursor-pointer"
        title="Send prompt"
      >
        <Send className="w-4 h-4" />
      </button>
    </form>
  );

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="md"
      icon={<Bot className="w-5 h-5 text-[#236B4F]" />}
      title="AI SEO Diagnostic Studio"
      subtitle="Root-cause SEO intelligence"
      footer={footerContent}
      bodyClassName="p-5 space-y-5"
    >
      {/* Quick Prompts */}
      <div className="space-y-2">
        <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">
          Diagnostic Quick-Prompts
        </span>
        <div className="space-y-1.5">
          {quickPrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handleDiagnose(p)}
              className="w-full text-left p-2.5 rounded-xl bg-[#F7FAF7] hover:bg-[#EAF2EA] hover:border-[#B8DFC9] border border-[#DCE8DC] text-xs font-semibold text-[#2E4E40] hover:text-[#142820] transition-colors flex items-center justify-between group cursor-pointer"
            >
              <span className="truncate pr-2">{p}</span>
              <ArrowRight className="w-3.5 h-3.5 text-[#587568] group-hover:text-[#236B4F] shrink-0" />
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
                Configure <code className="bg-amber-100 px-1 py-0.5 rounded font-mono">AI_API_KEY</code> in your backend environment to activate AI diagnostics (Supported AI Provider: Gemini).
              </div>
            )}
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="p-8 text-center space-y-3 bg-[#F1F7F1] rounded-2xl border border-[#B8DFC9]">
          <Sparkles className="w-7 h-7 text-[#236B4F] mx-auto animate-spin" />
          <p className="text-xs text-[#174A38] font-bold">
            Synthesizing rank shifts, GBP changes, reviews, crawl signals, and NAP citations...
          </p>
        </div>
      )}

      {/* Analysis Result Output */}
      {analysis && !loading && (
        <div className="space-y-5 animate-in fade-in duration-200">
          {/* Summary Box */}
          <div className="p-4 rounded-2xl bg-[#EAF2EA] border border-[#B8DFC9] space-y-1.5">
            <span className="text-[10px] font-black text-[#174A38] uppercase tracking-wider flex items-center space-x-1">
              <Sparkles className="w-3.5 h-3.5 text-[#236B4F]" />
              <span>Executive Summary</span>
            </span>
            <p className="text-xs text-[#142820] leading-relaxed font-semibold">
              {analysis.summary}
            </p>
          </div>

          {/* Likely Causes */}
          <div className="space-y-2.5">
            <span className="text-[10px] font-black text-[#587568] uppercase tracking-wider">
              Identified Causes
            </span>
            <div className="space-y-2">
              {analysis.likely_causes.map((cause, cIdx) => (
                <div
                  key={cIdx}
                  className="p-3.5 rounded-xl bg-white border border-[#DCE8DC] shadow-2xs space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#142820]">{cause.category}</span>
                    <StatusBadge status={cause.confidence} />
                  </div>
                  <p className="text-[11px] text-[#2E4E40] leading-relaxed font-medium">
                    {cause.description}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Recommended Actions */}
          <div className="space-y-2.5">
            <span className="text-[10px] font-black text-[#587568] uppercase tracking-wider">
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
    </Drawer>
  );
};

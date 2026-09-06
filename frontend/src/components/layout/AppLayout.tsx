import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { RightInsightsPanel } from './RightInsightsPanel';
import { AIAssistantDrawer } from '../ai/AIAssistantDrawer';

export const AppLayout: React.FC = () => {
  const [isAIDrawerOpen, setIsAIDrawerOpen] = useState(false);
  const location = useLocation();

  // Show Right Insights Panel primarily on Dashboard/Overview or everywhere
  const showRightPanel = location.pathname === '/' || location.pathname === '';

  return (
    <div className="flex h-screen bg-[#F8FAFC] text-slate-900 overflow-hidden font-sans">
      {/* 1. Left Vertical Navigation (230px) */}
      <Sidebar />

      {/* 2. Main Central Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header onOpenAI={() => setIsAIDrawerOpen(true)} />

        <main className="flex-1 overflow-y-auto p-5 md:p-6 bg-[#F8FAFC]">
          <div className="max-w-[1400px] mx-auto space-y-6">
            <Outlet />
          </div>
        </main>
      </div>

      {/* 3. Dedicated Right Insights Panel (300-320px) */}
      {showRightPanel && <RightInsightsPanel />}

      {/* Floating AI Diagnostic Assistant Drawer */}
      <AIAssistantDrawer
        isOpen={isAIDrawerOpen}
        onClose={() => setIsAIDrawerOpen(false)}
      />
    </div>
  );
};

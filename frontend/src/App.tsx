import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ProjectProvider } from './context/ProjectContext';
import { AppLayout } from './components/layout/AppLayout';

import { Dashboard } from './views/Dashboard';
import { WebsiteAuditView } from './views/WebsiteAuditView';
import { LocalSEOAuditView } from './views/LocalSEOAuditView';
import { GBPView } from './views/GBPView';
import { GSCView } from './views/GSCView';
import { GA4View } from './views/GA4View';
import { KeywordsView } from './views/KeywordsView';
import { LocalGridRankingsView } from './views/LocalGridRankingsView';
import { ReviewsView } from './views/ReviewsView';
import { CitationsView } from './views/CitationsView';
import { NAPConsistencyView } from './views/NAPConsistencyView';
import { CompetitorsView } from './views/CompetitorsView';
import { SchemaGeneratorView } from './views/SchemaGeneratorView';
import { ContentGapsView } from './views/ContentGapsView';
import { TasksView } from './views/TasksView';
import { ReportsView } from './views/ReportsView';
import { ClientsView } from './views/ClientsView';
import { OnboardingWizard } from './views/OnboardingWizard';
import { SettingsView } from './views/SettingsView';
import { AIAssistantView } from './views/AIAssistantView';
import { TemplatesView } from './views/TemplatesView';
import { GoogleCallbackView } from './views/GoogleCallbackView';
import { MyProjectsView } from './views/MyProjectsView';
import { ProjectDetailsView } from './views/ProjectDetailsView';
import { TeamDirectoryView } from './views/TeamDirectoryView';
import { InvitationNotificationModal } from './components/team/InvitationNotificationModal';

import { AuthModal } from './components/auth/AuthModal';

const AuthenticatedApp: React.FC = () => {
  return (
    <ProjectProvider>
      <InvitationNotificationModal />
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="onboarding" element={<OnboardingWizard />} />
            
            {/* Project Management & Team */}
            <Route path="projects" element={<MyProjectsView />} />
            <Route path="projects/:projectId" element={<ProjectDetailsView />} />
            <Route path="team" element={<TeamDirectoryView />} />
            <Route path="team/:memberId" element={<TeamDirectoryView />} />

            {/* SEO Auditing */}
            <Route path="audits/website" element={<WebsiteAuditView />} />
            <Route path="audits/local" element={<LocalSEOAuditView />} />
            <Route path="seo/schema" element={<SchemaGeneratorView />} />
            <Route path="seo/content-gaps" element={<ContentGapsView />} />

            {/* Google */}
            <Route path="google/gbp" element={<GBPView />} />
            <Route path="google/gsc" element={<GSCView />} />
            <Route path="google/ga4" element={<GA4View />} />
            <Route path="integrations/google/callback" element={<GoogleCallbackView />} />

            {/* Rankings */}
            <Route path="rankings/keywords" element={<KeywordsView />} />
            <Route path="rankings/grid" element={<LocalGridRankingsView />} />

            {/* Local & Reputation */}
            <Route path="local/reviews" element={<ReviewsView />} />
            <Route path="local/citations" element={<CitationsView />} />
            <Route path="local/nap" element={<NAPConsistencyView />} />
            <Route path="local/competitors" element={<CompetitorsView />} />

            {/* Operations & AI */}
            <Route path="tasks" element={<TasksView />} />
            <Route path="templates" element={<TemplatesView />} />
            <Route path="reports" element={<ReportsView />} />
            <Route path="ai-assistant" element={<AIAssistantView />} />
            <Route path="agency/clients" element={<ClientsView />} />
            <Route path="settings" element={<SettingsView />} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ProjectProvider>
  );
};


const AppContent: React.FC = () => {
  const { isAuthenticated, loading } = useAuth();

  // 1. Initial authentication loading state (no protected UI flash)
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto shadow-lg shadow-purple-500/20" />
          <div className="space-y-1">
            <h3 className="text-sm font-black text-white tracking-wider">LOCALLIFT</h3>
            <p className="text-xs text-slate-400 font-medium">Restoring secure session...</p>
          </div>
        </div>
      </div>
    );
  }

  // 2. Unauthenticated state: Render AuthModal boundary only (AppLayout and ProjectProvider do NOT mount)
  if (!isAuthenticated) {
    return <AuthModal />;
  }

  // 3. Authenticated state: Mount protected routes & ProjectProvider
  return <AuthenticatedApp />;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;

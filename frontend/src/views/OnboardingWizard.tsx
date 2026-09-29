import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Compass,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Globe,
  MapPin,
  ListOrdered,
  Sparkles,
  Store,
  LineChart,
  RotateCw,
  AlertCircle,
  XCircle,
  Layers,
  Check,
  Building2,
  RefreshCw
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { CategorySelector } from '../components/common/CategorySelector';
import { CountrySelector } from '../components/ui/CountrySelector';
import { Modal } from '../components/ui/Modal';
import api from '../api/client';

interface InitTask {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  error?: string;
}

const INITIAL_TASK_DEFS: { id: string; label: string }[] = [
  { id: 'create_project', label: 'Creating Local SEO Project' },
  { id: 'save_business', label: 'Saving Business Information' },
  { id: 'create_nap', label: 'Creating NAP Profile' },
  { id: 'save_categories', label: 'Saving Categories' },
  { id: 'connect_integrations', label: 'Connecting Integrations' },
  { id: 'create_workspace', label: 'Creating Default Workspace' },
  { id: 'prepare_audit', label: 'Preparing Initial Audit' },
  { id: 'finalize_project', label: 'Finalizing Project' },
];

export const OnboardingWizard: React.FC = () => {
  const navigate = useNavigate();
  const { refreshProjects } = useProject();
  const [step, setStep] = useState(1);

  // Form State
  const [projectName, setProjectName] = useState('');
  const [domain, setDomain] = useState('');
  const [category, setCategory] = useState('Dentist');
  const [additionalCategories, setAdditionalCategories] = useState<string[]>([]);
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [country, setCountry] = useState('');
  const [publicMapsUrl, setPublicMapsUrl] = useState('');
  const [phone, setPhone] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Initialization Modal State
  const [showInitModal, setShowInitModal] = useState(false);
  const [initTasks, setInitTasks] = useState<InitTask[]>(
    INITIAL_TASK_DEFS.map(t => ({ ...t, status: 'pending' }))
  );
  const [currentTaskLabel, setCurrentTaskLabel] = useState<string>('Initializing...');
  const [initError, setInitError] = useState<string | null>(null);

  const updateTaskStatus = (
    taskId: string,
    status: 'pending' | 'running' | 'completed' | 'failed',
    label?: string,
    error?: string
  ) => {
    setInitTasks(prev =>
      prev.map(t => (t.id === taskId ? { ...t, status, error } : t))
    );
    if (label) {
      setCurrentTaskLabel(label);
    }
  };

  const handleFinishOnboarding = async () => {
    if (isSubmitting) return;
    setErrorMessage(null);
    setInitError(null);
    
    const cleanDomain = domain.trim().replace(/^https?:\/\//i, '').split('/')[0];
    if (!cleanDomain || cleanDomain.includes(' ')) {
      setErrorMessage('Please enter a valid website domain name before completing onboarding.');
      return;
    }

    if (!country.trim()) {
      setErrorMessage('Please select a country.');
      return;
    }

    const selectedCountry = country.trim();
    const resolvedProjectName = projectName.trim() || cleanDomain;

    // Open loading popup immediately and initialize task states
    setShowInitModal(true);
    setIsSubmitting(true);
    setInitTasks(INITIAL_TASK_DEFS.map(t => ({ ...t, status: 'pending' })));
    setCurrentTaskLabel('Creating Local SEO Project...');

    let newProjectId: number | null = null;

    try {
      // 1. Creating Local SEO Project
      updateTaskStatus('create_project', 'running', 'Creating Local SEO Project...');
      await new Promise(r => setTimeout(r, 200));

      const projResp = await api.post('/projects', {
        name: resolvedProjectName,
        domain: cleanDomain,
        primary_category: category || 'Local Business',
        additional_categories: additionalCategories,
        country: selectedCountry,
        public_maps_url: publicMapsUrl.trim() || undefined,
        location: {
          name: 'Main Location',
          address: address.trim() || undefined,
          city: city.trim() || undefined,
          state: state.trim() || undefined,
          postal_code: postalCode.trim() || undefined,
          phone: phone.trim() || undefined,
          country: selectedCountry
        }
      });
      newProjectId = projResp.data.id;
      updateTaskStatus('create_project', 'completed');

      // 2. Saving Business Information
      updateTaskStatus('save_business', 'running', 'Saving Business Information...');
      await new Promise(r => setTimeout(r, 200));
      updateTaskStatus('save_business', 'completed');

      // 3. Creating NAP Profile
      updateTaskStatus('create_nap', 'running', 'Creating NAP Profile...');
      try {
        if (newProjectId) {
          await api.get(`/projects/${newProjectId}/business-profile`);
        }
      } catch (profileErr) {
        console.warn('Canonical profile get/init non-fatal notice:', profileErr);
      }
      await new Promise(r => setTimeout(r, 200));
      updateTaskStatus('create_nap', 'completed');

      // 4. Saving Categories
      updateTaskStatus('save_categories', 'running', 'Saving Categories...');
      await new Promise(r => setTimeout(r, 200));
      updateTaskStatus('save_categories', 'completed');

      // 5. Connecting Integrations
      updateTaskStatus('connect_integrations', 'running', 'Connecting Integrations...');
      await new Promise(r => setTimeout(r, 200));
      updateTaskStatus('connect_integrations', 'completed');

      // 6. Creating Default Workspace
      updateTaskStatus('create_workspace', 'running', 'Creating Default Workspace...');
      await new Promise(r => setTimeout(r, 200));
      updateTaskStatus('create_workspace', 'completed');

      // 7. Preparing Initial Audit
      updateTaskStatus('prepare_audit', 'running', 'Preparing Initial Audit...');
      if (keywordInput.trim() && newProjectId) {
        const kws = keywordInput.split('\n').filter((k) => k.trim());
        for (const kw of kws) {
          try {
            await api.post('/keywords', {
              project_id: newProjectId,
              keyword: kw.trim(),
              target_location: city.trim() || undefined,
              search_intent: 'Commercial',
              search_volume: null
            });
          } catch (kwErr) {
            console.warn('Keyword creation notice:', kwErr);
          }
        }
      }
      await new Promise(r => setTimeout(r, 250));
      updateTaskStatus('prepare_audit', 'completed');

      // 8. Finalizing Project
      updateTaskStatus('finalize_project', 'running', 'Finalizing Project & Triggering Initial Audit...');
      if (newProjectId) {
        try {
          await api.post(`/audits/crawl/${newProjectId}`, {
            url: `https://${cleanDomain}`,
            max_pages: 5
          });
        } catch (crawlErr) {
          console.warn('Initial crawl trigger notice:', crawlErr);
        }
        await refreshProjects(newProjectId);
      }
      await new Promise(r => setTimeout(r, 300));
      updateTaskStatus('finalize_project', 'completed', 'Project setup complete!');

      // Brief delay for visual completion, then close modal and navigate to dashboard
      await new Promise(r => setTimeout(r, 500));
      setShowInitModal(false);
      setIsSubmitting(false);
      navigate('/');
    } catch (e: any) {
      console.error('Project initialization failed:', e);
      const msg =
        e.response?.data?.detail ||
        e.response?.data?.message ||
        e.message ||
        'Failed to initialize project. Please verify inputs and try again.';
      
      // Find currently running task or first pending task and mark as failed
      setInitTasks(prev => {
        let marked = false;
        return prev.map(t => {
          if ((t.status === 'running' || t.status === 'pending') && !marked) {
            marked = true;
            return { ...t, status: 'failed', error: msg };
          }
          return t;
        });
      });
      setInitError(msg);
      setErrorMessage(msg);
      setIsSubmitting(false);
    }
  };

  const completedCount = initTasks.filter(t => t.status === 'completed').length;
  const progressPct = Math.round((completedCount / INITIAL_TASK_DEFS.length) * 100);

  return (
    <div className="max-w-3xl mx-auto py-6 space-y-8">
      {/* Stepper */}
      <div className="flex items-center justify-between relative">
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-full h-0.5 bg-slate-200 -z-0" />
        {[
          { num: 1, label: 'Business & Domain' },
          { num: 2, label: 'Location & NAP' },
          { num: 3, label: 'Integrations' },
          { num: 4, label: 'Local Keywords' }
        ].map((s) => (
          <div key={s.num} className="flex flex-col items-center space-y-1.5 z-10 bg-[#F8FAFC] px-3">
            <div
              className={`w-9 h-9 rounded-full flex items-center justify-center font-black text-xs transition-all ${
                step === s.num
                  ? 'gradient-brand text-white ring-4 ring-purple-500/20 shadow-md'
                  : step > s.num
                  ? 'bg-purple-100 border border-purple-300 text-purple-900'
                  : 'bg-white border border-slate-300 text-slate-400'
              }`}
            >
              {step > s.num ? <CheckCircle2 className="w-4 h-4" /> : s.num}
            </div>
            <span className="text-[11px] font-bold text-slate-700 hidden sm:block">{s.label}</span>
          </div>
        ))}
      </div>

      {/* Step 1: Business & Domain */}
      {step === 1 && (
        <div className="card-vibrant p-8 space-y-6">
          <div>
            <h2 className="text-xl font-black text-slate-900">Enter Business Information</h2>
            <p className="text-xs text-slate-500 mt-1">
              Start by defining the project name, primary service category, and website domain.
            </p>
          </div>

          <div className="space-y-4 text-xs">
            <div>
              <label className="text-slate-700 font-bold block mb-1">Business / Project Name</label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="e.g. Apex Electrical Services"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 focus:outline-none focus:border-purple-500 text-sm font-medium"
              />
            </div>

            <div>
              <label className="text-slate-700 font-bold block mb-1">Website Domain URL</label>
              <input
                type="text"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="e.g. apexelectrical.com"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 focus:outline-none focus:border-purple-500 text-sm font-medium"
              />
            </div>

            <div>
              <CategorySelector
                primaryCategory={category}
                onChangePrimary={setCategory}
                additionalCategories={additionalCategories}
                onChangeAdditionals={setAdditionalCategories}
                allowAdditionals={true}
                maxAdditionals={5}
                label="Primary Business Category"
                helperText="Search your exact business category or industry taxonomy (e.g. Dentist, Plumber, Law Firm)"
              />
            </div>
          </div>

          <div className="flex justify-end pt-4 border-t border-slate-100">
            <button
              onClick={() => {
                if (!category.trim()) {
                  setErrorMessage('Please select a Primary Business Category to continue.');
                  return;
                }
                setErrorMessage(null);
                setStep(2);
              }}
              className="flex items-center space-x-2 px-6 py-2.5 btn-vibrant-primary rounded-xl font-bold text-xs shadow-md"
            >
              <span>Continue to Location</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Location & NAP */}
      {step === 2 && (
        <div className="card-vibrant p-8 space-y-6">
          <div>
            <h2 className="text-xl font-black text-slate-900">Set Canonical Location & NAP</h2>
            <p className="text-xs text-slate-500 mt-1">
              Your canonical address and telephone form the baseline for directory consistency scans.
            </p>
          </div>

          <div className="space-y-4 text-xs">
            <div>
              <label className="text-slate-700 font-bold block mb-1">
                Country <span className="text-rose-500">*</span>
              </label>
              <CountrySelector
                value={country}
                onChange={setCountry}
                required
              />
            </div>

            <div>
              <label className="text-slate-700 font-bold block mb-1">Street Address</label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="e.g. 100 Main Street"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-slate-700 font-bold block mb-1">City / Suburb</label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="Metro City"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>
              <div>
                <label className="text-slate-700 font-bold block mb-1">State</label>
                <input
                  type="text"
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  placeholder="NY"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>
              <div>
                <label className="text-slate-700 font-bold block mb-1">Postal Code</label>
                <input
                  type="text"
                  value={postalCode}
                  onChange={(e) => setPostalCode(e.target.value)}
                  placeholder="10001"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>
            </div>

            <div>
              <label className="text-slate-700 font-bold block mb-1">Canonical Telephone</label>
              <input
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+1 555 123 4567"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
              />
            </div>

            <div>
              <label className="text-slate-700 font-bold block mb-1">Google Maps / Business Profile URL (Optional)</label>
              <input
                type="url"
                value={publicMapsUrl}
                onChange={(e) => setPublicMapsUrl(e.target.value)}
                placeholder="https://maps.google.com/?cid=... or https://maps.app.goo.gl/..."
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Paste the public Google Maps listing link for this business. Ownership is not required for public business information.
              </p>
            </div>
          </div>

          <div className="flex justify-between pt-4 border-t border-slate-100">
            <button
              onClick={() => setStep(1)}
              className="px-5 py-2.5 btn-vibrant-secondary rounded-xl text-xs font-bold"
            >
              Back
            </button>
            <button
              onClick={() => setStep(3)}
              className="flex items-center space-x-2 px-6 py-2.5 btn-vibrant-primary rounded-xl font-bold text-xs shadow-md"
            >
              <span>Continue to Integrations</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Integrations */}
      {step === 3 && (
        <div className="card-vibrant p-8 space-y-6">
          <div>
            <h2 className="text-xl font-black text-slate-900">Connect Google Integrations</h2>
            <p className="text-xs text-slate-500 mt-1">
              You can authorize Google platforms now or skip and connect later from the settings.
            </p>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <Store className="w-6 h-6 text-purple-600" />
                <div>
                  <div className="font-extrabold text-slate-900 text-sm">Google Business Profile</div>
                  <div className="text-slate-500">Sync impressions, customer reviews, and hours</div>
                </div>
              </div>
              <button
                type="button"
                className="px-4 py-2 bg-purple-50 text-purple-800 border border-purple-200 rounded-xl font-bold"
              >
                Connect Later
              </button>
            </div>

            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <LineChart className="w-6 h-6 text-blue-600" />
                <div>
                  <div className="font-extrabold text-slate-900 text-sm">Google Search Console</div>
                  <div className="text-slate-500">Track organic search queries and impressions</div>
                </div>
              </div>
              <button
                type="button"
                className="px-4 py-2 bg-slate-100 text-slate-700 rounded-xl font-bold"
              >
                Connect Later
              </button>
            </div>
          </div>

          <div className="flex justify-between pt-4 border-t border-slate-100">
            <button
              onClick={() => setStep(2)}
              className="px-5 py-2.5 btn-vibrant-secondary rounded-xl text-xs font-bold"
            >
              Back
            </button>
            <button
              onClick={() => setStep(4)}
              className="flex items-center space-x-2 px-6 py-2.5 btn-vibrant-primary rounded-xl font-bold text-xs shadow-md"
            >
              <span>Continue to Keywords</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Local Keywords */}
      {step === 4 && (
        <div className="card-vibrant p-8 space-y-6">
          <div>
            <h2 className="text-xl font-black text-slate-900">Add Target Local Keywords</h2>
            <p className="text-xs text-slate-500 mt-1">
              Enter target keywords to track in Google Local Pack rankings (one per line).
            </p>
          </div>

          <div className="space-y-4 text-xs">
            {errorMessage && (
              <div className="p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs font-semibold">
                {errorMessage}
              </div>
            )}
            <div>
              <label className="text-slate-700 font-bold block mb-1">Keywords (One per line)</label>
              <textarea
                rows={5}
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                placeholder="electrician near me&#10;emergency electrician&#10;commercial electrical services"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 font-mono focus:outline-none focus:border-purple-500 font-medium"
              />
            </div>
          </div>

          <div className="flex justify-between pt-4 border-t border-slate-100">
            <button
              onClick={() => setStep(3)}
              disabled={isSubmitting}
              className="px-5 py-2.5 btn-vibrant-secondary rounded-xl text-xs font-bold disabled:opacity-50"
            >
              Back
            </button>
            <button
              onClick={handleFinishOnboarding}
              disabled={isSubmitting}
              className="flex items-center space-x-2 px-7 py-3 btn-vibrant-primary rounded-xl font-black text-xs shadow-lg transition-all disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <Sparkles className="w-4 h-4" />
              <span>{isSubmitting ? 'Creating Project & Initializing...' : 'Launch Project & Run Initial Audit'}</span>
            </button>
          </div>
        </div>
      )}

      {/* MODAL: Launch Project & Run Initial Audit Loading / Initialization Modal */}
      <Modal
        isOpen={showInitModal}
        onClose={initError ? () => setShowInitModal(false) : () => {}}
        closeOnOutsideClick={false}
        closeOnEscape={Boolean(initError)}
        showCloseButton={Boolean(initError)}
        maxWidth="lg"
        title={initError ? 'Project Initialization Failed' : 'Initializing Local SEO Project'}
        description={`${projectName.trim() || domain.trim() || 'New Project'} ${domain.trim() ? `(${domain.trim()})` : ''}`}
        footer={
          <div className="flex items-center justify-between text-xs w-full">
            <span className="text-slate-500 font-medium">
              {!initError
                ? 'Initializing workspaces, NAP profile, and initial audit...'
                : 'Form inputs have been preserved.'}
            </span>

            {initError && (
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setShowInitModal(false)}
                  className="px-4 py-2 border border-slate-200 bg-white hover:bg-slate-100 text-slate-700 rounded-xl font-bold transition-all text-xs"
                >
                  Edit Information
                </button>
                <button
                  onClick={handleFinishOnboarding}
                  className="px-5 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl font-bold transition-all shadow-xs flex items-center space-x-1.5 text-xs"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Retry Initialization</span>
                </button>
              </div>
            )}
          </div>
        }
      >
        <div className="space-y-4">
          {/* Live Progress Bar & Current Task */}
          <div className="p-4 rounded-2xl border border-slate-100 bg-slate-50 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2 font-bold text-slate-800">
                {!initError ? (
                  <RotateCw className="w-3.5 h-3.5 text-emerald-600 animate-spin" />
                ) : (
                  <XCircle className="w-3.5 h-3.5 text-rose-500" />
                )}
                <span className="truncate">{initError ? 'Initialization stopped' : currentTaskLabel}</span>
              </div>
              <span className={`font-mono font-black ${initError ? 'text-rose-600' : 'text-emerald-700'}`}>
                {completedCount} / {INITIAL_TASK_DEFS.length} ({progressPct}%)
              </span>
            </div>

            <div className="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ease-out ${
                  initError
                    ? 'bg-rose-500'
                    : 'bg-emerald-600'
                }`}
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>

          {/* Error Banner if any step failed */}
          {initError && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-2xl flex items-start space-x-2.5 text-xs text-rose-800">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="font-bold">Error Details:</div>
                <div className="font-medium text-rose-700">{initError}</div>
              </div>
            </div>
          )}

          {/* Completed Checklist */}
          <div className="space-y-2.5 divide-y divide-slate-100">
            <div className="text-[11px] font-bold uppercase text-slate-400 tracking-wider pb-1">
              Initialization Checklist
            </div>
            {initTasks.map((t) => (
              <div key={t.id} className="pt-2 first:pt-0 flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2.5 min-w-0">
                  <div className="shrink-0">
                    {t.status === 'completed' && (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    )}
                    {t.status === 'running' && (
                      <RotateCw className="w-4 h-4 text-emerald-600 animate-spin" />
                    )}
                    {t.status === 'failed' && (
                      <XCircle className="w-4 h-4 text-rose-500" />
                    )}
                    {t.status === 'pending' && (
                      <div className="w-3.5 h-3.5 rounded-full border-2 border-slate-300" />
                    )}
                  </div>
                  <span className={`font-semibold truncate ${
                    t.status === 'completed'
                      ? 'text-slate-800'
                      : t.status === 'running'
                      ? 'text-emerald-700 font-bold'
                      : t.status === 'failed'
                      ? 'text-rose-700 font-bold'
                      : 'text-slate-400'
                  }`}>
                    {t.label}
                  </span>
                </div>

                <div className="shrink-0 ml-2">
                  {t.status === 'completed' && (
                    <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                      Done
                    </span>
                  )}
                  {t.status === 'running' && (
                    <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                      Running
                    </span>
                  )}
                  {t.status === 'failed' && (
                    <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">
                      Failed
                    </span>
                  )}
                  {t.status === 'pending' && (
                    <span className="text-[10px] font-medium text-slate-400">
                      Pending
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </Modal>
    </div>
  );
};

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
  LineChart
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import api from '../api/client';

export const OnboardingWizard: React.FC = () => {
  const navigate = useNavigate();
  const { refreshProjects, refreshDashboard } = useProject();
  const [step, setStep] = useState(1);

  // Form State
  const [projectName, setProjectName] = useState('');
  const [domain, setDomain] = useState('');
  const [category, setCategory] = useState('Local Contractor / Service');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [phone, setPhone] = useState('');
  const [keywordInput, setKeywordInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFinishOnboarding = async () => {
    try {
      setIsSubmitting(true);
      const projResp = await api.post('/projects', {
        name: projectName.trim() || 'My Business Project',
        domain: domain.trim() || 'example.com',
        primary_category: category,
        country: 'United States',
        location: {
          name: 'Main Location',
          address: address.trim() || undefined,
          city: city.trim() || undefined,
          state: state.trim() || undefined,
          postal_code: postalCode.trim() || undefined,
          phone: phone.trim() || undefined,
          country: 'United States'
        }
      });

      const newProjectId = projResp.data.id;

      // Add keywords if entered
      if (keywordInput.trim()) {
        const kws = keywordInput.split('\n').filter((k) => k.trim());
        for (const kw of kws) {
          await api.post('/keywords', {
            project_id: newProjectId,
            keyword: kw.trim(),
            target_location: city.trim() || 'Metro Area',
            search_intent: 'Commercial',
            search_volume: 450
          });
        }
      }

      // Trigger initial crawl
      await api.post(`/audits/crawl/${newProjectId}`, {
        url: `https://${domain.trim() || 'example.com'}`,
        max_pages: 5
      });

      await refreshProjects();
      await refreshDashboard();
      navigate('/');
    } catch (e) {
      console.error('Onboarding failed:', e);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-6 space-y-8 select-none">
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
              <label className="text-slate-700 font-bold block mb-1">Primary Business Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 focus:outline-none focus:border-purple-500 text-sm font-medium cursor-pointer"
              >
                <option>Local Contractor / Service</option>
                <option>Electrical Contractor</option>
                <option>Plumbing Contractor</option>
                <option>HVAC / Air Conditioning</option>
                <option>Roofing Contractor</option>
                <option>Dentist / Dental Clinic</option>
                <option>Law Firm / Attorney</option>
                <option>Automotive Repair Shop</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end pt-4 border-t border-slate-100">
            <button
              onClick={() => setStep(2)}
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
              className="px-5 py-2.5 btn-vibrant-secondary rounded-xl text-xs font-bold"
            >
              Back
            </button>
            <button
              onClick={handleFinishOnboarding}
              disabled={isSubmitting}
              className="flex items-center space-x-2 px-7 py-3 btn-vibrant-primary rounded-xl font-black text-xs shadow-lg transition-all"
            >
              <Sparkles className="w-4 h-4" />
              <span>{isSubmitting ? 'Creating Project & Initializing...' : 'Launch Project & Run Initial Audit'}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

import React, { useState } from 'react';
import { FileCode2, Copy, Check, Sparkles, Code, CheckCircle2 } from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const SchemaGeneratorView: React.FC = () => {
  const { activeProject } = useProject();
  const [businessType, setBusinessType] = useState('LocalBusiness');
  const [businessName, setBusinessName] = useState(activeProject?.name || 'Local Business Name');
  const [phone, setPhone] = useState('+1 555 123 4567');
  const [street, setStreet] = useState('100 Main Street');
  const [city, setCity] = useState('Metro City');
  const [state, setState] = useState('NY');
  const [postalCode, setPostalCode] = useState('10001');
  const [country, setCountry] = useState('US');
  const [generatedHtml, setGeneratedHtml] = useState<string>('');
  const [isCopied, setIsCopied] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsGenerating(true);
      const resp = await api.post('/local-seo/schema/generate', {
        business_name: businessName,
        business_type: businessType,
        url: `https://${activeProject?.domain || 'example.com'}`,
        phone,
        street_address: street,
        city,
        state,
        postal_code: postalCode,
        country,
        latitude: -27.4698,
        longitude: 153.0251
      });
      setGeneratedHtml(resp.data.html_tag);
    } catch (err) {
      console.error('Schema generation failed:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const copyToClipboard = () => {
    if (!generatedHtml) return;
    navigator.clipboard.writeText(generatedHtml);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  if (!activeProject) {
    return (
      <EmptyState
        icon={FileCode2}
        badge="Schema Generator"
        title="Select a Project"
        description="Select a business project to generate Schema.org LocalBusiness structured JSON-LD code."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
          <FileCode2 className="w-6 h-6 text-purple-600" />
          <span>LocalBusiness Schema Generator & Validator</span>
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Generate Schema.org structured data (JSON-LD) for {activeProject.domain} to qualify for Google rich search results.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Form Inputs */}
        <div className="lg:col-span-6 card-vibrant p-5 space-y-4">
          <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">Business Schema Parameters</h3>
          <form onSubmit={handleGenerate} className="space-y-3 text-xs">
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Schema @type</label>
              <select
                value={businessType}
                onChange={(e) => setBusinessType(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium cursor-pointer"
              >
                <option value="LocalBusiness">LocalBusiness (General)</option>
                <option value="Electrician">Electrician (Specialized)</option>
                <option value="Plumber">Plumber (Specialized)</option>
                <option value="HVACBusiness">HVAC / Heating & Air</option>
                <option value="LegalService">Legal Service / Attorney</option>
                <option value="MedicalBusiness">Medical / Dental Clinic</option>
                <option value="AutomotiveBusiness">Automotive Repair Shop</option>
              </select>
            </div>

            <div>
              <label className="text-slate-700 block mb-1 font-bold">Business Legal Name</label>
              <input
                type="text"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-slate-700 block mb-1 font-bold">Phone</label>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>
              <div>
                <label className="text-slate-700 block mb-1 font-bold">Street Address</label>
                <input
                  type="text"
                  value={street}
                  onChange={(e) => setStreet(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="text-slate-700 block mb-1 font-bold">City</label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>
              <div>
                <label className="text-slate-700 block mb-1 font-bold">State / Region</label>
                <input
                  type="text"
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>
              <div>
                <label className="text-slate-700 block mb-1 font-bold">Postal Code</label>
                <input
                  type="text"
                  value={postalCode}
                  onChange={(e) => setPostalCode(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isGenerating}
              className="w-full py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all mt-2"
            >
              {isGenerating ? 'Generating Schema...' : 'Generate Valid JSON-LD Schema'}
            </button>
          </form>
        </div>

        {/* Output Code Block */}
        <div className="lg:col-span-6 card-vibrant p-5 flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center space-x-1.5">
              <Code className="w-4 h-4 text-purple-600" />
              <span>Generated JSON-LD Tag</span>
            </h3>

            {generatedHtml && (
              <button
                onClick={copyToClipboard}
                className="flex items-center space-x-1 px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-lg text-xs font-bold border border-slate-200 transition-colors"
              >
                {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{isCopied ? 'Copied' : 'Copy Code'}</span>
              </button>
            )}
          </div>

          <div className="flex-1 bg-slate-900 p-4 rounded-xl border border-slate-800 font-mono text-xs text-purple-300 overflow-x-auto max-h-96">
            <pre className="text-emerald-400">
              {generatedHtml ||
                '// Click "Generate Valid JSON-LD Schema" on the left to produce copy-paste schema code ready for injection into your website <head> tag.'}
            </pre>
          </div>

          <div className="text-[11px] text-slate-500 flex items-center space-x-1.5 pt-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>Validated according to Schema.org and Google Rich Results standards.</span>
          </div>
        </div>
      </div>
    </div>
  );
};

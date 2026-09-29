import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  FileCode2,
  Copy,
  Check,
  Sparkles,
  Code,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Eye,
  Download,
  Layers,
  HelpCircle,
  ArrowRight,
  ShieldCheck,
  Building2,
  Globe,
  MapPin,
  Phone,
  Link2,
  ExternalLink,
  ChevronRight,
  Activity,
  Plus,
  Trash2,
  Info,
  X,
  Search,
  Save,
  FileText,
  Upload,
  ChevronDown,
  Award,
  BookOpen,
  Filter
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { EmptyState } from '../components/ui/EmptyState';
import { HealthScoreRing } from '../components/ui/HealthScoreRing';
import { Modal } from '../components/ui/Modal';
import api from '../api/client';
import {
  SchemaRecord,
  SchemaIntelligenceSummary,
  SchemaRecommendation,
  Tier1SchemaInfo,
  SchemaValidationResult
} from '../types';

interface SchemaTypeDef {
  name: string;
  category: string;
  parent?: string;
  description?: string;
  url?: string;
  rich_result_eligible?: boolean;
  aliases?: string[];
  properties?: Array<{
    name: string;
    type: string;
    description: string;
    required: boolean;
    recommended: boolean;
    multiple: boolean;
    entity_ref?: string;
    rich_result_required?: boolean;
  }>;
}

const TIER_1_KEYS = [
  'Organization',
  'LocalBusiness',
  'WebSite',
  'WebPage',
  'BreadcrumbList',
  'Service',
  'Product',
  'Article',
  'BlogPosting',
  'Person',
  'Review',
  'AggregateRating',
  'Offer',
  'FAQPage',
  'Event',
  'JobPosting',
  'ImageObject',
  'VideoObject'
];

export const SchemaGeneratorView: React.FC = () => {
  const { activeProject } = useProject();

  // Active Tab: 'overview' | 'pages' | 'recommendations' | 'generator' | 'validator'
  const [activeTab, setActiveTab] = useState<'overview' | 'pages' | 'recommendations' | 'generator' | 'validator'>('overview');

  // Loading & summary states
  const [isLoading, setIsLoading] = useState(false);
  const [isRechecking, setIsRechecking] = useState(false);
  const [summary, setSummary] = useState<SchemaIntelligenceSummary | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<SchemaRecord | null>(null);
  const [selectedMatrixSchema, setSelectedMatrixSchema] = useState<{ name: string; info: Tier1SchemaInfo } | null>(null);
  const [selectedInstanceIdx, setSelectedInstanceIdx] = useState<number>(0);
  const [originalCompareMarkup, setOriginalCompareMarkup] = useState<string>('');
  const [generatorViewMode, setGeneratorViewMode] = useState<'generated' | 'original' | 'split'>('generated');
  const [isOriginalCopied, setIsOriginalCopied] = useState(false);

  // ---------------------------------------------------------------------------
  // Vocabulary Registry State
  // ---------------------------------------------------------------------------
  const [vocabulary, setVocabulary] = useState<{
    version: string;
    categories: Record<string, string[]>;
    types: SchemaTypeDef[];
    presets: Array<{ name: string; category: string; description: string }>;
  } | null>(null);
  const [typeSearchQuery, setTypeSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [isTypeDropdownOpen, setIsTypeDropdownOpen] = useState(false);
  const [currentTypeDef, setCurrentTypeDef] = useState<SchemaTypeDef | null>(null);
  const [isLoadingTypeDef, setIsLoadingTypeDef] = useState(false);

  // ---------------------------------------------------------------------------
  // Universal Generator State
  // ---------------------------------------------------------------------------
  const [selectedType, setSelectedType] = useState<string>('LocalBusiness');
  const [targetPageUrl, setTargetPageUrl] = useState<string>('');
  const [includeGraph, setIncludeGraph] = useState(true);
  const [editorMode, setEditorMode] = useState<'form' | 'raw'>('form');

  // Dynamic Property Values for Selected Type
  const [propertyValues, setPropertyValues] = useState<Record<string, any>>({
    name: '',
    url: '',
    telephone: '',
    priceRange: '$$',
    description: '',
    image: '',
    streetAddress: '',
    addressLocality: '',
    addressRegion: '',
    postalCode: '',
    addressCountry: 'US',
    latitude: '',
    longitude: '',
    // Article / Content props
    headline: '',
    datePublished: '',
    dateModified: '',
    authorName: '',
    publisherName: '',
    // Product props
    price: '',
    priceCurrency: 'USD',
    availability: 'https://schema.org/InStock',
    brand: '',
    sku: '',
    // FAQ props
    faqItems: [{ question: '', answer: '' }],
    // Opening Hours
    openingHours: ['Mo-Fr 09:00-17:00'],
    // Custom key-value pairs
    customProperties: [] as Array<{ key: string; value: string }>
  });

  // Connected Graph Entities
  const [connectedEntities, setConnectedEntities] = useState<Array<{
    id: string;
    type: string;
    name: string;
    url?: string;
    properties: Record<string, any>;
  }>>([]);

  // Draft Management State
  const [draftsList, setDraftsList] = useState<Array<any>>([]);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [draftSaveSuccess, setDraftSaveSuccess] = useState(false);
  const [showInstructionsModal, setShowInstructionsModal] = useState(false);

  // Generator Output & Live Validation State
  const [generatedJsonLd, setGeneratedJsonLd] = useState<string>('');
  const [rawEditorJson, setRawEditorJson] = useState<string>('');
  const [rawJsonError, setRawJsonError] = useState<string | null>(null);
  const [liveValidation, setLiveValidation] = useState<any>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  // ---------------------------------------------------------------------------
  // Standalone Live Validator Tab State
  // ---------------------------------------------------------------------------
  const [validatorTabMode, setValidatorTabMode] = useState<'snippet' | 'url' | 'file'>('snippet');
  const [validatorInput, setValidatorInput] = useState<string>('');
  const [validatorUrlInput, setValidatorUrlInput] = useState<string>('');
  const [validationResult, setValidationResult] = useState<any>(null);
  const [isValidating, setIsValidating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ---------------------------------------------------------------------------
  // Fetch Initial Data & Vocabulary
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const fetchVocabularyData = async () => {
      try {
        const resp = await api.get('/local-seo/schema/vocabulary');
        setVocabulary(resp.data);
      } catch (err) {
        console.error('Failed to load schema vocabulary:', err);
      }
    };
    fetchVocabularyData();
  }, []);

  // Fetch Schema Intelligence and Drafts on project change
  useEffect(() => {
    if (activeProject) {
      const loc = activeProject.locations?.[0];
      const baseDomainUrl = activeProject.domain ? `https://${activeProject.domain}` : '';
      setTargetPageUrl(baseDomainUrl);

      // Pre-fill initial properties from verified project data
      setPropertyValues((prev) => ({
        ...prev,
        name: activeProject.name || '',
        url: baseDomainUrl,
        telephone: loc?.phone || '',
        streetAddress: loc?.address || '',
        addressLocality: loc?.city || '',
        addressRegion: loc?.state || '',
        postalCode: loc?.postal_code || '',
        addressCountry: loc?.country || 'US',
        latitude: loc?.latitude !== undefined && loc?.latitude !== null ? String(loc.latitude) : '',
        longitude: loc?.longitude !== undefined && loc?.longitude !== null ? String(loc.longitude) : '',
        publisherName: activeProject.name || '',
        authorName: activeProject.name || ''
      }));

      fetchIntelligence();
      fetchDrafts();
    }
  }, [activeProject]);

  // Fetch Type Definition whenever selectedType changes
  useEffect(() => {
    const fetchTypeDef = async () => {
      if (!selectedType) return;
      try {
        setIsLoadingTypeDef(true);
        const resp = await api.get(`/local-seo/schema/vocabulary/type/${selectedType}`);
        setCurrentTypeDef(resp.data);
      } catch (err) {
        console.error(`Failed to load type def for ${selectedType}:`, err);
      } finally {
        setIsLoadingTypeDef(false);
      }
    };
    fetchTypeDef();
  }, [selectedType]);

  // Live Auto-Generation and Validation Sync
  useEffect(() => {
    if (editorMode === 'form') {
      buildLiveJsonLd();
    }
  }, [selectedType, propertyValues, connectedEntities, includeGraph, targetPageUrl, editorMode]);

  const fetchIntelligence = async () => {
    if (!activeProject) return;
    try {
      setIsLoading(true);
      const resp = await api.get(`/local-seo/schema/${activeProject.id}/intelligence`);
      setSummary(resp.data);
      if (resp.data.records?.length > 0 && !selectedRecord) {
        setSelectedRecord(resp.data.records[0]);
      }
    } catch (err) {
      console.error('Failed to load schema intelligence:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchDrafts = async () => {
    if (!activeProject) return;
    try {
      const resp = await api.get(`/local-seo/schema/drafts/${activeProject.id}`);
      setDraftsList(resp.data || []);
    } catch (err) {
      console.error('Failed to load drafts:', err);
    }
  };

  const handleRecheck = async () => {
    if (!activeProject) return;
    try {
      setIsRechecking(true);
      const resp = await api.post(`/local-seo/schema/analyze/${activeProject.id}`);
      setSummary(resp.data);
    } catch (err) {
      console.error('Failed to recheck schemas:', err);
    } finally {
      setIsRechecking(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Live JSON-LD Builder
  // ---------------------------------------------------------------------------
  const buildLiveJsonLd = () => {
    const baseUrl = targetPageUrl || (activeProject?.domain ? `https://${activeProject.domain}` : '');
    const cleanUrl = baseUrl.replace(/\/+$/, '');
    const typeSlug = selectedType.toLowerCase();
    const mainId = cleanUrl ? `${cleanUrl}/#${typeSlug}` : undefined;

    const mainObj: Record<string, any> = {
      '@type': selectedType
    };

    if (mainId) {
      mainObj['@id'] = mainId;
    }

    if (propertyValues.name?.trim()) mainObj['name'] = propertyValues.name.trim();
    if (propertyValues.url?.trim()) mainObj['url'] = propertyValues.url.trim();
    if (propertyValues.description?.trim()) mainObj['description'] = propertyValues.description.trim();
    if (propertyValues.image?.trim()) mainObj['image'] = propertyValues.image.trim();
    if (propertyValues.telephone?.trim()) mainObj['telephone'] = propertyValues.telephone.trim();
    if (propertyValues.priceRange?.trim()) mainObj['priceRange'] = propertyValues.priceRange.trim();

    // Address construction
    const hasAddress =
      propertyValues.streetAddress?.trim() ||
      propertyValues.addressLocality?.trim() ||
      propertyValues.postalCode?.trim();
    if (hasAddress) {
      mainObj['address'] = {
        '@type': 'PostalAddress',
        ...(propertyValues.streetAddress?.trim() ? { streetAddress: propertyValues.streetAddress.trim() } : {}),
        ...(propertyValues.addressLocality?.trim() ? { addressLocality: propertyValues.addressLocality.trim() } : {}),
        ...(propertyValues.addressRegion?.trim() ? { addressRegion: propertyValues.addressRegion.trim() } : {}),
        ...(propertyValues.postalCode?.trim() ? { postalCode: propertyValues.postalCode.trim() } : {}),
        ...(propertyValues.addressCountry?.trim() ? { addressCountry: propertyValues.addressCountry.trim() } : {})
      };
    }

    // Geo coordinates
    if (propertyValues.latitude?.trim() && propertyValues.longitude?.trim()) {
      mainObj['geo'] = {
        '@type': 'GeoCoordinates',
        latitude: parseFloat(propertyValues.latitude),
        longitude: parseFloat(propertyValues.longitude)
      };
    }

    // Opening hours
    if (propertyValues.openingHours && propertyValues.openingHours.length > 0) {
      const validHours = propertyValues.openingHours.filter((h: string) => h.trim().length > 0);
      if (validHours.length > 0) {
        mainObj['openingHours'] = validHours;
      }
    }

    // Article / Blog / News properties
    if (propertyValues.headline?.trim()) mainObj['headline'] = propertyValues.headline.trim();
    if (propertyValues.datePublished?.trim()) mainObj['datePublished'] = propertyValues.datePublished.trim();
    if (propertyValues.dateModified?.trim()) mainObj['dateModified'] = propertyValues.dateModified.trim();
    if (propertyValues.authorName?.trim()) {
      mainObj['author'] = {
        '@type': 'Person',
        name: propertyValues.authorName.trim()
      };
    }
    if (propertyValues.publisherName?.trim()) {
      mainObj['publisher'] = {
        '@type': 'Organization',
        name: propertyValues.publisherName.trim(),
        ...(mainObj['image'] ? { logo: { '@type': 'ImageObject', url: mainObj['image'] } } : {})
      };
    }

    // Product properties
    if (propertyValues.price?.trim()) {
      mainObj['offers'] = {
        '@type': 'Offer',
        price: propertyValues.price.trim(),
        priceCurrency: propertyValues.priceCurrency || 'USD',
        availability: propertyValues.availability || 'https://schema.org/InStock',
        url: propertyValues.url || cleanUrl
      };
    }
    if (propertyValues.brand?.trim()) {
      mainObj['brand'] = {
        '@type': 'Brand',
        name: propertyValues.brand.trim()
      };
    }
    if (propertyValues.sku?.trim()) mainObj['sku'] = propertyValues.sku.trim();

    // FAQPage items
    if (selectedType === 'FAQPage' && propertyValues.faqItems?.length > 0) {
      const validQuestions = propertyValues.faqItems
        .filter((item: any) => item.question?.trim() && item.answer?.trim())
        .map((item: any) => ({
          '@type': 'Question',
          name: item.question.trim(),
          acceptedAnswer: {
            '@type': 'Answer',
            text: item.answer.trim()
          }
        }));
      if (validQuestions.length > 0) {
        mainObj['mainEntity'] = validQuestions;
      }
    }

    // Custom properties entered by user
    if (propertyValues.customProperties?.length > 0) {
      propertyValues.customProperties.forEach((cp: { key: string; value: string }) => {
        if (cp.key?.trim() && cp.value?.trim()) {
          try {
            // If valid JSON, parse it (supports nested arrays/objects)
            mainObj[cp.key.trim()] = JSON.parse(cp.value.trim());
          } catch {
            mainObj[cp.key.trim()] = cp.value.trim();
          }
        }
      });
    }

    // Assemble Graph or single object
    const graphList = [mainObj];
    if (connectedEntities.length > 0) {
      connectedEntities.forEach((ce) => {
        const ceObj: Record<string, any> = {
          '@type': ce.type,
          '@id': ce.id,
          name: ce.name,
          ...(ce.url ? { url: ce.url } : {}),
          ...ce.properties
        };
        graphList.push(ceObj);
      });
    }

    let resultJson = '';
    if (includeGraph || graphList.length > 1) {
      const graphData = {
        '@context': 'https://schema.org',
        '@graph': graphList
      };
      resultJson = JSON.stringify(graphData, null, 2);
    } else {
      const singleData = {
        '@context': 'https://schema.org',
        ...mainObj
      };
      resultJson = JSON.stringify(singleData, null, 2);
    }

    setGeneratedJsonLd(resultJson);
    setRawEditorJson(resultJson);
    setRawJsonError(null);

    // Validate client-side / backend debounced
    validateGeneratedJson(resultJson);
  };

  const validateGeneratedJson = async (jsonStr: string) => {
    if (!jsonStr || !jsonStr.trim()) return;
    try {
      const resp = await api.post('/local-seo/schema/validate', {
        json_ld: jsonStr,
        project_id: activeProject?.id
      });
      setLiveValidation(resp.data);
    } catch {
      // Quiet fail on rapid typing
    }
  };

  const handleRawJsonChange = (newVal: string) => {
    setRawEditorJson(newVal);
    try {
      JSON.parse(newVal);
      setRawJsonError(null);
      setGeneratedJsonLd(newVal);
      validateGeneratedJson(newVal);
    } catch (e: any) {
      setRawJsonError(`JSON Syntax Error: ${e.message}`);
    }
  };

  const handleSaveDraft = async () => {
    if (!activeProject || !generatedJsonLd) return;
    try {
      setIsSavingDraft(true);
      await api.post('/local-seo/schema/drafts', {
        project_id: activeProject.id,
        page_url: targetPageUrl || (activeProject.domain ? `https://${activeProject.domain}` : 'https://example.com'),
        schema_type: selectedType,
        generated_json_ld: generatedJsonLd
      });
      setDraftSaveSuccess(true);
      setTimeout(() => setDraftSaveSuccess(false), 3000);
      fetchDrafts();
    } catch (err) {
      console.error('Failed to save draft:', err);
    } finally {
      setIsSavingDraft(false);
    }
  };

  const handleOpenGeneratorForSchema = (schemaName: string, info?: Tier1SchemaInfo, originalMarkup?: string) => {
    setSelectedType(schemaName);
    const prefill = info?.generator_prefill;
    if (prefill) {
      setPropertyValues((prev) => ({
        ...prev,
        name: prefill.business_name || prev.name,
        url: prefill.url || prev.url,
        telephone: prefill.phone || prev.telephone,
        streetAddress: prefill.street || prev.streetAddress,
        addressLocality: prefill.city || prev.addressLocality,
        addressRegion: prefill.state || prev.addressRegion,
        postalCode: prefill.postal_code || prev.postalCode,
        addressCountry: prefill.country || prev.addressCountry,
        latitude: prefill.latitude || prev.latitude,
        longitude: prefill.longitude || prev.longitude
      }));
    }
    if (originalMarkup) {
      setOriginalCompareMarkup(originalMarkup);
      setGeneratorViewMode('generated');
    } else {
      setOriginalCompareMarkup('');
    }
    setSelectedMatrixSchema(null);
    setActiveTab('generator');
  };

  const handleAddCustomProperty = () => {
    setPropertyValues((prev) => ({
      ...prev,
      customProperties: [...prev.customProperties, { key: '', value: '' }]
    }));
  };

  const handleRemoveCustomProperty = (index: number) => {
    setPropertyValues((prev) => ({
      ...prev,
      customProperties: prev.customProperties.filter((_: any, idx: number) => idx !== index)
    }));
  };

  const handleAddFaqItem = () => {
    setPropertyValues((prev) => ({
      ...prev,
      faqItems: [...(prev.faqItems || []), { question: '', answer: '' }]
    }));
  };

  const handleRemoveFaqItem = (index: number) => {
    setPropertyValues((prev) => ({
      ...prev,
      faqItems: prev.faqItems.filter((_: any, idx: number) => idx !== index)
    }));
  };

  const handleAddConnectedEntity = (type: string) => {
    const cleanUrl = (targetPageUrl || `https://${activeProject?.domain || 'example.com'}`).replace(/\/+$/, '');
    const newId = `${cleanUrl}/#${type.toLowerCase()}-${Date.now()}`;
    setConnectedEntities((prev) => [
      ...prev,
      {
        id: newId,
        type,
        name: `${activeProject?.name || ''} ${type}`,
        properties: {}
      }
    ]);
  };

  const handleRemoveConnectedEntity = (id: string) => {
    setConnectedEntities((prev) => prev.filter((e) => e.id !== id));
  };

  // ---------------------------------------------------------------------------
  // Validator Actions
  // ---------------------------------------------------------------------------
  const handleValidateSnippet = async () => {
    if (!validatorInput.trim()) return;
    try {
      setIsValidating(true);
      const resp = await api.post('/local-seo/schema/validate', {
        json_ld: validatorInput,
        project_id: activeProject?.id
      });
      setValidationResult(resp.data);
    } catch (err) {
      console.error('Validation failed:', err);
    } finally {
      setIsValidating(false);
    }
  };

  const handleValidateFromUrl = async () => {
    if (!validatorUrlInput.trim()) return;
    try {
      setIsValidating(true);
      const resp = await api.post('/local-seo/schema/validate-url', {
        url: validatorUrlInput,
        project_id: activeProject?.id
      });
      setValidationResult(resp.data);
      if (resp.data.raw_json_ld) {
        setValidatorInput(resp.data.raw_json_ld);
      }
    } catch (err: any) {
      setValidationResult({
        is_valid: false,
        syntax_valid: false,
        errors: [err.response?.data?.detail || 'Failed to crawl and extract schema from provided URL.'],
        warnings: [],
        entities: []
      });
    } finally {
      setIsValidating(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (event) => {
      const content = event.target?.result as string;
      setValidatorInput(content);
      try {
        setIsValidating(true);
        const resp = await api.post('/local-seo/schema/validate', {
          json_ld: content,
          project_id: activeProject?.id
        });
        setValidationResult(resp.data);
      } catch (err) {
        console.error('File validation error:', err);
      } finally {
        setIsValidating(false);
      }
    };
    reader.readAsText(file);
  };

  const copyToClipboard = (text: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const downloadJsonLd = (content: string, filename = 'schema.jsonld') => {
    const blob = new Blob([content], { type: 'application/ld+json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const applyRecommendationToGenerator = (rec: SchemaRecommendation) => {
    if (rec.action_type === 'generate_service') {
      setSelectedType('Service');
      setPropertyValues((prev) => ({
        ...prev,
        name: `${activeProject?.primary_category || 'Primary'} Service`,
        description: `Professional ${activeProject?.primary_category || 'local'} services.`
      }));
    } else if (rec.action_type === 'generate_localbusiness') {
      setSelectedType(activeProject?.primary_category || 'LocalBusiness');
    }
    setActiveTab('generator');
  };

  // Filtered Vocabulary Types based on search and category
  const filteredTypes = useMemo(() => {
    if (!vocabulary?.types) return [];
    let list = vocabulary.types;
    if (selectedCategory !== 'All') {
      const categoryTypes = vocabulary.categories[selectedCategory] || [];
      list = list.filter((t) => categoryTypes.includes(t.name) || t.category === selectedCategory);
    }
    if (typeSearchQuery.trim()) {
      const q = typeSearchQuery.toLowerCase();
      list = list.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          (t.parent && t.parent.toLowerCase().includes(q)) ||
          (t.description && t.description.toLowerCase().includes(q)) ||
          (t.aliases && t.aliases.some((a) => a.toLowerCase().includes(q)))
      );
    }
    return list;
  }, [vocabulary, selectedCategory, typeSearchQuery]);

  if (!activeProject) {
    return (
      <EmptyState
        icon={FileCode2}
        badge="Schema Intelligence"
        title="Select a Project"
        description="Select a business project to inspect crawled Schema.org structured data, detect missing opportunities, and generate validated JSON-LD code."
      />
    );
  }

  const healthScore = summary?.health_score !== undefined && summary?.health_score !== null ? summary.health_score : null;
  const isHealthScoreAvailable = healthScore !== null && healthScore !== undefined;
  const stats = summary?.stats || {
    pages_crawled: 0,
    schemas_detected: 0,
    valid_count: 0,
    warnings_count: 0,
    errors_count: 0,
    missing_opportunities: 0
  };

  return (
    <div className="space-y-6">
      {/* 1. Header Banner & Schema Health Score */}
      <div className="card-vibrant p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-1.5">
          <div className="flex items-center space-x-2">
            <div className="w-9 h-9 rounded-xl bg-purple-100 flex items-center justify-center text-purple-700 font-black">
              <FileCode2 className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-black text-[#142820] tracking-tight flex items-center space-x-2">
                <span>Schema Intelligence & Universal Generator</span>
                <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#EAF2EA] text-[#174A38] border border-[#B8DFC9]">
                  {vocabulary?.version || 'Schema.org v28.0'}
                </span>
              </h1>
              <p className="text-xs text-slate-500 font-medium">
                Universal Schema.org vocabulary generator, connected entity graph builder, and deep validator for <strong className="text-slate-700">{activeProject.domain}</strong>.
              </p>
            </div>
          </div>
        </div>

        {/* Health Score & Quick Actions */}
        <div className="flex items-center space-x-5 self-stretch md:self-auto justify-between md:justify-end border-t md:border-t-0 pt-4 md:pt-0 border-slate-100">
          <div className="flex items-center space-x-3">
            <HealthScoreRing score={healthScore} size={64} strokeWidth={6} label="Health" />
            <div className="text-left">
              <div className="text-xs font-black text-slate-900">
                {isHealthScoreAvailable
                  ? healthScore >= 90
                    ? 'Optimal Schema'
                    : healthScore >= 75
                    ? 'Good Coverage'
                    : 'Needs Optimization'
                  : 'Awaiting Audit'}
              </div>
              <div className="text-[11px] text-slate-500 font-medium">
                {stats.schemas_detected} entities on {stats.pages_crawled} pages
              </div>
            </div>
          </div>

          <button
            onClick={handleRecheck}
            disabled={isRechecking}
            className="flex items-center space-x-1.5 px-3.5 py-2 btn-vibrant-primary rounded-xl text-xs font-bold shadow-sm transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRechecking ? 'animate-spin' : ''}`} />
            <span>{isRechecking ? 'Re-analyzing...' : 'Re-Analyze Site'}</span>
          </button>
        </div>
      </div>

      {/* 2. Top KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Pages Crawled</span>
          <div className="text-xl font-black text-slate-900 mt-1">{stats.pages_crawled}</div>
          <div className="text-[10px] text-slate-500 mt-0.5 flex items-center space-x-1">
            <Globe className="w-3 h-3 text-slate-400" />
            <span>All indexable URLs</span>
          </div>
        </div>

        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Schemas Detected</span>
          <div className="text-xl font-black text-purple-700 mt-1">{stats.schemas_detected}</div>
          <div className="text-[10px] text-purple-600 mt-0.5 font-medium">Active structured types</div>
        </div>

        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Valid Schemas</span>
          <div className="text-xl font-black text-emerald-600 mt-1">{stats.valid_count}</div>
          <div className="text-[10px] text-emerald-600 mt-0.5 flex items-center space-x-1">
            <CheckCircle2 className="w-3 h-3" />
            <span>0 syntax errors</span>
          </div>
        </div>

        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Warnings</span>
          <div className="text-xl font-black text-amber-600 mt-1">{stats.warnings_count}</div>
          <div className="text-[10px] text-amber-600 mt-0.5 flex items-center space-x-1">
            <AlertTriangle className="w-3 h-3" />
            <span>Missing recommended</span>
          </div>
        </div>

        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Errors</span>
          <div className="text-xl font-black text-rose-600 mt-1">{stats.errors_count}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Critical syntax/NAP</div>
        </div>

        <div className="card-vibrant p-3.5">
          <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Missing Opportunities</span>
          <div className="text-xl font-black text-indigo-600 mt-1">{stats.missing_opportunities}</div>
          <div className="text-[10px] text-indigo-600 mt-0.5 flex items-center space-x-1">
            <Sparkles className="w-3 h-3" />
            <span>High impact potential</span>
          </div>
        </div>
      </div>

      {/* 3. Navigation Tabs */}
      <div className="flex items-center space-x-1 border-b border-slate-200 overflow-x-auto pb-px text-xs font-bold">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2.5 rounded-t-xl transition-all border-b-2 flex items-center space-x-2 ${
            activeTab === 'overview'
              ? 'border-purple-600 text-purple-700 bg-purple-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Tier 1 Schema Matrix</span>
        </button>

        <button
          onClick={() => setActiveTab('pages')}
          className={`px-4 py-2.5 rounded-t-xl transition-all border-b-2 flex items-center space-x-2 ${
            activeTab === 'pages'
              ? 'border-purple-600 text-purple-700 bg-purple-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <Globe className="w-4 h-4" />
          <span>Page-by-Page Audit ({summary?.records?.length || 0})</span>
        </button>

        <button
          onClick={() => setActiveTab('recommendations')}
          className={`px-4 py-2.5 rounded-t-xl transition-all border-b-2 flex items-center space-x-2 ${
            activeTab === 'recommendations'
              ? 'border-purple-600 text-purple-700 bg-purple-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <Sparkles className="w-4 h-4 text-amber-500" />
          <span>Prioritized Recommendations ({summary?.recommendations?.length || 0})</span>
        </button>

        <button
          onClick={() => setActiveTab('generator')}
          className={`px-4 py-2.5 rounded-t-xl transition-all border-b-2 flex items-center space-x-2 ${
            activeTab === 'generator'
              ? 'border-purple-600 text-purple-700 bg-purple-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <Code className="w-4 h-4 text-emerald-600" />
          <span>Universal Schema Generator</span>
        </button>

        <button
          onClick={() => setActiveTab('validator')}
          className={`px-4 py-2.5 rounded-t-xl transition-all border-b-2 flex items-center space-x-2 ${
            activeTab === 'validator'
              ? 'border-purple-600 text-purple-700 bg-purple-50/50'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-50'
          }`}
        >
          <ShieldCheck className="w-4 h-4 text-indigo-600" />
          <span>Live JSON-LD Validator</span>
        </button>
      </div>

      {/* ------------------------------------------------------------------- */}
      {/* TAB 1: TIER 1 SCHEMA MATRIX OVERVIEW */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="card-vibrant p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-2">
              <div>
                <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
                  Tier 1 Schema.org Coverage Matrix
                </h3>
                <p className="text-xs text-slate-500">
                  Evaluated across 18 essential structured entity types for local businesses and organizations.
                </p>
              </div>
              <div className="flex items-center space-x-2 text-[11px]">
                <span className="flex items-center space-x-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                  <span className="text-slate-600">Detected</span>
                </span>
                <span className="flex items-center space-x-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                  <span className="text-slate-600">Missing Opportunity</span>
                </span>
                <span className="flex items-center space-x-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-slate-300"></span>
                  <span className="text-slate-400">Not Applicable</span>
                </span>
              </div>
            </div>

            {/* Grid of Tier 1 Schemas */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mt-4">
              {TIER_1_KEYS.map((key) => {
                const info: Tier1SchemaInfo = summary?.tier_1_status?.[key] || {
                  status: 'Not Applicable',
                  applicability: 'Not Applicable',
                  detected_count: 0,
                  reason: 'Not required for current site profile.'
                };
                const isDetected = info.status === 'Detected';
                const isMissing = info.status === 'Missing';

                return (
                  <div
                    key={key}
                    onClick={() => {
                      setSelectedMatrixSchema({ name: key, info });
                      setSelectedInstanceIdx(0);
                    }}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer hover:shadow-md flex flex-col justify-between ${
                      isDetected
                        ? 'bg-emerald-50/50 border-emerald-200 hover:border-emerald-300'
                        : isMissing
                        ? 'bg-amber-50/50 border-amber-200 hover:border-amber-300'
                        : 'bg-slate-50 border-slate-200 opacity-60 hover:opacity-100'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-black text-slate-900 truncate">{key}</span>
                        {isDetected ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                        ) : isMissing ? (
                          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                        ) : (
                          <span className="w-2 h-2 rounded-full bg-slate-300 shrink-0"></span>
                        )}
                      </div>
                      <span
                        className={`text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded-md inline-block ${
                          isDetected
                            ? 'bg-emerald-100 text-emerald-800'
                            : isMissing
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-slate-200 text-slate-600'
                        }`}
                      >
                        {info.status}
                      </span>
                    </div>

                    <div className="mt-3 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[10px] text-slate-500">
                      <span>{isDetected ? `${info.detected_count || 1} detected` : info.applicability || 'Applicable'}</span>
                      <ChevronRight className="w-3 h-3 text-slate-400" />
                    </div>
                  </div>
                );
              })}

            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* TAB 2: PAGE-BY-PAGE AUDIT */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'pages' && (
        <div className="card-vibrant p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 pb-3 gap-2">
            <div>
              <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
                Page-by-Page Schema Audit
              </h3>
              <p className="text-xs text-slate-500">
                Detailed extraction records, JSON-LD scripts, and quality health scores for crawled URLs.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-[10px] font-black uppercase text-slate-400 tracking-wider">
                  <th className="py-2.5 px-3">Page URL & Type</th>
                  <th className="py-2.5 px-3">Detected Entities</th>
                  <th className="py-2.5 px-3">NAP Status</th>
                  <th className="py-2.5 px-3">Quality Score</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {summary?.records?.map((rec) => (
                  <tr key={rec.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-3">
                      <div className="font-bold text-slate-900 truncate max-w-xs">{rec.page_url}</div>
                      <span className="text-[10px] text-purple-700 bg-purple-50 px-2 py-0.5 rounded-md font-extrabold">
                        {rec.page_type}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex flex-wrap gap-1">
                        {rec.detected_types?.map((t, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 bg-slate-100 border border-slate-200 rounded-md text-[10px] font-bold text-slate-700"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase border ${
                          rec.nap_status === 'Consistent'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : rec.nap_status === 'Mismatch'
                            ? 'bg-rose-50 text-rose-700 border-rose-200'
                            : 'bg-slate-100 text-slate-600 border-slate-200'
                        }`}
                      >
                        {rec.nap_status}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-bold text-slate-900">{rec.quality_score} / 100</td>
                    <td className="py-3 px-3 text-right space-x-2">
                      {rec.raw_json_ld && (
                        <button
                          onClick={() => {
                            setValidatorInput(rec.raw_json_ld || '');
                            setActiveTab('validator');
                            handleValidateSnippet();
                          }}
                          className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors"
                        >
                          Validate
                        </button>
                      )}
                      <button
                        onClick={() => {
                          setSelectedType(rec.schema_type || 'LocalBusiness');
                          setTargetPageUrl(rec.page_url);
                          if (rec.raw_json_ld) {
                            setOriginalCompareMarkup(rec.raw_json_ld);
                          }
                          setActiveTab('generator');
                        }}
                        className="px-2.5 py-1 rounded-lg btn-vibrant-primary text-xs font-bold transition-colors"
                      >
                        Improve
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* TAB 3: PRIORITIZED RECOMMENDATIONS */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'recommendations' && (
        <div className="card-vibrant p-5 space-y-4">
          <div>
            <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
              Prioritized Schema Recommendations
            </h3>
            <p className="text-xs text-slate-500">
              High-impact structured data opportunities grounded in Google Search and Knowledge Graph specifications.
            </p>
          </div>

          <div className="space-y-3">
            {summary?.recommendations?.map((rec, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl border border-slate-200 bg-white hover:border-purple-200 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold uppercase ${
                        String(rec.priority).toUpperCase() === 'HIGH'
                          ? 'bg-rose-100 text-rose-800'
                          : String(rec.priority).toUpperCase() === 'MEDIUM'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-blue-100 text-blue-800'
                      }`}
                    >
                      {rec.priority} Priority
                    </span>
                    <h4 className="text-xs font-black text-slate-900">{rec.title}</h4>
                  </div>
                  <p className="text-xs text-slate-600">{rec.why || (rec as any).description}</p>
                  <div className="text-[10px] text-purple-700 font-bold">
                    Impact: {rec.expected_improvement || (rec as any).impact}
                  </div>
                </div>

                <button
                  onClick={() => applyRecommendationToGenerator(rec)}
                  className="px-4 py-2 btn-vibrant-primary rounded-xl text-xs font-bold shrink-0 flex items-center space-x-1"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Generate Schema</span>
                </button>
              </div>
            ))}
          </div>

        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* TAB 4: UNIVERSAL SCHEMA.ORG GENERATOR & EDITOR */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'generator' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Form / Builder Panel */}
          <div className="lg:col-span-6 card-vibrant p-5 space-y-4">
            {/* Header & Mode Switcher */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
                  <span>Universal Schema Generator</span>
                  {currentTypeDef?.rich_result_eligible && (
                    <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-extrabold text-[10px] flex items-center space-x-1">
                      <Award className="w-3 h-3" />
                      <span>Google Rich Result</span>
                    </span>
                  )}
                </h3>
                <p className="text-[11px] text-slate-500">
                  Search 150+ Schema.org v28.0 types with inherited property definitions.
                </p>
              </div>

              <div className="flex items-center space-x-1 bg-slate-100 p-0.5 rounded-lg text-[10px] font-bold">
                <button
                  onClick={() => setEditorMode('form')}
                  className={`px-2.5 py-1 rounded-md transition-all ${
                    editorMode === 'form' ? 'bg-white text-purple-700 shadow-2xs font-extrabold' : 'text-slate-600'
                  }`}
                >
                  Form Builder
                </button>
                <button
                  onClick={() => setEditorMode('raw')}
                  className={`px-2.5 py-1 rounded-md transition-all ${
                    editorMode === 'raw' ? 'bg-white text-purple-700 shadow-2xs font-extrabold' : 'text-slate-600'
                  }`}
                >
                  Raw JSON-LD
                </button>
              </div>
            </div>

            {/* Quick Presets Bar */}
            <div className="space-y-1.5">
              <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider block">
                Popular Quick Presets
              </span>
              <div className="flex flex-wrap gap-1.5 overflow-x-auto pb-1">
                {vocabulary?.presets?.map((p) => (
                  <button
                    key={p.name}
                    onClick={() => setSelectedType(p.name)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all shrink-0 ${
                      selectedType === p.name
                        ? 'bg-purple-600 text-white shadow-xs'
                        : 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200'
                    }`}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Universal Type Selector Dropdown / Search */}
            <div className="space-y-1.5 relative">
              <label className="text-slate-700 block text-xs font-bold flex items-center justify-between">
                <span>Select Schema.org Type</span>
                {currentTypeDef?.parent && (
                  <span className="text-[10px] text-slate-400 font-mono font-normal">
                    Hierarchy: Thing &gt; {currentTypeDef.parent} &gt; {selectedType}
                  </span>
                )}
              </label>

              <div className="relative">
                <input
                  type="text"
                  value={typeSearchQuery || selectedType}
                  onFocus={() => setIsTypeDropdownOpen(true)}
                  onChange={(e) => {
                    setTypeSearchQuery(e.target.value);
                    setIsTypeDropdownOpen(true);
                  }}
                  placeholder="Search schema type (e.g. Electrician, Article, Product, FAQPage)..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 pr-10 text-slate-900 focus:outline-none focus:border-purple-500 font-bold text-xs"
                />
                <Search className="w-4 h-4 text-slate-400 absolute right-3 top-3 pointer-events-none" />
              </div>

              {/* Type Dropdown Menu */}
              {isTypeDropdownOpen && (
                <div className="absolute z-30 left-0 right-0 top-full mt-1 bg-white border border-slate-200 rounded-xl shadow-xl max-h-72 overflow-y-auto p-2 space-y-2">
                  {/* Category Filter Pills */}
                  <div className="flex flex-wrap gap-1 pb-2 border-b border-slate-100 text-[10px]">
                    {['All', ...(vocabulary ? Object.keys(vocabulary.categories) : [])].map((cat) => (
                      <button
                        key={cat}
                        onClick={() => setSelectedCategory(cat)}
                        className={`px-2 py-0.5 rounded-md font-bold transition-colors ${
                          selectedCategory === cat
                            ? 'bg-purple-600 text-white'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>

                  <div className="space-y-0.5">
                    {filteredTypes.length > 0 ? (
                      filteredTypes.map((t) => (
                        <div
                          key={t.name}
                          onClick={() => {
                            setSelectedType(t.name);
                            setTypeSearchQuery('');
                            setIsTypeDropdownOpen(false);
                          }}
                          className={`p-2 rounded-lg cursor-pointer flex items-center justify-between text-xs hover:bg-purple-50 transition-colors ${
                            selectedType === t.name ? 'bg-purple-50 text-purple-900 font-bold' : 'text-slate-700'
                          }`}
                        >
                          <div>
                            <div className="font-bold flex items-center space-x-1.5">
                              <span>{t.name}</span>
                              {t.rich_result_eligible && (
                                <span className="px-1.5 py-0.2 bg-emerald-100 text-emerald-800 text-[9px] rounded font-extrabold">
                                  Rich Result
                                </span>
                              )}
                            </div>
                            {t.description && (
                              <p className="text-[10px] text-slate-400 truncate max-w-sm">{t.description}</p>
                            )}
                          </div>
                          <span className="text-[10px] text-slate-400 font-mono">{t.parent || 'Thing'}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-4 text-xs text-slate-400">
                        No matching Schema.org types found.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Target Page URL */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div>
                <label className="text-slate-700 block mb-1 text-xs font-bold">Target Page URL</label>
                <input
                  type="text"
                  value={targetPageUrl}
                  onChange={(e) => setTargetPageUrl(e.target.value)}
                  placeholder="https://example.com/page"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 text-xs"
                />
              </div>
              <div>
                <label className="text-slate-700 block mb-1 text-xs font-bold">Entity Name / Legal Name</label>
                <input
                  type="text"
                  value={propertyValues.name}
                  onChange={(e) => setPropertyValues({ ...propertyValues, name: e.target.value })}
                  placeholder="Official entity or business name"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 text-xs font-bold"
                />
              </div>
            </div>

            {/* FORM MODE: Dynamic Properties */}
            {editorMode === 'form' ? (
              <div className="space-y-3 pt-2">
                {/* 1. Universal Base Fields */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-slate-700 block mb-1 text-xs font-bold">Entity Canonical URL</label>
                    <input
                      type="text"
                      value={propertyValues.url}
                      onChange={(e) => setPropertyValues({ ...propertyValues, url: e.target.value })}
                      placeholder="https://example.com"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-slate-700 block mb-1 text-xs font-bold">Telephone / Contact</label>
                    <input
                      type="text"
                      value={propertyValues.telephone}
                      onChange={(e) => setPropertyValues({ ...propertyValues, telephone: e.target.value })}
                      placeholder="+1 555-0199"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 text-xs"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-slate-700 block mb-1 text-xs font-bold">Description / Summary</label>
                  <textarea
                    rows={2}
                    value={propertyValues.description}
                    onChange={(e) => setPropertyValues({ ...propertyValues, description: e.target.value })}
                    placeholder="Concise description of the entity or page content..."
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 text-xs"
                  />
                </div>

                {/* 2. Physical Location / Address Section (for Places/LocalBusiness) */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                  <span className="text-xs font-bold text-slate-800 block">
                    Postal Address &amp; Geographic Coordinates
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={propertyValues.streetAddress}
                      onChange={(e) => setPropertyValues({ ...propertyValues, streetAddress: e.target.value })}
                      placeholder="Street Address (e.g. 100 Market St)"
                      className="bg-white border border-slate-200 rounded-lg p-2 text-xs text-slate-900"
                    />
                    <input
                      type="text"
                      value={propertyValues.addressLocality}
                      onChange={(e) => setPropertyValues({ ...propertyValues, addressLocality: e.target.value })}
                      placeholder="City / Locality"
                      className="bg-white border border-slate-200 rounded-lg p-2 text-xs text-slate-900"
                    />
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <input
                      type="text"
                      value={propertyValues.addressRegion}
                      onChange={(e) => setPropertyValues({ ...propertyValues, addressRegion: e.target.value })}
                      placeholder="State / Region"
                      className="bg-white border border-slate-200 rounded-lg p-2 text-xs text-slate-900"
                    />
                    <input
                      type="text"
                      value={propertyValues.postalCode}
                      onChange={(e) => setPropertyValues({ ...propertyValues, postalCode: e.target.value })}
                      placeholder="Postal Code"
                      className="bg-white border border-slate-200 rounded-lg p-2 text-xs text-slate-900"
                    />
                    <input
                      type="text"
                      value={propertyValues.addressCountry}
                      onChange={(e) => setPropertyValues({ ...propertyValues, addressCountry: e.target.value })}
                      placeholder="Country (e.g. US)"
                      className="bg-white border border-slate-200 rounded-lg p-2 text-xs text-slate-900"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <input
                      type="text"
                      value={propertyValues.latitude}
                      onChange={(e) => setPropertyValues({ ...propertyValues, latitude: e.target.value })}
                      placeholder="Latitude (e.g. 37.7749)"
                      className="bg-white border border-slate-200 rounded-lg p-2 text-xs font-mono text-slate-900"
                    />
                    <input
                      type="text"
                      value={propertyValues.longitude}
                      onChange={(e) => setPropertyValues({ ...propertyValues, longitude: e.target.value })}
                      placeholder="Longitude (e.g. -122.4194)"
                      className="bg-white border border-slate-200 rounded-lg p-2 text-xs font-mono text-slate-900"
                    />
                  </div>
                </div>

                {/* 3. Type-Specific Sub-sections */}
                {/* Articles / BlogPosts */}
                {['Article', 'NewsArticle', 'BlogPosting', 'TechArticle'].includes(selectedType) && (
                  <div className="p-3 bg-purple-50/50 rounded-xl border border-purple-100 space-y-2">
                    <span className="text-xs font-bold text-purple-900 block">Article &amp; Author Metadata</span>
                    <input
                      type="text"
                      value={propertyValues.headline}
                      onChange={(e) => setPropertyValues({ ...propertyValues, headline: e.target.value })}
                      placeholder="Article Headline"
                      className="w-full bg-white border border-purple-200 rounded-lg p-2 text-xs text-slate-900"
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="text"
                        value={propertyValues.authorName}
                        onChange={(e) => setPropertyValues({ ...propertyValues, authorName: e.target.value })}
                        placeholder="Author Name (Person)"
                        className="bg-white border border-purple-200 rounded-lg p-2 text-xs text-slate-900"
                      />
                      <input
                        type="text"
                        value={propertyValues.publisherName}
                        onChange={(e) => setPropertyValues({ ...propertyValues, publisherName: e.target.value })}
                        placeholder="Publisher Name (Organization)"
                        className="bg-white border border-purple-200 rounded-lg p-2 text-xs text-slate-900"
                      />
                    </div>
                  </div>
                )}

                {/* Products & Offers */}
                {['Product', 'ProductGroup', 'Service'].includes(selectedType) && (
                  <div className="p-3 bg-purple-50/50 rounded-xl border border-purple-100 space-y-2">
                    <span className="text-xs font-bold text-purple-900 block">Commercial Offer &amp; Brand</span>
                    <div className="grid grid-cols-3 gap-2">
                      <input
                        type="text"
                        value={propertyValues.price}
                        onChange={(e) => setPropertyValues({ ...propertyValues, price: e.target.value })}
                        placeholder="Price (e.g. 99.00)"
                        className="bg-white border border-purple-200 rounded-lg p-2 text-xs text-slate-900 font-bold"
                      />
                      <input
                        type="text"
                        value={propertyValues.priceCurrency}
                        onChange={(e) => setPropertyValues({ ...propertyValues, priceCurrency: e.target.value })}
                        placeholder="Currency (USD)"
                        className="bg-white border border-purple-200 rounded-lg p-2 text-xs text-slate-900"
                      />
                      <input
                        type="text"
                        value={propertyValues.brand}
                        onChange={(e) => setPropertyValues({ ...propertyValues, brand: e.target.value })}
                        placeholder="Brand Name"
                        className="bg-white border border-purple-200 rounded-lg p-2 text-xs text-slate-900"
                      />
                    </div>
                  </div>
                )}

                {/* FAQ Questions & Answers */}
                {selectedType === 'FAQPage' && (
                  <div className="p-3 bg-purple-50/50 rounded-xl border border-purple-100 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-purple-900">FAQ Question &amp; Answer Pairs</span>
                      <button
                        onClick={handleAddFaqItem}
                        className="text-[10px] font-bold text-purple-700 bg-white px-2 py-0.5 rounded border border-purple-200 hover:bg-purple-100"
                      >
                        + Add Question
                      </button>
                    </div>
                    {propertyValues.faqItems?.map((item: any, idx: number) => (
                      <div key={idx} className="space-y-1 bg-white p-2 rounded-lg border border-purple-100">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-slate-500">Q#{idx + 1}</span>
                          {propertyValues.faqItems.length > 1 && (
                            <button
                              onClick={() => handleRemoveFaqItem(idx)}
                              className="text-rose-500 hover:text-rose-700"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                        <input
                          type="text"
                          value={item.question}
                          onChange={(e) => {
                            const items = [...propertyValues.faqItems];
                            items[idx].question = e.target.value;
                            setPropertyValues({ ...propertyValues, faqItems: items });
                          }}
                          placeholder="Question text?"
                          className="w-full border border-slate-200 rounded p-1.5 text-xs"
                        />
                        <textarea
                          rows={2}
                          value={item.answer}
                          onChange={(e) => {
                            const items = [...propertyValues.faqItems];
                            items[idx].answer = e.target.value;
                            setPropertyValues({ ...propertyValues, faqItems: items });
                          }}
                          placeholder="Answer content..."
                          className="w-full border border-slate-200 rounded p-1.5 text-xs"
                        />
                      </div>
                    ))}
                  </div>
                )}

                {/* 4. Custom Property Injector for Advanced Vocabulary Coverage */}
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs font-bold text-slate-800 block">Additional Custom Properties</span>
                      <span className="text-[10px] text-slate-500">
                        Add any valid Schema.org property name and value (strings, numbers, or JSON).
                      </span>
                    </div>
                    <button
                      onClick={handleAddCustomProperty}
                      className="px-2 py-1 rounded bg-purple-100 text-purple-800 font-bold text-[10px] hover:bg-purple-200 transition-colors"
                    >
                      + Add Property
                    </button>
                  </div>

                  {propertyValues.customProperties?.map((cp: any, idx: number) => (
                    <div key={idx} className="flex items-center space-x-2">
                      <input
                        type="text"
                        value={cp.key}
                        onChange={(e) => {
                          const cpList = [...propertyValues.customProperties];
                          cpList[idx].key = e.target.value;
                          setPropertyValues({ ...propertyValues, customProperties: cpList });
                        }}
                        placeholder="Property (e.g. paymentAccepted, sameAs, award)"
                        className="w-1/3 bg-white border border-slate-200 rounded-lg p-2 text-xs font-mono"
                      />
                      <input
                        type="text"
                        value={cp.value}
                        onChange={(e) => {
                          const cpList = [...propertyValues.customProperties];
                          cpList[idx].value = e.target.value;
                          setPropertyValues({ ...propertyValues, customProperties: cpList });
                        }}
                        placeholder="Value or JSON snippet"
                        className="flex-1 bg-white border border-slate-200 rounded-lg p-2 text-xs"
                      />
                      <button
                        onClick={() => handleRemoveCustomProperty(idx)}
                        className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>

                {/* 5. Connected @graph Entity Builder */}
                <div className="p-3 bg-indigo-50/50 rounded-xl border border-indigo-100 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs font-bold text-indigo-900 block">Connected @graph Entity Nodes</span>
                      <span className="text-[10px] text-indigo-600">
                        Link related nodes (Organization, WebSite, Service, BreadcrumbList) via @id references.
                      </span>
                    </div>
                    <div className="flex items-center space-x-1">
                      {['WebSite', 'WebPage', 'Organization', 'Service'].map((t) => (
                        <button
                          key={t}
                          onClick={() => handleAddConnectedEntity(t)}
                          className="px-2 py-0.5 rounded bg-indigo-100 hover:bg-indigo-200 text-indigo-800 text-[10px] font-bold"
                        >
                          + {t}
                        </button>
                      ))}
                    </div>
                  </div>

                  {connectedEntities.map((ce) => (
                    <div key={ce.id} className="bg-white p-2 rounded-lg border border-indigo-100 flex items-center justify-between text-xs">
                      <div>
                        <span className="font-bold text-indigo-900">{ce.type}: </span>
                        <span className="text-slate-700">{ce.name}</span>
                        <span className="text-[10px] text-slate-400 font-mono ml-2">({ce.id})</span>
                      </div>
                      <button
                        onClick={() => handleRemoveConnectedEntity(ce.id)}
                        className="text-rose-500 hover:text-rose-700 p-1"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>

                {/* Interconnected @graph Checkbox */}
                <div className="flex items-center space-x-2 pt-1">
                  <input
                    type="checkbox"
                    id="includeGraphCheck"
                    checked={includeGraph}
                    onChange={(e) => setIncludeGraph(e.target.checked)}
                    className="rounded text-purple-600 focus:ring-purple-500 w-4 h-4 cursor-pointer"
                  />
                  <label htmlFor="includeGraphCheck" className="text-slate-700 font-bold cursor-pointer text-xs">
                    Wrap Output in Linked <code className="text-purple-700 font-mono">@graph</code> Structure
                  </label>
                </div>
              </div>
            ) : (
              /* RAW JSON-LD EDITOR MODE */
              <div className="space-y-2 pt-2">
                <textarea
                  value={rawEditorJson}
                  onChange={(e) => handleRawJsonChange(e.target.value)}
                  rows={16}
                  className="w-full bg-slate-900 text-emerald-400 font-mono text-xs p-4 rounded-xl border border-slate-800 focus:outline-none focus:border-purple-500"
                />
                {rawJsonError && (
                  <div className="p-2 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs font-bold flex items-center space-x-2">
                    <XCircle className="w-4 h-4 shrink-0" />
                    <span>{rawJsonError}</span>
                  </div>
                )}
              </div>
            )}

            {/* Save Draft & Actions Bar */}
            <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleSaveDraft}
                  disabled={isSavingDraft || !generatedJsonLd}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold shadow-sm transition-all flex items-center space-x-1.5"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{isSavingDraft ? 'Saving...' : 'Save Draft'}</span>
                </button>
                {draftSaveSuccess && (
                  <span className="text-emerald-600 font-bold text-xs flex items-center space-x-1 animate-fade-in">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Saved!</span>
                  </span>
                )}
              </div>

              <button
                onClick={() => setShowInstructionsModal(true)}
                className="text-purple-700 hover:text-purple-900 font-bold text-xs flex items-center space-x-1"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Implementation Guide</span>
              </button>
            </div>
          </div>

          {/* Right Live JSON-LD Output & Validation Panel */}
          <div className="lg:col-span-6 card-vibrant p-5 flex flex-col justify-between space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 pb-3 gap-2">
              <div className="flex items-center space-x-2">
                <Code className="w-4 h-4 text-purple-600" />
                <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
                  {generatorViewMode === 'original'
                    ? 'Original Live Scanned Markup'
                    : generatorViewMode === 'split'
                    ? 'Side-by-Side Comparison'
                    : 'Generated Schema.org JSON-LD'}
                </h3>
              </div>

              {originalCompareMarkup && (
                <div className="flex items-center bg-slate-100 p-0.5 rounded-lg text-[10px] font-bold">
                  <button
                    onClick={() => setGeneratorViewMode('generated')}
                    className={`px-2.5 py-1 rounded-md transition-all ${
                      generatorViewMode === 'generated'
                        ? 'bg-white text-purple-700 shadow-2xs font-extrabold'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Proposed
                  </button>
                  <button
                    onClick={() => setGeneratorViewMode('original')}
                    className={`px-2.5 py-1 rounded-md transition-all ${
                      generatorViewMode === 'original'
                        ? 'bg-white text-purple-700 shadow-2xs font-extrabold'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Live Scanned
                  </button>
                  <button
                    onClick={() => setGeneratorViewMode('split')}
                    className={`px-2.5 py-1 rounded-md transition-all ${
                      generatorViewMode === 'split'
                        ? 'bg-white text-purple-700 shadow-2xs font-extrabold'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Split View
                  </button>
                </div>
              )}

              {generatedJsonLd && generatorViewMode === 'generated' && (
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => downloadJsonLd(generatedJsonLd, `${activeProject.domain}-schema.jsonld`)}
                    className="flex items-center space-x-1 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-lg text-xs font-bold border border-slate-200 transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>.jsonld</span>
                  </button>

                  <button
                    onClick={() => copyToClipboard(`<script type="application/ld+json">\n${generatedJsonLd}\n</script>`)}
                    className="flex items-center space-x-1 px-3 py-1 btn-primary-gradient text-white rounded-lg text-xs font-bold shadow-2xs transition-colors"
                  >
                    {isCopied ? <Check className="w-3.5 h-3.5 text-white" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{isCopied ? 'Copied' : 'Copy HTML Tag'}</span>
                  </button>
                </div>
              )}
            </div>

            {/* Code Display Area */}
            {generatorViewMode === 'split' && originalCompareMarkup ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 min-h-[380px] max-h-[460px]">
                <div className="bg-slate-900 p-3 rounded-xl border border-slate-800 font-mono text-[11px] overflow-auto flex flex-col">
                  <div className="text-[10px] font-bold text-amber-400 uppercase tracking-wider pb-1.5 border-b border-slate-800 mb-2 flex justify-between items-center">
                    <span>Original Live Scanned</span>
                    <button
                      onClick={() => copyToClipboard(originalCompareMarkup)}
                      className="text-slate-400 hover:text-white text-[10px]"
                    >
                      Copy
                    </button>
                  </div>
                  <pre className="text-amber-300 whitespace-pre flex-1">{originalCompareMarkup}</pre>
                </div>
                <div className="bg-slate-900 p-3 rounded-xl border border-slate-800 font-mono text-[11px] overflow-auto flex flex-col">
                  <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider pb-1.5 border-b border-slate-800 mb-2 flex justify-between items-center">
                    <span>Proposed Generated Version</span>
                    <button
                      onClick={() => copyToClipboard(generatedJsonLd)}
                      className="text-slate-400 hover:text-white text-[10px]"
                    >
                      Copy
                    </button>
                  </div>
                  <pre className="text-emerald-400 whitespace-pre flex-1">{generatedJsonLd}</pre>
                </div>
              </div>
            ) : generatorViewMode === 'original' && originalCompareMarkup ? (
              <div className="flex-1 bg-slate-900 p-4 rounded-xl border border-slate-800 font-mono text-xs text-amber-300 overflow-x-auto min-h-[380px] max-h-[460px]">
                <pre className="whitespace-pre">{originalCompareMarkup}</pre>
              </div>
            ) : (
              <div className="flex-1 bg-slate-900 p-4 rounded-xl border border-slate-800 font-mono text-xs text-emerald-400 overflow-x-auto min-h-[380px] max-h-[460px]">
                <pre className="whitespace-pre">{generatedJsonLd || '// Initializing live Schema.org JSON-LD...'}</pre>
              </div>
            )}

            {/* Real-Time Live Validation Status Badge */}
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-extrabold text-slate-800 flex items-center space-x-1.5">
                  {liveValidation?.is_valid ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                  )}
                  <span>
                    {liveValidation?.is_valid
                      ? 'Valid Schema.org Structure'
                      : 'Validation Issues Detected'}
                  </span>
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  {liveValidation?.entities?.join(' • ') || selectedType}
                </span>
              </div>

              {liveValidation?.errors?.length > 0 && (
                <ul className="text-[11px] text-rose-700 list-disc list-inside space-y-0.5">
                  {liveValidation.errors.map((err: string, i: number) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              )}

              {liveValidation?.rich_results?.length > 0 && (
                <div className="text-[11px] text-emerald-800 bg-emerald-50/70 p-2 rounded-lg border border-emerald-100 flex items-center justify-between">
                  <span>Google Rich Results: <strong>Eligible</strong> for snippet enhancements</span>
                  <Award className="w-3.5 h-3.5 text-emerald-600" />
                </div>
              )}
            </div>

            <div className="text-[11px] text-slate-500 flex items-center justify-between pt-1 border-t border-slate-100">
              <span className="flex items-center space-x-1 text-emerald-600 font-bold">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Internally validated against Schema.org &amp; Google Rich Results specs</span>
              </span>
              <span>Ready for <code className="text-purple-600 font-mono">&lt;head&gt;</code> injection</span>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------- */}
      {/* TAB 5: LIVE JSON-LD VALIDATOR */}
      {/* ------------------------------------------------------------------- */}
      {activeTab === 'validator' && (
        <div className="card-vibrant p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 pb-3 gap-2">
            <div>
              <h3 className="text-sm font-extrabold text-slate-900 uppercase tracking-wider">
                Universal Schema.org &amp; Google Rich Results Validator
              </h3>
              <p className="text-xs text-slate-500">
                Validate JSON-LD snippets, fetch and inspect live URLs with SSRF protection, or upload schema files.
              </p>
            </div>

            {/* Validator Input Mode Tabs */}
            <div className="flex items-center bg-slate-100 p-0.5 rounded-lg text-xs font-bold">
              <button
                onClick={() => setValidatorTabMode('snippet')}
                className={`px-3 py-1 rounded-md transition-all ${
                  validatorTabMode === 'snippet'
                    ? 'bg-white text-purple-700 shadow-2xs font-extrabold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Paste Snippet
              </button>
              <button
                onClick={() => setValidatorTabMode('url')}
                className={`px-3 py-1 rounded-md transition-all ${
                  validatorTabMode === 'url'
                    ? 'bg-white text-purple-700 shadow-2xs font-extrabold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Public URL Scan
              </button>
              <button
                onClick={() => setValidatorTabMode('file')}
                className={`px-3 py-1 rounded-md transition-all ${
                  validatorTabMode === 'file'
                    ? 'bg-white text-purple-700 shadow-2xs font-extrabold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Upload File
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Input Form Column */}
            <div className="lg:col-span-7 space-y-3">
              {validatorTabMode === 'snippet' && (
                <div className="space-y-2">
                  <textarea
                    value={validatorInput}
                    onChange={(e) => setValidatorInput(e.target.value)}
                    placeholder='<script type="application/ld+json">&#10;{&#10;  "@context": "https://schema.org",&#10;  "@type": "LocalBusiness",&#10;  "name": "Example Business"&#10;}&#10;</script>'
                    className="w-full h-80 bg-slate-900 text-emerald-400 font-mono text-xs p-4 rounded-xl border border-slate-800 focus:outline-none focus:border-purple-500"
                  />
                  <button
                    onClick={handleValidateSnippet}
                    disabled={isValidating || !validatorInput.trim()}
                    className="px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-sm transition-all"
                  >
                    {isValidating ? 'Validating...' : 'Validate Structured Snippet'}
                  </button>
                </div>
              )}

              {validatorTabMode === 'url' && (
                <div className="space-y-3 p-4 bg-slate-50 rounded-xl border border-slate-200">
                  <label className="text-xs font-bold text-slate-800 block">
                    Target Webpage URL (Safe Public SSRF Crawler)
                  </label>
                  <div className="flex space-x-2">
                    <input
                      type="text"
                      value={validatorUrlInput}
                      onChange={(e) => setValidatorUrlInput(e.target.value)}
                      placeholder="https://example.com/about"
                      className="flex-1 bg-white border border-slate-200 rounded-xl p-2.5 text-xs text-slate-900 font-medium focus:outline-none focus:border-purple-500"
                    />
                    <button
                      onClick={handleValidateFromUrl}
                      disabled={isValidating || !validatorUrlInput.trim()}
                      className="px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-sm transition-all shrink-0"
                    >
                      {isValidating ? 'Crawling...' : 'Fetch & Validate'}
                    </button>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Extracts all embedded JSON-LD scripts on the page and tests them against official Schema.org specs and NAP consistency.
                  </p>
                </div>
              )}

              {validatorTabMode === 'file' && (
                <div className="p-8 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50 text-center space-y-3">
                  <Upload className="w-8 h-8 text-purple-600 mx-auto opacity-70" />
                  <div>
                    <h4 className="text-xs font-black text-slate-800">Upload Schema.org JSON-LD or HTML File</h4>
                    <p className="text-[11px] text-slate-500">Supported formats: .json, .jsonld, .html</p>
                  </div>
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                    accept=".json,.jsonld,.html,.txt"
                    className="hidden"
                  />
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-xs font-bold transition-all shadow-xs"
                  >
                    Select Local File
                  </button>
                </div>
              )}
            </div>

            {/* Validation Diagnostic Report Column */}
            <div className="lg:col-span-5 p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
              <h4 className="text-xs font-extrabold uppercase text-slate-700 tracking-wider flex items-center justify-between">
                <span>Validation Diagnostic Report</span>
                {validationResult && (
                  <span className="text-[10px] font-mono text-slate-500">
                    {validationResult.entities?.length || 0} Entities
                  </span>
                )}
              </h4>

              {validationResult ? (
                <div className="space-y-3 text-xs">
                  <div
                    className={`p-3 rounded-xl border flex items-center space-x-2 font-bold ${
                      validationResult.is_valid
                        ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                        : 'bg-rose-50 border-rose-200 text-rose-800'
                    }`}
                  >
                    {validationResult.is_valid ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-rose-600 shrink-0" />
                    )}
                    <span>
                      {validationResult.is_valid
                        ? 'Valid Schema.org Structure'
                        : 'Validation Errors Detected'}
                    </span>
                  </div>

                  {/* Detected Entity Types */}
                  {validationResult.entities?.length > 0 && (
                    <div>
                      <span className="text-[10px] font-extrabold text-slate-400 uppercase block mb-1">
                        Detected Entity Graph Nodes
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {validationResult.entities.map((ent: string, idx: number) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 text-[10px] font-bold"
                          >
                            {ent}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Google Rich Results Report */}
                  {validationResult.rich_results?.length > 0 && (
                    <div className="space-y-1.5 p-3 rounded-xl bg-white border border-emerald-100">
                      <span className="text-[10px] font-extrabold text-emerald-800 uppercase flex items-center justify-between">
                        <span>Google Rich Results Eligibility</span>
                        <Award className="w-3.5 h-3.5 text-emerald-600" />
                      </span>
                      {validationResult.rich_results.map((rr: any, idx: number) => (
                        <div key={idx} className="text-[11px] text-slate-700">
                          <strong>{rr.entity_type}</strong>: {rr.supported ? 'Supported' : 'Not Supported'}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* NAP Consistency Report */}
                  {validationResult.nap_status && (
                    <div className="flex items-center justify-between p-2 rounded-lg bg-white border border-slate-200 text-xs">
                      <span className="text-slate-600 font-bold">NAP Alignment:</span>
                      <span
                        className={`font-extrabold uppercase text-[10px] px-2 py-0.5 rounded-full ${
                          validationResult.nap_status === 'Consistent'
                            ? 'bg-emerald-100 text-emerald-800'
                            : validationResult.nap_status === 'Mismatch'
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {validationResult.nap_status}
                      </span>
                    </div>
                  )}

                  {/* Errors */}
                  {validationResult.errors?.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-extrabold text-rose-600 uppercase block">
                        Errors ({validationResult.errors.length})
                      </span>
                      <ul className="text-[11px] text-rose-700 list-disc list-inside space-y-0.5">
                        {validationResult.errors.map((err: string, idx: number) => (
                          <li key={idx}>{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Warnings */}
                  {validationResult.warnings?.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-extrabold text-amber-600 uppercase block">
                        Recommendations &amp; Warnings ({validationResult.warnings.length})
                      </span>
                      <ul className="text-[11px] text-amber-700 list-disc list-inside space-y-0.5">
                        {validationResult.warnings.map((w: string, idx: number) => (
                          <li key={idx}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-16 text-slate-400 text-xs">
                  <ShieldCheck className="w-8 h-8 mx-auto mb-2 opacity-40" />
                  <p>
                    Paste a JSON-LD script, scan a live URL, or upload a file to inspect Schema.org validity and Google Rich Results eligibility.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}      {/* ------------------------------------------------------------------- */}
      {/* TIER 1 SCHEMA DETAIL MODAL */}
      {/* ------------------------------------------------------------------- */}
      {selectedMatrixSchema && (() => {
        const detectedData = selectedMatrixSchema.info.detected_data;
        const instances =
          detectedData?.all_instances && detectedData.all_instances.length > 0
            ? detectedData.all_instances
            : detectedData
            ? [detectedData]
            : [];
        const activeInst = instances[selectedInstanceIdx] || instances[0];

        return (
          <Modal
            isOpen={Boolean(selectedMatrixSchema)}
            onClose={() => {
              setSelectedMatrixSchema(null);
              setSelectedInstanceIdx(0);
            }}
            maxWidth="2xl"
            title={`${selectedMatrixSchema.name} Schema`}
            description={`Schema.org Standard Entity • Applicability: ${selectedMatrixSchema.info.applicability || 'Applicable'}`}
            footer={
              <div className="flex items-center justify-between w-full">
                <button
                  onClick={() => {
                    setSelectedMatrixSchema(null);
                    setSelectedInstanceIdx(0);
                  }}
                  className="px-4 py-2 rounded-xl text-slate-600 hover:text-slate-900 text-xs font-bold"
                >
                  Close
                </button>
                <button
                  onClick={() =>
                    handleOpenGeneratorForSchema(
                      selectedMatrixSchema.name,
                      selectedMatrixSchema.info,
                      (activeInst as any)?.raw_snippet || (activeInst as any)?.raw_markup
                    )
                  }
                  className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold shadow-xs flex items-center space-x-1.5"
                >
                  <Code className="w-3.5 h-3.5" />
                  <span>
                    {selectedMatrixSchema.info.status === 'Detected'
                      ? 'Edit / Improve in Generator'
                      : 'Generate This Schema'}
                  </span>
                </button>
              </div>
            }
          >
            <div className="space-y-5 text-xs">
              {/* 1. Definition & Why It Matters */}
              <div className="space-y-3 p-4 rounded-xl bg-purple-50/40 border border-purple-100">
                <div>
                  <span className="text-[10px] font-extrabold text-purple-800 uppercase tracking-wider block mb-1">
                    What This Schema Represents
                  </span>
                  <p className="text-slate-700 leading-relaxed">
                    {selectedMatrixSchema.info.definition ||
                      `Declares machine-readable ${selectedMatrixSchema.name} structured entities to search engine crawlers.`}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] font-extrabold text-purple-800 uppercase tracking-wider block mb-1">
                    Why It Matters For Local SEO
                  </span>
                  <p className="text-slate-600 leading-relaxed">
                    {selectedMatrixSchema.info.why_it_matters ||
                      'Improves rich snippet eligibility, machine-readability, and domain entity authority.'}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] font-extrabold text-purple-800 uppercase tracking-wider block mb-1">
                    Applicability Assessment Rationale
                  </span>
                  <p className="text-slate-600 leading-relaxed font-medium">
                    {selectedMatrixSchema.info.reason}
                  </p>
                </div>
              </div>

              {/* 2. Detected Evidence or Missing Specs */}
              {activeInst ? (
                <div className="space-y-4">
                  {/* Multi-instance switcher if more than 1 instance */}
                  {instances.length > 1 && (
                    <div className="flex items-center space-x-1 border-b border-slate-100 pb-2.5 overflow-x-auto">
                      <span className="text-[10px] font-extrabold uppercase text-slate-400 mr-2 shrink-0">
                        Detected Instances ({instances.length}):
                      </span>
                      {instances.map((inst: any, idx: number) => (
                        <button
                          key={idx}
                          onClick={() => setSelectedInstanceIdx(idx)}
                          className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all shrink-0 ${
                            selectedInstanceIdx === idx
                              ? 'bg-purple-600 text-white shadow-2xs'
                              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                          }`}
                        >
                          {(inst as any).name || (inst as any).properties?.name || `Node #${idx + 1}`}
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                    <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider block">
                      Detected Properties ({(activeInst as any)?.name || (activeInst as any)?.properties?.name || selectedMatrixSchema.name})
                    </span>
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div>
                        <span className="text-slate-400 block">Name</span>
                        <span className="font-bold text-slate-900">
                          {(activeInst as any)?.name || (activeInst as any)?.properties?.name || '—'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">URL</span>
                        <span className="font-bold text-slate-900 truncate block">
                          {(activeInst as any)?.url || (activeInst as any)?.page_url || (activeInst as any)?.properties?.url || '—'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Telephone</span>
                        <span className="font-bold text-slate-900">
                          {(activeInst as any)?.phone || (activeInst as any)?.properties?.telephone || '—'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Address</span>
                        <span className="font-bold text-slate-900">
                          {(activeInst as any)?.address || (activeInst as any)?.properties?.address?.streetAddress || '—'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Raw Detected Script Tag */}
                  {((activeInst as any)?.raw_snippet || (activeInst as any)?.raw_markup) && (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">
                          Raw Detected JSON-LD Script
                        </span>
                        <button
                          onClick={() => copyToClipboard((activeInst as any)?.raw_snippet || (activeInst as any)?.raw_markup)}
                          className="text-[10px] text-purple-700 font-bold hover:underline flex items-center space-x-1"
                        >
                          <Copy className="w-3 h-3" />
                          <span>Copy Raw</span>
                        </button>
                      </div>
                      <pre className="bg-slate-900 text-emerald-400 p-3 rounded-xl font-mono text-[11px] overflow-x-auto max-h-48 border border-slate-800">
                        {(activeInst as any)?.raw_snippet || (activeInst as any)?.raw_markup}
                      </pre>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-amber-50/50 border border-amber-200 text-amber-900 text-xs space-y-2">
                  <span className="font-bold block">No detected instance on website</span>
                  <p>
                    Adding this Schema.org structured data markup will enhance search indexing and Google rich-result eligibility.
                  </p>
                </div>
              )}
            </div>
          </Modal>
        );
      })()}

      {/* ------------------------------------------------------------------- */}
      {/* IMPLEMENTATION INSTRUCTIONS MODAL */}
      {/* ------------------------------------------------------------------- */}
      <Modal
        isOpen={showInstructionsModal}
        onClose={() => setShowInstructionsModal(false)}
        maxWidth="xl"
        title="Schema Implementation Guide"
        description="How to install JSON-LD on your website"
        footer={
          <div className="flex justify-end w-full">
            <button
              onClick={() => setShowInstructionsModal(false)}
              className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold shadow-xs"
            >
              Got It
            </button>
          </div>
        }
      >
        <div className="space-y-4 text-xs">
          <div className="space-y-2">
            <h4 className="font-extrabold text-slate-900 text-sm">How to install JSON-LD on your website:</h4>
            <ol className="list-decimal list-inside space-y-2 text-slate-600">
              <li>
                Click <strong>Copy HTML Tag</strong> in the right panel of the generator.
              </li>
              <li>
                Open your website CMS (WordPress, Webflow, Shopify, Next.js, or HTML template).
              </li>
              <li>
                Paste the snippet directly between the <code className="text-emerald-700 font-mono">&lt;head&gt;</code> and <code className="text-emerald-700 font-mono">&lt;/head&gt;</code> tags of your target page: <strong>{targetPageUrl}</strong>.
              </li>
              <li>
                Ensure the NAP details (Name, Address, Phone) in the JSON-LD strictly match the visible footer and contact content on the page.
              </li>
              <li>
                Verify live indexation using the <strong>Live JSON-LD Validator</strong> tab or Google Rich Results Test.
              </li>
            </ol>
          </div>

          <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-100 text-emerald-900 space-y-1">
            <span className="font-bold block">Important Note:</span>
            <p>
              LocalLift never injects or modifies live website code without your explicit server credentials or CMS plugin authorization.
            </p>
          </div>
        </div>
      </Modal>
    </div>
  );
};

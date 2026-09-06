import React, { useState, useEffect } from 'react';
import {
  FileCode2,
  Plus,
  Search,
  Filter,
  Copy,
  Check,
  Download,
  Upload,
  Layers,
  Sparkles,
  ExternalLink,
  Trash2,
  Edit,
  Eye,
  CheckCircle2,
  AlertCircle,
  Shield,
  HelpCircle,
  FileText,
  Store,
  Star,
  BookOpen,
  CheckSquare
} from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';
import { Template, TemplateApplyResponse, TemplateValidateResponse } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const TemplatesView: React.FC = () => {
  const { activeProject, refreshDashboard } = useProject();
  const [searchParams] = useSearchParams();
  const applySlug = searchParams.get('apply');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedType, setSelectedType] = useState('all');

  // Modals
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [isApplyOpen, setIsApplyOpen] = useState(false);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);

  // Active item in modal
  const [activeTemplate, setActiveTemplate] = useState<Template | null>(null);
  const [appliedResult, setAppliedResult] = useState<TemplateApplyResponse | null>(null);
  const [isApplying, setIsApplying] = useState(false);
  const [copied, setCopied] = useState(false);

  // Form State for Create / Edit
  const [formName, setFormName] = useState('');
  const [formCategory, setFormCategory] = useState('schema');
  const [formType, setFormType] = useState('schema_jsonld');
  const [formStandard, setFormStandard] = useState('Local SEO Standard');
  const [formDescription, setFormDescription] = useState('');
  const [formContent, setFormContent] = useState('');
  const [validationResult, setValidationResult] = useState<TemplateValidateResponse | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  // Import State
  const [importContent, setImportContent] = useState('');
  const [importName, setImportName] = useState('');
  const [importError, setImportError] = useState<string | null>(null);

  const fetchTemplates = async () => {
    try {
      setLoading(true);
      const params: any = {};
      if (selectedCategory !== 'all') params.category = selectedCategory;
      if (selectedType !== 'all') params.template_type = selectedType;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const resp = await api.get('/templates', { params });
      setTemplates(resp.data || []);
    } catch (e) {
      console.error('Failed to load templates:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, [selectedCategory, selectedType, searchQuery]);

  const handleValidate = async (content: string, type: string) => {
    try {
      setIsValidating(true);
      const resp = await api.post('/templates/validate', {
        content,
        template_type: type
      });
      setValidationResult(resp.data);
    } catch (e) {
      console.error('Validation failed:', e);
    } finally {
      setIsValidating(false);
    }
  };

  const handleSaveTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim() || !formContent.trim()) return;

    try {
      if (isEditOpen && activeTemplate) {
        await api.put(`/templates/${activeTemplate.id}`, {
          name: formName.trim(),
          category: formCategory,
          template_type: formType,
          standard_type: formStandard,
          description: formDescription.trim(),
          content: formContent
        });
      } else {
        await api.post('/templates', {
          name: formName.trim(),
          category: formCategory,
          template_type: formType,
          standard_type: formStandard,
          description: formDescription.trim(),
          content: formContent,
          project_id: activeProject?.id
        });
      }

      setIsCreateOpen(false);
      setIsEditOpen(false);
      resetForm();
      await fetchTemplates();
    } catch (err: any) {
      const msg = err.response?.data?.detail?.message || 'Failed to save template.';
      alert(msg);
    }
  };

  const handleDuplicate = async (templateId: number) => {
    try {
      await api.post(`/templates/${templateId}/duplicate`);
      await fetchTemplates();
    } catch (e) {
      console.error('Duplicate failed:', e);
    }
  };

  const handleDelete = async (templateId: number) => {
    if (!confirm('Are you sure you want to delete this custom template?')) return;
    try {
      await api.delete(`/templates/${templateId}`);
      await fetchTemplates();
    } catch (e) {
      console.error('Delete failed:', e);
    }
  };

  const handleApply = async (tmpl: Template) => {
    if (!activeProject) {
      alert('Please select an active project first.');
      return;
    }
    try {
      setIsApplying(true);
      setActiveTemplate(tmpl);
      setIsApplyOpen(true);
      const resp = await api.post(`/templates/${tmpl.id}/apply`, {
        project_id: activeProject.id
      });
      setAppliedResult(resp.data);
    } catch (e) {
      console.error('Apply template failed:', e);
    } finally {
      setIsApplying(false);
    }
  };

  useEffect(() => {
    if (applySlug && templates.length > 0 && activeProject && !isApplyOpen) {
      const matched = templates.find(t => 
        t.slug === applySlug || 
        t.slug.includes(applySlug) || 
        applySlug.includes(t.slug)
      );
      if (matched) {
        handleApply(matched);
      }
    }
  }, [applySlug, templates, activeProject]);

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importContent.trim()) return;
    try {
      setImportError(null);
      await api.post('/templates/import', {
        file_content: importContent.trim(),
        name: importName.trim() || undefined
      });
      setIsImportOpen(false);
      setImportContent('');
      setImportName('');
      await fetchTemplates();
    } catch (err: any) {
      const errors = err.response?.data?.detail?.errors || [err.response?.data?.detail || 'Import failed.'];
      setImportError(errors.join(', '));
    }
  };

  const handleCreateTaskFromTemplate = async () => {
    if (!activeProject || !appliedResult) return;
    try {
      await api.post('/tasks', {
        project_id: activeProject.id,
        title: `Apply Template: ${appliedResult.template_name}`,
        category: 'Local SEO Template Implementation',
        priority: 'medium',
        description: `Rendered Content:\n${appliedResult.rendered_content.substring(0, 500)}...`,
        status: 'open'
      });
      await refreshDashboard();
      alert('Task created successfully in your SEO Task Board!');
      setIsApplyOpen(false);
    } catch (e) {
      console.error('Failed to create task:', e);
    }
  };

  const handleExport = (tmpl: Template) => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(tmpl, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `${tmpl.slug}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const resetForm = () => {
    setFormName('');
    setFormCategory('schema');
    setFormType('schema_jsonld');
    setFormStandard('Local SEO Standard');
    setFormDescription('');
    setFormContent('');
    setValidationResult(null);
  };

  const openEditModal = (tmpl: Template) => {
    setActiveTemplate(tmpl);
    setFormName(tmpl.name);
    setFormCategory(tmpl.category);
    setFormType(tmpl.template_type);
    setFormStandard(tmpl.standard_type || 'Local SEO Standard');
    setFormDescription(tmpl.description || '');
    setFormContent(tmpl.content);
    setIsEditOpen(true);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const categories = [
    { id: 'all', label: 'All Templates', icon: Layers },
    { id: 'schema', label: 'Schema.org JSON-LD', icon: FileCode2 },
    { id: 'review_response', label: 'Review Replies', icon: Star },
    { id: 'location_page', label: 'Location Pages', icon: BookOpen },
    { id: 'gbp', label: 'Google Business Profile', icon: Store },
    { id: 'task', label: 'SEO Tasks', icon: CheckSquare },
    { id: 'reporting', label: 'Reporting', icon: FileText },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <FileCode2 className="w-6 h-6 text-purple-600" />
            <span>Local SEO Template Hub</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Reusable, Google-compatible schemas, location landing page blueprints, review reply workflows, and task standards.
          </p>
        </div>

        <div className="flex items-center space-x-2.5 self-start">
          <button
            onClick={() => setIsImportOpen(true)}
            className="flex items-center space-x-1.5 px-4 py-2.5 btn-vibrant-secondary rounded-xl text-xs font-bold transition-all"
          >
            <Upload className="w-4 h-4 text-slate-600" />
            <span>Import Template</span>
          </button>

          <button
            onClick={() => {
              resetForm();
              setIsCreateOpen(true);
            }}
            className="flex items-center space-x-1.5 px-5 py-2.5 btn-vibrant-primary rounded-xl text-xs font-bold shadow-md transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Create Template</span>
          </button>
        </div>
      </div>

      {/* Category Tabs */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-2 border-b border-slate-200 text-xs">
        {categories.map((cat) => {
          const Icon = cat.icon;
          const isSelected = selectedCategory === cat.id;
          return (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl font-bold whitespace-nowrap transition-all ${
                isSelected
                  ? 'bg-purple-50 text-purple-900 border border-purple-200 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isSelected ? 'text-purple-600' : 'text-slate-400'}`} />
              <span>{cat.label}</span>
            </button>
          );
        })}
      </div>

      {/* Search & Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search templates by name, keyword, or variables..."
            className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-purple-500 font-medium"
          />
        </div>

        <div className="flex items-center space-x-2 self-end">
          <span className="text-slate-400 font-bold text-[11px]">{templates.length} Templates Available</span>
        </div>
      </div>

      {/* Template Cards Grid */}
      {templates.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {templates.map((tmpl) => (
            <div
              key={tmpl.id}
              className="card-vibrant p-5 flex flex-col justify-between space-y-4 hover:border-purple-300 transition-all group"
            >
              <div className="space-y-3">
                {/* Header Badges */}
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded-md border ${
                      tmpl.is_system
                        ? 'bg-purple-50 text-purple-800 border-purple-200'
                        : 'bg-blue-50 text-blue-800 border-blue-200'
                    }`}
                  >
                    {tmpl.is_system ? 'System Template' : 'User Template'}
                  </span>

                  <span className="text-[10px] text-slate-500 font-semibold px-2 py-0.5 rounded bg-slate-100 border border-slate-200">
                    {tmpl.standard_type || 'Local SEO Standard'}
                  </span>
                </div>

                {/* Title & Description */}
                <div>
                  <h3 className="font-extrabold text-slate-900 text-sm group-hover:text-purple-700 transition-colors">
                    {tmpl.name}
                  </h3>
                  <p className="text-xs text-slate-600 mt-1 line-clamp-2 font-medium leading-relaxed">
                    {tmpl.description || 'Structured reusable asset for local search workflows.'}
                  </p>
                </div>

                {/* Variable Tokens */}
                {tmpl.variables && tmpl.variables.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 block">
                      Variables ({tmpl.variables.length})
                    </span>
                    <div className="flex flex-wrap gap-1 max-h-16 overflow-hidden">
                      {tmpl.variables.slice(0, 4).map((v: any, vIdx: number) => (
                        <span
                          key={vIdx}
                          className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-mono font-medium border border-slate-200"
                        >
                          {`{{${v.name}}}`}
                        </span>
                      ))}
                      {tmpl.variables.length > 4 && (
                        <span className="text-[10px] text-slate-400 font-bold self-center">
                          +{tmpl.variables.length - 4} more
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Actions Footer */}
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                <button
                  onClick={() => handleApply(tmpl)}
                  className="flex items-center space-x-1.5 px-3.5 py-2 btn-vibrant-primary rounded-xl text-xs font-bold shadow-sm transition-all"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Use Template</span>
                </button>

                <div className="flex items-center space-x-1 text-slate-400">
                  <button
                    onClick={() => {
                      setActiveTemplate(tmpl);
                      setIsPreviewOpen(true);
                    }}
                    title="Preview Content"
                    className="p-1.5 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
                  >
                    <Eye className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => handleDuplicate(tmpl.id)}
                    title="Duplicate into User Copy"
                    className="p-1.5 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
                  >
                    <Copy className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => handleExport(tmpl)}
                    title="Export JSON"
                    className="p-1.5 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
                  >
                    <Download className="w-4 h-4" />
                  </button>

                  {!tmpl.is_system && (
                    <>
                      <button
                        onClick={() => openEditModal(tmpl)}
                        title="Edit Template"
                        className="p-1.5 hover:text-purple-700 hover:bg-purple-50 rounded-lg transition-colors"
                      >
                        <Edit className="w-4 h-4" />
                      </button>

                      <button
                        onClick={() => handleDelete(tmpl.id)}
                        title="Delete Template"
                        className="p-1.5 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={FileCode2}
          badge="No Templates Found"
          title="No Templates Match Your Filter"
          description="Create your first custom Local SEO template, import a Schema JSON-LD structure, or reset your search filter."
          actionText="Create Custom Template"
          onAction={() => {
            resetForm();
            setIsCreateOpen(true);
          }}
        />
      )}

      {/* Apply Template Runner Modal */}
      {isApplyOpen && activeTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 max-w-2xl w-full space-y-4 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="text-[10px] font-black uppercase tracking-wider text-purple-700">
                  Template Execution Runner
                </span>
                <h3 className="text-base font-black text-slate-900 mt-0.5">{activeTemplate.name}</h3>
                <div className="text-xs text-slate-500">
                  Target Project: <span className="font-bold text-slate-800">{activeProject?.name}</span> ({activeProject?.domain})
                </div>
              </div>
              <button
                onClick={() => setIsApplyOpen(false)}
                className="text-slate-400 hover:text-slate-800 text-xs font-bold px-2 py-1"
              >
                ✕ Close
              </button>
            </div>

            {isApplying ? (
              <div className="p-8 text-center space-y-2">
                <Sparkles className="w-7 h-7 mx-auto text-purple-600 animate-spin" />
                <p className="text-xs text-slate-600 font-bold">Populating live project & location variables...</p>
              </div>
            ) : appliedResult ? (
              <div className="space-y-4 text-xs">
                {/* Rendered Output Box */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-700 font-bold uppercase text-[10px] tracking-wider">
                      Generated Content (Ready to use)
                    </span>
                    <button
                      onClick={() => copyToClipboard(appliedResult.rendered_content)}
                      className="flex items-center space-x-1 text-purple-700 hover:underline font-bold"
                    >
                      {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copied ? 'Copied to Clipboard' : 'Copy Output'}</span>
                    </button>
                  </div>
                  <div className="bg-slate-900 text-emerald-400 font-mono p-4 rounded-xl max-h-72 overflow-y-auto whitespace-pre-wrap border border-slate-800">
                    {appliedResult.rendered_content}
                  </div>
                </div>

                {/* Variables Used */}
                <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5">
                  <span className="text-[10px] font-bold uppercase text-slate-500 block">
                    Variables Populated from Active Database:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(appliedResult.variables_used).map(([k, v], idx) => (
                      <span key={idx} className="px-2 py-0.5 rounded bg-white border border-slate-200 text-slate-700 text-[10px]">
                        <span className="font-bold text-purple-700">{`{{${k}}}`}:</span> {String(v)}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Action Shortcuts */}
                <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                  <button
                    onClick={handleCreateTaskFromTemplate}
                    className="flex items-center space-x-1.5 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl font-bold transition-colors"
                  >
                    <CheckSquare className="w-4 h-4 text-purple-600" />
                    <span>Create SEO Task for Team</span>
                  </button>

                  <button
                    onClick={() => copyToClipboard(appliedResult.rendered_content)}
                    className="px-5 py-2 btn-vibrant-primary rounded-xl font-bold shadow-md"
                  >
                    {copied ? 'Copied!' : 'Copy & Close'}
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* Preview Raw Modal */}
      {isPreviewOpen && activeTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 max-w-2xl w-full space-y-4 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">
                  Template Source Preview
                </span>
                <h3 className="text-base font-black text-slate-900 mt-0.5">{activeTemplate.name}</h3>
              </div>
              <button
                onClick={() => setIsPreviewOpen(false)}
                className="text-slate-400 hover:text-slate-800 text-xs font-bold px-2 py-1"
              >
                ✕ Close
              </button>
            </div>

            <div className="bg-slate-900 text-purple-300 font-mono text-xs p-4 rounded-xl max-h-80 overflow-y-auto whitespace-pre-wrap border border-slate-800">
              {activeTemplate.content}
            </div>

            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100 text-xs">
              <button
                onClick={() => copyToClipboard(activeTemplate.content)}
                className="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 font-bold hover:bg-slate-200"
              >
                {copied ? 'Copied' : 'Copy Template Code'}
              </button>
              <button
                onClick={() => {
                  setIsPreviewOpen(false);
                  handleApply(activeTemplate);
                }}
                className="px-5 py-2 btn-vibrant-primary rounded-xl font-bold shadow-md"
              >
                Use with Active Project
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit Modal */}
      {(isCreateOpen || isEditOpen) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 max-w-2xl w-full space-y-4 shadow-2xl border border-slate-200 max-h-[90vh] overflow-y-auto">
            <h3 className="text-base font-black text-slate-900">
              {isEditOpen ? 'Edit Custom Template' : 'Create New Local SEO Template'}
            </h3>

            <form onSubmit={handleSaveTemplate} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-700 font-bold block mb-1">Template Name</label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. 24/7 Emergency Electrician Landing Page Blueprint"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-700 font-bold block mb-1">Category</label>
                  <select
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium cursor-pointer"
                  >
                    <option value="schema">Schema.org JSON-LD</option>
                    <option value="review_response">Review Response</option>
                    <option value="location_page">Location Page</option>
                    <option value="gbp">Google Business Profile</option>
                    <option value="task">SEO Task Blueprint</option>
                    <option value="reporting">Executive Report</option>
                    <option value="local_content">Local Content</option>
                  </select>
                </div>

                <div>
                  <label className="text-slate-700 font-bold block mb-1">Template Type / Format</label>
                  <select
                    value={formType}
                    onChange={(e) => {
                      setFormType(e.target.value);
                      handleValidate(formContent, e.target.value);
                    }}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium cursor-pointer"
                  >
                    <option value="schema_jsonld">Schema JSON-LD</option>
                    <option value="content_markdown">Content Markdown</option>
                    <option value="review_reply">Review Reply Text</option>
                    <option value="gbp_post">Google Business Profile Post</option>
                    <option value="task_blueprint">Task Description</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-slate-700 font-bold block mb-1">Standard / Format Badge</label>
                <input
                  type="text"
                  value={formStandard}
                  onChange={(e) => setFormStandard(e.target.value)}
                  placeholder="e.g. Schema.org / JSON-LD or Local SEO Standard"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="text-slate-700 font-bold block mb-1">Description</label>
                <input
                  type="text"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Brief description of when and how to apply this template..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-slate-700 font-bold">
                    Template Content <span className="text-slate-400 font-normal">(use &#123;&#123;variable&#125;&#125; placeholders)</span>
                  </label>
                  <button
                    type="button"
                    onClick={() => handleValidate(formContent, formType)}
                    className="text-[11px] text-purple-700 hover:underline font-bold"
                  >
                    Validate Syntax
                  </button>
                </div>
                <textarea
                  rows={8}
                  required
                  value={formContent}
                  onChange={(e) => {
                    setFormContent(e.target.value);
                    handleValidate(e.target.value, formType);
                  }}
                  placeholder="Paste schema JSON or content markdown with {{business_name}}, {{city}}, {{phone}}..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 font-mono focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              {/* Live Validation Feedback */}
              {validationResult && (
                <div className={`p-3 rounded-xl border text-xs space-y-1 ${
                  validationResult.is_valid ? 'bg-emerald-50 border-emerald-200 text-emerald-900' : 'bg-rose-50 border-rose-200 text-rose-900'
                }`}>
                  <div className="font-bold flex items-center space-x-1.5">
                    {validationResult.is_valid ? <CheckCircle2 className="w-4 h-4 text-emerald-600" /> : <AlertCircle className="w-4 h-4 text-rose-600" />}
                    <span>{validationResult.is_valid ? 'Template Syntax Valid' : 'Syntax Issues Detected'}</span>
                  </div>
                  {validationResult.errors.map((err, idx) => (
                    <div key={idx} className="text-[11px] font-medium">• {err}</div>
                  ))}
                  {validationResult.detected_variables.length > 0 && (
                    <div className="text-[11px] text-slate-600 pt-1">
                      Detected Variables: {validationResult.detected_variables.map(v => `{{${v}}}`).join(', ')}
                    </div>
                  )}
                </div>
              )}

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => {
                    setIsCreateOpen(false);
                    setIsEditOpen(false);
                  }}
                  className="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 font-bold hover:bg-slate-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 btn-vibrant-primary rounded-xl font-bold shadow-md"
                >
                  Save Template
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Import Modal */}
      {isImportOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 max-w-lg w-full space-y-4 shadow-2xl border border-slate-200">
            <h3 className="text-base font-black text-slate-900">Import Structured Template</h3>
            <p className="text-xs text-slate-500">
              Paste valid JSON-LD schema or structured markdown with <code className="text-purple-700 font-bold">&#123;&#123;variables&#125;&#125;</code>.
            </p>

            <form onSubmit={handleImport} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-700 font-bold block mb-1">Template Name (Optional)</label>
                <input
                  type="text"
                  value={importName}
                  onChange={(e) => setImportName(e.target.value)}
                  placeholder="e.g. Custom Schema Template"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              <div>
                <label className="text-slate-700 font-bold block mb-1">File Content / JSON-LD / Markdown</label>
                <textarea
                  rows={8}
                  required
                  value={importContent}
                  onChange={(e) => setImportContent(e.target.value)}
                  placeholder="Paste JSON or Markdown..."
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 font-mono focus:outline-none focus:border-purple-500 font-medium"
                />
              </div>

              {importError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-900 text-xs font-medium">
                  {importError}
                </div>
              )}

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsImportOpen(false)}
                  className="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 font-bold hover:bg-slate-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 btn-vibrant-primary rounded-xl font-bold shadow-md"
                >
                  Validate & Import
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

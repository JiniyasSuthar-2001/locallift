import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Search,
  Check,
  X,
  ChevronDown,
  ChevronRight,
  Plus,
  Sparkles,
  Layers,
  FolderOpen,
  ArrowRight,
  AlertCircle,
  HelpCircle,
  Building2,
  Laptop,
  Code,
  Heart,
  Wrench,
  Scale,
  Car,
  Utensils,
  Sun,
  Shield,
  Activity,
  Home,
  Briefcase
} from 'lucide-react';
import api from '../../api/client';
import { BusinessCategory } from '../../types';
import { Modal } from '../ui/Modal';

interface CategorySelectorProps {
  primaryCategory: string;
  onChangePrimary: (category: string) => void;
  additionalCategories?: string[];
  onChangeAdditionals?: (categories: string[]) => void;
  allowAdditionals?: boolean;
  maxAdditionals?: number;
  label?: string;
  helperText?: string;
  className?: string;
}

interface HierarchyGroup {
  name: string;
  total_categories: number;
  subcategories: {
    name: string;
    count: number;
    categories: BusinessCategory[];
  }[];
}

// Fallback representative categories across major industries if offline
const REPRESENTATIVE_FALLBACKS: BusinessCategory[] = [
  { id: 'dentist', name: 'Dentist', slug: 'dentist', group: 'Dental & Oral Health', is_popular: true },
  { id: 'doctor', name: 'Doctor', slug: 'doctor', group: 'Healthcare & Medical', is_popular: true },
  { id: 'it-services', name: 'IT Services', slug: 'it-services', group: 'Information Technology (IT)', is_popular: true },
  { id: 'software-company', name: 'Software Company', slug: 'software-company', group: 'Software & SaaS', is_popular: true },
  { id: 'web-development-company', name: 'Web Development Company', slug: 'web-development-company', group: 'Software & SaaS', is_popular: true },
  { id: 'cybersecurity-company', name: 'Cybersecurity Company', slug: 'cybersecurity-company', group: 'Information Technology (IT)', is_popular: true },
  { id: 'plumber', name: 'Plumber', slug: 'plumber', group: 'Home Services & Trades', is_popular: true },
  { id: 'electrician', name: 'Electrician', slug: 'electrician', group: 'Home Services & Trades', is_popular: true },
  { id: 'hvac-contractor', name: 'HVAC Contractor', slug: 'hvac-contractor', group: 'Home Services & Trades', is_popular: true },
  { id: 'roofing-contractor', name: 'Roofing Contractor', slug: 'roofing-contractor', group: 'Home Services & Trades', is_popular: true },
  { id: 'general-contractor', name: 'General Contractor', slug: 'general-contractor', group: 'Construction & Building', is_popular: true },
  { id: 'law-firm', name: 'Law Firm', slug: 'law-firm', group: 'Legal & Law', is_popular: true },
  { id: 'personal-injury-attorney', name: 'Personal Injury Attorney', slug: 'personal-injury-attorney', group: 'Legal & Law', is_popular: true },
  { id: 'accountant', name: 'Accountant', slug: 'accountant', group: 'Professional Services', is_popular: true },
  { id: 'marketing-agency', name: 'Marketing Agency', slug: 'marketing-agency', group: 'Digital Marketing & Advertising', is_popular: true },
  { id: 'real-estate-agency', name: 'Real Estate Agency', slug: 'real-estate-agency', group: 'Real Estate & Property', is_popular: true },
  { id: 'auto-repair-shop', name: 'Auto Repair Shop', slug: 'auto-repair-shop', group: 'Automotive & Transportation', is_popular: true },
  { id: 'car-dealer', name: 'Car Dealer', slug: 'car-dealer', group: 'Automotive & Transportation', is_popular: true },
  { id: 'restaurant', name: 'Restaurant', slug: 'restaurant', group: 'Restaurants & Food', is_popular: true },
  { id: 'cafe', name: 'Cafe', slug: 'cafe', group: 'Restaurants & Food', is_popular: true },
  { id: 'hair-salon', name: 'Hair Salon', slug: 'hair-salon', group: 'Beauty & Personal Care', is_popular: true },
  { id: 'barber-shop', name: 'Barber Shop', slug: 'barber-shop', group: 'Beauty & Personal Care', is_popular: true },
  { id: 'gym', name: 'Gym', slug: 'gym', group: 'Health, Fitness & Wellness', is_popular: true },
  { id: 'hotel', name: 'Hotel', slug: 'hotel', group: 'Hotels & Hospitality', is_popular: true },
  { id: 'veterinarian', name: 'Veterinarian', slug: 'veterinarian', group: 'Pets & Veterinary', is_popular: true },
  { id: 'moving-company', name: 'Moving Company', slug: 'moving-company', group: 'Logistics & Transportation', is_popular: true },
  { id: 'house-cleaning-service', name: 'House Cleaning Service', slug: 'house-cleaning-service', group: 'Cleaning & Facility Services', is_popular: true },
  { id: 'event-venue', name: 'Event Venue', slug: 'event-venue', group: 'Events & Entertainment', is_popular: true },
  { id: 'photographer', name: 'Photographer', slug: 'photographer', group: 'Events & Entertainment', is_popular: true },
  { id: 'insurance-agency', name: 'Insurance Agency', slug: 'insurance-agency', group: 'Professional Services', is_popular: true }
];

export const CategorySelector: React.FC<CategorySelectorProps> = ({
  primaryCategory,
  onChangePrimary,
  additionalCategories = [],
  onChangeAdditionals,
  allowAdditionals = true,
  maxAdditionals = 5,
  label = 'Primary Business Category',
  helperText = 'Search your business category or industry type (e.g. IT Services, Software, Dentist, Plumber, Law Firm)',
  className = ''
}) => {
  // Modal / Dropdown state
  const [isOpen, setIsOpen] = useState(false);
  const [isAdditionalModalOpen, setIsAdditionalModalOpen] = useState(false);
  
  // Search query & results
  const [searchQuery, setSearchQuery] = useState('');
  const [categories, setCategories] = useState<BusinessCategory[]>([]);
  const [popularCategories, setPopularCategories] = useState<BusinessCategory[]>([]);
  const [hierarchyGroups, setHierarchyGroups] = useState<HierarchyGroup[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  // Active selected index for keyboard navigation
  const [highlightedIndex, setHighlightedIndex] = useState<number>(0);
  
  // View mode inside modal: 'popular' | 'industry_browse' | 'search_results'
  const [activeTab, setActiveTab] = useState<'popular' | 'industry'>('popular');
  const [expandedIndustryGroups, setExpandedIndustryGroups] = useState<Record<string, boolean>>({
    'Information Technology (IT)': true,
    'Software & SaaS': true,
    'Healthcare & Medical': true
  });

  // References
  const searchInputRef = useRef<HTMLInputElement>(null);
  const resultsContainerRef = useRef<HTMLDivElement>(null);

  // Fetch initial popular categories & hierarchy catalog
  const loadInitialCatalog = useCallback(async () => {
    try {
      const [popRes, hierRes] = await Promise.allSettled([
        api.get('/categories/popular'),
        api.get('/categories/hierarchy')
      ]);

      if (popRes.status === 'fulfilled' && popRes.value.data?.items) {
        setPopularCategories(popRes.value.data.items);
      } else {
        setPopularCategories(REPRESENTATIVE_FALLBACKS);
      }

      if (hierRes.status === 'fulfilled' && hierRes.value.data?.groups) {
        setHierarchyGroups(hierRes.value.data.groups);
      }
    } catch (err) {
      console.warn('Error loading taxonomy catalog, using fallback:', err);
      setPopularCategories(REPRESENTATIVE_FALLBACKS);
    }
  }, []);

  useEffect(() => {
    loadInitialCatalog();
  }, [loadInitialCatalog]);

  // Fetch search results with debouncing
  const searchCategories = useCallback(async (query: string) => {
    if (!query.trim()) {
      setCategories([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const res = await api.get('/categories', {
        params: { q: query.trim(), limit: 50 }
      });
      if (res.data?.items) {
        setCategories(res.data.items);
      }
    } catch (err) {
      console.warn('Category search API error, filtering local catalog:', err);
      const qLower = query.toLowerCase().trim();
      const localMatches = REPRESENTATIVE_FALLBACKS.filter(c =>
        c.name.toLowerCase().includes(qLower) ||
        (c.group && c.group.toLowerCase().includes(qLower))
      );
      setCategories(localMatches);
    } finally {
      setIsLoading(false);
      setHighlightedIndex(0);
    }
  }, []);

  // Debounce search query changes
  useEffect(() => {
    if (!isOpen && !isAdditionalModalOpen) return;

    if (!searchQuery.trim()) {
      setCategories([]);
      return;
    }

    const timer = setTimeout(() => {
      searchCategories(searchQuery);
    }, 150);

    return () => clearTimeout(timer);
  }, [searchQuery, isOpen, isAdditionalModalOpen, searchCategories]);

  // Focus search input when selector opens
  useEffect(() => {
    if (isOpen || isAdditionalModalOpen) {
      setHighlightedIndex(0);
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 60);
    }
  }, [isOpen, isAdditionalModalOpen]);

  // Keyboard navigation handler
  const handleKeyDown = (e: React.KeyboardEvent) => {
    const listToNavigate = searchQuery.trim() ? categories : popularCategories;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex(prev => (prev < listToNavigate.length - 1 ? prev + 1 : prev));
      scrollHighlightedIntoView(highlightedIndex + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex(prev => (prev > 0 ? prev - 1 : 0));
      scrollHighlightedIntoView(highlightedIndex - 1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (listToNavigate[highlightedIndex]) {
        handleSelectCategory(listToNavigate[highlightedIndex].name);
      } else if (searchQuery.trim()) {
        handleSelectCategory(searchQuery.trim());
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closeModals();
    }
  };

  const scrollHighlightedIntoView = (index: number) => {
    if (!resultsContainerRef.current) return;
    const items = resultsContainerRef.current.querySelectorAll('[data-category-item]');
    if (items[index]) {
      items[index].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  };

  const openPrimarySelector = () => {
    setSearchQuery('');
    setActiveTab('popular');
    setIsOpen(true);
  };

  const openAdditionalSelector = () => {
    setSearchQuery('');
    setActiveTab('popular');
    setIsAdditionalModalOpen(true);
  };

  const closeModals = () => {
    setIsOpen(false);
    setIsAdditionalModalOpen(false);
    setSearchQuery('');
  };

  const handleSelectCategory = (categoryName: string) => {
    if (isOpen) {
      onChangePrimary(categoryName);
      if (onChangeAdditionals && additionalCategories.includes(categoryName)) {
        onChangeAdditionals(additionalCategories.filter(c => c !== categoryName));
      }
    } else if (isAdditionalModalOpen && onChangeAdditionals) {
      if (
        categoryName !== primaryCategory &&
        !additionalCategories.includes(categoryName) &&
        additionalCategories.length < maxAdditionals
      ) {
        onChangeAdditionals([...additionalCategories, categoryName]);
      }
    }
    closeModals();
  };

  const handleRemoveAdditional = (catToRemove: string) => {
    if (onChangeAdditionals) {
      onChangeAdditionals(additionalCategories.filter(c => c !== catToRemove));
    }
  };

  const toggleGroupExpansion = (groupName: string) => {
    setExpandedIndustryGroups(prev => ({
      ...prev,
      [groupName]: !prev[groupName]
    }));
  };

  // Grouped search results
  const groupedSearchResults = useMemo(() => {
    const map: Record<string, BusinessCategory[]> = {};
    for (const cat of categories) {
      const g = cat.group || 'Other Specialized Businesses';
      if (!map[g]) map[g] = [];
      map[g].push(cat);
    }
    return map;
  }, [categories]);

  return (
    <div className={`space-y-4 ${className}`}>
      {/* 1. Primary Category Display / Trigger */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-slate-800 font-bold text-xs flex items-center gap-1.5">
            <span>{label}</span>
            <span className="text-rose-500 font-black">*</span>
          </label>
          {primaryCategory && (
            <button
              type="button"
              onClick={openPrimarySelector}
              className="text-[11px] font-bold text-purple-600 hover:text-purple-700 transition-colors"
            >
              Change Category
            </button>
          )}
        </div>

        {primaryCategory ? (
          <div className="flex items-center justify-between bg-slate-50 hover:bg-slate-100/80 border border-slate-200 hover:border-purple-300 rounded-xl p-3 transition-all">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-purple-100 text-purple-700 flex items-center justify-center font-bold text-xs shrink-0">
                <Sparkles className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-bold text-slate-900 truncate">{primaryCategory}</div>
                <div className="text-[11px] text-slate-500 truncate">Primary SEO entity & search taxonomy anchor</div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={openPrimarySelector}
                className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 hover:bg-purple-50 hover:text-purple-700 hover:border-purple-300 transition-all shadow-sm"
              >
                Change
              </button>
              <button
                type="button"
                onClick={() => onChangePrimary('')}
                className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                title="Clear selection"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={openPrimarySelector}
            className="w-full flex items-center justify-between bg-white hover:bg-purple-50/40 border border-slate-200 hover:border-purple-400 rounded-xl p-3 text-left transition-all group shadow-sm"
          >
            <div className="flex items-center gap-2.5 text-slate-500 group-hover:text-purple-700">
              <Search className="w-4 h-4 text-slate-400 group-hover:text-purple-600" />
              <span className="text-sm font-medium">Search & select business category (e.g. IT Services, Software, Dentist)...</span>
            </div>
            <span className="text-xs font-bold text-purple-600 bg-purple-50 group-hover:bg-purple-100 px-2.5 py-1 rounded-lg transition-colors">
              Browse
            </span>
          </button>
        )}
        <p className="text-[11px] text-slate-500 mt-1.5">{helperText}</p>
      </div>

      {/* 2. Additional Categories (Optional) */}
      {allowAdditionals && onChangeAdditionals && (
        <div className="pt-2 border-t border-slate-100">
          <div className="flex items-center justify-between mb-2">
            <div>
              <label className="text-slate-800 font-bold text-xs flex items-center gap-1.5">
                <span>Additional Business Categories</span>
                <span className="text-[10px] font-normal text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                  Optional ({additionalCategories.length}/{maxAdditionals})
                </span>
              </label>
              <p className="text-[11px] text-slate-500">
                Support secondary services (e.g. Managed IT Services, Cybersecurity, Cloud Solutions)
              </p>
            </div>
            {additionalCategories.length < maxAdditionals && (
              <button
                type="button"
                onClick={openAdditionalSelector}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-slate-100 hover:bg-purple-100 text-slate-700 hover:text-purple-800 text-xs font-bold rounded-lg transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Category</span>
              </button>
            )}
          </div>

          {additionalCategories.length > 0 ? (
            <div className="flex flex-wrap gap-2 pt-1">
              {additionalCategories.map(cat => (
                <span
                  key={cat}
                  className="inline-flex items-center gap-1.5 px-3 py-1 bg-purple-50 border border-purple-200 text-purple-900 rounded-lg text-xs font-medium shadow-sm"
                >
                  <span>{cat}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveAdditional(cat)}
                    className="text-purple-400 hover:text-rose-600 p-0.5 rounded transition-colors"
                    title={`Remove ${cat}`}
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <div className="text-[11px] text-slate-500 italic">
              No additional categories selected. Click "+ Add Category" to specify secondary offerings.
            </div>
          )}
        </div>
      )}

      {/* 3. Search & Hierarchical Industry Browser Modal */}
      <Modal
        isOpen={isOpen || isAdditionalModalOpen}
        onClose={closeModals}
        title={isOpen ? 'Select Primary Business Category' : 'Add Additional Business Category'}
        subtitle="Search across hundreds of structured Industry & Google Business Profile categories"
        maxWidth="2xl"
        bodyClassName="p-0 overflow-y-auto max-h-[calc(85vh-120px)]"
        footer={
          <div className="w-full flex items-center justify-between text-[11px] text-slate-500">
            <div className="flex items-center gap-3 hidden sm:flex">
              <span>
                <kbd className="px-1.5 py-0.5 bg-white border border-slate-200 rounded text-[10px] font-mono font-bold text-slate-600 mr-1">↑</kbd>
                <kbd className="px-1.5 py-0.5 bg-white border border-slate-200 rounded text-[10px] font-mono font-bold text-slate-600">↓</kbd> Navigate
              </span>
              <span>
                <kbd className="px-1.5 py-0.5 bg-white border border-slate-200 rounded text-[10px] font-mono font-bold text-slate-600">Enter</kbd> Select
              </span>
              <span>
                <kbd className="px-1.5 py-0.5 bg-white border border-slate-200 rounded text-[10px] font-mono font-bold text-slate-600">Esc</kbd> Close
              </span>
            </div>
            <button
              type="button"
              onClick={closeModals}
              className="px-3 py-1 bg-white border border-slate-200 hover:bg-slate-100 rounded-lg text-xs font-semibold text-slate-700 ml-auto"
            >
              Done
            </button>
          </div>
        }
      >
        <div onKeyDown={handleKeyDown}>
          {/* Prominent Search Bar */}
          <div className="p-4 border-b border-slate-100 space-y-3">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Type to search (e.g. IT, cybersecurity, software, dentist, plumber, doctor, law)..."
                className="w-full pl-10 pr-10 py-3 bg-slate-50 border border-slate-200 focus:border-purple-500 focus:bg-white rounded-xl text-slate-900 text-sm font-medium focus:outline-none transition-all shadow-inner"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery('');
                    searchInputRef.current?.focus();
                  }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 p-1"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* View Mode Tabs (When no active search query) */}
            {!searchQuery && (
              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl">
                  <button
                    type="button"
                    onClick={() => setActiveTab('popular')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                      activeTab === 'popular'
                        ? 'bg-white text-purple-700 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Popular Categories ({popularCategories.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('industry')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                      activeTab === 'industry'
                        ? 'bg-white text-purple-700 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Browse by Industry ({hierarchyGroups.length || 27})
                  </button>
                </div>
                <span className="text-[11px] text-slate-400 font-medium hidden sm:inline">
                  Click category to apply
                </span>
              </div>
            )}
          </div>

          {/* Results / Navigation Container */}
          <div
            ref={resultsContainerRef}
            className="max-h-[380px] overflow-y-auto p-3 divide-y divide-slate-100"
          >
            {/* 1. Live Search Results */}
            {searchQuery.trim() ? (
              isLoading ? (
                <div className="p-8 text-center text-slate-500 text-xs font-medium">
                  <div className="w-6 h-6 border-2 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  Searching taxonomy and aliases...
                </div>
              ) : categories.length === 0 ? (
                <div className="p-8 text-center space-y-2">
                  <AlertCircle className="w-8 h-8 text-slate-400 mx-auto" />
                  <div className="text-sm font-bold text-slate-800">No matching business categories found</div>
                  <p className="text-xs text-slate-500 max-w-xs mx-auto">
                    Try typing related keywords (e.g. "IT", "cyber security", "software", "doctor", "construction").
                  </p>
                  <div className="pt-2">
                    <button
                      type="button"
                      onClick={() => handleSelectCategory(searchQuery.trim())}
                      className="px-3 py-1.5 bg-purple-50 text-purple-800 border border-purple-200 rounded-lg text-xs font-bold hover:bg-purple-100 transition-colors"
                    >
                      Use custom category: "{searchQuery.trim()}"
                    </button>
                  </div>
                </div>
              ) : (
                Object.entries(groupedSearchResults).map(([groupName, items]) => (
                  <div key={groupName} className="py-2.5 first:pt-0">
                    <div className="px-3 py-1 text-[10px] font-black text-purple-800 uppercase tracking-wider flex items-center justify-between">
                      <span>{groupName}</span>
                      <span className="text-slate-400 font-mono">{items.length}</span>
                    </div>
                    <div className="space-y-1 mt-1">
                      {items.map((cat) => {
                        const globalIndex = categories.findIndex(c => c.id === cat.id);
                        const isPrimary = primaryCategory.toLowerCase() === cat.name.toLowerCase();
                        const isSelected = isOpen
                          ? isPrimary
                          : additionalCategories.map(a => a.toLowerCase()).includes(cat.name.toLowerCase());
                        const isHighlighted = globalIndex === highlightedIndex;

                        return (
                          <button
                            key={cat.id || cat.name}
                            data-category-item
                            type="button"
                            disabled={isAdditionalModalOpen && isPrimary}
                            onClick={() => handleSelectCategory(cat.name)}
                            onMouseEnter={() => setHighlightedIndex(globalIndex)}
                            className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-left transition-all ${
                              isHighlighted
                                ? 'bg-purple-50 text-purple-950 ring-1 ring-purple-300'
                                : 'hover:bg-slate-50 text-slate-800'
                            } ${isAdditionalModalOpen && isPrimary ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                          >
                            <div className="flex items-center gap-2.5 min-w-0">
                              <span className="font-bold text-xs truncate">{cat.name}</span>
                              {cat.schema_type && (
                                <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded hidden sm:inline">
                                  {cat.schema_type}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              {isPrimary && (
                                <span className="text-[10px] font-bold bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full">
                                  Primary
                                </span>
                              )}
                              {isSelected && !isPrimary && (
                                <span className="text-[10px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full flex items-center gap-1">
                                  <Check className="w-3 h-3" /> Selected
                                </span>
                              )}
                              <ArrowRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-purple-600" />
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))
              )
            ) : activeTab === 'popular' ? (
              /* 2. Popular Categories Pill Grid */
              <div className="py-2 space-y-3">
                <div className="px-1 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  Featured Local SEO Categories
                </div>
                <div className="flex flex-wrap gap-2">
                  {popularCategories.map((pop, idx) => {
                    const isPrimary = primaryCategory.toLowerCase() === pop.name.toLowerCase();
                    const isSelected = isOpen
                      ? isPrimary
                      : additionalCategories.map(a => a.toLowerCase()).includes(pop.name.toLowerCase());
                    const isHighlighted = idx === highlightedIndex;

                    return (
                      <button
                        key={pop.id || pop.name}
                        data-category-item
                        type="button"
                        onClick={() => handleSelectCategory(pop.name)}
                        onMouseEnter={() => setHighlightedIndex(idx)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                          isSelected
                            ? 'bg-purple-600 text-white shadow-xs'
                            : isHighlighted
                            ? 'bg-purple-100 text-purple-900 border border-purple-300'
                            : 'bg-slate-100 hover:bg-purple-50 text-slate-700 hover:text-purple-800 border border-slate-200'
                        }`}
                      >
                        <span>{pop.name}</span>
                        {isSelected && <Check className="w-3 h-3 text-white" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : (
              /* 3. Hierarchical Industry Tree Browser */
              <div className="py-2 space-y-3">
                {hierarchyGroups.map((grp) => {
                  const isExpanded = !!expandedIndustryGroups[grp.name];
                  return (
                    <div key={grp.name} className="border border-slate-200 rounded-xl overflow-hidden bg-white">
                      {/* Parent Group Header */}
                      <button
                        type="button"
                        onClick={() => toggleGroupExpansion(grp.name)}
                        className="w-full px-3.5 py-2.5 bg-slate-50 hover:bg-slate-100 flex items-center justify-between text-left transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-purple-600" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-slate-400" />
                          )}
                          <span className="font-extrabold text-xs text-slate-900">{grp.name}</span>
                        </div>
                        <span className="text-[10px] font-mono font-bold text-slate-600 bg-white border border-slate-200 px-2 py-0.5 rounded-full">
                          {grp.total_categories} categories
                        </span>
                      </button>

                      {/* Expanded Subcategories & Category Pills */}
                      {isExpanded && (
                        <div className="p-3 bg-white space-y-3 border-t border-slate-100">
                          {grp.subcategories.map((sub) => (
                            <div key={sub.name} className="space-y-1.5">
                              <div className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">
                                {sub.name}
                              </div>
                              <div className="flex flex-wrap gap-1.5">
                                {sub.categories.map((cat) => {
                                  const isPrimary = primaryCategory.toLowerCase() === cat.name.toLowerCase();
                                  const isSelected = isOpen
                                    ? isPrimary
                                    : additionalCategories.map(a => a.toLowerCase()).includes(cat.name.toLowerCase());

                                  return (
                                    <button
                                      key={cat.id || cat.name}
                                      type="button"
                                      onClick={() => handleSelectCategory(cat.name)}
                                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all flex items-center gap-1 ${
                                        isSelected
                                          ? 'bg-purple-600 text-white shadow-xs'
                                          : 'bg-slate-100 hover:bg-purple-100 text-slate-700 hover:text-purple-900 border border-slate-200'
                                      }`}
                                    >
                                      <span>{cat.name}</span>
                                      {isSelected && <Check className="w-3 h-3 text-white" />}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </Modal>
    </div>
  );
};

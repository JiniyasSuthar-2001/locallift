import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Search,
  Check,
  X,
  ChevronDown,
  Plus,
  Sparkles,
  Layers,
  FolderOpen,
  ArrowRight,
  AlertCircle,
  HelpCircle
} from 'lucide-react';
import api from '../../api/client';
import { BusinessCategory } from '../../types';

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

export const CategorySelector: React.FC<CategorySelectorProps> = ({
  primaryCategory,
  onChangePrimary,
  additionalCategories = [],
  onChangeAdditionals,
  allowAdditionals = true,
  maxAdditionals = 5,
  label = 'Primary Business Category',
  helperText = 'Search your business category or industry type (e.g. Dentist, Plumber, Law Firm)',
  className = ''
}) => {
  // Modal / Dropdown state
  const [isOpen, setIsOpen] = useState(false);
  const [isAdditionalModalOpen, setIsAdditionalModalOpen] = useState(false);
  
  // Search query & results
  const [searchQuery, setSearchQuery] = useState('');
  const [categories, setCategories] = useState<BusinessCategory[]>([]);
  const [groups, setGroups] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  
  // Active selected index for keyboard navigation
  const [highlightedIndex, setHighlightedIndex] = useState<number>(0);
  
  // Browse by group mode
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [isBrowsingGroups, setIsBrowsingGroups] = useState(false);

  // References
  const searchInputRef = useRef<HTMLInputElement>(null);
  const resultsContainerRef = useRef<HTMLDivElement>(null);

  // Popular fallback categories if offline or initial load
  const popularFallbacks: string[] = useMemo(() => [
    'Dentist',
    'Plumber',
    'Electrician',
    'Law Firm',
    'Restaurant',
    'Real Estate Agency',
    'HVAC Contractor',
    'Roofing Contractor',
    'Auto Repair Shop',
    'Hair Salon',
    'Marketing Agency',
    'Accountant'
  ], []);

  // Fetch categories from backend API with debouncing
  const fetchCategories = useCallback(async (query: string, groupFilter: string | null = null) => {
    setIsLoading(true);
    try {
      const params: Record<string, string | number | boolean> = { limit: 35 };
      if (query.trim()) {
        params.q = query.trim();
      } else {
        params.popular_only = !groupFilter;
      }
      if (groupFilter) {
        params.group = groupFilter;
      }

      const res = await api.get('/categories', { params });
      if (res.data?.items) {
        setCategories(res.data.items);
      }
      if (res.data?.groups && res.data.groups.length > 0) {
        setGroups(res.data.groups);
      }
    } catch (err) {
      console.warn('Category fetch error, using local fallback:', err);
      // Fallback search filtering if API is unreachable
      const qLower = query.toLowerCase().trim();
      if (qLower) {
        const fallbackMatches = popularFallbacks
          .filter(c => c.toLowerCase().includes(qLower))
          .map(c => ({
            id: c.toLowerCase().replace(/\s+/g, '-'),
            name: c,
            slug: c.toLowerCase().replace(/\s+/g, '-'),
            group: 'Popular Services',
            is_popular: true
          }));
        setCategories(fallbackMatches);
      } else {
        const fallbacks = popularFallbacks.map(c => ({
          id: c.toLowerCase().replace(/\s+/g, '-'),
          name: c,
          slug: c.toLowerCase().replace(/\s+/g, '-'),
          group: 'Popular Services',
          is_popular: true
        }));
        setCategories(fallbacks);
      }
    } finally {
      setIsLoading(false);
      setHasSearched(true);
      setHighlightedIndex(0);
    }
  }, [popularFallbacks]);

  // Initial load
  useEffect(() => {
    fetchCategories('');
  }, [fetchCategories]);

  // Debounce search query changes
  useEffect(() => {
    if (!isOpen && !isAdditionalModalOpen) return;

    const timer = setTimeout(() => {
      fetchCategories(searchQuery, selectedGroup);
    }, 180);

    return () => clearTimeout(timer);
  }, [searchQuery, selectedGroup, isOpen, isAdditionalModalOpen, fetchCategories]);

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
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex(prev => (prev < categories.length - 1 ? prev + 1 : prev));
      scrollHighlightedIntoView(highlightedIndex + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex(prev => (prev > 0 ? prev - 1 : 0));
      scrollHighlightedIntoView(highlightedIndex - 1);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (categories[highlightedIndex]) {
        handleSelectCategory(categories[highlightedIndex].name);
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
    setSelectedGroup(null);
    setIsBrowsingGroups(false);
    setIsOpen(true);
  };

  const openAdditionalSelector = () => {
    setSearchQuery('');
    setSelectedGroup(null);
    setIsBrowsingGroups(false);
    setIsAdditionalModalOpen(true);
  };

  const closeModals = () => {
    setIsOpen(false);
    setIsAdditionalModalOpen(false);
    setSearchQuery('');
    setSelectedGroup(null);
    setIsBrowsingGroups(false);
  };

  const handleSelectCategory = (categoryName: string) => {
    if (isOpen) {
      onChangePrimary(categoryName);
      // Remove from additional categories if present
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

  // Grouped search results
  const groupedResults = useMemo(() => {
    const map: Record<string, BusinessCategory[]> = {};
    for (const cat of categories) {
      const g = cat.group || 'General Categories';
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
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-purple-100 text-purple-700 flex items-center justify-center font-bold text-xs">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900">{primaryCategory}</div>
                <div className="text-[11px] text-slate-500">Primary SEO entity & search taxonomy anchor</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
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
              <span className="text-sm font-medium">Search & select business category...</span>
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
                Support secondary services (e.g. Cosmetic Dentist, Orthodontics, Emergency Repair)
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

      {/* 3. Search Modal / Popover Overlay */}
      {(isOpen || isAdditionalModalOpen) && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div
            className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150"
            onKeyDown={handleKeyDown}
          >
            {/* Modal Header */}
            <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div>
                <h3 className="font-bold text-slate-900 text-sm">
                  {isOpen ? 'Select Primary Business Category' : 'Add Additional Business Category'}
                </h3>
                <p className="text-[11px] text-slate-500">
                  Search across hundreds of verified Local SEO & Google Business Profile categories
                </p>
              </div>
              <button
                type="button"
                onClick={closeModals}
                className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Prominent Search Bar */}
            <div className="p-4 border-b border-slate-100">
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={searchQuery}
                  onChange={e => {
                    setSearchQuery(e.target.value);
                    if (isBrowsingGroups) setIsBrowsingGroups(false);
                  }}
                  placeholder="Type to search (e.g. dentist, plumber, law, restaurant, hvac)..."
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

              {/* Group filter badges or popular quick-chips */}
              {!searchQuery && !isBrowsingGroups && (
                <div className="mt-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                      Popular Categories
                    </span>
                    <button
                      type="button"
                      onClick={() => setIsBrowsingGroups(true)}
                      className="text-[11px] font-bold text-purple-600 hover:text-purple-700 flex items-center gap-1"
                    >
                      <span>Browse by Industry</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {popularFallbacks.map(pop => (
                      <button
                        key={pop}
                        type="button"
                        onClick={() => handleSelectCategory(pop)}
                        className="px-2.5 py-1 bg-slate-100 hover:bg-purple-100 text-slate-700 hover:text-purple-800 text-xs font-semibold rounded-lg transition-colors"
                      >
                        {pop}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Industry groups browser */}
              {!searchQuery && isBrowsingGroups && (
                <div className="mt-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                      Browse by Industry Sector
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setIsBrowsingGroups(false);
                        setSelectedGroup(null);
                      }}
                      className="text-[11px] font-bold text-slate-500 hover:text-slate-800"
                    >
                      Back to Popular
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 max-h-36 overflow-y-auto pr-1">
                    {groups.map(grp => (
                      <button
                        key={grp}
                        type="button"
                        onClick={() => {
                          setSelectedGroup(grp === selectedGroup ? null : grp);
                          fetchCategories('', grp === selectedGroup ? null : grp);
                        }}
                        className={`text-left px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center justify-between ${
                          selectedGroup === grp
                            ? 'bg-purple-100 text-purple-900 border border-purple-300'
                            : 'bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200'
                        }`}
                      >
                        <span className="truncate">{grp}</span>
                        {selectedGroup === grp && <Check className="w-3.5 h-3.5 text-purple-700 flex-shrink-0" />}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Results List */}
            <div
              ref={resultsContainerRef}
              className="max-h-72 overflow-y-auto p-2 divide-y divide-slate-50"
            >
              {isLoading ? (
                <div className="p-8 text-center text-slate-500 text-xs font-medium">
                  <div className="w-6 h-6 border-2 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  Searching verified taxonomy...
                </div>
              ) : categories.length === 0 ? (
                <div className="p-8 text-center space-y-2">
                  <AlertCircle className="w-8 h-8 text-slate-400 mx-auto" />
                  <div className="text-sm font-bold text-slate-800">No matching business categories found</div>
                  <p className="text-xs text-slate-500 max-w-xs mx-auto">
                    Try typing a broader industry term (e.g. "dental", "plumbing", "health", "legal", "food").
                  </p>
                  {searchQuery && (
                    <div className="pt-2">
                      <button
                        type="button"
                        onClick={() => handleSelectCategory(searchQuery.trim())}
                        className="px-3 py-1.5 bg-purple-50 text-purple-800 border border-purple-200 rounded-lg text-xs font-bold hover:bg-purple-100 transition-colors"
                      >
                        Use custom category: "{searchQuery.trim()}"
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                Object.entries(groupedResults).map(([groupName, items]) => (
                  <div key={groupName} className="py-2 first:pt-0">
                    <div className="px-3 py-1 text-[10px] font-black text-slate-600 uppercase tracking-wider">
                      {groupName}
                    </div>
                    <div className="space-y-0.5 mt-1">
                      {items.map((cat, idx) => {
                        const globalIndex = categories.findIndex(c => c.id === cat.id);
                        const isSelected = isOpen
                          ? primaryCategory.toLowerCase() === cat.name.toLowerCase()
                          : additionalCategories.map(a => a.toLowerCase()).includes(cat.name.toLowerCase());
                        const isPrimary = primaryCategory.toLowerCase() === cat.name.toLowerCase();
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
                              <span className="font-semibold text-xs truncate">{cat.name}</span>
                              {cat.schema_type && (
                                <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded hidden sm:inline">
                                  {cat.schema_type}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
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
              )}
            </div>

            {/* Footer with Keyboard Hints */}
            <div className="p-3 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
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
          </div>
        </div>
      )}
    </div>
  );
};

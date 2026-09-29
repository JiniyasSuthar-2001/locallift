import React, { useState, useEffect, useMemo } from 'react';
import {
  Package,
  Wrench,
  Layers,
  RefreshCw,
  Search,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  Building2,
  Calendar,
  ShoppingBag,
  Plus,
  Edit2,
  Trash2,
  Upload,
  X
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { ProductOrServiceItem, ProductsServicesResponse } from '../types';
import { EmptyState } from '../components/ui/EmptyState';
import { Modal } from '../components/ui/Modal';
import api from '../api/client';
import { getErrorMessage } from '../utils/error';

export const ProductsServicesView: React.FC = () => {
  const { activeProject } = useProject();

  const [items, setItems] = useState<ProductOrServiceItem[]>([]);
  const [data, setData] = useState<ProductsServicesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [filterType, setFilterType] = useState<'all' | 'product' | 'service'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Modal States
  const [productModalOpen, setProductModalOpen] = useState(false);
  const [serviceModalOpen, setServiceModalOpen] = useState(false);
  const [bulkImportModalOpen, setBulkImportModalOpen] = useState(false);
  const [deleteConfirmItem, setDeleteConfirmItem] = useState<ProductOrServiceItem | null>(null);
  const [editingItem, setEditingItem] = useState<ProductOrServiceItem | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Form Fields
  const [formName, setFormName] = useState('');
  const [formCategory, setFormCategory] = useState('');
  const [formPrice, setFormPrice] = useState('');
  const [formPriceRange, setFormPriceRange] = useState('');
  const [formImageUrl, setFormImageUrl] = useState('');
  const [formActionUrl, setFormActionUrl] = useState('');
  const [formActionType, setFormActionType] = useState('VIEW');
  const [formDescription, setFormDescription] = useState('');
  const [bulkJson, setBulkJson] = useState('');

  // Fetch Products & Services
  const fetchProductsServices = async (showLoading: boolean = true) => {
    if (!activeProject) return;
    try {
      if (showLoading) setLoading(true);
      const resp = await api.get(`/gbp/${activeProject.id}/products-services`);
      if (resp.data) {
        setData(resp.data);
        setItems(resp.data.items || []);
      }
    } catch (e: any) {
      console.error('Failed to load products and services:', e);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  // Sync / Refresh Products & Services
  const handleSync = async () => {
    if (!activeProject) return;
    try {
      setSyncing(true);
      setStatusMsg(null);
      const resp = await api.post(`/gbp/${activeProject.id}/products-services/sync`);
      if (resp.data) {
        setData(resp.data);
        setItems(resp.data.items || []);
        if (resp.data.sync_status === 'NOT_AVAILABLE') {
          setStatusMsg({
            type: 'error',
            text: resp.data.sync_message || 'Product/service sync is not available through the connected Google API.'
          });
        } else if (resp.data.sync_status === 'FAILED') {
          setStatusMsg({
            type: 'error',
            text: resp.data.sync_message || 'Synchronization failed.'
          });
        } else {
          setStatusMsg({
            type: 'success',
            text: resp.data.sync_message || `Synchronized ${resp.data.total_products} products and ${resp.data.total_services} services.`
          });
        }
      }
    } catch (e: any) {
      console.error('Failed to sync products and services:', e);
      setStatusMsg({
        type: 'error',
        text: getErrorMessage(e, 'Failed to synchronize products and services from Google Business Profile.')
      });
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    fetchProductsServices(true);
  }, [activeProject]);

  const openAddProductModal = () => {
    setEditingItem(null);
    setFormName('');
    setFormCategory(activeProject?.primary_category || 'Products');
    setFormPrice('');
    setFormPriceRange('');
    setFormImageUrl('');
    setFormActionUrl('');
    setFormActionType('VIEW');
    setFormDescription('');
    setProductModalOpen(true);
  };

  const openEditProductModal = (item: ProductOrServiceItem) => {
    setEditingItem(item);
    setFormName(item.name || '');
    setFormCategory(item.category || '');
    setFormPrice(item.price || '');
    setFormPriceRange(item.price_range || '');
    setFormImageUrl(item.image_url || '');
    setFormActionUrl(item.action_url || '');
    setFormActionType(item.action_type || 'VIEW');
    setFormDescription(item.description || '');
    setProductModalOpen(true);
  };

  const openAddServiceModal = () => {
    setEditingItem(null);
    setFormName('');
    setFormCategory(activeProject?.primary_category || 'Services');
    setFormPrice('');
    setFormPriceRange('');
    setFormImageUrl('');
    setFormActionUrl('');
    setFormActionType('BOOK');
    setFormDescription('');
    setServiceModalOpen(true);
  };

  const openEditServiceModal = (item: ProductOrServiceItem) => {
    setEditingItem(item);
    setFormName(item.name || '');
    setFormCategory(item.category || '');
    setFormPrice(item.price || '');
    setFormPriceRange(item.price_range || '');
    setFormImageUrl('');
    setFormActionUrl(item.action_url || '');
    setFormActionType(item.action_type || 'BOOK');
    setFormDescription(item.description || '');
    setServiceModalOpen(true);
  };

  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !formName.trim()) return;
    try {
      setSubmitting(true);
      const payload = {
        name: formName.trim(),
        description: formDescription.trim() || undefined,
        category: formCategory.trim() || undefined,
        price: formPrice.trim() || undefined,
        price_range: formPriceRange.trim() || undefined,
        image_url: formImageUrl.trim() || undefined,
        action_url: formActionUrl.trim() || undefined,
        action_type: formActionType
      };

      if (editingItem) {
        const resp = await api.put(`/gbp/${activeProject.id}/products/${editingItem.id}`, payload);
        const updated = resp.data;
        setItems(prev => prev.map(it => it.id === editingItem.id ? updated : it));
        setStatusMsg({ type: 'success', text: `Product "${formName}" updated successfully.` });
      } else {
        const resp = await api.post(`/gbp/${activeProject.id}/products`, payload);
        const created = resp.data;
        setItems(prev => [created, ...prev]);
        setStatusMsg({ type: 'success', text: `Product "${formName}" created successfully.` });
      }
      setProductModalOpen(false);
    } catch (err: any) {
      console.error('Failed to save product:', err);
      setStatusMsg({ type: 'error', text: getErrorMessage(err, 'Failed to save product.') });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveService = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !formName.trim()) return;
    try {
      setSubmitting(true);
      const payload = {
        name: formName.trim(),
        description: formDescription.trim() || undefined,
        category: formCategory.trim() || undefined,
        price: formPrice.trim() || undefined,
        price_range: formPriceRange.trim() || undefined,
        action_url: formActionUrl.trim() || undefined,
        action_type: formActionType
      };

      if (editingItem) {
        const resp = await api.put(`/gbp/${activeProject.id}/services/${editingItem.id}`, payload);
        const updated = resp.data;
        setItems(prev => prev.map(it => it.id === editingItem.id ? updated : it));
        setStatusMsg({ type: 'success', text: `Service "${formName}" updated successfully.` });
      } else {
        const resp = await api.post(`/gbp/${activeProject.id}/services`, payload);
        const created = resp.data;
        setItems(prev => [created, ...prev]);
        setStatusMsg({ type: 'success', text: `Service "${formName}" created successfully.` });
      }
      setServiceModalOpen(false);
    } catch (err: any) {
      console.error('Failed to save service:', err);
      setStatusMsg({ type: 'error', text: getErrorMessage(err, 'Failed to save service.') });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteItem = async () => {
    if (!activeProject || !deleteConfirmItem) return;
    try {
      setSubmitting(true);
      const isProd = deleteConfirmItem.type === 'product';
      const endpoint = isProd
        ? `/gbp/${activeProject.id}/products/${deleteConfirmItem.id}`
        : `/gbp/${activeProject.id}/services/${deleteConfirmItem.id}`;
      
      await api.delete(endpoint);
      setItems(prev => prev.filter(it => it.id !== deleteConfirmItem.id));
      setStatusMsg({
        type: 'success',
        text: `${isProd ? 'Product' : 'Service'} "${deleteConfirmItem.name}" deleted successfully.`
      });
      setDeleteConfirmItem(null);
    } catch (err: any) {
      console.error('Failed to delete item:', err);
      setStatusMsg({ type: 'error', text: getErrorMessage(err, 'Failed to delete catalog item.') });
    } finally {
      setSubmitting(false);
    }
  };

  const handleBulkImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProject || !bulkJson.trim()) return;
    try {
      setSubmitting(true);
      const parsed = JSON.parse(bulkJson);
      const payload = {
        products: Array.isArray(parsed.products) ? parsed.products : [],
        services: Array.isArray(parsed.services) ? parsed.services : []
      };

      const resp = await api.post(`/gbp/${activeProject.id}/products-services/bulk-import`, payload);
      if (resp.data) {
        setData(resp.data);
        setItems(resp.data.items || []);
        setStatusMsg({
          type: 'success',
          text: `Bulk imported ${payload.products.length} products and ${payload.services.length} services successfully.`
        });
      }
      setBulkImportModalOpen(false);
      setBulkJson('');
    } catch (err: any) {
      console.error('Failed bulk import:', err);
      setStatusMsg({
        type: 'error',
        text: 'Invalid JSON format. Please ensure valid {"products": [...], "services": [...]} structure.'
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Formatted date helper
  const formatDateTime = (isoStr?: string | null) => {
    if (!isoStr) return 'Not yet synchronized';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
    } catch {
      return isoStr;
    }
  };

  // Filtered items computation
  const filteredItems = useMemo(() => {
    let list = items;
    if (filterType !== 'all') {
      list = list.filter(item => item.type === filterType);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      list = list.filter(item =>
        item.name.toLowerCase().includes(q) ||
        (item.description && item.description.toLowerCase().includes(q)) ||
        (item.category && item.category.toLowerCase().includes(q))
      );
    }
    return list;
  }, [items, filterType, searchQuery]);

  if (!activeProject) {
    return (
      <EmptyState
        icon={ShoppingBag}
        badge="Catalog & Offerings"
        title="Select a Project"
        description="Select a business project to view and manage its verified Google Business Profile products and services."
      />
    );
  }

  const totalProducts = items.filter(i => i.type === 'product').length;
  const totalServices = items.filter(i => i.type === 'service').length;
  const totalItems = totalProducts + totalServices;
  const lastSyncStr = formatDateTime(data?.last_synced_at);

  return (
    <div className="space-y-6">
      {/* ─── Page Header & Controls ─── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl gradient-brand flex items-center justify-center text-white shadow-xs">
              <Package className="w-4 h-4 text-white stroke-[2.4]" />
            </div>
            <span>Products & Services</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Verified business catalog offerings synchronized directly with your Google Business Profile.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={openAddProductModal}
            className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5 shadow-xs cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Product</span>
          </button>
          <button
            onClick={openAddServiceModal}
            className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5 shadow-xs cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Service</span>
          </button>
          <button
            onClick={() => setBulkImportModalOpen(true)}
            className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-all flex items-center space-x-1.5 shadow-2xs cursor-pointer"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Bulk Import</span>
          </button>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="px-4 py-2 bg-[#236B4F] hover:bg-[#1D5A42] text-white text-xs font-bold rounded-xl transition-all flex items-center space-x-2 disabled:opacity-50 shadow-xs cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span>{syncing ? 'Synchronizing...' : 'Sync Catalog'}</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {statusMsg && (
        <div
          className={`p-3.5 rounded-xl border flex items-center space-x-2.5 text-xs ${
            statusMsg.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : 'bg-rose-50 border-rose-200 text-rose-900'
          }`}
        >
          {statusMsg.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-[#236B4F] shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          )}
          <span className="flex-1 font-medium">{statusMsg.text}</span>
          <button
            onClick={() => setStatusMsg(null)}
            className="font-bold opacity-60 hover:opacity-100 px-1 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* ─── Top Overview KPIs ─── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {/* Business Profile Name Card */}
        <div className="col-span-2 sm:col-span-1 p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Business Profile</span>
            <Building2 className="w-4 h-4 text-[#236B4F]" />
          </div>
          <div className="mt-2">
            <h3 className="font-extrabold text-slate-900 text-sm truncate">
              {data?.business_name || activeProject.name}
            </h3>
            <p className="text-[11px] text-slate-400 truncate mt-0.5">
              {data?.connected_account || 'Google Business Profile'}
            </p>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 font-medium flex items-center gap-1">
            <Calendar className="w-3 h-3 text-slate-400" />
            <span>Synced: {lastSyncStr}</span>
          </div>
        </div>

        {/* Total Catalog Offerings */}
        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Total Offerings</span>
            <Layers className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-black text-slate-900">{totalItems}</div>
            <div className="text-[11px] text-slate-500 font-medium mt-0.5">
              Products & Services
            </div>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 font-medium">
            Active Catalog Items
          </div>
        </div>

        {/* Products Count */}
        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Products</span>
            <Package className="w-4 h-4 text-blue-600" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-black text-blue-900">{totalProducts}</div>
            <div className="text-[11px] text-blue-700 font-medium mt-0.5">
              Physical & Digital Goods
            </div>
          </div>
          <div className="mt-2 text-[10px] text-blue-500 font-medium">
            Google Products Catalog
          </div>
        </div>

        {/* Services Count */}
        <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#587568]">Services</span>
            <Wrench className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2">
            <div className="text-2xl font-black text-emerald-900">{totalServices}</div>
            <div className="text-[11px] text-emerald-700 font-medium mt-0.5">
              Service Items & Repairs
            </div>
          </div>
          <div className="mt-2 text-[10px] text-emerald-500 font-medium">
            Google Service List
          </div>
        </div>
      </div>

      {/* ─── Search & Type Filter Bar ─── */}
      <div className="p-4 rounded-2xl border border-[#DCE8DC] bg-white shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* Filter Pills */}
        <div className="flex items-center space-x-1.5 shrink-0 overflow-x-auto pb-1 sm:pb-0">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mr-1">
            Filter:
          </span>
          <button
            onClick={() => setFilterType('all')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              filterType === 'all'
                ? 'bg-[#236B4F] text-white shadow-2xs'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            All Items ({totalItems})
          </button>
          <button
            onClick={() => setFilterType('product')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              filterType === 'product'
                ? 'bg-blue-600 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            Products ({totalProducts})
          </button>
          <button
            onClick={() => setFilterType('service')}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              filterType === 'service'
                ? 'bg-emerald-600 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            Services ({totalServices})
          </button>
        </div>

        {/* Search Input Box */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search items by name, category, or description..."
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-[#236B4F]/20 focus:border-[#236B4F]"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs font-bold"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* ─── Products & Services Grid ─── */}
      <div>
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-400 bg-white rounded-2xl border border-slate-200">
            <RefreshCw className="w-8 h-8 animate-spin text-[#236B4F] mb-3" />
            <p className="text-xs font-bold text-slate-700">Loading catalog items...</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Fetching verified products and services</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-12 text-center bg-white rounded-2xl border border-slate-200">
            <Package className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <h3 className="font-extrabold text-slate-900 text-sm">
              {filterType === 'product'
                ? 'No products are currently available.'
                : filterType === 'service'
                ? 'No services are currently available.'
                : 'No catalog items found.'}
            </h3>
            <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
              {searchQuery
                ? 'No offerings matched your search criteria. Try modifying your search keyword.'
                : 'Create new catalog items or sync with Google Business Profile.'}
            </p>
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                onClick={openAddProductModal}
                className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-xs cursor-pointer"
              >
                Add Product
              </button>
              <button
                onClick={openAddServiceModal}
                className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-xs cursor-pointer"
              >
                Add Service
              </button>
              <button
                onClick={handleSync}
                className="px-4 py-2 bg-[#236B4F] hover:bg-[#1D5A42] text-white rounded-xl text-xs font-bold shadow-xs cursor-pointer"
              >
                Sync with Google
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {filteredItems.map((item) => {
              const isProduct = item.type === 'product';
              const badgeBg = isProduct ? 'bg-blue-100 text-blue-800 border-blue-200' : 'bg-emerald-100 text-emerald-800 border-emerald-200';
              const IconComponent = isProduct ? Package : Wrench;

              return (
                <div
                  key={item.id}
                  className="bg-white rounded-2xl border border-[#DCE8DC] overflow-hidden shadow-xs hover:shadow-md hover:border-[#236B4F]/50 transition-all flex flex-col justify-between group"
                >
                  {/* Item Image or Category Header */}
                  {item.image_url ? (
                    <div className="relative w-full h-44 bg-slate-100 overflow-hidden">
                      <img
                        src={item.image_url}
                        alt={item.name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = 'none';
                        }}
                      />
                      <span className={`absolute top-3 left-3 px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider border shadow-xs ${badgeBg}`}>
                        {item.type}
                      </span>
                      <div className="absolute top-3 right-3 flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => openEditProductModal(item)}
                          className="p-1.5 bg-white/90 hover:bg-white text-slate-700 rounded-lg shadow-xs transition-all"
                          title="Edit"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setDeleteConfirmItem(item)}
                          className="p-1.5 bg-white/90 hover:bg-rose-50 text-rose-600 rounded-lg shadow-xs transition-all"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="p-4 bg-gradient-to-br from-[#F7FAF7] to-slate-100 border-b border-slate-100 flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${isProduct ? 'bg-blue-500 text-white' : 'bg-[#236B4F] text-white'} shadow-xs`}>
                          <IconComponent className="w-4 h-4" />
                        </div>
                        <span className={`px-2 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider border ${badgeBg}`}>
                          {item.type}
                        </span>
                      </div>
                      <div className="flex items-center space-x-1.5">
                        {item.category && (
                          <span className="text-[10px] font-bold text-slate-500 bg-white/80 px-2 py-0.5 rounded border border-slate-200 truncate max-w-[100px]">
                            {item.category}
                          </span>
                        )}
                        <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => isProduct ? openEditProductModal(item) : openEditServiceModal(item)}
                            className="p-1 text-slate-400 hover:text-slate-700 transition-colors"
                            title="Edit"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => setDeleteConfirmItem(item)}
                            className="p-1 text-rose-400 hover:text-rose-600 transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Item Content Body */}
                  <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
                    <div className="space-y-1.5">
                      <h4 className="font-extrabold text-slate-900 text-sm line-clamp-1 group-hover:text-[#236B4F] transition-colors">
                        {item.name}
                      </h4>

                      {item.description ? (
                        <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed font-normal">
                          {item.description}
                        </p>
                      ) : (
                        <p className="text-xs text-slate-400 italic">
                          No detailed description provided.
                        </p>
                      )}
                    </div>

                    <div className="space-y-2 pt-2 border-t border-slate-100">
                      {/* Price / Price Range */}
                      {(item.price || item.price_range) && (
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-[10px] font-bold uppercase text-slate-400">Price:</span>
                          <span className="font-black text-slate-900 text-sm">
                            {item.price || item.price_range}
                          </span>
                        </div>
                      )}

                      {/* Action Link Button */}
                      {item.action_url && (
                        <a
                          href={item.action_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="w-full py-1.5 px-3 rounded-xl bg-[#F7FAF7] hover:bg-[#EBF2EB] border border-[#DCE8DC] text-[#236B4F] text-xs font-bold transition-all flex items-center justify-center space-x-1.5 mt-2"
                        >
                          <span>{item.action_type === 'BOOK' ? 'Book Service' : (item.action_type === 'ORDER' ? 'Order Now' : 'View Details')}</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}

                      {/* Source Metadata & Inline Action */}
                      <div className="text-[10px] text-slate-400 flex items-center justify-between pt-1">
                        <span>Source:</span>
                        <span className="font-semibold text-slate-600">
                          {item.source === 'LOCALLIFT_MANUAL'
                            ? 'LocalLift (Manual)'
                            : item.source === 'AI_SUGGESTED'
                            ? 'AI Suggested'
                            : item.source === 'WEBSITE_IMPORTED'
                            ? 'Website Imported'
                            : 'Google Business Profile'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ─── Product Modal (Create / Edit) ─── */}
      <Modal
        isOpen={productModalOpen}
        onClose={() => setProductModalOpen(false)}
        maxWidth="lg"
        title={editingItem ? 'Edit Product' : 'Add New Product'}
        description="Local SEO Product Catalog"
      >
        <form onSubmit={handleSaveProduct} className="space-y-3 text-xs">
          <div>
            <label className="text-slate-700 block mb-1 font-bold">Product Name *</label>
            <input
              type="text"
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. Premium Filter Set"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Category</label>
              <input
                type="text"
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
                placeholder="e.g. Products, Hardware"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
              />
            </div>
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Price / Price Range</label>
              <input
                type="text"
                value={formPrice}
                onChange={(e) => setFormPrice(e.target.value)}
                placeholder="e.g. $49.99 or $40 - $60"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
              />
            </div>
          </div>
          <div>
            <label className="text-slate-700 block mb-1 font-bold">Image URL</label>
            <input
              type="url"
              value={formImageUrl}
              onChange={(e) => setFormImageUrl(e.target.value)}
              placeholder="https://example.com/product.jpg"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Action URL</label>
              <input
                type="url"
                value={formActionUrl}
                onChange={(e) => setFormActionUrl(e.target.value)}
                placeholder="https://..."
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
              />
            </div>
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Action Button Label</label>
              <select
                value={formActionType}
                onChange={(e) => setFormActionType(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
              >
                <option value="VIEW">View Details</option>
                <option value="ORDER">Order Now</option>
                <option value="BUY">Buy Online</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-slate-700 block mb-1 font-bold">Description</label>
            <textarea
              rows={3}
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              placeholder="Detailed product features, specifications, and warranty..."
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
            />
          </div>

          <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setProductModalOpen(false)}
              className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 font-bold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold disabled:opacity-50 shadow-xs"
            >
              {submitting ? 'Saving...' : editingItem ? 'Update Product' : 'Save Product'}
            </button>
          </div>
        </form>
      </Modal>

      {/* ─── Service Modal (Create / Edit) ─── */}
      <Modal
        isOpen={serviceModalOpen}
        onClose={() => setServiceModalOpen(false)}
        maxWidth="lg"
        title={editingItem ? 'Edit Service' : 'Add New Service'}
        description="Local SEO Service Catalog"
      >
        <form onSubmit={handleSaveService} className="space-y-3 text-xs">
          <div>
            <label className="text-slate-700 block mb-1 font-bold">Service Name *</label>
            <input
              type="text"
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. Emergency Pipe Repair"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Category</label>
              <input
                type="text"
                value={formCategory}
                onChange={(e) => setFormCategory(e.target.value)}
                placeholder="e.g. Plumbing, Installations"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
              />
            </div>
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Price / Rate</label>
              <input
                type="text"
                value={formPrice}
                onChange={(e) => setFormPrice(e.target.value)}
                placeholder="e.g. $85/hr or Fixed Estimate"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Booking / Action URL</label>
              <input
                type="url"
                value={formActionUrl}
                onChange={(e) => setFormActionUrl(e.target.value)}
                placeholder="https://..."
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
              />
            </div>
            <div>
              <label className="text-slate-700 block mb-1 font-bold">Action Button Label</label>
              <select
                value={formActionType}
                onChange={(e) => setFormActionType(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
              >
                <option value="BOOK">Book Service</option>
                <option value="QUOTE">Request Quote</option>
                <option value="CALL">Call Now</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-slate-700 block mb-1 font-bold">Description</label>
            <textarea
              rows={3}
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              placeholder="Service coverage, response times, certifications, and deliverables..."
              className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2.5 text-slate-900 focus:outline-none focus:border-emerald-500 font-medium"
            />
          </div>

          <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setServiceModalOpen(false)}
              className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 font-bold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold disabled:opacity-50 shadow-xs"
            >
              {submitting ? 'Saving...' : editingItem ? 'Update Service' : 'Save Service'}
            </button>
          </div>
        </form>
      </Modal>

      {/* ─── Bulk Import Modal ─── */}
      <Modal
        isOpen={bulkImportModalOpen}
        onClose={() => setBulkImportModalOpen(false)}
        maxWidth="lg"
        title="Bulk Import Products & Services"
        description="Paste JSON containing products and services arrays to import catalog items in bulk."
      >
        <form onSubmit={handleBulkImport} className="space-y-3 text-xs">
          <textarea
            rows={8}
            required
            value={bulkJson}
            onChange={(e) => setBulkJson(e.target.value)}
            placeholder={`{\n  "products": [\n    {"name": "Filter Model A", "price": "$39.99", "category": "Hardware"}\n  ],\n  "services": [\n    {"name": "Standard Inspection", "price": "$79", "category": "Maintenance"}\n  ]\n}`}
            className="w-full bg-slate-50 border border-slate-200 rounded-lg p-3 font-mono text-[11px] text-slate-900 focus:outline-none focus:border-emerald-500"
          />
          <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setBulkImportModalOpen(false)}
              className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 font-bold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold disabled:opacity-50 shadow-xs"
            >
              {submitting ? 'Importing...' : 'Import Catalog'}
            </button>
          </div>
        </form>
      </Modal>

      {/* ─── Delete Confirmation Modal ─── */}
      <Modal
        isOpen={Boolean(deleteConfirmItem)}
        onClose={() => setDeleteConfirmItem(null)}
        maxWidth="sm"
        title="Confirm Deletion"
        description={`Remove item from your ${deleteConfirmItem?.type || 'catalog'}`}
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-600 leading-relaxed">
            Are you sure you want to delete <span className="font-bold text-slate-900">"{deleteConfirmItem?.name}"</span> from your {deleteConfirmItem?.type} catalog?
          </p>
          <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setDeleteConfirmItem(null)}
              className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 font-bold text-xs"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleDeleteItem}
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs disabled:opacity-50 shadow-xs"
            >
              {submitting ? 'Deleting...' : 'Yes, Delete'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default ProductsServicesView;

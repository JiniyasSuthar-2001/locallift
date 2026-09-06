import React, { useState, useEffect } from 'react';
import {
  Star,
  MessageSquare,
  Sparkles,
  CheckCircle2,
  Send,
  ThumbsUp,
  AlertCircle,
  Filter,
  Check
} from 'lucide-react';
import { useProject } from '../context/ProjectContext';
import { Review } from '../types';
import { StatusBadge } from '../components/ui/StatusBadge';
import { EmptyState } from '../components/ui/EmptyState';
import api from '../api/client';

export const ReviewsView: React.FC = () => {
  const { activeProject } = useProject();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(false);
  const [draftingId, setDraftingId] = useState<number | null>(null);
  const [editingReply, setEditingReply] = useState<{ [id: number]: string }>({});
  const [filterSentiment, setFilterSentiment] = useState('all');

  const fetchReviews = async () => {
    if (!activeProject) return;
    try {
      setLoading(true);
      const resp = await api.get(`/local-seo/reviews/${activeProject.id}`);
      setReviews(resp.data || []);
    } catch (e) {
      console.error('Failed to load reviews:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews();
  }, [activeProject?.id]);

  const handleGenerateReply = async (reviewId: number) => {
    try {
      setDraftingId(reviewId);
      const resp = await api.post(`/ai/review-response/${reviewId}`);
      setEditingReply(prev => ({ ...prev, [reviewId]: resp.data.draft_response }));
      await fetchReviews();
    } catch (e) {
      console.error('AI draft generation failed:', e);
    } finally {
      setDraftingId(null);
    }
  };

  const handlePublishReply = async (reviewId: number) => {
    try {
      const responseText = editingReply[reviewId];
      await api.post(`/local-seo/reviews/${reviewId}/respond`, {
        response_text: responseText
      });
      await fetchReviews();
    } catch (e) {
      console.error('Publishing reply failed:', e);
    }
  };

  const filtered = reviews.filter(r => {
    if (filterSentiment === 'all') return true;
    return r.sentiment?.toLowerCase() === filterSentiment.toLowerCase();
  });

  const totalReviews = reviews.length;
  const avgRating = totalReviews > 0 ? (reviews.reduce((acc, r) => acc + r.rating, 0) / totalReviews).toFixed(1) : '0.0';
  const positiveCount = reviews.filter(r => r.sentiment === 'positive').length;

  if (!activeProject) {
    return (
      <EmptyState
        icon={Star}
        badge="Reviews Hub"
        title="Select a Project"
        description="Select a business project to view customer feedback, analyze review sentiment, and draft AI responses."
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center space-x-2">
            <Star className="w-6 h-6 text-purple-600" />
            <span>Customer Reviews & AI Reputation</span>
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Monitor incoming customer reviews, analyze sentiment themes, and draft approved responses before publishing.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <select
            value={filterSentiment}
            onChange={(e) => setFilterSentiment(e.target.value)}
            className="bg-white border border-slate-200 rounded-xl px-3 py-1.5 text-xs font-bold text-slate-800 focus:outline-none focus:border-purple-500 cursor-pointer"
          >
            <option value="all">All Sentiments</option>
            <option value="positive">Positive</option>
            <option value="neutral">Neutral</option>
            <option value="negative">Negative</option>
          </select>
        </div>
      </div>

      {/* Overview Stat Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card-vibrant p-4 space-y-1">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">Average Rating</span>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl font-black text-slate-900">{avgRating}</span>
            <div className="text-amber-400 text-sm">★★★★★</div>
          </div>
          <span className="text-[11px] text-slate-500 font-medium">Across all verified reviews</span>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">Total Reviews</span>
          <div className="text-2xl font-black text-slate-900">{totalReviews}</div>
          <span className="text-[11px] text-purple-700 font-bold">Google Business Profile</span>
        </div>

        <div className="card-vibrant p-4 space-y-1">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">Positive Sentiment</span>
          <div className="text-2xl font-black text-emerald-700">
            {totalReviews > 0 ? Math.round((positiveCount / totalReviews) * 100) : 0}%
          </div>
          <span className="text-[11px] text-slate-500 font-medium">{positiveCount} positive feedbacks</span>
        </div>
      </div>

      {/* Reviews List */}
      <div className="space-y-4">
        {filtered.length > 0 ? (
          filtered.map((rev) => {
            const hasDraft = rev.ai_draft_response || editingReply[rev.id];
            const isDrafting = draftingId === rev.id;

            return (
              <div
                key={rev.id}
                className="card-vibrant p-5 space-y-4 transition-all"
              >
                {/* Author & Rating */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-full gradient-brand text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-sm">
                      {rev.author_name ? rev.author_name[0] : 'U'}
                    </div>
                    <div>
                      <h4 className="font-extrabold text-slate-900 text-sm">{rev.author_name}</h4>
                      <div className="text-[11px] text-slate-400 font-medium">
                        {rev.review_date || rev.published_at ? new Date(rev.review_date || rev.published_at || '').toLocaleDateString() : 'Recent'}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3">
                    <div className="flex text-amber-400 text-xs">
                      {'★'.repeat(rev.rating)}
                      <span className="text-slate-200">{'★'.repeat(Math.max(0, 5 - rev.rating))}</span>
                    </div>
                    <StatusBadge status={rev.sentiment || 'neutral'} />
                  </div>
                </div>

                {/* Review Text */}
                <p className="text-xs text-slate-700 leading-relaxed font-medium">
                  "{rev.review_text || 'No review comment provided.'}"
                </p>

                {/* Response Section */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center space-x-1">
                      <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                      <span>Response Management</span>
                    </span>
                    <StatusBadge status={rev.response_status || 'unanswered'} />
                  </div>

                  {rev.response_status === 'published' ? (
                    <div className="text-xs text-slate-800 bg-white p-3 rounded-lg border border-slate-200 font-medium">
                      <span className="font-bold text-emerald-800 block mb-1">Published Owner Response:</span>
                      {rev.response_text || rev.final_response_text || rev.ai_draft_response}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {hasDraft ? (
                        <div className="space-y-2">
                          <textarea
                            rows={3}
                            value={editingReply[rev.id] !== undefined ? editingReply[rev.id] : (rev.ai_draft_response || '')}
                            onChange={(e) => setEditingReply({ ...editingReply, [rev.id]: e.target.value })}
                            className="w-full bg-white border border-slate-200 rounded-lg p-3 text-xs text-slate-900 focus:outline-none focus:border-purple-500 font-medium"
                          />
                          <div className="flex items-center justify-between pt-1">
                            <span className="text-[11px] text-slate-500">
                              Requires human approval before publishing.
                            </span>
                            <div className="flex space-x-2">
                              <button
                                onClick={() => handleGenerateReply(rev.id)}
                                disabled={isDrafting}
                                className="px-3 py-1.5 rounded-lg btn-vibrant-secondary text-xs font-bold"
                              >
                                {isDrafting ? 'Regenerating...' : 'Regenerate'}
                              </button>
                              <button
                                onClick={() => handlePublishReply(rev.id)}
                                className="flex items-center space-x-1 px-4 py-1.5 btn-vibrant-primary rounded-lg text-xs font-bold shadow-sm"
                              >
                                <Check className="w-3.5 h-3.5" />
                                <span>Approve & Publish Response</span>
                              </button>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-slate-500 font-medium">
                            No response drafted yet for this customer review.
                          </span>
                          <button
                            onClick={() => handleGenerateReply(rev.id)}
                            disabled={isDrafting}
                            className="flex items-center space-x-1.5 px-3.5 py-2 btn-vibrant-primary rounded-xl text-xs font-bold shadow-sm"
                          >
                            <Sparkles className={`w-3.5 h-3.5 ${isDrafting ? 'animate-spin' : ''}`} />
                            <span>{isDrafting ? 'Drafting with AI...' : 'Draft AI Response'}</span>
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        ) : (
          <EmptyState
            icon={Star}
            badge="No Reviews"
            title="No Reviews Found"
            description="Sync your Google Business Profile to import and manage live customer reviews."
            actionText="Sync Reviews"
            actionLink="/google/gbp"
          />
        )}
      </div>
    </div>
  );
};

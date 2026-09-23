export interface User {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  organization_id: number | null;
  role: string | null;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}

export interface Location {
  id: number;
  project_id: number;
  name: string;
  address?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  country?: string;
  phone?: string;
  latitude?: number;
  longitude?: number;
  place_id?: string;
}

export interface BusinessCategory {
  id: string;
  name: string;
  slug: string;
  group: string;
  aliases?: string[];
  schema_type?: string;
  gbp_category?: string;
  is_popular?: boolean;
}

export interface Project {
  id: number;
  organization_id: number;
  client_id?: number;
  name: string;
  domain: string;
  primary_category: string;
  additional_categories?: string[];
  country: string;
  status?: string;
  is_archived?: boolean;
  team_member_count?: number;
  health_score?: number | null;
  technical_score?: number | null;
  onpage_score?: number | null;
  local_score?: number | null;
  gbp_score?: number | null;
  reviews_score?: number | null;
  citations_score?: number | null;
  keywords_score?: number | null;
  maps_score?: number | null;
  public_maps_url?: string | null;
  created_at: string;
  updated_at: string;
  locations: Location[];
}


export interface DashboardSummary {
  health_score?: number | null;
  scores: {
    technical?: number | null;
    onpage?: number | null;
    local?: number | null;
    gbp?: number | null;
    reviews?: number | null;
    citations?: number | null;
    keywords?: number | null;
    maps?: number | null;
  };
  counts: {
    open_issues: number;
    active_tasks: number;
    tracked_keywords: number;
    reviews_total: number;
  };
  recent_issues: SEOIssue[];
  recent_tasks: SEOTask[];
  recent_reviews: Review[];
  top_keywords: Keyword[];
  gbp_summary?: {
    connected: boolean;
    business_name?: string;
    completeness_score?: number | null;
    search_impressions?: number;
    maps_impressions?: number;
    calls?: number;
    website_clicks?: number;
  };
  gsc_summary?: {
    connected?: boolean;
    has_data?: boolean;
    clicks?: number | null;
    impressions?: number | null;
    ctr?: number | null;
    avg_position?: number | null;
    status?: string;
  };
  ga4_summary?: {
    connected?: boolean;
    has_data?: boolean;
    organic_users?: number | null;
    sessions?: number | null;
    engagement_rate?: number | null;
    conversions?: number | null;
    status?: string;
  };
}

export interface SEOIssue {
  id: number;
  project_id: number;
  audit_id?: number;
  category: string;
  severity: 'critical' | 'warning' | 'opportunity' | 'info' | string;
  title: string;
  evidence?: string;
  why_it_matters?: string;
  recommended_solution?: string;
  action_type?: string;
  affected_url?: string;
  status: 'open' | 'in_task' | 'resolved' | 'ignored' | string;
  created_at: string;
}

export interface SEOTask {
  id: number;
  project_id: number;
  issue_id?: number;
  assigned_to_id?: number;
  title: string;
  description?: string;
  priority: 'high' | 'medium' | 'low' | string;
  category: string;
  status: 'open' | 'in_progress' | 'waiting' | 'completed' | 'ignored' | 'recheck_required' | string;
  evidence?: string;
  notes?: string;
  due_date?: string;
  created_at: string;
  completed_at?: string;
}

export interface WebsitePage {
  id: number;
  website_id: number;
  url: string;
  status_code: number;
  title?: string;
  meta_description?: string;
  h1?: string;
  h2_list: string[];
  word_count: number;
  canonical_url?: string;
  is_indexable: boolean;
  load_time_ms: number;
  schema_types: string[];
  images_count: number;
  missing_alt_count: number;
  internal_links_count: number;
  external_links_count: number;
  broken_links: string[];
  issues_detected: string[];
}

export interface Keyword {
  id: number;
  project_id: number;
  keyword: string;
  search_intent: string;
  search_volume: number;
  difficulty?: number;
  target_location?: string;
  current_rank?: number | null;
  previous_rank?: number | null;
  target_rank?: number;
  ranking_url?: string;
  serp_type?: string;
  opportunity_score?: string;
  business_relevance?: string;
  last_checked_at?: string;
}

export interface GridPoint {
  point_number?: number;
  row: number;
  col: number;
  lat: number;
  lng: number;
  latitude?: number;
  longitude?: number;
  rank: number | null;
  status: 'SUCCESS' | 'NOT_FOUND' | 'PROVIDER_ERROR' | 'TIMEOUT' | 'green' | 'yellow' | 'red' | string;
  pin_status?: 'found' | 'not_found' | 'failed' | string;
  keyword?: string;
  provider?: string;
  matched_business?: string | null;
  matched_place_id?: string | null;
  matched_domain?: string | null;
  ranking_url?: string;
  competitor_ahead?: string;
  searched_at?: string;
  error?: string | null;
}

export interface GeoGridProviderInfo {
  name: string;
  is_configured: boolean;
  live: boolean;
  status: string;
}

export interface GeoGridScan {
  id: number;
  scan_id?: number;
  project_id: number;
  keyword_id: number;
  keyword?: string;
  center_name: string;
  center_lat: number;
  center_lng: number;
  center?: {
    lat: number;
    lng: number;
    name?: string;
  };
  radius_km: number;
  grid_size: number;
  average_rank?: number | null;
  local_visibility_pct: number;
  scan_status?: 'completed' | 'completed_with_errors' | 'failed' | string;
  total_points?: number;
  successful_points?: number;
  failed_points?: number;
  completed_points?: number;
  ranking_found_points?: number;
  not_found_points?: number;
  provider_error_points?: number;
  timeout_points?: number;
  provider?: GeoGridProviderInfo;
  grid_points: GridPoint[];
  points?: GridPoint[];
  scanned_at: string;
}

export interface Review {
  id: number;
  project_id: number;
  source?: string;
  author_name: string;
  author_photo_url?: string;
  rating: number;
  review_text?: string;
  review_date?: string;
  published_at?: string;
  response_text?: string;
  final_response_text?: string;
  ai_draft_response?: string;
  response_status?: 'unanswered' | 'drafted' | 'approved' | 'published' | string;
  sentiment?: 'positive' | 'neutral' | 'negative' | string;
  sentiment_score?: number;
  topics?: string[];
}

export interface BusinessProfile {
  id: number;
  project_id: number;
  business_name: string;
  website?: string | null;
  primary_phone?: string | null;
  primary_address?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  primary_category?: string | null;
  additional_categories?: string[];
  service_area?: string | null;
  place_id?: string | null;
  maps_url?: string | null;
  source: string;
  verification_status: 'VERIFIED' | 'OBSERVED' | 'USER_PROVIDED' | 'DETECTED' | 'INFERRED' | 'NOT_VERIFIED' | 'FAILED' | 'NOT_APPLICABLE' | string;
  last_verified_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  id: number;
  project_id: number;
  source_name: string;
  directory_name?: string;
  domain?: string;
  listing_url?: string | null;
  domain_authority?: number | null;
  category: string;
  status: string; // 'listed' | 'missing' | 'incorrect' | 'pending' | 'active'
  nap_status: string; // 'match' | 'consistent' | 'mismatch' | 'missing'
  citation_type?: string;
  verification_status?: string;
  confidence?: number | null;
  evidence?: Record<string, any>;
  source_type?: string;
  found_name?: string | null;
  found_address?: string | null;
  found_phone?: string | null;
  found_website?: string | null;
  last_checked_at: string;
}

export interface NAPRecord {
  id: number;
  project_id: number;
  source_name?: string;
  listed_name?: string;
  listed_address?: string;
  listed_phone?: string;
  has_discrepancy?: boolean;
  canonical_name?: string;
  canonical_address?: string;
  canonical_phone?: string;
  canonical_website?: string;
  nap_score?: number;
  total_checked?: number;
  consistent_count?: number;
  mismatches_count?: number;
  mismatches_data?: Array<{
    directory: string;
    field: string;
    expected: string;
    found: string;
    severity: string;
    action: string;
  }>;
  last_audit_date?: string;
}

export interface Competitor {
  id: number;
  project_id: number;
  name: string;
  domain?: string;
  gbp_name?: string;
  rating?: number;
  reviews_count?: number;
  total_reviews?: number;
  avg_maps_rank?: number;
  local_visibility_score?: number;
  top_keywords_count?: number;
  place_id?: string;
  categories?: string[];
  gbp_status?: string;
  citations_count?: number;
  backlinks_count?: number;
  geo_grid_share_pct?: number;
  tracked_keywords_overlap?: number;
  comparison_data?: Record<string, any>;
  opportunities_found?: string[];
}

export interface LocalAuditFinding {
  id: number;
  project_id: number;
  audit_run_id: number;
  category: string;
  check_key: string;
  title: string;
  status: 'PASS' | 'PARTIAL' | 'FAIL' | 'NOT_VERIFIED' | 'NOT_APPLICABLE' | 'ERROR';
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
  score_impact: number;
  evidence?: Record<string, any>;
  source?: string;
  source_url?: string;
  verification_status: 'VERIFIED' | 'OBSERVED' | 'USER_PROVIDED' | 'DETECTED' | 'INFERRED' | 'NOT_VERIFIED' | 'FAILED' | 'NOT_APPLICABLE';
  recommendation?: string;
  created_at: string;
}

export interface LocalAuditRun {
  id: number;
  project_id: number;
  framework_version: string;
  status: 'COMPLETED' | 'RUNNING' | 'FAILED' | string;
  overall_score?: number | null;
  category_scores: Record<string, any>;
  findings_summary?: {
    total?: number;
    pass?: number;
    fail?: number;
    partial?: number;
    not_verified?: number;
    not_applicable?: number;
    [key: string]: any;
  };
  total_checks?: number;
  passed_checks?: number;
  failed_checks?: number;
  not_verified_checks?: number;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string;
  executed_at?: string;
  findings: LocalAuditFinding[];
}

export interface LocalVisibilityStats {
  total_points: number;
  valid_observations: number;
  failed_observations: number;
  top3_count: number;
  top10_count: number;
  top3_visibility_pct: number;
  top10_visibility_pct: number;
  average_rank: number | null;
}

export interface GBPProfile {
  id: number;
  business_name: string;
  primary_category: string;
  additional_categories?: string[];
  address?: string;
  phone?: string;
  website_url?: string;
  description?: string;
  completeness_score: number;
  is_verified?: boolean;
  search_impressions: number;
  maps_impressions: number;
  website_clicks: number;
  call_clicks: number;
  direction_requests?: number;
  photos_count?: number;
  posts_count?: number;
  last_synced_at?: string;
}

export type GoogleBusinessProfile = GBPProfile;

export interface GBPChange {
  id: number;
  field_name: string;
  old_value?: string;
  new_value?: string;
  detected_at: string;
}

export interface AICauseEvidence {
  category: string;
  description: string;
  confidence: 'Confirmed' | 'Likely' | 'Possible' | 'Unknown';
}

export interface AIAnalysisResponse {
  summary: string;
  likely_causes: AICauseEvidence[];
  evidence_points?: string[];
  recommended_actions: string[];
  actionable_tasks?: string[];
}

export interface ContentOpportunity {
  topic: string;
  page_type: string;
  primary_keyword: string;
  secondary_keywords: string[];
  search_intent: string;
  search_volume?: number | null;
  search_volume_status?: string;
  business_value: string;
  competition_level?: string;
  target_slug: string;
}

export interface TemplateVariable {
  name: string;
  label?: string;
  required?: boolean;
  source?: string;
  default?: string;
}

export interface Template {
  id: number;
  project_id?: number;
  organization_id?: number;
  name: string;
  slug: string;
  category: 'gbp' | 'local_seo' | 'schema' | 'review_response' | 'local_content' | 'location_page' | 'service_location' | 'task' | 'reporting' | string;
  template_type: 'schema_jsonld' | 'content_markdown' | 'review_reply' | 'gbp_post' | 'task_blueprint' | 'report_summary' | string;
  description?: string;
  content: string;
  variables: TemplateVariable[];
  required_fields: string[];
  is_system: boolean;
  standard_type: string;
  version: number;
  usage_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface TemplateApplyResponse {
  template_id: number;
  template_name: string;
  rendered_content: string;
  variables_used: Record<string, any>;
  missing_variables: string[];
}

export interface TemplateValidateResponse {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  detected_variables: string[];
}

export interface SchemaPropertyResult {
  property: string;
  value: string;
  source?: string;
  confidence?: number;
  status: 'Verified' | 'User Provided' | 'Detected' | 'Missing' | string;
}

export interface SchemaRecommendation {
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  affected_url?: string;
  why: string;
  evidence: string;
  expected_improvement: string;
  action_type: string;
  action_label?: string;
}

export interface Tier1SchemaInfo {
  status: 'Detected' | 'Missing' | 'Invalid' | 'Not Applicable';
  applicability: 'Highly Applicable' | 'Applicable' | 'Potentially Applicable' | 'Not Applicable';
  reason: string;
}

export interface SchemaRecord {
  id: number;
  project_id: number;
  page_url: string;
  schema_type: string;
  page_type?: string;
  business_type?: string;
  is_valid: boolean;
  quality_score: number;
  score_breakdown?: Record<string, number>;
  detected_types: string[];
  applicable_schemas?: Record<string, any>;
  errors: string[];
  warnings: string[];
  missing_properties?: string[];
  property_results?: SchemaPropertyResult[];
  recommendations?: SchemaRecommendation[];
  schema_source?: string;
  schema_entities?: any[];
  nap_status?: 'Consistent' | 'Mismatch' | 'Not Applicable' | string;
  raw_json_ld?: string | null;
  generated_json_ld?: string | null;
  last_validated_at: string;
}

export interface SchemaIntelligenceSummary {
  project_id: number;
  domain: string;
  health_score: number;
  score_breakdown: {
    detection: number;
    validity: number;
    completeness: number;
    data_accuracy: number;
    relationships: number;
    applicability: number;
  };
  deductions: string[];
  stats: {
    pages_crawled: number;
    schemas_detected: number;
    valid_count: number;
    warnings_count: number;
    errors_count: number;
    missing_opportunities: number;
  };
  tier_1_status: Record<string, Tier1SchemaInfo>;
  industry_type: string;
  records: SchemaRecord[];
  recommendations: SchemaRecommendation[];
}

export interface SchemaValidationResult {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  entities: string[];
}

export interface SingleServiceStatus {
  connected: boolean;
  google_email?: string;
  status: 'connected' | 'expired' | 'error' | 'disconnected' | 'not_connected' | string;
  scopes?: string[];
  last_sync_at?: string;
  last_error?: string;
  resource_count?: number;
}

export interface GoogleConnectionSummary {
  business_profile?: SingleServiceStatus;
  google_ads?: SingleServiceStatus;
  search_console?: SingleServiceStatus;
  analytics?: SingleServiceStatus;

  connected?: boolean;
  is_connected?: boolean;
  google_email?: string;
  account_email?: string;
  status?: string;
  created_at?: string;
  last_sync_at?: string;
  last_error?: string;
  sync_error?: string;
  has_gbp?: boolean;
  has_ads?: boolean;
  has_gsc?: boolean;
  has_ga4?: boolean;
  counts?: {
    gbp_locations: number;
    ads_accounts: number;
    gsc_properties: number;
    ga4_properties: number;
    public_listings: number;
  };
}

export interface DiscoveredGBPLocation {
  account_id: string;
  location_id: string;
  location_name: string;
  address?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  country?: string;
  phone?: string;
  website_url?: string;
  category?: string;
  maps_uri?: string;
  latitude?: number;
  longitude?: number;
  already_imported?: boolean;
}

export interface GoogleAdsAccountItem {
  id: number;
  customer_id: string;
  descriptive_name?: string;
  currency_code?: string;
  time_zone?: string;
  status?: string;
  is_active: boolean;
  last_sync_at?: string;
}

export interface GoogleSearchConsoleItem {
  id?: number;
  site_url: string;
  permission_level?: string;
  is_active?: boolean;
  project_id?: number | null;
  last_sync_at?: string;
}

export interface GoogleAnalyticsItem {
  id?: number;
  property_id: string;
  property_name?: string;
  account_name?: string;
  is_active?: boolean;
  project_id?: number | null;
  last_sync_at?: string;
}

export interface PublicBusinessListingItem {
  id: number;
  organization_id: number;
  project_id?: number | null;
  place_id?: string | null;
  name: string;
  formatted_address?: string | null;
  phone?: string | null;
  website_url?: string | null;
  primary_category?: string | null;
  rating?: number | null;
  review_count?: number | null;
  maps_url?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  is_managed?: boolean;
  monitoring_status?: string;
  created_at?: string | null;
  last_checked_at?: string | null;
}

export interface DiscoveredResourcesResponse {
  connected: boolean;
  gbp_locations: DiscoveredGBPLocation[];
  ads_accounts: GoogleAdsAccountItem[];
  gsc_properties: GoogleSearchConsoleItem[];
  ga4_properties: GoogleAnalyticsItem[];
  message: string;
}

export interface TeamMember {
  id: number;
  user_id: number;
  name: string;
  email: string;
  role: string;
  permissions: string[];
  status: string;
  created_at: string;
}

export interface TeamInvitation {
  id: number;
  project_id: number;
  project_name: string;
  email: string;
  role: string;
  permissions: string[];
  status: string;
  invited_by_name?: string;
  created_at: string;
  expires_at: string;
}

export interface ProjectTeamSummary {
  project_id: number;
  project_name: string;
  owner: {
    name: string;
    email: string;
    role: string;
  };
  seats_used: number;
  max_seats: number;
  seats_available: number;
  members: TeamMember[];
  pending_invitations: TeamInvitation[];
}

export interface UserPendingInvitation {
  id: number;
  project_id: number;
  project_name: string;
  project_domain: string;
  organization_name: string;
  invited_by_name: string;
  role: string;
  permissions: string[];
  created_at: string;
  expires_at: string;
}

export interface TeamDirectoryMember {
  user_id: number;
  name: string;
  email: string;
  global_role: string;
  project_count: number;
  projects: {
    id: number;
    name: string;
    role: string;
    permissions: string[];
  }[];
  status: string;
}




// ============================================================
// Local SEO Intelligence Types (Part 2 Architecture)
// ============================================================

export interface LocalIntelligenceSummary {
  project_id: number;
  audit: {
    id: number;
    overall_score: number | null;
    category_scores: Record<string, number | null>;
    findings_summary: {
      total?: number;
      pass?: number;
      fail?: number;
      partial?: number;
      not_verified?: number;
      not_applicable?: number;
    };
    status: string;
    completed_at: string | null;
  } | null;
  geo_visibility: {
    id: number;
    keyword: string | null;
    average_rank: number | null;
    local_visibility_pct: number | null;
    total_points: number | null;
    scan_status: string | null;
    scanned_at: string | null;
  } | null;
  keywords: {
    total: number;
    average_rank: number | null;
  };
  reviews: {
    total: number;
    average_rating: number | null;
    unanswered: number;
  };
  citations: {
    total: number;
    nap_conflicts: number;
  };
  business_profile: {
    business_name: string;
    verification_status: string;
    has_coordinates: boolean;
    has_phone: boolean;
    has_address: boolean;
    primary_category: string | null;
  } | null;
  gbp: {
    connected: boolean;
    business_name?: string;
    completeness_score?: number | null;
    is_verified?: boolean | null;
  } | null;
  open_issues: number;
  active_tasks: number;
  priority_findings: PriorityFinding[];
}

export interface PriorityFinding {
  id: number;
  category: string;
  check_key: string;
  title: string;
  status: string;
  severity: string;
  evidence: string | null;
  recommendation: string | null;
  verification_status: string;
}

export interface GeoGridHistoryEntry {
  id: number;
  keyword_id: number;
  keyword: string | null;
  center_name: string;
  center_lat: number;
  center_lng: number;
  radius_km: number;
  grid_size: number;
  average_rank: number | null;
  local_visibility_pct: number | null;
  total_points: number | null;
  completed_points: number | null;
  ranking_found_points: number | null;
  not_found_points: number | null;
  provider_error_points: number | null;
  scan_status: string | null;
  scanned_at: string;
}

export interface GeoGridComparison {
  scan_a: {
    id: number;
    average_rank: number | null;
    local_visibility_pct: number | null;
    scanned_at: string;
  };
  scan_b: {
    id: number;
    average_rank: number | null;
    local_visibility_pct: number | null;
    scanned_at: string;
  };
  delta: {
    average_rank_change: number | null;
    visibility_change: number | null;
  };
  point_comparisons: {
    point_number: number;
    rank_a: number | null;
    rank_b: number | null;
    rank_change: number | null;
    status_a: string;
    status_b: string;
  }[];
}

/** 20 audit category keys used in the framework */
export type AuditCategoryKey =
  | 'google_business_profile'
  | 'categories_taxonomy'
  | 'reviews_reputation'
  | 'nap_consistency'
  | 'local_onpage_seo'
  | 'proximity_location'
  | 'citations_directories'
  | 'local_backlinks'
  | 'review_responses'
  | 'gbp_media'
  | 'local_landing_pages'
  | 'gbp_activity'
  | 'website_authority'
  | 'internal_linking'
  | 'technical_seo'
  | 'schema_localbusiness'
  | 'local_content'
  | 'social_brand_signals'
  | 'user_engagement'
  | 'competitor_market_analysis';

/** Human-readable display names for audit categories */
export const AUDIT_CATEGORY_LABELS: Record<AuditCategoryKey, string> = {
  google_business_profile: 'Google Business Profile',
  categories_taxonomy: 'Categories & Taxonomy',
  reviews_reputation: 'Reviews & Reputation',
  nap_consistency: 'NAP Consistency',
  local_onpage_seo: 'Local On-Page SEO',
  proximity_location: 'Proximity & Location',
  citations_directories: 'Citations & Directories',
  local_backlinks: 'Local Backlinks',
  review_responses: 'Review Responses',
  gbp_media: 'GBP Photos & Media',
  local_landing_pages: 'Local Landing Pages',
  gbp_activity: 'GBP Activity',
  website_authority: 'Website Authority',
  internal_linking: 'Internal Linking',
  technical_seo: 'Technical SEO',
  schema_localbusiness: 'LocalBusiness Schema',
  local_content: 'Local Content',
  social_brand_signals: 'Social & Brand Signals',
  user_engagement: 'User Engagement',
  competitor_market_analysis: 'Competitor Analysis',
};

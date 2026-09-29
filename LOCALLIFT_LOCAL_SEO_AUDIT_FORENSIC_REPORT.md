# LocalLift — Deep Forensic Audit: Local SEO Audit Failures & Architecture Report

**Document Version:** 1.0.0  
**Audit Date:** September 25, 2026  
**Auditor:** Antigravity AI Forensic Engine  
**Target Modules:**  
- **Backend:** [`backend/app/services/local_seo/audit_framework.py`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/backend/app/services/local_seo/audit_framework.py), [`backend/app/api/v1/local_audits.py`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/backend/app/api/v1/local_audits.py), [`backend/app/services/seo_auditor.py`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/backend/app/services/seo_auditor.py), [`backend/app/api/v1/audits.py`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/backend/app/api/v1/audits.py), [`backend/app/services/crawler.py`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/backend/app/services/crawler.py)
- **Frontend:** [`frontend/src/views/LocalSEOAuditView.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/views/LocalSEOAuditView.tsx), [`frontend/src/components/audit/FindingCard.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/components/audit/FindingCard.tsx), [`frontend/src/components/audit/CategoryScoreCard.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/components/audit/CategoryScoreCard.tsx), [`frontend/src/views/WebsiteAuditView.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/views/WebsiteAuditView.tsx)
- **Database:** `local_audit_runs`, `local_audit_findings`, `seo_audits`, `seo_issues`, `website_pages`, `audit_jobs`  
**Scope:** Strictly Audit-Only (Zero code/config modifications)

---

## Executive Summary

The Local SEO Audit experience within LocalLift is split across two subsystems:
1. **20-Category Local SEO Audit Framework** (`/audits/local` via [`LocalSEOAuditView.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/views/LocalSEOAuditView.tsx)): Evaluates business health across 20 distinct categories with traceable evidence and provenance.
2. **6-Pillar Technical Website Audit** (`/audits/website` via [`WebsiteAuditView.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/views/WebsiteAuditView.tsx)): Crawls website HTML to check crawlability, on-page SEO, schema markup, and cross-compares against Google Business Profile and directory citations.

The user-reported issues on the Local SEO Audit results page ("*visually crude, excessively tall, difficult to read, and appears to contain many failed, missing, or incomplete audit checks*") stem from **three distinct architectural root causes**:

1. **Frontend Presentation & Layout Defects**:
   - In [`FindingCard.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/components/audit/FindingCard.tsx), each individual check card has heavy vertical padding (`p-4` to `p-5`), tall header strips, large multi-line evidence boxes (`p-3 bg-slate-50`), and standalone recommendation boxes (`p-3 bg-[#F1F7F1]`). When rendered across 20 categories, the page expands into an enormous, un-scannable vertical wall of cards.
   - The default category view in [`CategoryScoreCard.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/components/audit/CategoryScoreCard.tsx) does not offer a compact, consolidated summary table or matrix, forcing users to manually expand and scroll endlessly through verbose text.
2. **Pre-requisite Data Dependency & "NOT_VERIFIED" Cascade**:
   - When a user runs a Local SEO audit on a newly created or partially connected project (e.g., Google Business Profile not yet OAuth-linked, website not yet crawled by the crawler, directory citations not yet imported, schema not yet validated), the backend audit framework in [`audit_framework.py`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/backend/app/services/local_seo/audit_framework.py) correctly returns `status="NOT_VERIFIED"` or `status="FAIL"`.
   - However, the frontend visually styles these missing prerequisites with prominent warning/error banners and fails to clearly guide the user with a unified "Prerequisites & Data Sync Checklist".
3. **Dual Audit Engine Disconnect**:
   - The app maintains two separate audit systems (`/audits/local` vs `/audits/website`). While `LocalSEOAuditFramework` pulls summary data from `seo_audits`, the crawl job and the local audit are triggered independently. If the user runs the Local SEO Audit before running the Website Crawler, all on-page, crawl health, landing page, and internal linking checks default to `NOT_VERIFIED`.

---

## Section B1: Complete Audit Lifecycle Trace

```text
1. User Action:
   User selects project in UI and clicks "Run Audit" in LocalSEOAuditView.tsx (or "Run Local Audit" in WebsiteAuditView.tsx)
       │
       ▼
2. API Request:
   POST /api/v1/audits/{project_id}/local/run  (or POST /api/v1/audits/crawl/{project_id})
       │
       ▼
3. Access Verification:
   app/core/deps.py: verify_project_access(project_id, current_user, db) ensures tenant isolation.
       │
       ▼
4. Execution Engine:
   LocalSEOAuditFramework.run_audit(project_id, db, framework_version="local_seo_v1")
   in app/services/local_seo/audit_framework.py
       │
       ├─► Fetches canonical BusinessProfile via BusinessProfileService
       ├─► Queries Citations from 'citations' table
       ├─► Queries Reviews from 'reviews' table
       ├─► Queries Competitors from 'competitors' table
       ├─► Queries Schema records from 'schema_records' table
       ├─► Queries latest SEOAudit from 'seo_audits' table
       ├─► Queries Crawled Pages from 'website_pages' table
       ├─► Queries linked GoogleBusinessProfile from 'google_business_profiles' table
       ├─► Queries latest GeoGridScan from 'geogrid_scans' table
       └─► Executes NAP comparison via NAPComparisonService
       │
       ▼
5. Scoring & Categorization:
   - Iterates through 20 Categories (lines 133–703)
   - Generates 20+ LocalAuditFinding dictionaries with provenance, status, severity, and evidence.
   - Calculates category scores: PASS (100%), PARTIAL (50%), FAIL (0%).
   - Active weight summation excludes NOT_VERIFIED / NOT_APPLICABLE checks.
       │
       ▼
6. Database Persistence:
   - Inserts record into 'local_audit_runs' (status="completed", overall_score, category_scores, findings_summary)
   - Inserts all records into 'local_audit_findings'
   - Commits transaction via AsyncSession.
       │
       ▼
7. API Response & Frontend Render:
   - Returns LocalAuditRunOut JSON with loaded findings list.
   - Frontend stores state in auditRun and renders overall score ring, summary counters, and category cards.
```

---

## Section B2: Complete Inventory of the 20 Local SEO Audit Categories & Rules

The following table documents all 20 categories evaluated in [`backend/app/services/local_seo/audit_framework.py`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/backend/app/services/local_seo/audit_framework.py):

| # | Category Identifier | Weight | Check Key & Title | Input Data Required | Service / Source | Default Status When Data Absent |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `google_business_profile` | 10.0% | `gbp_claimed_verified` / `gbp_connection` | `GoogleBusinessProfile` model | GBP Service / DB | `NOT_VERIFIED` (Warning) |
| 2 | `categories_taxonomy` | 5.0% | `primary_category_selected` | `primary_category`, `additional_categories` | Business Profile / GBP | `FAIL` (Critical) if generic |
| 3 | `reviews_reputation` | 8.0% | `review_rating_threshold` / `review_presence` | `Review` records | Reviews Service / GBP | `NOT_VERIFIED` (Warning) |
| 4 | `nap_consistency` | 8.0% | `nap_uniformity` / `nap_sources` | `NAPComparisonService.compare_project_nap` | NAP Service / Citations | `NOT_VERIFIED` (Warning) |
| 5 | `local_onpage_seo` | 8.0% | `geo_keyword_in_title` / `crawl_pages_analyzed` | `WebsitePage` records, `city` | Website Crawler | `NOT_VERIFIED` (Info) |
| 6 | `proximity_location` | 6.0% | `geo_coordinates_bound` | `latitude`, `longitude` | Business Profile / GBP | `FAIL` (Critical) |
| 7 | `citations_directories` | 6.0% | `directory_citation_volume` / `citation_presence` | `Citation` records | Citations Registry | `NOT_VERIFIED` (Warning) |
| 8 | `local_backlinks` | 4.0% | `backlink_signals` | Backlink integration | Brand Intelligence | `NOT_VERIFIED` (Info) |
| 9 | `review_responses` | 4.0% | `owner_response_rate` | `Review.response_status` | Reviews Service / GBP | `NOT_APPLICABLE` (Info) |
| 10 | `gbp_media` | 4.0% | `photo_upload_count` | `GoogleBusinessProfile.photos_count` | GBP Service | `NOT_VERIFIED` (Info) |
| 11 | `local_landing_pages` | 5.0% | `landing_page_presence` | `WebsitePage` count | Website Crawler | `NOT_VERIFIED` (Info) |
| 12 | `gbp_activity` | 3.0% | `post_recency` | `GoogleBusinessProfile.posts_count` | GBP Service | `NOT_VERIFIED` (Info) |
| 13 | `website_authority` | 4.0% | `ssl_https_secured` | `profile.website` URL scheme | Website Inspector | `PASS` / `FAIL` (Evaluated) |
| 14 | `internal_linking` | 3.0% | `internal_link_structure` | `WebsitePage.internal_links_count` | Website Crawler | `NOT_VERIFIED` (Info) |
| 15 | `technical_seo` | 5.0% | `crawl_health_score` | `SEOAudit.overall_score` | SEO Technical Auditor | `NOT_VERIFIED` (Info) |
| 16 | `schema_localbusiness` | 7.0% | `localbusiness_jsonld` | `SchemaRecord` records | Schema Validator | `NOT_VERIFIED` (Warning) |
| 17 | `local_content` | 4.0% | `local_relevance_content` | Crawled content analysis | Content Analyzer | `NOT_VERIFIED` (Info) |
| 18 | `social_brand_signals` | 2.0% | `brand_profile_links` | Social connectors | Brand Intelligence | `NOT_VERIFIED` (Info) |
| 19 | `user_engagement` | 2.0% | `interaction_signals` | `GBP` calls, clicks, directions | GBP Service | `NOT_VERIFIED` (Info) |
| 20 | `competitor_market_analysis`| 2.0% | `competitor_tracking_active` | `Competitor` records | Competitor Engine | `NOT_VERIFIED` (Info) |

---

## Section B3: Investigation into Why Checks Fail or Appear Missing

1. **Unexecuted Background Website Crawl**:
   - If a user has not triggered a technical crawl from `/audits/website`, the `website_pages` and `seo_audits` tables have 0 rows for that project.
   - Consequently, Categories 5 (`local_onpage_seo`), 11 (`local_landing_pages`), 14 (`internal_linking`), and 15 (`technical_seo`) immediately output `NOT_VERIFIED`.
2. **Disconnected Google Business Profile**:
   - If Google OAuth has not been connected or the user is working on an unlinked project, Categories 1 (`google_business_profile`), 10 (`gbp_media`), 12 (`gbp_activity`), and 19 (`user_engagement`) immediately output `NOT_VERIFIED`.
3. **Unvalidated Structured Data**:
   - If the user has not run Schema validation under `/schemas`, Category 16 (`schema_localbusiness`) outputs `NOT_VERIFIED`.
4. **Empty Directory Citations Registry**:
   - If citations have not been imported under `/citations`, Categories 4 (`nap_consistency`) and 7 (`citations_directories`) output `NOT_VERIFIED`.
5. **No Rule Execution Errors or Exceptions Swallowed**:
   - The backend audit framework runs completely without throwing unhandled exceptions. It handles `None` values safely.

---

## Section B4: Status Model Integrity Audit

The system supports the following canonical status enum in `app/models/local_seo.py`:
* **`PASS`**: Check executed successfully, meeting full criteria (Score = 100%).
* **`PARTIAL`**: Check partially met or warning criteria present (Score = 50%).
* **`FAIL`**: Check executed and strictly failed (Score = 0%).
* **`NOT_VERIFIED`**: Data source is unavailable or unconnected. **Crucially, this is excluded from score inflation and deflation.**
* **`NOT_APPLICABLE`**: Rule does not apply to this business model or context (excluded from score calculation).
* **`ERROR`**: External provider or parsing error occurred.

### Status Integrity Evaluation:
- Checks that were not executed are **never shown as passed**.
- A missing GBP connection does **not** fail independent website checks (e.g., SSL, Category Taxonomy, Competitors).
- Category weights dynamically normalize over only active/evaluated categories.

---

## Section B5: Scoring Engine Audit

### Formula in [`audit_framework.py`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/backend/app/services/local_seo/audit_framework.py) (Lines 704–750):
1. For each category $C$ with weight $W_C$:
   - Filters findings where $\text{status} \in \{\text{PASS}, \text{PARTIAL}, \text{FAIL}\}$.
   - If evaluated findings exist:
     $$\text{Score}_C = \text{round}\left( \frac{\sum (\text{PASS}=100, \text{PARTIAL}=50, \text{FAIL}=0)}{N_{\text{evaluated}}} \right)$$
     $$\text{WeightedSum} += \text{Score}_C \times W_C$$
     $$\text{ActiveWeightSum} += W_C$$
   - If no evaluated findings exist (all `NOT_VERIFIED` / `NOT_APPLICABLE`):
     $$\text{Score}_C = \text{null}$$
2. Final Overall Score:
   $$\text{OverallScore} = \text{round}\left( \frac{\text{WeightedSum}}{\text{ActiveWeightSum}} \right) \quad \text{if } \text{ActiveWeightSum} > 0 \text{ else null}$$

### Scoring Engine Verdict:
- Category weights sum to exactly $100.0\%$.
- Score is mathematically accurate and does not artificially award 100% to unverified categories.
- The score displayed in [`LocalSEOAuditView.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/views/LocalSEOAuditView.tsx) exactly matches `LocalAuditRun.overall_score` stored in SQLite.

---

## Section B6: API Endpoints & Multi-Tenant Isolation Audit

| Endpoint | Method | Security Dependency | Isolation Guarantee |
| :--- | :--- | :--- | :--- |
| `/api/v1/audits/{project_id}/local/run` | `POST` | `verify_project_access` | Project ID strictly validated against current user/org membership. |
| `/api/v1/audits/{project_id}/local/latest` | `GET` | `verify_project_access` | Returns latest run filtered strictly by `project_id`. |
| `/api/v1/audits/{project_id}/local/history` | `GET` | `verify_project_access` | Paginated history filtered strictly by `project_id`. |
| `/api/v1/audits/{project_id}/local/runs/{run_id}` | `GET` | `verify_project_access` | Double filter: `id == run_id AND project_id == project_id`. |

**Verdict:** Zero tenant leakage risk. All database queries enforce project-level boundaries.

---

## Section B7: Frontend Results Page Audit (Why Cards Look Crude & Oversized)

Inspection of [`LocalSEOAuditView.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/views/LocalSEOAuditView.tsx), [`FindingCard.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/components/audit/FindingCard.tsx), and [`CategoryScoreCard.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/components/audit/CategoryScoreCard.tsx):

1. **Card Height Bloat**:
   - Each `FindingCard` occupies ~180px–240px vertical space. When a category has 2–3 findings, that category card expands to 600px+.
   - 20 categories $\times$ 500px average height = **10,000px+ vertical scroll height**.
2. **Visual Hierarchy Deficiencies**:
   - Excessive borders (`border-2`, nested `border-b`, rounded containers inside rounded containers).
   - High visual friction from solid color pills and repetitive labels (*"Evidence"*, *"Recommended Action"*, *"Source"*).
3. **Lack of Compact Matrix Mode**:
   - There is no high-level 20-category grid or table view allowing the user to scan category scores at a glance without scrolling.
4. **Disconnection Between Local SEO Audit and Website Audit Views**:
   - Users are presented with two different audit tabs in the sidebar (*"Local SEO Audit"* at `/audits/local` vs *"Website Audit"* at `/audits/website`).
   - The user cannot tell from `/audits/local` why crawl-based checks are `NOT_VERIFIED` unless they know to navigate to `/audits/website` and run a crawl first.

---

## Section C: Required Tests & Coverage Matrix

Current backend test suite has 265 collected tests. Audit framework test cases to verify during implementation:

1. **Fully Successful Audit**: All 20 categories populated with mock verified data $\rightarrow$ Expected Overall Score $\ge 90/100$.
2. **Partial Audit (No GBP)**: Project with crawled pages and citations but no GBP connection $\rightarrow$ GBP categories return `NOT_VERIFIED`, website/NAP categories evaluate $\rightarrow$ Valid weighted score calculated without dividing by zero.
3. **Crawler Timeout / Blocked URL**: Website returns 403 / 500 / Timeout $\rightarrow$ `WebsitePage` records reflect error status codes; Technical SEO category generates `FAIL` with explicit error evidence.
4. **Zero Discovered Pages**: Project with no crawl $\rightarrow$ Categories 5, 11, 14, 15 return `NOT_VERIFIED` with clear recommendation to launch crawler.
5. **Multi-Tenant Project Isolation**: User in Org A cannot query or trigger audit for Project in Org B $\rightarrow$ HTTP 403 / 404.

---

## Prioritized Remediation Plan

| Priority | Component | Action Item | Target Files |
| :--- | :--- | :--- | :--- |
| **P0 (Frontend)** | **Geo-Grid Map** | Restore interactive map experience by implementing dual-engine map rendering (Google Maps JS API when key present + Leaflet/OpenStreetMap interactive canvas when key absent). | [`frontend/src/components/rankings/LocalGridMap.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/components/rankings/LocalGridMap.tsx) |
| **P0 (Frontend)** | **Local SEO Audit UI** | Redesign `FindingCard.tsx` and `CategoryScoreCard.tsx` with a compact, modern design system: condensed cards, 20-category scannable overview grid, clear status badges, and expandable drawer details. | [`frontend/src/components/audit/FindingCard.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/components/audit/FindingCard.tsx), [`frontend/src/components/audit/CategoryScoreCard.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/components/audit/CategoryScoreCard.tsx), [`frontend/src/views/LocalSEOAuditView.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/views/LocalSEOAuditView.tsx) |
| **P1 (Frontend)** | **Audit Onboarding & Pre-requisite Helper** | Add an "Audit Data Readiness" banner in `LocalSEOAuditView.tsx` displaying status of GBP connection, Website Crawl, Schema Validation, and Citations with one-click quick-actions. | [`frontend/src/views/LocalSEOAuditView.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/views/LocalSEOAuditView.tsx) |
| **P1 (Integration)** | **Unified "Run Full Audit" Trigger** | In `LocalSEOAuditView.tsx`, allow the "Run Audit" button to optionally initiate or refresh the website crawl and intelligence scan simultaneously if crawl data is missing or stale. | [`frontend/src/views/LocalSEOAuditView.tsx`](file:///c:/Users/Jiniyas%20Suthar/OneDrive/Desktop/LocalLift/frontend/src/views/LocalSEOAuditView.tsx) |

---

**End of Local SEO Audit Forensic Report**

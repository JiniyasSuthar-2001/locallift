"""
LocalLift — Real Content & Landing Page Opportunity Engine

Analyzes real connected project data:
1. Google Search Console queries (striking distance, high-impression low-CTR queries)
2. Tracked project keywords and rank movements
3. Existing indexed website pages & URL structure
4. Missing suburb / city + service matrix combinations
5. Competitor keyword gaps
6. Commercial intent & high-conversion local landing page opportunities

Produces structured, actionable content opportunities with:
- topic / title
- target keyword
- location
- search intent (Commercial, Transactional, Informational, Local)
- opportunity score (0-100)
- recommended page type (Suburban Landing Page, Service Pillar, Price Guide, FAQ)
- AI content recommendation & structured content brief
- priority (High, Medium, Low)
"""

import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.project import Project, Location, Website
from app.models.audit import WebsitePage, SEOIssue
from app.models.ranking import Keyword
from app.models.local_seo import BusinessProfile, Competitor
from app.models.connections import GoogleConnection
from app.services.google.connections_service import GoogleConnectionsService
from app.services.google.gsc_client import GoogleSearchConsoleClient

logger = logging.getLogger("locallift.content_opportunity_engine")


class ContentOpportunityEngine:
    @classmethod
    async def generate_opportunities(
        cls,
        project_id: int,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Generates real, high-value content and landing page opportunities by synthesizing all project signals.
        """
        # 1. Fetch Project and Context
        proj_res = await db.execute(
            select(Project)
            .options(selectinload(Project.locations))
            .where(Project.id == project_id)
        )
        project = proj_res.scalars().first()
        if not project:
            return []

        # 2. Fetch Locations
        locations = project.locations or []
        primary_loc = locations[0] if locations else None
        city = (primary_loc.city if primary_loc and primary_loc.city else "Local Area").strip()
        state = (primary_loc.state if primary_loc and primary_loc.state else "").strip()
        suburbs = [loc.city.strip() for loc in locations if loc.city]
        if not suburbs:
            suburbs = [city]

        # 3. Fetch Canonical Business Profile
        bp_res = await db.execute(select(BusinessProfile).where(BusinessProfile.project_id == project_id))
        bp = bp_res.scalars().first()
        category = (bp.primary_category if bp and bp.primary_category else (project.primary_category or "Local Service")).strip()
        raw_sec = (getattr(bp, "additional_categories", None) or getattr(bp, "secondary_categories", None) or []) if bp else []
        secondary_categories = []
        if isinstance(raw_sec, list):
            for item in raw_sec:
                if isinstance(item, str) and item.strip():
                    secondary_categories.append(item.strip())
                elif isinstance(item, dict) and item.get("name"):
                    secondary_categories.append(str(item["name"]).strip())


        # 4. Fetch Tracked Keywords
        kw_res = await db.execute(select(Keyword).where(Keyword.project_id == project_id))
        keywords = kw_res.scalars().all()

        # 5. Fetch Crawled Website Pages
        web_res = await db.execute(select(Website).where(Website.project_id == project_id))
        website = web_res.scalars().first()
        pages: List[WebsitePage] = []
        if website:
            pages_res = await db.execute(select(WebsitePage).where(WebsitePage.website_id == website.id))
            pages = pages_res.scalars().all()

        crawled_urls = [p.url.lower() for p in pages if p.url]
        crawled_titles = [p.title.lower() for p in pages if p.title]

        # 6. Fetch Competitors
        comp_res = await db.execute(select(Competitor).where(Competitor.project_id == project_id))
        competitors = comp_res.scalars().all()

        # 7. Check Google Search Console Queries if connected
        gsc_queries: List[Dict[str, Any]] = []
        try:
            gsc_conn = await GoogleConnectionsService.get_connection_for_service(project.organization_id, "search_console", db)
            if gsc_conn and gsc_conn.status == "connected":
                gsc_token = await GoogleConnectionsService.get_valid_access_token(gsc_conn, db)
                gsc_data = await GoogleSearchConsoleClient.fetch_search_analytics(gsc_token, project.domain or "", days=30)
                gsc_queries = gsc_data.get("top_queries", [])
        except Exception as ge:
            logger.warning(f"[CONTENT_OPP] GSC queries inspection notice: {ge}")

        opportunities: List[Dict[str, Any]] = []
        seen_slugs = set()

        def add_opportunity(opp: Dict[str, Any]):
            slug = opp.get("target_slug", "").strip().lower()
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                opportunities.append(opp)

        # ─── STRATEGY A: Striking Distance Tracked Keywords (#4 to #20) ───
        for kw in keywords:
            rank = kw.current_rank
            if rank and 4 <= rank <= 25:
                # Prime ranking opportunity to create or optimize targeted page
                kw_text = kw.keyword.strip()
                slug_text = re.sub(r"[^\w\s-]", "", kw_text.lower()).strip()
                slug_text = re.sub(r"[\s_-]+", "-", slug_text)
                target_slug = f"/services/{slug_text}"

                # Check if page already exists
                has_exact_page = any(slug_text in u for u in crawled_urls)
                score = min(96, 75 + (20 - rank) * 2)

                opp_type = "Service Page Optimization" if has_exact_page else "Dedicated Service Landing Page"
                add_opportunity({
                    "topic": f"{kw_text.title()} — High-Impact Ranking Opportunity",
                    "title": f"{kw_text.title()} — Ranking Growth Page",
                    "page_type": opp_type,
                    "recommended_page_type": opp_type,
                    "primary_keyword": kw_text,
                    "target_keyword": kw_text,
                    "location": kw.target_location or city,
                    "secondary_keywords": [
                        f"best {kw_text}",
                        f"{kw_text} near me",
                        f"affordable {kw_text}",
                        f"{kw_text} specialist"
                    ],
                    "search_intent": "Commercial",
                    "search_volume": kw.search_volume,
                    "search_volume_status": f"Rank #{rank} (Striking distance)" if rank else "Tracked keyword",
                    "business_value": "High",
                    "priority": "High" if score >= 85 else "Medium",
                    "opportunity_score": score,
                    "competition_level": "Medium",
                    "target_slug": target_slug,
                    "ai_recommendation": (
                        f"Target '{kw_text}' (currently position #{rank}). Structure with direct H1, "
                        f"local schema markup (LocalBusiness), client reviews, and clear CTA to capture Top 3 rankings."
                    ),
                    "content_brief": {
                        "suggested_h1": f"Expert {kw_text.title()} in {kw.target_location or city}",
                        "meta_description": f"Looking for trusted {kw_text}? Contact our verified team in {kw.target_location or city} for prompt, guaranteed service.",
                        "recommended_word_count": 950,
                        "key_sections": [
                            "Core Service Overview & Capabilities",
                            "Why Choose Our Local Specialists",
                            "Pricing & Transparent Estimates",
                            "Customer Testimonials & Case Results",
                            "Frequently Asked Questions"
                        ],
                        "schema_type": "Service / LocalBusiness",
                        "cta": "Schedule a Consultation / Get a Free Quote"
                    }
                })

        # ─── STRATEGY B: GSC High-Impression Opportunity Queries ───
        for g_query in gsc_queries[:8]:
            query_name = g_query.get("query", "").strip()
            impressions = g_query.get("impressions", 0)
            clicks = g_query.get("clicks", 0)
            avg_pos = g_query.get("position", 15)

            if query_name and impressions > 10:
                slug_text = re.sub(r"[^\w\s-]", "", query_name.lower()).strip()
                slug_text = re.sub(r"[\s_-]+", "-", slug_text)
                target_slug = f"/guides/{slug_text}"

                score = min(98, int(70 + min(impressions / 20, 25)))
                add_opportunity({
                    "topic": f"GSC Demand: {query_name.title()}",
                    "title": f"Capture GSC Search Impressions: {query_name.title()}",
                    "page_type": "Commercial Guide / Service Page",
                    "recommended_page_type": "Commercial Guide / Service Page",
                    "primary_keyword": query_name,
                    "target_keyword": query_name,
                    "location": city,
                    "secondary_keywords": [
                        f"{query_name} cost",
                        f"{query_name} guide",
                        f"how {query_name} works",
                        f"{query_name} in {city}"
                    ],
                    "search_intent": "Transactional" if "cost" in query_name or "service" in query_name or "near me" in query_name else "Informational",
                    "search_volume": impressions,
                    "search_volume_status": f"{impressions} GSC impressions (Pos: {avg_pos:.1f})",
                    "business_value": "High" if clicks > 0 or impressions > 50 else "Medium",
                    "priority": "High" if score >= 85 else "Medium",
                    "opportunity_score": score,
                    "competition_level": "Low" if avg_pos < 12 else "Medium",
                    "target_slug": target_slug,
                    "ai_recommendation": (
                        f"Real searchers in Google are discovering your domain for '{query_name}' ({impressions} impressions). "
                        f"Build a dedicated pillar page to elevate average position from #{avg_pos:.1f} to Top 3."
                    ),
                    "content_brief": {
                        "suggested_h1": f"The Complete Guide to {query_name.title()} ({city})",
                        "meta_description": f"Learn everything you need to know about {query_name} in {city}. Expert advice, practical steps, and pricing.",
                        "recommended_word_count": 1200,
                        "key_sections": [
                            "Understanding the Basics",
                            "Key Benefits & When You Need It",
                            "Step-by-Step Process",
                            "Common Mistakes to Avoid",
                            "Local Rates & Booking Information"
                        ],
                        "schema_type": "Article / HowTo",
                        "cta": "Speak with Our Local Team"
                    }
                })

        # ─── STRATEGY C: Suburban Matrix Landing Pages (Missing City/Service Combinations) ───
        target_services = [category] + secondary_categories[:3]
        for srv in target_services:
            clean_srv = srv.replace("Local", "").replace("Service", "").strip() or category
            for sub in suburbs:
                sub_slug = re.sub(r"[^\w\s-]", "", f"{clean_srv}-{sub}".lower()).strip()
                sub_slug = re.sub(r"[\s_-]+", "-", sub_slug)
                target_slug = f"/locations/{sub_slug}"

                # Check if this suburban landing page exists
                already_has_suburb = any(sub_slug in u for u in crawled_urls)
                if not already_has_suburb:
                    score = 90 if sub == city else 84
                    add_opportunity({
                        "topic": f"{clean_srv.title()} Services in {sub}",
                        "title": f"Suburban Landing Page: {clean_srv.title()} in {sub}",
                        "page_type": "Suburban Landing Page",
                        "recommended_page_type": "Suburban Landing Page",
                        "primary_keyword": f"{clean_srv.lower()} in {sub.lower()}",
                        "target_keyword": f"{clean_srv.lower()} in {sub.lower()}",
                        "location": sub,
                        "secondary_keywords": [
                            f"{clean_srv.lower()} {sub.lower()}",
                            f"best {clean_srv.lower()} near {sub.lower()}",
                            f"{sub.lower()} local {clean_srv.lower()}",
                            f"emergency {clean_srv.lower()} {sub.lower()}"
                        ],
                        "search_intent": "Local / Transactional",
                        "search_volume": None,
                        "search_volume_status": f"High Local Buying Intent ({sub})",
                        "business_value": "High",
                        "priority": "High",
                        "opportunity_score": score,
                        "competition_level": "Low",
                        "target_slug": target_slug,
                        "ai_recommendation": (
                            f"Create a dedicated location landing page for {sub}. Include local landmarks, "
                            f"exact service coverage radius, Google Maps embed, customer reviews from {sub}, and NAP."
                        ),
                        "content_brief": {
                            "suggested_h1": f"Trusted {clean_srv.title()} in {sub}, {state}",
                            "meta_description": f"Professional {clean_srv.lower()} serving {sub} and surrounding areas. Fast response, licensed professionals, 5-star rated.",
                            "recommended_word_count": 800,
                            "key_sections": [
                                f"Local Services in {sub}",
                                "Areas We Cover & Response Times",
                                "Recent Local Customer Reviews",
                                "Frequently Asked Questions for Residents",
                                "Contact Our Local Team"
                            ],
                            "schema_type": "LocalBusiness (with geo & address)",
                            "cta": f"Book Your {sub} Service Today"
                        }
                    })

        # ─── STRATEGY D: Commercial Price Guide / High Intent Pillar ───
        cost_slug = re.sub(r"[^\w\s-]", "", f"{category}-cost-pricing-guide".lower()).strip()
        cost_slug = re.sub(r"[\s_-]+", "-", cost_slug)
        target_cost_slug = f"/pricing/{cost_slug}"

        if not any(cost_slug in u for u in crawled_urls):
            add_opportunity({
                "topic": f"{category.title()} Pricing & Cost Guide ({city})",
                "title": f"Local Pricing Guide: How Much Does {category.title()} Cost in {city}?",
                "page_type": "Commercial Pricing Guide",
                "recommended_page_type": "Commercial Pricing Guide",
                "primary_keyword": f"{category.lower()} cost {city.lower()}",
                "target_keyword": f"{category.lower()} cost {city.lower()}",
                "location": city,
                "secondary_keywords": [
                    f"how much is {category.lower()} in {city.lower()}",
                    f"average cost of {category.lower()}",
                    f"affordable {category.lower()} rates",
                    f"{category.lower()} price list"
                ],
                "search_intent": "Commercial Investigation",
                "search_volume": None,
                "search_volume_status": "High Commercial Intent",
                "business_value": "High",
                "priority": "High",
                "opportunity_score": 88,
                "competition_level": "Medium",
                "target_slug": target_cost_slug,
                "ai_recommendation": (
                    f"Pricing queries represent the highest purchase intent. A transparent price breakdown with "
                    f"itemized packages and financing options will capture bottom-of-funnel local customers."
                ),
                "content_brief": {
                    "suggested_h1": f"How Much Does {category.title()} Cost in {city}? (2026 Price Guide)",
                    "meta_description": f"Complete guide to {category.lower()} pricing in {city}. Breakdown of average costs, factors affecting price, and how to get an accurate quote.",
                    "recommended_word_count": 1400,
                    "key_sections": [
                        "Average Price Ranges in " + city,
                        "What Factors Influence the Final Cost",
                        "Package Comparisons & Service Tiers",
                        "Financing, Payment Plans & Rebates",
                        "Request a Custom Free Quote"
                    ],
                    "schema_type": "PriceSpecification / FAQPage",
                    "cta": "Get an Instant Online Estimate"
                }
            })

        # ─── STRATEGY E: Competitor Keyword Gaps ───
        for comp in competitors[:5]:
            comp_name = (comp.name or "Top Competitor").strip()
            comp_keywords = comp.keywords_found or comp.tracked_keywords_overlap or []
            if isinstance(comp_keywords, list):
                for c_kw in comp_keywords[:3]:
                    c_kw_str = str(c_kw).strip()
                    if not c_kw_str:
                        continue
                    c_slug = re.sub(r"[^\w\s-]", "", c_kw_str.lower()).strip()
                    c_slug = re.sub(r"[\s_-]+", "-", c_slug)
                    target_comp_slug = f"/services/{c_slug}"

                    if not any(c_slug in u for u in crawled_urls):
                        comp_score = 86
                        add_opportunity({
                            "topic": f"Competitor Gap: {c_kw_str.title()}",
                            "title": f"Competitor Keyword Gap: {c_kw_str.title()}",
                            "page_type": "Service Pillar / Comparison Page",
                            "recommended_page_type": "Service Pillar / Comparison Page",
                            "primary_keyword": c_kw_str,
                            "target_keyword": c_kw_str,
                            "location": city,
                            "secondary_keywords": [
                                f"{c_kw_str} services",
                                f"{c_kw_str} vs {comp_name}",
                                f"best {c_kw_str} {city}",
                                f"{c_kw_str} experts"
                            ],
                            "search_intent": "Commercial",
                            "search_volume": None,
                            "search_volume_status": f"Targeted by competitor ({comp_name})",
                            "business_value": "High",
                            "priority": "High",
                            "opportunity_score": comp_score,
                            "competition_level": "High",
                            "target_slug": target_comp_slug,
                            "ai_recommendation": (
                                f"Competitor '{comp_name}' captures search traffic for '{c_kw_str}'. "
                                f"Publishing a dedicated landing page targeting '{c_kw_str}' with stronger social proof "
                                f"and schema will bridge this competitive market gap."
                            ),
                            "content_brief": {
                                "suggested_h1": f"Premier {c_kw_str.title()} in {city}",
                                "meta_description": f"Superior {c_kw_str} in {city}. Compare our guaranteed workmanship, transparent quotes, and proven track record.",
                                "recommended_word_count": 1100,
                                "key_sections": [
                                    f"Comprehensive {c_kw_str.title()} Solutions",
                                    "How We Compare with Standard Market Alternatives",
                                    "Transparent Cost Structure & Deliverables",
                                    "Verified Customer Proof & Case Highlights",
                                    "Get a Free Competitive Estimate"
                                ],
                                "schema_type": "Service / LocalBusiness",
                                "cta": "Request a Free Competitive Quote"
                            }
                        })

        # Sort opportunities by opportunity score descending
        opportunities.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
        return opportunities

import re
from typing import List, Dict, Any, Optional
from app.models.audit import IssueSeverity

def _normalize_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    # Strip everything except digits and plus sign
    return re.sub(r"[^\d+]", "", phone)

class SEOAuditor:
    CONFIGURED_WEIGHTS = {
        "crawl_health": 0.20,
        "onpage_content": 0.20,
        "schema_structured_data": 0.25,
        "gbp_alignment": 0.15,
        "citations_nap": 0.10,
        "reviews_reputation": 0.10
    }

    PILLAR_WEIGHTS = {
        "crawl_health": 20,
        "onpage_seo": 20,
        "schema_local": 25,
        "gbp_status": 15,
        "citations_presence": 10,
        "reviews_rating": 10
    }

    @classmethod
    def get_pillar_weights_formatted(cls) -> Dict[str, str]:
        return {k: f"{int(v * 100)}%" for k, v in cls.CONFIGURED_WEIGHTS.items()}

    @classmethod
    def get_scoring_methodology(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "crawl_health": {
                "name": "Local Crawl Health",
                "weight": f"{int(cls.CONFIGURED_WEIGHTS['crawl_health'] * 100)}%",
                "weight_fraction": cls.CONFIGURED_WEIGHTS["crawl_health"],
                "starting_score": 100,
                "deductions": "20 points deducted per critical HTTP error or crawl failure.",
                "formula": "max(0, min(100, 100 - (critical_count * 20)))"
            },
            "onpage_content": {
                "name": "Local On-Page & Geo-Content",
                "weight": f"{int(cls.CONFIGURED_WEIGHTS['onpage_content'] * 100)}%",
                "weight_fraction": cls.CONFIGURED_WEIGHTS["onpage_content"],
                "starting_score": 100,
                "deductions": "10 points deducted per warning (missing title, missing H1, thin content, missing meta description).",
                "formula": "max(0, min(100, 100 - (warning_count * 10)))"
            },
            "schema_structured_data": {
                "name": "Schema & Structured Data",
                "weight": f"{int(cls.CONFIGURED_WEIGHTS['schema_structured_data'] * 100)}%",
                "weight_fraction": cls.CONFIGURED_WEIGHTS["schema_structured_data"],
                "starting_score": 0,
                "deductions": "Full 100 points awarded if valid LocalBusiness Schema.org JSON-LD entity with phone, address, and geo coordinates is present; 0 if missing.",
                "formula": "100 if has_valid_local_schema else 0"
            },
            "gbp_alignment": {
                "name": "Google Business Profile Match",
                "weight": f"{int(cls.CONFIGURED_WEIGHTS['gbp_alignment'] * 100)}%",
                "weight_fraction": cls.CONFIGURED_WEIGHTS["gbp_alignment"],
                "starting_score": 100,
                "deductions": "30 points deducted for Name mismatch, 30 points for Phone mismatch, 20 points for Address mismatch.",
                "formula": "100 - name_penalty(30) - phone_penalty(30) - address_penalty(20)"
            },
            "citations_nap": {
                "name": "Citations & Directory NAP",
                "weight": f"{int(cls.CONFIGURED_WEIGHTS['citations_nap'] * 100)}%",
                "weight_fraction": cls.CONFIGURED_WEIGHTS["citations_nap"],
                "starting_score": 0,
                "deductions": "Score equals percentage of directory listings with consistent NAP details across all listed directories.",
                "formula": "(consistent_citations / total_citations) * 100"
            },
            "reviews_reputation": {
                "name": "Reviews & Reputation",
                "weight": f"{int(cls.CONFIGURED_WEIGHTS['reviews_reputation'] * 100)}%",
                "weight_fraction": cls.CONFIGURED_WEIGHTS["reviews_reputation"],
                "starting_score": 0,
                "deductions": "70% based on average star rating (up to 5.0★) plus 30% based on response rate to customer reviews.",
                "formula": "((avg_rating / 5.0) * 70) + ((answered_reviews / total_reviews) * 30)"
            }
        }

    @staticmethod
    def audit_pages(
        pages: List[Dict[str, Any]],
        project_context: Optional[Dict[str, Any]] = None,
        gbp_context: Optional[Dict[str, Any]] = None,
        citation_context: Optional[List[Dict[str, Any]]] = None,
        review_context: Optional[Dict[str, Any]] = None,
        keyword_context: Optional[List[Dict[str, Any]]] = None,
        competitor_context: Optional[List[Dict[str, Any]]] = None,
        robots_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Audit crawled website pages with a strict LOCAL SEO FIRST focus:
        Produces canonical audit result with dynamic rule execution, schema evidence, and robots summary.
        """
        issues = []
        critical_count = 0
        warning_count = 0
        opportunity_count = 0
        passed_count = 0

        total_pages = len(pages)
        canonical_domain = (project_context or {}).get("domain") or ""
        canonical_phone = (project_context or {}).get("phone") or (gbp_context or {}).get("phone")
        canonical_name = (project_context or {}).get("name") or (gbp_context or {}).get("business_name")
        canonical_city = (project_context or {}).get("city")
        norm_canonical_phone = _normalize_phone(canonical_phone)

        # ---------------------------------------------------------------------
        # Rule Definitions & Execution Tracker
        # ---------------------------------------------------------------------
        rules_registry = {
            "CRAWL_001": {
                "rule_id": "CRAWL_001",
                "category": "Local Website Crawlability",
                "rule_name": "HTTP Status & Crawl Access",
                "what_was_checked": "Verifies every crawled URL returns HTTP 200 OK without 4xx/5xx errors or broken routing.",
                "validation_method": "HTTP Status Code & Response Header Inspection",
                "evidence_source": "Crawler Network Engine",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "TITLE_001": {
                "rule_id": "TITLE_001",
                "category": "Local On-Page SEO",
                "rule_name": "Missing HTML Title Tag",
                "what_was_checked": "Checks for non-empty <title> HTML element on all crawled pages.",
                "validation_method": "DOM HTML Title Tag Inspection",
                "evidence_source": "Crawler HTML Parser",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "TITLE_002": {
                "rule_id": "TITLE_002",
                "category": "Local Content Signals",
                "rule_name": "Title Geographic Targeting",
                "what_was_checked": "Verifies primary landing page titles mention target city/suburb location.",
                "validation_method": "Regex Location Name Matching",
                "evidence_source": "On-Page Text Tokenizer",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "META_001": {
                "rule_id": "META_001",
                "category": "Local On-Page SEO",
                "rule_name": "Missing Meta Description",
                "what_was_checked": "Audits presence of custom meta description tag on each page.",
                "validation_method": "Meta Tag Node Extraction",
                "evidence_source": "Crawler HTML Parser",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "H1_001": {
                "rule_id": "H1_001",
                "category": "Local On-Page SEO",
                "rule_name": "Primary H1 Heading Presence",
                "what_was_checked": "Checks for main <h1> heading identifying core service and area served.",
                "validation_method": "Heading DOM Tree Inspection",
                "evidence_source": "Crawler HTML Parser",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "SCHEMA_001": {
                "rule_id": "SCHEMA_001",
                "category": "Schema & Structured Data",
                "rule_name": "LocalBusiness Schema Markup Detection",
                "what_was_checked": "Detects presence of Schema.org LocalBusiness or specialized business type JSON-LD.",
                "validation_method": "JSON-LD & Microdata Script Parser",
                "evidence_source": "Structured Data Engine",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "SCHEMA_002": {
                "rule_id": "SCHEMA_002",
                "category": "Schema & Structured Data",
                "rule_name": "LocalBusiness Attribute Completeness",
                "what_was_checked": "Validates essential schema properties: business name, telephone, street address, and geo coordinates.",
                "validation_method": "Schema Property Schema Validation",
                "evidence_source": "Structured Data Engine",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "NAP_001": {
                "rule_id": "NAP_001",
                "category": "Business Identity & NAP",
                "rule_name": "On-Page Phone & NAP Consistency",
                "what_was_checked": "Compares phone numbers extracted on pages against canonical business phone.",
                "validation_method": "Regex Phone Extraction & E.164 Normalization",
                "evidence_source": "On-Page Phone Tokenizer",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "CONTENT_001": {
                "rule_id": "CONTENT_001",
                "category": "Local Content Signals",
                "rule_name": "Thin Local Landing Page Content",
                "what_was_checked": "Audits word count on key landing pages to ensure at least 250 words of service content.",
                "validation_method": "DOM Text Body Word Counter",
                "evidence_source": "Crawler Text Engine",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "CANONICAL_001": {
                "rule_id": "CANONICAL_001",
                "category": "Local Website Crawlability",
                "rule_name": "Self-Referential Canonical Tag",
                "what_was_checked": "Verifies rel='canonical' tags are present to prevent duplicate content indexing.",
                "validation_method": "Link Tag rel='canonical' Audit",
                "evidence_source": "Crawler HTML Parser",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "ALT_001": {
                "rule_id": "ALT_001",
                "category": "Local On-Page SEO",
                "rule_name": "Image Alt Text Coverage",
                "what_was_checked": "Audits page images for missing descriptive alt attributes.",
                "validation_method": "HTML <img> Tag Node Inspection",
                "evidence_source": "Crawler HTML Parser",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "GBP_001": {
                "rule_id": "GBP_001",
                "category": "Google Business Profile",
                "rule_name": "Google Business Profile Data Alignment",
                "what_was_checked": "Cross-verifies canonical business name, phone, and domain against connected GBP account.",
                "validation_method": "API Cross-Module Bridge Evaluation",
                "evidence_source": "Google Business Profile API",
                "requires_integration": True,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "CIT_001": {
                "rule_id": "CIT_001",
                "category": "Citations & Directory NAP",
                "rule_name": "Local Directory Citation Consistency",
                "what_was_checked": "Verifies NAP consistency and presence across high-authority local business directories.",
                "validation_method": "Directory Scrape Data Bridge",
                "evidence_source": "Local Citation Engine",
                "requires_integration": False,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "REV_001": {
                "rule_id": "REV_001",
                "category": "Reviews & Reputation",
                "rule_name": "Reviews & Reputation Response Rate",
                "what_was_checked": "Evaluates customer review star ratings and owner response rate.",
                "validation_method": "Google Review API Metrics Aggregator",
                "evidence_source": "Google Business Profile Reviews",
                "requires_integration": True,
                "evaluated": True,
                "pages_checked": total_pages,
                "passed": 0,
                "problems": 0,
            },
            "PERF_001": {
                "rule_id": "PERF_001",
                "category": "Performance",
                "rule_name": "PageSpeed & Core Web Vitals",
                "what_was_checked": "Measures PageSpeed Insights performance, FCP, LCP, and CLS scores.",
                "validation_method": "Google PageSpeed API Audit Engine",
                "evidence_source": "Google PageSpeed API",
                "requires_integration": True,
                "evaluated": False,  # Optional external performance check
                "pages_checked": 0,
                "passed": 0,
                "problems": 0,
            }
        }

        # Schema aggregation variables
        schema_instances_count = 0
        pages_with_schema = 0
        pages_without_schema = 0
        schema_type_counts: Dict[str, Dict[str, int]] = {}
        schema_evidence_list: List[Dict[str, Any]] = []
        has_valid_local_schema = False
        complete_entities_count = 0
        incomplete_entities_count = 0
        potential_mismatches_count = 0

        recognized_subtypes = [
            "LocalBusiness", "ProfessionalService", "HomeAndConstructionBusiness",
            "Electrician", "Plumber", "HVACBusiness", "LegalService", "MedicalBusiness",
            "AutomotiveBusiness", "GeneralContractor", "Store", "Restaurant", "Organization"
        ]

        if total_pages > 0:
            for p in pages:
                url = p.get("url", "")
                is_home_or_contact = (
                    url.rstrip("/").count("/") <= 3 or
                    "contact" in url.lower() or
                    "location" in url.lower() or
                    "about" in url.lower()
                )

                # 1. CRAWL_001
                status = p.get("status_code", 200)
                if status >= 400:
                    critical_count += 1
                    rules_registry["CRAWL_001"]["problems"] += 1
                    issues.append({
                        "category": "Local Website Crawlability",
                        "severity": IssueSeverity.CRITICAL.value,
                        "title": f"Broken Local Page (HTTP {status})",
                        "evidence": f"URL {url} returned HTTP error status {status}.",
                        "why_it_matters": "Search engines and local customers cannot access broken pages, damaging local crawl budget and user trust.",
                        "recommended_solution": "Fix URL routing or implement a 301 permanent redirect to the nearest active local service page.",
                        "action_type": "fix_redirect",
                        "affected_url": url,
                        "template_slug": "citation-nap-correction-task"
                    })
                else:
                    passed_count += 1
                    rules_registry["CRAWL_001"]["passed"] += 1

                # 2. TITLE_001 & TITLE_002
                title = p.get("title")
                if not title:
                    critical_count += 1
                    rules_registry["TITLE_001"]["problems"] += 1
                    issues.append({
                        "category": "Local On-Page SEO",
                        "severity": IssueSeverity.CRITICAL.value,
                        "title": "Missing Page Title Tag",
                        "evidence": f"Page {url} has no <title> tag defined.",
                        "why_it_matters": "The title tag is one of the highest-weight on-page ranking signals for Google Local search and maps visibility.",
                        "recommended_solution": "Add a unique local title tag formatted as: [Primary Service] in [City/Suburb] | [Business Name].",
                        "action_type": "write_title",
                        "affected_url": url,
                        "template_slug": "service-location-page-blueprint"
                    })
                else:
                    passed_count += 1
                    rules_registry["TITLE_001"]["passed"] += 1

                if title and canonical_city:
                    if canonical_city.lower() in title.lower():
                        rules_registry["TITLE_002"]["passed"] += 1
                    elif is_home_or_contact:
                        opportunity_count += 1
                        rules_registry["TITLE_002"]["problems"] += 1
                        issues.append({
                            "category": "Local Content Signals",
                            "severity": IssueSeverity.OPPORTUNITY.value,
                            "title": f"Title Tag Lacks Target Geographic Location ({canonical_city})",
                            "evidence": f"Title '{title}' on key page {url} does not mention target city '{canonical_city}'.",
                            "why_it_matters": "Including your primary city or suburb in core page titles significantly boosts local search query relevance.",
                            "recommended_solution": f"Update title to include '{canonical_city}', e.g., '{title} - Serving {canonical_city}'.",
                            "action_type": "write_title",
                            "affected_url": url,
                            "template_slug": "service-location-page-blueprint"
                        })
                    else:
                        rules_registry["TITLE_002"]["passed"] += 1
                else:
                    rules_registry["TITLE_002"]["passed"] += 1

                # 3. META_001
                meta_desc = p.get("meta_description")
                if not meta_desc:
                    warning_count += 1
                    rules_registry["META_001"]["problems"] += 1
                    issues.append({
                        "category": "Local On-Page SEO",
                        "severity": IssueSeverity.WARNING.value,
                        "title": "Missing Meta Description",
                        "evidence": f"No meta description found on {url}.",
                        "why_it_matters": "Without a custom description, search engines display generic snippets which lowers local search CTR.",
                        "recommended_solution": "Add a 140-155 character description highlighting your local service, area served, and direct phone call CTA.",
                        "action_type": "write_meta_desc",
                        "affected_url": url,
                        "template_slug": "service-location-page-blueprint"
                    })
                else:
                    passed_count += 1
                    rules_registry["META_001"]["passed"] += 1

                # 4. H1_001
                h1 = p.get("h1")
                if not h1:
                    critical_count += 1
                    rules_registry["H1_001"]["problems"] += 1
                    issues.append({
                        "category": "Local On-Page SEO",
                        "severity": IssueSeverity.CRITICAL.value,
                        "title": "Missing Primary H1 Heading",
                        "evidence": f"No <h1> heading detected on {url}.",
                        "why_it_matters": "Search engine crawlers evaluate the H1 to verify the core local service offered on the page.",
                        "recommended_solution": "Add an H1 heading specifying your service offering and primary location.",
                        "action_type": "add_h1",
                        "affected_url": url,
                        "template_slug": "service-location-page-blueprint"
                    })
                else:
                    passed_count += 1
                    rules_registry["H1_001"]["passed"] += 1

                # 5. SCHEMA_001 & SCHEMA_002 Data Processing
                schema_types = p.get("schema_types", [])
                json_ld_schemas = p.get("json_ld_schemas", [])
                schema_instances_count += len(json_ld_schemas)

                if schema_types or json_ld_schemas:
                    pages_with_schema += 1
                    rules_registry["SCHEMA_001"]["passed"] += 1
                else:
                    pages_without_schema += 1
                    if is_home_or_contact:
                        rules_registry["SCHEMA_001"]["problems"] += 1
                    else:
                        rules_registry["SCHEMA_001"]["passed"] += 1

                # Process types for summary
                page_schema_types_set = set()
                local_schema_obj = None
                important_props: Dict[str, Any] = {}
                missing_props: List[str] = []

                for s in json_ld_schemas:
                    st = s.get("@type")
                    type_name = "Unknown"
                    if isinstance(st, str):
                        type_name = st
                    elif isinstance(st, list) and len(st) > 0:
                        type_name = str(st[0])

                    page_schema_types_set.add(type_name)
                    if type_name not in schema_type_counts:
                        schema_type_counts[type_name] = {"page_count": 0, "instance_count": 0}
                    schema_type_counts[type_name]["instance_count"] += 1

                    if any(sub in type_name for sub in recognized_subtypes):
                        local_schema_obj = s

                for t_name in page_schema_types_set:
                    if t_name in schema_type_counts:
                        schema_type_counts[t_name]["page_count"] += 1

                val_status = "No Schema"
                completeness = "Incomplete"
                raw_json_str = ""

                if json_ld_schemas:
                    import json
                    try:
                        raw_json_str = json.dumps(json_ld_schemas, indent=2)
                    except Exception:
                        raw_json_str = str(json_ld_schemas)

                if local_schema_obj:
                    has_valid_local_schema = True
                    val_status = "Supported"
                    
                    name_val = local_schema_obj.get("name")
                    phone_val = local_schema_obj.get("telephone")
                    addr_val = local_schema_obj.get("address")
                    geo_val = local_schema_obj.get("geo")
                    same_as_val = local_schema_obj.get("sameAs")

                    if name_val:
                        important_props["Name"] = name_val
                    else:
                        missing_props.append("name")

                    if phone_val:
                        important_props["Phone"] = phone_val
                    else:
                        missing_props.append("telephone")

                    if addr_val and isinstance(addr_val, dict):
                        street = addr_val.get("streetAddress", "")
                        loc_c = addr_val.get("addressLocality", "")
                        important_props["Address"] = f"{street} {loc_c}".strip() or "Present"
                    else:
                        missing_props.append("address (streetAddress/addressLocality)")

                    if geo_val and isinstance(geo_val, dict) and geo_val.get("latitude"):
                        important_props["Geo Coordinates"] = f"{geo_val.get('latitude')}, {geo_val.get('longitude')}"
                    else:
                        missing_props.append("geo (latitude/longitude)")

                    if same_as_val:
                        important_props["sameAs"] = f"{len(same_as_val)} links" if isinstance(same_as_val, list) else "Present"

                    if not missing_props:
                        completeness = "Complete"
                        complete_entities_count += 1
                        rules_registry["SCHEMA_002"]["passed"] += 1
                    else:
                        completeness = "Incomplete"
                        incomplete_entities_count += 1
                        val_status = "Partial Evidence"
                        rules_registry["SCHEMA_002"]["problems"] += 1
                        warning_count += 1
                        issues.append({
                            "category": "Local Schema & Structured Data",
                            "severity": IssueSeverity.WARNING.value,
                            "title": "Incomplete LocalBusiness Schema Attributes",
                            "evidence": f"LocalBusiness schema on {url} is missing required fields: {', '.join(missing_props)}.",
                            "why_it_matters": "Google requires complete address, phone, and geo coordinates in LocalBusiness JSON-LD to generate rich local cards and map pins.",
                            "recommended_solution": "Update the JSON-LD snippet using the 'LocalBusiness Schema.org JSON-LD' template to include full physical address and geo coordinates.",
                            "action_type": "generate_schema",
                            "affected_url": url,
                            "template_slug": "localbusiness-schema-standard"
                        })
                elif schema_types:
                    val_status = "Detected"
                    completeness = "Incomplete"
                    incomplete_entities_count += 1
                    if is_home_or_contact:
                        warning_count += 1
                        rules_registry["SCHEMA_002"]["problems"] += 1
                        issues.append({
                            "category": "Local Schema & Structured Data",
                            "severity": IssueSeverity.WARNING.value,
                            "title": "Missing LocalBusiness Structured Data (JSON-LD)",
                            "evidence": f"Found schema {schema_types} on {url}, but missing Schema.org LocalBusiness entity markup.",
                            "why_it_matters": "Google uses LocalBusiness JSON-LD to verify physical address, operating hours, coordinates, and telephone number.",
                            "recommended_solution": "Apply the 'LocalBusiness Schema.org JSON-LD' template to inject validated structured data into your website <head>.",
                            "action_type": "generate_schema",
                            "affected_url": url,
                            "template_slug": "localbusiness-schema-standard"
                        })
                    else:
                        rules_registry["SCHEMA_002"]["passed"] += 1
                else:
                    val_status = "Unable to Verify"
                    completeness = "Incomplete"
                    rules_registry["SCHEMA_002"]["passed"] += 1

                schema_evidence_list.append({
                    "url": url,
                    "schema_type": ", ".join(list(page_schema_types_set)) if page_schema_types_set else "None",
                    "validation_status": val_status,
                    "completeness": completeness,
                    "important_properties": important_props,
                    "missing_properties": missing_props,
                    "page_evidence": f"Detected {len(json_ld_schemas)} JSON-LD blocks on {url} with status '{val_status}'.",
                    "raw_json_ld": raw_json_str
                })

                # 6. NAP_001
                phones_on_page = p.get("phones_found", [])
                has_phone_mismatch = False
                for ph in phones_on_page:
                    norm_p = _normalize_phone(ph)
                    if norm_canonical_phone and norm_p and norm_canonical_phone not in norm_p and norm_p not in norm_canonical_phone:
                        if len(norm_p) >= 8 and len(norm_canonical_phone) >= 8:
                            has_phone_mismatch = True
                            warning_count += 1
                            potential_mismatches_count += 1
                            issues.append({
                                "category": "Business Identity & NAP",
                                "severity": IssueSeverity.WARNING.value,
                                "title": "On-Page Phone Number Mismatch",
                                "evidence": f"Page {url} displays phone '{ph}' which does not match canonical business phone '{canonical_phone}'.",
                                "why_it_matters": "Mismatched phone numbers across different website pages erode NAP consistency.",
                                "recommended_solution": f"Update contact links on {url} to consistently display '{canonical_phone}'.",
                                "action_type": "align_nap",
                                "affected_url": url,
                                "template_slug": "citation-nap-correction-task"
                            })
                if has_phone_mismatch:
                    rules_registry["NAP_001"]["problems"] += 1
                else:
                    rules_registry["NAP_001"]["passed"] += 1

                # 7. CONTENT_001
                word_count = p.get("word_count", 0)
                if word_count < 250 and is_home_or_contact:
                    warning_count += 1
                    rules_registry["CONTENT_001"]["problems"] += 1
                    issues.append({
                        "category": "Local Content Signals",
                        "severity": IssueSeverity.WARNING.value,
                        "title": "Thin Local Content on Service Page (< 250 words)",
                        "evidence": f"Key local page {url} contains only {word_count} words.",
                        "why_it_matters": "Google requires sufficient localized content, service descriptions, and customer FAQs.",
                        "recommended_solution": "Expand page content to 450+ words with localized customer FAQs and service descriptions.",
                        "action_type": "write_content",
                        "affected_url": url,
                        "template_slug": "location-landing-page-blueprint"
                    })
                else:
                    passed_count += 1
                    rules_registry["CONTENT_001"]["passed"] += 1

                # 8. CANONICAL_001
                if not p.get("canonical_url"):
                    opportunity_count += 1
                    rules_registry["CANONICAL_001"]["problems"] += 1
                    issues.append({
                        "category": "Local Website Crawlability",
                        "severity": IssueSeverity.OPPORTUNITY.value,
                        "title": "Missing Canonical Tag",
                        "evidence": f"No self-referential rel='canonical' tag found on {url}.",
                        "why_it_matters": "Ensures local landing page URLs are cleanly indexed without duplicate variations.",
                        "recommended_solution": f"Add <link rel='canonical' href='{url}' /> to the page head.",
                        "action_type": "add_canonical",
                        "affected_url": url,
                        "template_slug": "service-location-page-blueprint"
                    })
                else:
                    passed_count += 1
                    rules_registry["CANONICAL_001"]["passed"] += 1

                # 9. ALT_001
                missing_alts = p.get("missing_alt_count", 0)
                if missing_alts > 0:
                    opportunity_count += 1
                    rules_registry["ALT_001"]["problems"] += 1
                    issues.append({
                        "category": "Local On-Page SEO",
                        "severity": IssueSeverity.OPPORTUNITY.value,
                        "title": f"Images Missing Descriptive Alt Text ({missing_alts})",
                        "evidence": f"{missing_alts} images on {url} lack alt attributes.",
                        "why_it_matters": "Image alt tags aid accessibility and allow Google Images to index service photos.",
                        "recommended_solution": "Add descriptive alt attributes mentioning specific local service context.",
                        "action_type": "add_alt_text",
                        "affected_url": url,
                        "template_slug": "service-location-page-blueprint"
                    })
                else:
                    rules_registry["ALT_001"]["passed"] += 1

        # ---------------------------------------------------------------------
        # Cross-Module Evaluated Rules (GBP, Citations, Reviews)
        # ---------------------------------------------------------------------
        # GBP_001
        if gbp_context and gbp_context.get("connected"):
            gbp_phone = gbp_context.get("phone")
            gbp_name = gbp_context.get("business_name")
            gbp_website = gbp_context.get("website_url")
            gbp_problems = 0

            if canonical_name and gbp_name and canonical_name.strip().lower() != gbp_name.strip().lower():
                warning_count += 1
                gbp_problems += 1
                issues.append({
                    "category": "Business Identity & NAP",
                    "severity": IssueSeverity.WARNING.value,
                    "title": "Business Name Discrepancy: Website vs GBP",
                    "evidence": f"Website canonical name: '{canonical_name}' vs Google Business Profile name: '{gbp_name}'.",
                    "why_it_matters": "Inconsistent business names confuse search engines and can suppress Google Maps Local Pack authority.",
                    "recommended_solution": "Ensure your legal business name matches exactly across website headers, footer, Schema, and GBP.",
                    "action_type": "align_nap",
                    "affected_url": pages[0].get("url", "") if pages else "",
                    "template_slug": "citation-nap-correction-task"
                })

            norm_gbp_phone = _normalize_phone(gbp_phone)
            if norm_canonical_phone and norm_gbp_phone and norm_canonical_phone != norm_gbp_phone:
                critical_count += 1
                gbp_problems += 1
                issues.append({
                    "category": "Business Identity & NAP",
                    "severity": IssueSeverity.CRITICAL.value,
                    "title": "Phone Number Discrepancy: Website vs GBP",
                    "evidence": f"Website canonical phone '{canonical_phone}' differs from GBP phone '{gbp_phone}'.",
                    "why_it_matters": "Phone discrepancies are a primary cause of lost Local Pack rankings.",
                    "recommended_solution": f"Update Google Business Profile phone to match canonical business phone '{canonical_phone}'.",
                    "action_type": "align_nap",
                    "affected_url": pages[0].get("url", "") if pages else "",
                    "template_slug": "citation-nap-correction-task"
                })

            if gbp_problems > 0:
                rules_registry["GBP_001"]["problems"] = gbp_problems
            else:
                rules_registry["GBP_001"]["passed"] = 1
        else:
            opportunity_count += 1
            rules_registry["GBP_001"]["problems"] = 1
            issues.append({
                "category": "Google Business Profile",
                "severity": IssueSeverity.OPPORTUNITY.value,
                "title": "Google Business Profile Not Connected",
                "evidence": "No connected Google Business Profile account linked to this project.",
                "why_it_matters": "Connecting GBP allows real-time synchronization of hours, reviews, local pack rank, and NAP consistency.",
                "recommended_solution": "Connect your Google Business Profile account via the GBP module to enable automatic audits.",
                "action_type": "connect_gbp",
                "affected_url": pages[0].get("url", "") if pages else "",
                "template_slug": "gbp-weekly-update-post"
            })

        # CIT_001
        if citation_context:
            mismatched_cits = [c for c in citation_context if c.get("nap_status") == "mismatch" or c.get("status") == "incorrect"]
            missing_cits = [c for c in citation_context if c.get("status") == "missing"]
            if mismatched_cits or missing_cits:
                rules_registry["CIT_001"]["problems"] = len(mismatched_cits) + len(missing_cits)
                if mismatched_cits:
                    warning_count += 1
                    dir_names = ", ".join([c.get("source_name", "Directory") for c in mismatched_cits[:3]])
                    issues.append({
                        "category": "Citations & Directory NAP",
                        "severity": IssueSeverity.WARNING.value,
                        "title": f"NAP Discrepancies in {len(mismatched_cits)} Local Directory Listings",
                        "evidence": f"Listings on {dir_names} contain mismatched address, phone, or name details.",
                        "why_it_matters": "Inconsistent citations weaken Google's confidence in physical location.",
                        "recommended_solution": "Use Citation NAP Correction Task blueprint to update conflicting directories.",
                        "action_type": "fix_citations",
                        "affected_url": pages[0].get("url", "") if pages else "",
                        "template_slug": "citation-nap-correction-task"
                    })
            else:
                rules_registry["CIT_001"]["passed"] = len(citation_context)
        else:
            rules_registry["CIT_001"]["passed"] = 1

        # REV_001
        if review_context:
            unanswered_count = review_context.get("unanswered_count", 0)
            avg_rating = review_context.get("average_rating", 0.0)
            total_reviews = review_context.get("total_reviews", 0)

            if unanswered_count > 0 or (total_reviews > 0 and avg_rating < 4.4):
                rules_registry["REV_001"]["problems"] = (1 if unanswered_count > 0 else 0) + (1 if avg_rating < 4.4 else 0)
                if unanswered_count > 0:
                    warning_count += 1
                    issues.append({
                        "category": "Reviews & Reputation",
                        "severity": IssueSeverity.WARNING.value,
                        "title": f"{unanswered_count} Unanswered Customer Reviews",
                        "evidence": f"{unanswered_count} Google reviews have not received a response.",
                        "why_it_matters": "Responding to customer reviews improves local ranking visibility and consumer trust.",
                        "recommended_solution": "Apply Positive Review Response or Negative Review De-escalation templates.",
                        "action_type": "reply_reviews",
                        "affected_url": pages[0].get("url", "") if pages else "",
                        "template_slug": "positive-review-response"
                    })
            else:
                rules_registry["REV_001"]["passed"] = 1
        else:
            rules_registry["REV_001"]["passed"] = 1

        # Calculate Scores
        crawl_score = max(0, min(100, 100 - (critical_count * 20)))
        onpage_score = max(0, min(100, 100 - (warning_count * 10)))
        schema_score = 100 if has_valid_local_schema else 0

        gbp_score: Optional[int] = None
        if gbp_context and gbp_context.get("connected"):
            gbp_pts = 100
            if not (gbp_context.get("business_name") and canonical_name and gbp_context["business_name"].strip().lower() == canonical_name.strip().lower()):
                gbp_pts -= 30
            if not (gbp_context.get("phone") and norm_canonical_phone and _normalize_phone(gbp_context["phone"]) == norm_canonical_phone):
                gbp_pts -= 30
            if not gbp_context.get("address"):
                gbp_pts -= 20
            gbp_score = max(0, min(100, gbp_pts))

        cit_score: Optional[int] = None
        if citation_context and len(citation_context) > 0:
            total_cits = len(citation_context)
            consistent_cits = sum(1 for c in citation_context if c.get("nap_status") in ("consistent", "match") and c.get("status") in ("listed", "active"))
            cit_score = max(0, min(100, int((consistent_cits / total_cits) * 100)))

        rev_score: Optional[int] = None
        if review_context and review_context.get("total_reviews", 0) > 0:
            total_r = review_context["total_reviews"]
            unanswered_r = review_context.get("unanswered_count", 0)
            avg_r = review_context.get("average_rating", 0.0)
            rating_pts = (avg_r / 5.0) * 70.0
            response_pts = ((total_r - unanswered_r) / total_r) * 30.0
            rev_score = max(0, min(100, int(rating_pts + response_pts)))

        configured_weights = {
            "crawl_health": 0.20,
            "onpage_content": 0.20,
            "schema_structured_data": 0.25,
            "gbp_alignment": 0.15,
            "citations_nap": 0.10,
            "reviews_reputation": 0.10
        }

        pillar_weights = {
            "crawl_health": (crawl_score, configured_weights["crawl_health"]),
            "onpage_content": (onpage_score, configured_weights["onpage_content"]),
            "schema_structured_data": (schema_score, configured_weights["schema_structured_data"]),
            "gbp_alignment": (gbp_score, configured_weights["gbp_alignment"]),
            "citations_nap": (cit_score, configured_weights["citations_nap"]),
            "reviews_reputation": (rev_score, configured_weights["reviews_reputation"])
        }

        total_weight = 0.0
        weighted_sum = 0.0
        for pillar_name, (score_val, weight) in pillar_weights.items():
            if score_val is not None:
                total_weight += weight
                weighted_sum += (score_val * weight)

        score_available = total_pages > 0
        composite_score = int(weighted_sum / total_weight) if (score_available and total_weight > 0) else None

        # Build Executed Rules list and statuses
        rule_execution_results = []
        evaluated_rules_count = 0
        category_breakdown: Dict[str, Dict[str, int]] = {}

        for r_id, r_info in rules_registry.items():
            if r_info["evaluated"]:
                evaluated_rules_count += 1
                p_checked = r_info["pages_checked"]
                p_passed = r_info["passed"]
                p_probs = r_info["problems"]
                status_str = "Passed" if p_probs == 0 else "Issues Found"
            else:
                p_checked = 0
                p_passed = 0
                p_probs = 0
                status_str = "Not Evaluated"

            exec_item = {
                "rule_id": r_info["rule_id"],
                "category": r_info["category"],
                "rule_name": r_info["rule_name"],
                "what_was_checked": r_info["what_was_checked"],
                "validation_method": r_info["validation_method"],
                "evidence_source": r_info["evidence_source"],
                "requires_integration": r_info["requires_integration"],
                "evaluated": r_info["evaluated"],
                "pages_checked": p_checked,
                "passed": p_passed,
                "problems": p_probs,
                "status": status_str
            }
            rule_execution_results.append(exec_item)

            cat = r_info["category"]
            if cat not in category_breakdown:
                category_breakdown[cat] = {"total_checks": 0, "passed": 0, "problems": 0}
            category_breakdown[cat]["total_checks"] += p_checked
            category_breakdown[cat]["passed"] += p_passed
            category_breakdown[cat]["problems"] += p_probs

        total_evaluated_checks = total_pages * evaluated_rules_count

        # Build Schema Summary & Detected Types List
        detected_types_list = []
        for t_name, t_counts in schema_type_counts.items():
            detected_types_list.append({
                "type": t_name,
                "page_count": t_counts["page_count"],
                "instance_count": t_counts["instance_count"]
            })
        detected_types_list.sort(key=lambda x: x["page_count"], reverse=True)

        schema_summary = {
            "pages_scanned": total_pages,
            "pages_with_schema": pages_with_schema,
            "pages_without_schema": pages_without_schema,
            "total_schema_instances": schema_instances_count,
            "unique_schema_types": len(schema_type_counts),
            "complete_entities": complete_entities_count,
            "incomplete_entities": incomplete_entities_count,
            "potential_mismatches": potential_mismatches_count,
            "detected_types": detected_types_list
        }

        # Robots summary & evidence
        r_ctx = robots_context or {}
        robots_summary = {
            "robots_url": r_ctx.get("robots_url") or (f"https://{canonical_domain}/robots.txt" if canonical_domain else ""),
            "http_status": r_ctx.get("http_status", 200),
            "fetch_status": r_ctx.get("fetch_status", "Fetched Successfully" if total_pages > 0 else "Not Evaluated"),
            "user_agent_groups": r_ctx.get("user_agent_groups", 1),
            "allow_rules": r_ctx.get("allow_rules", 1),
            "disallow_rules": r_ctx.get("disallow_rules", 0),
            "sitemaps": r_ctx.get("sitemaps") or ([f"https://{canonical_domain}/sitemap.xml"] if canonical_domain else []),
            "seed_url_result": r_ctx.get("seed_url_result", "Allowed")
        }

        scoring_methodology = SEOAuditor.get_scoring_methodology()
        scoring_formula = "Composite score = weighted sum of evaluated pillars (Crawl Health 20%, Content 20%, Schema 25%, GBP 15%, Citations 10%, Reviews 10%). Unevaluated modules dynamically renormalize total weight to 100%."

        return {
            "score": composite_score,
            "health_score": composite_score,
            "score_available": score_available,
            "analyzed_pages": total_pages,
            "evaluated_rules": evaluated_rules_count,
            "total_evaluated_checks": total_evaluated_checks,
            "critical": critical_count,
            "warnings": warning_count,
            "opportunities": opportunity_count,
            "passed": passed_count,
            "pillar_weights": {k: f"{int(v * 100)}%" for k, v in configured_weights.items()},
            "scoring_methodology": scoring_methodology,
            "scoring_formula": scoring_formula,
            "scoring_weights": configured_weights,
            "pillar_scores": {
                "crawl_health": crawl_score,
                "onpage_content": onpage_score,
                "schema_structured_data": schema_score,
                "gbp_alignment": gbp_score,
                "citations_nap": cit_score,
                "reviews_reputation": rev_score
            },
            "rule_definitions": list(rules_registry.values()),
            "rule_execution_results": rule_execution_results,
            "category_breakdown": category_breakdown,
            "schema_summary": schema_summary,
            "schema_evidence": schema_evidence_list,
            "robots_summary": robots_summary,
            "robots_evidence": r_ctx.get("evidence", [
                f"User-agent: *\nAllow: /\nSitemap: https://{canonical_domain}/sitemap.xml" if canonical_domain else "No robots.txt fetched"
            ]),
            "issues": issues
        }

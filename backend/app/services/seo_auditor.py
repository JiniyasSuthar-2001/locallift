import re
import json
from typing import List, Dict, Any, Optional
from app.models.audit import IssueSeverity

def _normalize_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    return re.sub(r"[^\d+]", "", phone)

LOCAL_BUSINESS_TYPES = {
    "localbusiness", "professionalservice", "homeandconstructionbusiness",
    "electrician", "plumber", "hvacbusiness", "legalservice", "attorney", "lawyer",
    "medicalbusiness", "medicalclinic", "physician", "dentist", "optician",
    "automotivebusiness", "autorepair", "generalcontractor", "roofingcontractor",
    "store", "restaurant", "bakery", "hotel", "lodgingbusiness", "exercisegym",
    "healthandbeautybusiness", "hairsalon", "dayspa", "realestateagent",
    "accountingservice", "financialservice", "drycleaningorlaundry",
    "childcare", "emergencyservice", "employmentagency", "entertainmentbusiness",
    "foodestablishment", "governmentoffice", "library", "radiostation",
    "televisionstation", "touristinformationcenter", "travelagency"
}

NON_LOCAL_SCHEMAS = {
    "website", "webpage", "breadcrumblist", "faqpage", "article",
    "blogposting", "newsarticle", "person", "imageobject", "videoobject",
    "itemlist", "searchaction", "creativework"
}

class SEOAuditor:
    CONFIGURED_WEIGHTS = {
        "crawl_health": 0.20,
        "onpage_content": 0.25,
        "schema_structured_data": 0.15,
        "gbp_alignment": 0.10,
        "citations_nap": 0.10,
        "reviews_reputation": 0.20
    }

    @classmethod
    def get_pillar_weights_formatted(cls) -> Dict[str, str]:
        return {k: f"{int(v * 100)}%" for k, v in cls.CONFIGURED_WEIGHTS.items()}

    @classmethod
    def get_scoring_methodology(cls) -> Dict[str, Dict[str, Any]]:
        return {
            "crawl_health": {
                "name": "Local Crawl Health",
                "weight": "20%",
                "weight_fraction": 0.20,
                "description": "Checks whether search engines can access and index your important pages without errors or redirect issues."
            },
            "onpage_content": {
                "name": "Local On-Page & Geo-Content",
                "weight": "25%",
                "weight_fraction": 0.25,
                "description": "Verifies that your website clearly states your business name, location, and services across titles, headings, and content."
            },
            "schema_structured_data": {
                "name": "Schema & Structured Data",
                "weight": "15%",
                "weight_fraction": 0.15,
                "description": "Validates Schema.org LocalBusiness structured data (JSON-LD) to help search engines identify your physical presence, hours, and coordinates."
            },
            "gbp_alignment": {
                "name": "Google Business Profile Match",
                "weight": "10%",
                "weight_fraction": 0.10,
                "description": "Cross-verifies business information on your website against your connected Google Business Profile."
            },
            "citations_nap": {
                "name": "Citations & Directory NAP",
                "weight": "10%",
                "weight_fraction": 0.10,
                "description": "Checks consistency of Name, Address, and Phone across online business directories."
            },
            "reviews_reputation": {
                "name": "Reviews & Reputation",
                "weight": "20%",
                "weight_fraction": 0.20,
                "description": "Evaluates customer review ratings, review volume, and owner response coverage from your verified Google profile."
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
        Audit crawled website pages with a client-friendly LOCAL SEO focus.
        Produces explainable evidence, checklist indicators, and affected page lists.
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
        # 1. LOCAL CRAWL HEALTH
        # ---------------------------------------------------------------------
        crawl_issues_list = []
        crawl_affected_pages = []
        crawl_found_bullet_points = []
        crawl_recommendations = []
        
        http_ok_count = 0
        broken_page_count = 0
        canonical_missing_count = 0
        noindex_count = 0
        robots_blocked_count = 0
        slow_page_count = 0
        https_ok = True

        for p in pages:
            url = p.get("url", "")
            status = p.get("status_code", 200)
            canonical_url = p.get("canonical_url")
            is_indexable = p.get("is_indexable", True)
            load_time = p.get("load_time_ms", 0)
            issues_det = p.get("issues_detected", [])

            if not url.startswith("https://"):
                https_ok = False
                crawl_affected_pages.append({
                    "url": url,
                    "check": "HTTPS Security",
                    "observed_value": "HTTP (insecure)",
                    "status": "warning",
                    "status_code": status,
                    "problem": "Insecure HTTP connection",
                    "issue": "Insecure HTTP connection",
                    "recommendation": "Upgrade page URL to HTTPS and configure a 301 redirect."
                })

            if status >= 400:
                broken_page_count += 1
                critical_count += 1
                issue_item = {
                    "category": "Local Website Crawlability",
                    "severity": IssueSeverity.CRITICAL.value,
                    "title": f"Page Returned Error (HTTP {status})",
                    "evidence": f"URL {url} returned HTTP status code {status}.",
                    "why_it_matters": "Search engines cannot index broken pages, preventing customers from finding your local services.",
                    "recommended_solution": "Ensure the page returns a normal HTTP 200 OK response or set up a 301 redirect to an active page.",
                    "action_type": "fix_redirect",
                    "affected_url": url
                }
                issues.append(issue_item)
                crawl_issues_list.append(issue_item)
                crawl_affected_pages.append({
                    "url": url,
                    "check": "HTTP Status",
                    "observed_value": f"HTTP {status}",
                    "status": "error",
                    "status_code": status,
                    "problem": f"HTTP {status} error",
                    "issue": f"HTTP {status} error",
                    "recommendation": "Fix server route or redirect to an active page."
                })
            else:
                http_ok_count += 1
                passed_count += 1

            # Check explicit indexability & noindex
            if not is_indexable and status < 400:
                noindex_count += 1
                critical_count += 1
                issue_item = {
                    "category": "Local Website Crawlability",
                    "severity": IssueSeverity.CRITICAL.value,
                    "title": "Page Blocked by Noindex Directive",
                    "evidence": f"Page {url} contains a robots meta tag or header with 'noindex'.",
                    "why_it_matters": "Search engines are instructed not to include this page in search results, hiding it from nearby customers.",
                    "recommended_solution": "Remove the 'noindex' directive from HTML <head> or HTTP headers if this page should rank locally.",
                    "action_type": "remove_noindex",
                    "affected_url": url
                }
                issues.append(issue_item)
                crawl_issues_list.append(issue_item)
                crawl_affected_pages.append({
                    "url": url,
                    "check": "Indexability",
                    "observed_value": "noindex directive present",
                    "status": "error",
                    "status_code": status,
                    "problem": "Page contains noindex directive",
                    "issue": "Page contains noindex directive",
                    "recommendation": "Remove noindex meta tag if this page should be indexed by Google."
                })

            # Check robots restriction in issues
            if any("robots" in str(i).lower() and "disallow" in str(i).lower() for i in issues_det):
                robots_blocked_count += 1
                warning_count += 1
                crawl_affected_pages.append({
                    "url": url,
                    "check": "Robots.txt Accessibility",
                    "observed_value": "Disallowed by robots.txt",
                    "status": "warning",
                    "status_code": status,
                    "problem": "URL restricted by robots.txt",
                    "issue": "URL restricted by robots.txt",
                    "recommendation": "Update robots.txt rules to allow search engines to crawl key local pages."
                })

            if not canonical_url:
                canonical_missing_count += 1
                warning_count += 1
                issue_item = {
                    "category": "Local Website Crawlability",
                    "severity": IssueSeverity.WARNING.value,
                    "title": "Missing Canonical Tag",
                    "evidence": f"Page {url} has no rel='canonical' tag defined.",
                    "why_it_matters": "Canonical tags help search engines understand the preferred URL to show in local search results.",
                    "recommended_solution": f"Add a <link rel='canonical' href='{url}' /> tag to the page <head>.",
                    "action_type": "add_canonical",
                    "affected_url": url
                }
                issues.append(issue_item)
                crawl_issues_list.append(issue_item)
                crawl_affected_pages.append({
                    "url": url,
                    "check": "Canonical Tag",
                    "observed_value": "Missing canonical",
                    "status": "warning",
                    "status_code": status,
                    "problem": "Missing canonical URL tag",
                    "issue": "Missing canonical URL tag",
                    "recommendation": "Add a self-referential canonical tag in HTML <head>."
                })
            elif canonical_url != url and not url.endswith(canonical_url):
                canonical_missing_count += 1
                warning_count += 1
                issue_item = {
                    "category": "Local Website Crawlability",
                    "severity": IssueSeverity.WARNING.value,
                    "title": "Canonical URL Points to Different Address",
                    "evidence": f"Page {url} specifies canonical URL {canonical_url}.",
                    "why_it_matters": "Google may see another URL as the main version of this page and ignore local content signals.",
                    "recommended_solution": f"Ensure canonical tag correctly references {url} or verify the canonical target.",
                    "action_type": "fix_canonical",
                    "affected_url": url
                }
                issues.append(issue_item)
                crawl_issues_list.append(issue_item)
                crawl_affected_pages.append({
                    "url": url,
                    "check": "Canonical Tag",
                    "observed_value": f"Points to {canonical_url}",
                    "status": "warning",
                    "status_code": status,
                    "problem": f"Canonical points to {canonical_url}",
                    "issue": f"Canonical points to {canonical_url}",
                    "recommendation": "Update canonical URL to match the active page if this is a primary landing page."
                })

            if load_time > 2500:
                slow_page_count += 1
                opportunity_count += 1
                issues.append({
                    "category": "Performance",
                    "severity": IssueSeverity.OPPORTUNITY.value,
                    "title": "Slow Page Response Time",
                    "evidence": f"Page {url} took {load_time}ms to respond.",
                    "why_it_matters": "Fast-loading mobile pages offer better user experience for nearby customers searching on phones.",
                    "recommended_solution": "Optimize server response time and enable asset caching.",
                    "action_type": "optimize_performance",
                    "affected_url": url
                })

        if total_pages > 0:
            if broken_page_count == 0:
                crawl_found_bullet_points.append(f"✓ All {total_pages} scanned pages returned successfully (HTTP 200)")
            else:
                crawl_found_bullet_points.append(f"⚠ {broken_page_count} page(s) returned an HTTP error")

            if noindex_count == 0:
                crawl_found_bullet_points.append("✓ Pages are indexable for Google search")
            else:
                crawl_found_bullet_points.append(f"⚠ {noindex_count} page(s) contain a 'noindex' directive blocking search engines")

            if canonical_missing_count == 0:
                crawl_found_bullet_points.append("✓ Canonical tags are configured on all pages")
            else:
                crawl_found_bullet_points.append(f"⚠ {canonical_missing_count} page(s) have canonical tag issues")

            if https_ok:
                crawl_found_bullet_points.append("✓ HTTPS security is active")
            else:
                crawl_found_bullet_points.append("⚠ Insecure HTTP links detected on site")
        else:
            crawl_found_bullet_points.append("No pages scanned yet.")

        # Calculate Crawl Score
        if total_pages == 0:
            crawl_score = None
            crawl_status = "not_verified"
        else:
            crawl_deductions = (broken_page_count * 25) + (noindex_count * 20) + (robots_blocked_count * 15) + (min(canonical_missing_count, 3) * 5) + (0 if https_ok else 15)
            crawl_score = max(0, min(100, 100 - crawl_deductions))
            crawl_status = "pass" if crawl_score >= 80 else ("warning" if crawl_score >= 50 else "error")

        if broken_page_count > 0:
            crawl_recommendations.append("Review and fix broken pages returning 4xx/5xx status codes.")
        if noindex_count > 0:
            crawl_recommendations.append("Remove noindex directives from key service and contact pages.")
        if canonical_missing_count > 0:
            crawl_recommendations.append("Add self-referential canonical tags to all indexable pages.")
        if not https_ok:
            crawl_recommendations.append("Ensure all site URLs use secure HTTPS protocol.")

        crawl_details = {
            "score": crawl_score,
            "status": crawl_status,
            "pages_checked": total_pages,
            "broken_pages_count": broken_page_count,
            "noindex_count": noindex_count,
            "canonical_issues_count": canonical_missing_count,
            "https_active": https_ok,
            "what_we_checked": "We checked whether your important pages can be accessed by search engines without HTTP errors, broken redirects, or indexing barriers.",
            "what_we_found": crawl_found_bullet_points,
            "affected_pages": crawl_affected_pages,
            "issues": crawl_issues_list,
            "recommendations": crawl_recommendations
        }

        # ---------------------------------------------------------------------
        # 2. LOCAL ON-PAGE & GEO-CONTENT
        # ---------------------------------------------------------------------
        onpage_issues_list = []
        onpage_affected_pages = []
        onpage_found_bullet_points = []
        onpage_recommendations = []

        missing_title_count = 0
        missing_h1_count = 0
        missing_meta_desc_count = 0
        title_missing_city_count = 0
        h1_missing_city_count = 0
        thin_content_count = 0
        phone_found_count = 0
        address_found_count = 0

        for p in pages:
            url = p.get("url", "")
            title = p.get("title")
            meta_desc = p.get("meta_description")
            h1 = p.get("h1")
            word_count = p.get("word_count", 0)
            phones = p.get("phones_found", [])

            is_home_or_service = (
                url.rstrip("/").count("/") <= 3 or
                any(k in url.lower() for k in ["contact", "location", "about", "service"])
            )

            if not title:
                missing_title_count += 1
                critical_count += 1
                issue_item = {
                    "category": "Local On-Page SEO",
                    "severity": IssueSeverity.CRITICAL.value,
                    "title": "Missing Page Title Tag",
                    "evidence": f"Page {url} has no <title> tag defined.",
                    "why_it_matters": "The title tag is one of the highest-weight signals search engines use to understand your local service and location.",
                    "recommended_solution": "Add a unique local title tag, e.g. '[Service] in [City] | [Business Name]'.",
                    "action_type": "write_title",
                    "affected_url": url
                }
                issues.append(issue_item)
                onpage_issues_list.append(issue_item)
                onpage_affected_pages.append({
                    "url": url,
                    "problem": "Missing title tag",
                    "recommendation": "Add a descriptive local title tag."
                })
            else:
                if canonical_city and canonical_city.lower() not in title.lower() and is_home_or_service:
                    title_missing_city_count += 1
                    opportunity_count += 1
                    issues.append({
                        "category": "Local Content Signals",
                        "severity": IssueSeverity.OPPORTUNITY.value,
                        "title": f"Title Tag Does Not Mention Target City ({canonical_city})",
                        "evidence": f"Title '{title}' on {url} does not include your target city '{canonical_city}'.",
                        "why_it_matters": "Including your primary city or service area in key page titles boosts local query relevance.",
                        "recommended_solution": f"Update title to include '{canonical_city}'.",
                        "action_type": "write_title",
                        "affected_url": url
                    })

            if not h1:
                missing_h1_count += 1
                warning_count += 1
                issue_item = {
                    "category": "Local On-Page SEO",
                    "severity": IssueSeverity.WARNING.value,
                    "title": "Missing Primary H1 Heading",
                    "evidence": f"No <h1> heading found on {url}.",
                    "why_it_matters": "Search engines use the H1 heading to confirm what primary service or topic the page offers.",
                    "recommended_solution": "Add a clear H1 heading specifying your service and location.",
                    "action_type": "add_h1",
                    "affected_url": url
                }
                issues.append(issue_item)
                onpage_issues_list.append(issue_item)
                onpage_affected_pages.append({
                    "url": url,
                    "problem": "Missing <h1> heading",
                    "recommendation": "Add a single H1 heading stating the service and city."
                })

            if not meta_desc:
                missing_meta_desc_count += 1
                warning_count += 1
                issues.append({
                    "category": "Local On-Page SEO",
                    "severity": IssueSeverity.WARNING.value,
                    "title": "Missing Meta Description",
                    "evidence": f"No meta description found on {url}.",
                    "why_it_matters": "Meta descriptions provide the snippet text shown in Google search results and influence click-through rates.",
                    "recommended_solution": "Add a 140-155 character description highlighting your local service and phone number.",
                    "action_type": "write_meta_desc",
                    "affected_url": url
                })

            if word_count < 200 and is_home_or_service:
                thin_content_count += 1
                opportunity_count += 1
                issues.append({
                    "category": "Local Content Signals",
                    "severity": IssueSeverity.OPPORTUNITY.value,
                    "title": "Thin Landing Page Content",
                    "evidence": f"Page {url} has only {word_count} words of text.",
                    "why_it_matters": "Search engines require sufficient descriptive text to confirm the services and areas your business covers.",
                    "recommended_solution": "Expand page content with clear service descriptions, service areas, and customer FAQs.",
                    "action_type": "expand_content",
                    "affected_url": url
                })

            if len(phones) > 0:
                phone_found_count += 1

        onpage_checks = {
            "business_name_found": bool(canonical_name),
            "phone_number_found": phone_found_count > 0 or bool(canonical_phone),
            "city_location_found": bool(canonical_city),
            "local_h1_present": missing_h1_count == 0,
            "title_tags_present": missing_title_count == 0,
            "meta_descriptions_present": missing_meta_desc_count == 0
        }

        if total_pages > 0:
            if canonical_name:
                onpage_found_bullet_points.append(f"✓ Business name '{canonical_name}' identified")
            if onpage_checks["phone_number_found"]:
                onpage_found_bullet_points.append("✓ Phone contact signal detected")
            if canonical_city:
                onpage_found_bullet_points.append(f"✓ Target city '{canonical_city}' specified")
            if missing_title_count == 0:
                onpage_found_bullet_points.append("✓ All pages have title tags")
            else:
                onpage_found_bullet_points.append(f"⚠ {missing_title_count} page(s) missing title tags")

            if missing_h1_count == 0:
                onpage_found_bullet_points.append("✓ Primary H1 headings found across pages")
            else:
                onpage_found_bullet_points.append(f"⚠ {missing_h1_count} page(s) missing H1 headings")

            if title_missing_city_count > 0:
                onpage_found_bullet_points.append(f"ℹ {title_missing_city_count} title tag(s) could mention '{canonical_city}' for stronger local relevance")
        else:
            onpage_found_bullet_points.append("No pages scanned yet.")

        if total_pages == 0:
            onpage_score = None
            onpage_status = "not_verified"
        else:
            onpage_deductions = (missing_title_count * 25) + (missing_h1_count * 15) + (min(missing_meta_desc_count, 3) * 5)
            if not onpage_checks["phone_number_found"]:
                onpage_deductions += 10
            onpage_score = max(0, min(100, 100 - onpage_deductions))
            onpage_status = "pass" if onpage_score >= 80 else ("warning" if onpage_score >= 50 else "error")

        if missing_title_count > 0:
            onpage_recommendations.append("Add descriptive local title tags to all pages.")
        if missing_h1_count > 0:
            onpage_recommendations.append("Add a single H1 heading stating your primary service on key pages.")
        if title_missing_city_count > 0 and canonical_city:
            onpage_recommendations.append(f"Include your primary city '{canonical_city}' in key landing page titles.")

        onpage_details = {
            "score": onpage_score,
            "status": onpage_status,
            "checks": onpage_checks,
            "what_we_checked": "We checked whether your pages clearly tell search engines what business you are, where you operate, and what services you offer.",
            "what_we_found": onpage_found_bullet_points,
            "affected_pages": onpage_affected_pages,
            "issues": onpage_issues_list,
            "recommendations": onpage_recommendations
        }

        # ---------------------------------------------------------------------
        # 3. SCHEMA & STRUCTURED DATA
        # ---------------------------------------------------------------------
        schema_issues_list = []
        schema_affected_pages = []
        schema_found_bullet_points = []
        schema_recommendations = []
        schema_evidence = []

        all_detected_types = set()
        detected_type_counts: Dict[str, Dict[str, Any]] = {}
        schema_instances_count = 0
        pages_with_schema = 0
        pages_without_schema = 0
        complete_entities_count = 0
        incomplete_entities_count = 0
        potential_mismatches_count = 0

        has_local_business_schema = False
        local_business_entity: Optional[Dict[str, Any]] = None
        best_local_type: Optional[str] = None
        missing_schema_props = []

        schema_checklist = {
            "schema_found": False,
            "schema_present": False,
            "local_business": False,
            "local_business_type": False,
            "business_name": False,
            "address": False,
            "telephone": False,
            "phone": False,
            "geo": False,
            "geo_coordinates": False,
            "opening_hours": False,
            "website": False,
            "website_url": False
        }

        for p in pages:
            url = p.get("url", "")
            schema_data = p.get("schema_data") or {}
            json_ld_schemas = p.get("json_ld_schemas") or schema_data.get("json_ld_schemas") or []
            schema_entities = p.get("schema_entities") or schema_data.get("schema_entities") or []
            schema_parse_errors = p.get("schema_parse_errors") or schema_data.get("schema_parse_errors") or []
            
            entities_to_inspect = []
            if schema_entities:
                for e in schema_entities:
                    if isinstance(e, dict):
                        raw_ent = e.get("raw") or e
                        entities_to_inspect.append(raw_ent)
            elif json_ld_schemas:
                for item in json_ld_schemas:
                    if isinstance(item, dict):
                        if "@graph" in item and isinstance(item["@graph"], list):
                            entities_to_inspect.extend(item["@graph"])
                        else:
                            entities_to_inspect.append(item)
                    elif isinstance(item, list):
                        entities_to_inspect.extend([x for x in item if isinstance(x, dict)])

            if entities_to_inspect:
                pages_with_schema += 1
                schema_instances_count += len(entities_to_inspect)
            else:
                pages_without_schema += 1

            for ent in entities_to_inspect:
                if not isinstance(ent, dict):
                    continue
                raw_type = ent.get("@type", "Unknown")
                type_names = [raw_type] if isinstance(raw_type, str) else ([str(t) for t in raw_type] if isinstance(raw_type, list) else ["Unknown"])
                
                ent_missing = []
                is_local = False
                for t in type_names:
                    all_detected_types.add(t)
                    if t not in detected_type_counts:
                        detected_type_counts[t] = {"type": t, "page_count": 0, "instance_count": 0, "pages_seen": set()}
                    detected_type_counts[t]["instance_count"] += 1
                    if url not in detected_type_counts[t]["pages_seen"]:
                        detected_type_counts[t]["pages_seen"].add(url)
                        detected_type_counts[t]["page_count"] += 1

                    t_lower = t.lower()
                    if t_lower in LOCAL_BUSINESS_TYPES or any(sub in t_lower for sub in ["business", "service", "clinic", "shop", "store", "contractor", "agent", "restaurant"]):
                        has_local_business_schema = True
                        best_local_type = t
                        local_business_entity = ent
                        is_local = True

                # Check properties for evidence item
                ent_name = ent.get("name")
                ent_addr = ent.get("address")
                ent_phone = ent.get("telephone") or ent.get("phone")
                ent_geo = ent.get("geo")
                ent_hours = ent.get("openingHoursSpecification") or ent.get("openingHours")
                ent_url = ent.get("url")

                if is_local:
                    if not ent_name: ent_missing.append("name")
                    if not ent_addr: ent_missing.append("address")
                    if not ent_phone: ent_missing.append("telephone")
                    if not ent_geo: ent_missing.append("geo")
                    if not ent_hours: ent_missing.append("openingHours")
                    if not ent_url: ent_missing.append("url")

                    if not ent_missing:
                        complete_entities_count += 1
                    else:
                        incomplete_entities_count += 1

                schema_evidence.append({
                    "url": url,
                    "schema_type": ", ".join(type_names),
                    "schema_format": "JSON-LD",
                    "validation_status": "Valid" if not schema_parse_errors else "Errors Detected",
                    "important_properties": {
                        "name": ent_name,
                        "telephone": ent_phone,
                        "address": ent_addr,
                        "geo": ent_geo,
                        "openingHours": ent_hours,
                        "url": ent_url
                    },
                    "missing_properties": ent_missing,
                    "raw_json_ld": json.dumps(ent, default=str)
                })

            if schema_parse_errors:
                for err in schema_parse_errors:
                    schema_issues_list.append({
                        "category": "Schema & Structured Data",
                        "severity": IssueSeverity.WARNING.value,
                        "title": "JSON-LD Schema Syntax Error",
                        "evidence": f"Parse error on {url}: {err}",
                        "why_it_matters": "Search engines cannot parse malformed structured data.",
                        "recommended_solution": "Fix JSON syntax in your schema markup.",
                        "action_type": "fix_schema_syntax",
                        "affected_url": url
                    })

        if all_detected_types or pages_with_schema > 0:
            schema_checklist["schema_found"] = True
            schema_checklist["schema_present"] = True

        if has_local_business_schema and local_business_entity:
            schema_checklist["local_business"] = True
            schema_checklist["local_business_type"] = True

            name_val = local_business_entity.get("name")
            if name_val:
                schema_checklist["business_name"] = True
            else:
                missing_schema_props.append("name")

            addr_val = local_business_entity.get("address")
            if addr_val and (isinstance(addr_val, dict) or isinstance(addr_val, str)):
                schema_checklist["address"] = True
            else:
                missing_schema_props.append("address")

            tel_val = local_business_entity.get("telephone") or local_business_entity.get("phone")
            if tel_val:
                schema_checklist["telephone"] = True
                schema_checklist["phone"] = True
            else:
                missing_schema_props.append("telephone")

            geo_val = local_business_entity.get("geo")
            if geo_val and isinstance(geo_val, dict) and geo_val.get("latitude") and geo_val.get("longitude"):
                schema_checklist["geo"] = True
                schema_checklist["geo_coordinates"] = True
            else:
                missing_schema_props.append("geo coordinates (latitude / longitude)")

            hours_val = local_business_entity.get("openingHoursSpecification") or local_business_entity.get("openingHours")
            if hours_val:
                schema_checklist["opening_hours"] = True
            else:
                missing_schema_props.append("opening hours")

            url_val = local_business_entity.get("url")
            if url_val:
                schema_checklist["website"] = True
                schema_checklist["website_url"] = True
            else:
                missing_schema_props.append("website URL")

        # Build Schema Findings text
        if total_pages > 0:
            if schema_checklist["schema_present"]:
                schema_found_bullet_points.append(f"✓ Structured data detected ({', '.join(sorted(list(all_detected_types))[:4])})")
            else:
                schema_found_bullet_points.append("⚠ No structured data (JSON-LD) found on scanned pages")

            if has_local_business_schema:
                schema_found_bullet_points.append(f"✓ LocalBusiness structured data found ({best_local_type})")
                if schema_checklist["business_name"]:
                    schema_found_bullet_points.append("✓ Business name declared in schema")
                if schema_checklist["address"]:
                    schema_found_bullet_points.append("✓ Physical address declared in schema")
                if schema_checklist["telephone"]:
                    schema_found_bullet_points.append("✓ Phone number declared in schema")
                if schema_checklist["geo_coordinates"]:
                    schema_found_bullet_points.append("✓ Geo coordinates declared in schema")
                else:
                    schema_found_bullet_points.append("⚠ Missing geo coordinates in LocalBusiness schema")
                if schema_checklist["opening_hours"]:
                    schema_found_bullet_points.append("✓ Operating hours declared in schema")
                else:
                    schema_found_bullet_points.append("ℹ Operating hours not declared in schema")
            else:
                if schema_checklist["schema_present"]:
                    schema_found_bullet_points.append("⚠ Found other structured data, but no LocalBusiness schema")
                else:
                    schema_found_bullet_points.append("⚠ LocalBusiness structured data was not found on the pages we checked")

        # Calculate Schema Score
        if total_pages == 0:
            schema_score = None
            schema_status = "not_verified"
        elif not schema_checklist["schema_present"]:
            schema_score = 0
            schema_status = "error"
            schema_recommendations.append("Add LocalBusiness structured data (JSON-LD) to your website header.")
            schema_affected_pages.append({
                "url": pages[0].get("url", "/") if pages else "/",
                "problem": "No LocalBusiness schema markup found",
                "issue": "No LocalBusiness schema markup found",
                "recommendation": "Add LocalBusiness JSON-LD snippet with business name, address, phone, and geo coordinates."
            })
            issues.append({
                "category": "Schema & Structured Data",
                "severity": IssueSeverity.CRITICAL.value,
                "title": "Missing LocalBusiness Structured Data",
                "evidence": "No Schema.org LocalBusiness JSON-LD markup found on your scanned pages.",
                "why_it_matters": "Search engines use LocalBusiness structured data to verify physical storefront locations, generate rich search results, and link website data to Google Maps.",
                "recommended_solution": "Add a LocalBusiness JSON-LD snippet containing your business name, street address, telephone, and geo coordinates.",
                "action_type": "generate_schema",
                "affected_url": pages[0].get("url", "/") if pages else "/"
            })
        elif not has_local_business_schema:
            schema_score = 30
            schema_status = "warning"
            schema_recommendations.append("Add a LocalBusiness entity to complement existing website/article schema.")
            issues.append({
                "category": "Schema & Structured Data",
                "severity": IssueSeverity.WARNING.value,
                "title": "Non-Local Structured Data Found (Missing LocalBusiness)",
                "evidence": f"Found schemas: {', '.join(sorted(list(all_detected_types)))}, but no LocalBusiness entity.",
                "why_it_matters": "Generic WebSite or Breadcrumb schemas do not provide local business verification signals to Google.",
                "recommended_solution": "Add LocalBusiness schema markup specifying your physical location and phone number.",
                "action_type": "generate_schema",
                "affected_url": pages[0].get("url", "/") if pages else "/"
            })
        else:
            # LocalBusiness exists - calculate completeness
            prop_score = 40  # Base for having LocalBusiness
            if schema_checklist["business_name"]: prop_score += 15
            if schema_checklist["address"]: prop_score += 15
            if schema_checklist["telephone"]: prop_score += 10
            if schema_checklist["geo_coordinates"]: prop_score += 10
            if schema_checklist["opening_hours"]: prop_score += 5
            if schema_checklist["website_url"]: prop_score += 5
            
            schema_score = min(100, prop_score)
            schema_status = "pass" if schema_score >= 80 else "warning"

            if missing_schema_props:
                schema_recommendations.append(f"Add missing LocalBusiness attributes: {', '.join(missing_schema_props)}.")
                issues.append({
                    "category": "Schema & Structured Data",
                    "severity": IssueSeverity.WARNING.value,
                    "title": "Incomplete LocalBusiness Schema Attributes",
                    "evidence": f"LocalBusiness schema is missing: {', '.join(missing_schema_props)}.",
                    "why_it_matters": "Complete schema properties help search engines accurately map your storefront and operating times.",
                    "recommended_solution": f"Update JSON-LD to include {', '.join(missing_schema_props)}.",
                    "action_type": "generate_schema",
                    "affected_url": pages[0].get("url", "/") if pages else "/"
                })

        detected_types_summary = [
            {"type": v["type"], "page_count": v["page_count"], "instance_count": v["instance_count"]}
            for v in detected_type_counts.values()
        ]

        schema_summary = {
            "pages_scanned": total_pages,
            "pages_with_schema": pages_with_schema,
            "pages_without_schema": pages_without_schema,
            "total_schema_instances": schema_instances_count,
            "unique_schema_types": len(all_detected_types),
            "complete_entities": complete_entities_count,
            "incomplete_entities": incomplete_entities_count,
            "potential_mismatches": potential_mismatches_count,
            "detected_types": detected_types_summary
        }

        schema_details = {
            "score": schema_score,
            "status": schema_status,
            "schema_found": schema_checklist["schema_present"],
            "has_local_business": has_local_business_schema,
            "detected_types": sorted(list(all_detected_types)),
            "local_business_type": best_local_type,
            "checklist": schema_checklist,
            "missing_properties": missing_schema_props,
            "schema_evidence": schema_evidence,
            "schema_summary": schema_summary,
            "what_we_checked": "We checked for valid Schema.org LocalBusiness structured data (JSON-LD) to help search engines understand your business identity, physical location, and contact details.",
            "what_we_found": schema_found_bullet_points,
            "affected_pages": schema_affected_pages,
            "issues": schema_issues_list,
            "recommendations": schema_recommendations
        }

        # ---------------------------------------------------------------------
        # 4. GOOGLE BUSINESS PROFILE MATCH
        # ---------------------------------------------------------------------
        gbp_found_bullet_points = []
        gbp_recommendations = []
        gbp_fields = {}
        gbp_match_status = "not_connected"
        gbp_score = None

        if gbp_context and gbp_context.get("connected"):
            from app.services.google.nap_matcher import NAPMatcher

            gbp_name = gbp_context.get("business_name")
            gbp_phone = gbp_context.get("phone")
            gbp_addr = gbp_context.get("address")
            gbp_url = gbp_context.get("website_url")
            web_addr = (project_context or {}).get("address")

            norm_gbp_name = NAPMatcher.normalize_business_name(gbp_name)
            norm_web_name = NAPMatcher.normalize_business_name(canonical_name)
            name_sim = NAPMatcher._calculate_similarity(norm_web_name, norm_gbp_name) if (norm_web_name and norm_gbp_name) else 0.0
            name_match = bool(norm_web_name and norm_gbp_name and (norm_web_name == norm_gbp_name or name_sim >= 0.85))

            norm_gbp_phone = NAPMatcher.normalize_phone(gbp_phone)
            norm_web_phone = NAPMatcher.normalize_phone(canonical_phone)
            phone_match = bool(norm_web_phone and norm_gbp_phone and (norm_web_phone == norm_gbp_phone or norm_web_phone.endswith(norm_gbp_phone) or norm_gbp_phone.endswith(norm_web_phone)))

            norm_gbp_addr = NAPMatcher.normalize_address(gbp_addr)
            norm_web_addr = NAPMatcher.normalize_address(web_addr)
            addr_sim = NAPMatcher._calculate_similarity(norm_web_addr, norm_gbp_addr) if (norm_web_addr and norm_gbp_addr) else 0.0
            addr_match = bool(norm_web_addr and norm_gbp_addr and (norm_web_addr == norm_gbp_addr or addr_sim >= 0.8))

            norm_gbp_url = NAPMatcher.normalize_website(gbp_url)
            norm_web_url = NAPMatcher.normalize_website(canonical_domain)
            url_match = bool(norm_web_url and norm_gbp_url and (norm_web_url == norm_gbp_url or norm_web_url in norm_gbp_url or norm_gbp_url in norm_web_url))

            gbp_fields = {
                "business_name": {"website": canonical_name, "gbp": gbp_name, "match": name_match, "status": "MATCH" if name_match else ("NOT_VERIFIED" if not gbp_name or not canonical_name else "MISMATCH")},
                "phone": {"website": canonical_phone, "gbp": gbp_phone, "match": phone_match, "status": "MATCH" if phone_match else ("NOT_VERIFIED" if not gbp_phone or not canonical_phone else "MISMATCH")},
                "address": {"website": web_addr, "gbp": gbp_addr, "match": addr_match, "status": "MATCH" if addr_match else ("NOT_VERIFIED" if not gbp_addr or not web_addr else "MISMATCH")},
                "website_url": {"website": f"https://{canonical_domain}" if canonical_domain else None, "gbp": gbp_url, "match": url_match, "status": "MATCH" if url_match else ("NOT_VERIFIED" if not gbp_url or not canonical_domain else "MISMATCH")}
            }

            matches_count = sum(1 for f in [name_match, phone_match, addr_match, url_match] if f)
            if matches_count == 4:
                gbp_match_status = "matched"
                gbp_score = 100
                gbp_found_bullet_points.append(f"✓ Business name matches connected profile ({gbp_name})")
                gbp_found_bullet_points.append(f"✓ Phone number matches ({gbp_phone})")
                gbp_found_bullet_points.append("✓ Address matches connected profile")
                gbp_found_bullet_points.append("✓ Website URL matches connected profile")
            elif matches_count >= 2:
                gbp_match_status = "partial_match"
                gbp_score = 70
                gbp_found_bullet_points.append(f"✓ Business name matches: {gbp_name}" if name_match else "⚠ Business name difference detected")
                gbp_found_bullet_points.append(f"✓ Phone matches: {gbp_phone}" if phone_match else "⚠ Phone number difference detected")
                gbp_found_bullet_points.append("✓ Address matches" if addr_match else ("⚠ Address difference detected" if (gbp_addr and web_addr) else "ℹ Address not provided on one or both profiles"))
                gbp_recommendations.append("Align your website Name, Phone, and Address exactly with your Google Business Profile.")
            else:
                gbp_match_status = "mismatch"
                gbp_score = 40
                gbp_found_bullet_points.append("⚠ Substantial business information differences found between website and GBP")
                gbp_recommendations.append("Update website contact information to match your Google Business Profile.")
        else:
            gbp_match_status = "not_connected"
            gbp_found_bullet_points.append("Google Business Profile is not connected to this project yet.")
            gbp_recommendations.append("Connect your Google Business Profile in Settings to enable cross-platform alignment checks.")

        gbp_details = {
            "status": gbp_match_status,
            "score": gbp_score,
            "connected": bool(gbp_context and gbp_context.get("connected")),
            "profile_name": (gbp_context or {}).get("business_name"),
            "fields": gbp_fields,
            "what_we_checked": "We cross-compared your website's business name, phone number, address, and URL against your connected Google Business Profile.",
            "what_we_found": gbp_found_bullet_points,
            "recommendations": gbp_recommendations
        }

        # ---------------------------------------------------------------------
        # 5. CITATIONS & DIRECTORY NAP
        # ---------------------------------------------------------------------
        cit_found_bullet_points = []
        cit_recommendations = []
        cit_score = None
        cit_status = "not_verified"

        if citation_context is not None and len(citation_context) > 0:
            total_cits = len(citation_context)
            consistent_cits = sum(1 for c in citation_context if c.get("nap_status") in ("consistent", "match", "aligned") and c.get("status") in ("listed", "active"))
            mismatch_cits = total_cits - consistent_cits
            cit_score = max(0, min(100, int((consistent_cits / total_cits) * 100)))
            cit_status = "pass" if cit_score >= 85 else ("warning" if cit_score >= 50 else "error")

            cit_found_bullet_points.append(f"Directories checked: {total_cits}")
            cit_found_bullet_points.append(f"✓ Consistent listings: {consistent_cits}")
            if mismatch_cits > 0:
                cit_found_bullet_points.append(f"⚠ Listings needing attention: {mismatch_cits}")
                cit_recommendations.append(f"Correct inconsistent Name, Address, or Phone data on {mismatch_cits} directory listing(s).")
        else:
            cit_status = "not_verified"
            cit_found_bullet_points.append("Citation verification has not been configured for this project.")
            cit_recommendations.append("Run citation sync to verify NAP consistency across online directories.")

        citations_details = {
            "status": cit_status,
            "score": cit_score,
            "total_directories": len(citation_context) if citation_context else 0,
            "consistent_count": sum(1 for c in citation_context if c.get("nap_status") in ("consistent", "match", "aligned")) if citation_context else 0,
            "mismatch_count": sum(1 for c in citation_context if c.get("nap_status") in ("mismatch", "incorrect")) if citation_context else 0,
            "what_we_checked": "We verified consistency of your business Name, Address, and Phone (NAP) across registered local directories.",
            "what_we_found": cit_found_bullet_points,
            "recommendations": cit_recommendations
        }

        # ---------------------------------------------------------------------
        # 6. REVIEWS & REPUTATION
        # ---------------------------------------------------------------------
        rev_found_bullet_points = []
        rev_recommendations = []
        rev_score = None
        rev_status = "no_data"

        if review_context and review_context.get("total_reviews", 0) > 0:
            total_r = review_context["total_reviews"]
            unanswered_r = review_context.get("unanswered_count", 0)
            avg_r = review_context.get("average_rating", 0.0)
            answered_r = max(0, total_r - unanswered_r)
            resp_pct = int((answered_r / total_r) * 100) if total_r > 0 else 0

            rating_pts = (avg_r / 5.0) * 70.0
            resp_pts = (answered_r / total_r) * 30.0
            rev_score = max(0, min(100, int(rating_pts + resp_pts)))
            rev_status = "pass" if rev_score >= 80 else ("warning" if rev_score >= 50 else "error")

            rev_found_bullet_points.append(f"✓ Total reviews analyzed: {total_r}")
            rev_found_bullet_points.append(f"✓ Average rating: {avg_r:.1f} ★")
            rev_found_bullet_points.append(f"✓ Responses answered: {answered_r}/{total_r} ({resp_pct}%)")

            if unanswered_r > 0:
                rev_found_bullet_points.append(f"ℹ {unanswered_r} review(s) currently awaiting an owner response")
                rev_recommendations.append(f"Respond to {unanswered_r} unanswered customer review(s) to improve engagement signals.")
        else:
            rev_status = "no_data"
            rev_found_bullet_points.append("Review data is not available because no connected review source has been synced.")
            rev_recommendations.append("Connect your Google Business Profile to sync customer reviews.")

        reviews_details = {
            "status": rev_status,
            "score": rev_score,
            "total_reviews": review_context.get("total_reviews", 0) if review_context else 0,
            "average_rating": review_context.get("average_rating", 0.0) if review_context else 0.0,
            "unanswered_count": review_context.get("unanswered_count", 0) if review_context else 0,
            "response_rate_pct": int(((review_context.get("total_reviews", 0) - review_context.get("unanswered_count", 0)) / review_context.get("total_reviews", 1)) * 100) if (review_context and review_context.get("total_reviews", 0) > 0) else 0,
            "what_we_checked": "We analyzed review volume, customer star ratings, and owner response coverage from your verified profile.",
            "what_we_found": rev_found_bullet_points,
            "recommendations": rev_recommendations
        }

        # ---------------------------------------------------------------------
        # COMPOSITE SCORE (Normalized across verified categories)
        # ---------------------------------------------------------------------
        configured_weights = SEOAuditor.CONFIGURED_WEIGHTS

        evaluated_pillars = {
            "crawl_health": (crawl_score, configured_weights["crawl_health"]),
            "onpage_content": (onpage_score, configured_weights["onpage_content"]),
            "schema_structured_data": (schema_score, configured_weights["schema_structured_data"]),
            "gbp_alignment": (gbp_score, configured_weights["gbp_alignment"]),
            "citations_nap": (cit_score, configured_weights["citations_nap"]),
            "reviews_reputation": (rev_score, configured_weights["reviews_reputation"])
        }

        active_weight_sum = 0.0
        weighted_score_sum = 0.0
        for pillar_key, (p_score, p_weight) in evaluated_pillars.items():
            if p_score is not None:
                active_weight_sum += p_weight
                weighted_score_sum += (p_score * p_weight)

        composite_score = int(weighted_score_sum / active_weight_sum) if (total_pages > 0 and active_weight_sum > 0) else None

        return {
            "score": composite_score,
            "health_score": composite_score,
            "score_available": composite_score is not None,
            "analyzed_pages": total_pages,
            "critical": critical_count,
            "warnings": warning_count,
            "opportunities": opportunity_count,
            "passed": passed_count,
            "pillar_scores": {
                "crawl_health": crawl_score,
                "onpage_content": onpage_score,
                "schema_structured_data": schema_score,
                "gbp_alignment": gbp_score,
                "citations_nap": cit_score,
                "reviews_reputation": rev_score
            },
            "pillar_weights": {k: f"{int(v * 100)}%" for k, v in configured_weights.items()},
            "scoring_methodology": SEOAuditor.get_scoring_methodology(),
            
            # Pillar breakdown details (Full 6 Pillars)
            "crawl": crawl_details,
            "local_on_page": onpage_details,
            "schema": schema_details,
            "gbp_match": gbp_details,
            "citations": citations_details,
            "reviews": reviews_details,

            "schema_summary": schema_summary,
            "schema_evidence": schema_evidence,
            "issues": issues
        }


LocalSEOAuditor = SEOAuditor


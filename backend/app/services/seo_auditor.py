import re
from typing import List, Dict, Any, Optional
from app.models.audit import IssueSeverity

def _normalize_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    # Strip everything except digits and plus sign
    return re.sub(r"[^\d+]", "", phone)

class SEOAuditor:
    @staticmethod
    def audit_pages(
        pages: List[Dict[str, Any]],
        project_context: Optional[Dict[str, Any]] = None,
        gbp_context: Optional[Dict[str, Any]] = None,
        citation_context: Optional[List[Dict[str, Any]]] = None,
        review_context: Optional[Dict[str, Any]] = None,
        keyword_context: Optional[List[Dict[str, Any]]] = None,
        competitor_context: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Audit crawled website pages with a strict LOCAL SEO FIRST focus:
        1. Business Identity & NAP on-page consistency.
        2. Deep LocalBusiness Schema (JSON-LD) validation (name, phone, address, geo, hours).
        3. Local Landing Page & Suburb relevance and coverage.
        4. Cross-comparison with Google Business Profile (Name, Phone, Address, Website).
        5. Citations & Directory NAP verification.
        6. Reviews & Reputation responsiveness.
        7. Core crawlability and indexability.
        """
        issues = []
        critical_count = 0
        warning_count = 0
        opportunity_count = 0
        passed_count = 0

        total_pages = len(pages)
        if total_pages == 0:
            return {
                "score": 0,
                "critical": 0,
                "warnings": 0,
                "opportunities": 0,
                "passed": 0,
                "pillar_scores": {
                    "crawl_health": 0,
                    "onpage_content": 0,
                    "schema_structured_data": 0,
                    "gbp_alignment": 0,
                    "citations_nap": 0,
                    "reviews_reputation": 0
                },
                "issues": []
            }

        canonical_phone = (project_context or {}).get("phone") or (gbp_context or {}).get("phone")
        canonical_name = (project_context or {}).get("name") or (gbp_context or {}).get("business_name")
        canonical_city = (project_context or {}).get("city")
        canonical_domain = (project_context or {}).get("domain") or ""
        norm_canonical_phone = _normalize_phone(canonical_phone)

        has_valid_local_schema = False
        all_detected_phones = set()

        for p in pages:
            url = p.get("url", "")
            is_home_or_contact = (
                url.rstrip("/").count("/") <= 3 or
                "contact" in url.lower() or
                "location" in url.lower() or
                "about" in url.lower()
            )

            # -----------------------------------------------------------------
            # 1. Check HTTP Status & Crawlability
            # -----------------------------------------------------------------
            status = p.get("status_code", 200)
            if status >= 400:
                critical_count += 1
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

            # -----------------------------------------------------------------
            # 2. Check Title & Local Keyword Targeting
            # -----------------------------------------------------------------
            title = p.get("title")
            if not title:
                critical_count += 1
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
                if canonical_city and canonical_city.lower() not in title.lower() and is_home_or_contact:
                    opportunity_count += 1
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

            # -----------------------------------------------------------------
            # 3. Check Meta Description with Local Intent
            # -----------------------------------------------------------------
            meta_desc = p.get("meta_description")
            if not meta_desc:
                warning_count += 1
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

            # -----------------------------------------------------------------
            # 4. Check H1 Heading
            # -----------------------------------------------------------------
            h1 = p.get("h1")
            if not h1:
                critical_count += 1
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

            # -----------------------------------------------------------------
            # 5. Deep LocalBusiness JSON-LD Schema Validation
            # -----------------------------------------------------------------
            schema_types = p.get("schema_types", [])
            json_ld_schemas = p.get("json_ld_schemas", [])

            local_schema_obj = None
            recognized_subtypes = [
                "LocalBusiness", "ProfessionalService", "HomeAndConstructionBusiness",
                "Electrician", "Plumber", "HVACBusiness", "LegalService", "MedicalBusiness",
                "AutomotiveBusiness", "GeneralContractor", "Store", "Restaurant"
            ]

            for s in json_ld_schemas:
                st = s.get("@type")
                if isinstance(st, str) and any(sub in st for sub in recognized_subtypes):
                    local_schema_obj = s
                    break
                elif isinstance(st, list) and any(any(sub in item for sub in recognized_subtypes) for item in st if isinstance(item, str)):
                    local_schema_obj = s
                    break

            if local_schema_obj:
                has_valid_local_schema = True
                passed_count += 2

                missing_schema_fields = []
                if not local_schema_obj.get("name"):
                    missing_schema_fields.append("name")
                if not local_schema_obj.get("telephone"):
                    missing_schema_fields.append("telephone")
                
                addr = local_schema_obj.get("address")
                if not addr or not isinstance(addr, dict) or not (addr.get("addressLocality") or addr.get("streetAddress")):
                    missing_schema_fields.append("address (streetAddress / addressLocality)")
                
                geo = local_schema_obj.get("geo")
                if not geo or not isinstance(geo, dict) or not (geo.get("latitude") and geo.get("longitude")):
                    missing_schema_fields.append("geo (latitude, longitude)")

                if missing_schema_fields:
                    warning_count += 1
                    issues.append({
                        "category": "Local Schema & Structured Data",
                        "severity": IssueSeverity.WARNING.value,
                        "title": "Incomplete LocalBusiness Schema Attributes",
                        "evidence": f"LocalBusiness schema on {url} is missing required fields: {', '.join(missing_schema_fields)}.",
                        "why_it_matters": "Google requires complete address, phone, and geo coordinates in LocalBusiness JSON-LD to generate rich local cards and map pins.",
                        "recommended_solution": "Update the JSON-LD snippet using the 'LocalBusiness Schema.org JSON-LD' template to include full physical address and geo coordinates.",
                        "action_type": "generate_schema",
                        "affected_url": url,
                        "template_slug": "localbusiness-schema-standard"
                    })
                else:
                    passed_count += 1
            elif is_home_or_contact:
                warning_count += 1
                issues.append({
                    "category": "Local Schema & Structured Data",
                    "severity": IssueSeverity.WARNING.value,
                    "title": "Missing LocalBusiness Structured Data (JSON-LD)",
                    "evidence": f"Found schema {schema_types or 'None'} on {url}, but missing Schema.org LocalBusiness entity markup.",
                    "why_it_matters": "Google uses LocalBusiness JSON-LD to verify physical address, operating hours, coordinates, and telephone number for Google Maps and Knowledge Graph integration.",
                    "recommended_solution": "Apply the 'LocalBusiness Schema.org JSON-LD' template to inject validated structured data into your website <head>.",
                    "action_type": "generate_schema",
                    "affected_url": url,
                    "template_slug": "localbusiness-schema-standard"
                })

            # -----------------------------------------------------------------
            # 6. Phone Numbers Found & On-Page NAP Consistency
            # -----------------------------------------------------------------
            phones_on_page = p.get("phones_found", [])
            for ph in phones_on_page:
                all_detected_phones.add(ph)
                norm_p = _normalize_phone(ph)
                if norm_canonical_phone and norm_p and norm_canonical_phone not in norm_p and norm_p not in norm_canonical_phone:
                    if len(norm_p) >= 8 and len(norm_canonical_phone) >= 8:
                        warning_count += 1
                        issues.append({
                            "category": "Business Identity & NAP",
                            "severity": IssueSeverity.WARNING.value,
                            "title": "On-Page Phone Number Mismatch",
                            "evidence": f"Page {url} displays phone '{ph}' which does not match your canonical business phone '{canonical_phone}'.",
                            "why_it_matters": "Mismatched phone numbers across different website pages erode NAP consistency and confuse local customers.",
                            "recommended_solution": f"Update contact links and headers on {url} to consistently display '{canonical_phone}'.",
                            "action_type": "align_nap",
                            "affected_url": url,
                            "template_slug": "citation-nap-correction-task"
                        })

            # -----------------------------------------------------------------
            # 7. Check Thin Content on Local Landing Pages
            # -----------------------------------------------------------------
            word_count = p.get("word_count", 0)
            if word_count < 250 and is_home_or_contact:
                warning_count += 1
                issues.append({
                    "category": "Local Content Signals",
                    "severity": IssueSeverity.WARNING.value,
                    "title": "Thin Local Content on Service Page (< 250 words)",
                    "evidence": f"Key local page {url} contains only {word_count} words.",
                    "why_it_matters": "Google requires sufficient localized content, service descriptions, and customer FAQs to rank in competitive local search queries.",
                    "recommended_solution": "Expand page content to 450+ words with localized customer FAQs, neighborhood testimonials, and detailed service descriptions.",
                    "action_type": "write_content",
                    "affected_url": url,
                    "template_slug": "location-landing-page-blueprint"
                })

            # -----------------------------------------------------------------
            # 8. Check Canonical Tag
            # -----------------------------------------------------------------
            if not p.get("canonical_url"):
                opportunity_count += 1
                issues.append({
                    "category": "Local Website Crawlability",
                    "severity": IssueSeverity.OPPORTUNITY.value,
                    "title": "Missing Canonical Tag",
                    "evidence": f"No self-referential rel='canonical' tag found on {url}.",
                    "why_it_matters": "Ensures local landing page URLs are cleanly indexed without duplicate variations from tracking parameters.",
                    "recommended_solution": f"Add <link rel='canonical' href='{url}' /> to the page head.",
                    "action_type": "add_canonical",
                    "affected_url": url,
                    "template_slug": "service-location-page-blueprint"
                })
            else:
                passed_count += 1

            # -----------------------------------------------------------------
            # 9. Check Image Alt Tags with Local Service Context
            # -----------------------------------------------------------------
            missing_alts = p.get("missing_alt_count", 0)
            if missing_alts > 0:
                opportunity_count += 1
                issues.append({
                    "category": "Local On-Page SEO",
                    "severity": IssueSeverity.OPPORTUNITY.value,
                    "title": f"Images Missing Descriptive Alt Text ({missing_alts})",
                    "evidence": f"{missing_alts} images on {url} lack alt attributes.",
                    "why_it_matters": "Image alt tags aid accessibility and allow Google Images to index service photos with local context.",
                    "recommended_solution": "Add descriptive alt attributes mentioning the specific work or local equipment displayed.",
                    "action_type": "add_alt_text",
                    "affected_url": url,
                    "template_slug": "service-location-page-blueprint"
                })

        # =====================================================================
        # Cross-Module Bridge 1: Google Business Profile Connection
        # =====================================================================
        if gbp_context and gbp_context.get("connected"):
            gbp_phone = gbp_context.get("phone")
            gbp_name = gbp_context.get("business_name")
            gbp_website = gbp_context.get("website_url")

            # Name Check
            if canonical_name and gbp_name and canonical_name.strip().lower() != gbp_name.strip().lower():
                warning_count += 1
                issues.append({
                    "category": "Business Identity & NAP",
                    "severity": IssueSeverity.WARNING.value,
                    "title": "Business Name Discrepancy: Website vs GBP",
                    "evidence": f"Website canonical name: '{canonical_name}' vs Google Business Profile name: '{gbp_name}'.",
                    "why_it_matters": "Inconsistent business names confuse search engines and can suppress Google Maps Local Pack authority.",
                    "recommended_solution": "Ensure your legal business name matches exactly across website headers, footer, Schema, and Google Business Profile.",
                    "action_type": "align_nap",
                    "affected_url": pages[0].get("url", "") if pages else "",
                    "template_slug": "citation-nap-correction-task"
                })

            # Phone Check
            norm_gbp_phone = _normalize_phone(gbp_phone)
            if norm_canonical_phone and norm_gbp_phone and norm_canonical_phone != norm_gbp_phone:
                critical_count += 1
                issues.append({
                    "category": "Business Identity & NAP",
                    "severity": IssueSeverity.CRITICAL.value,
                    "title": "Phone Number Discrepancy: Website vs GBP",
                    "evidence": f"Website canonical phone '{canonical_phone}' differs from GBP phone '{gbp_phone}'.",
                    "why_it_matters": "Phone discrepancies are a primary cause of lost Local Pack rankings and suspended Google Maps listings.",
                    "recommended_solution": f"Update Google Business Profile phone to match your canonical business phone '{canonical_phone}'.",
                    "action_type": "align_nap",
                    "affected_url": pages[0].get("url", "") if pages else "",
                    "template_slug": "citation-nap-correction-task"
                })

            # Website URL Check
            if canonical_domain and gbp_website:
                clean_gbp_web = gbp_website.replace("https://", "").replace("http://", "").rstrip("/").lower()
                clean_can_dom = canonical_domain.replace("https://", "").replace("http://", "").rstrip("/").lower()
                if clean_gbp_web and clean_can_dom and clean_can_dom not in clean_gbp_web:
                    warning_count += 1
                    issues.append({
                        "category": "Google Business Profile",
                        "severity": IssueSeverity.WARNING.value,
                        "title": "Website URL Mismatch in Google Business Profile",
                        "evidence": f"GBP links to '{gbp_website}', but active project domain is '{canonical_domain}'.",
                        "why_it_matters": "Directing GBP traffic to an outdated or mismatched domain splits authority and tracking signals.",
                        "recommended_solution": f"Update the primary website link in GBP to https://{canonical_domain}.",
                        "action_type": "align_nap",
                        "affected_url": pages[0].get("url", "") if pages else "",
                        "template_slug": "gbp-weekly-update-post"
                    })
        else:
            opportunity_count += 1
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

        # =====================================================================
        # Cross-Module Bridge 2: Citations & NAP Verification
        # =====================================================================
        if citation_context:
            mismatched_cits = [c for c in citation_context if c.get("nap_status") == "mismatch" or c.get("status") == "incorrect"]
            missing_cits = [c for c in citation_context if c.get("status") == "missing"]

            if mismatched_cits:
                warning_count += 1
                dir_names = ", ".join([c.get("source_name", "Directory") for c in mismatched_cits[:3]])
                issues.append({
                    "category": "Citations & Directory NAP",
                    "severity": IssueSeverity.WARNING.value,
                    "title": f"NAP Discrepancies in {len(mismatched_cits)} Local Directory Listings",
                    "evidence": f"Listings on {dir_names} contain mismatched address, phone, or name details.",
                    "why_it_matters": "Inconsistent citations weaken Google's confidence in your physical location, reducing Local 3-Pack rank.",
                    "recommended_solution": "Use the Citation NAP Correction Task blueprint to update the conflicting directories.",
                    "action_type": "fix_citations",
                    "affected_url": pages[0].get("url", "") if pages else "",
                    "template_slug": "citation-nap-correction-task"
                })

            if missing_cits:
                opportunity_count += 1
                missing_names = ", ".join([c.get("source_name", "Directory") for c in missing_cits[:3]])
                issues.append({
                    "category": "Citations & Directory NAP",
                    "severity": IssueSeverity.OPPORTUNITY.value,
                    "title": f"Missing from {len(missing_cits)} High-Authority Local Directories",
                    "evidence": f"Your business is not listed on key directories: {missing_names}.",
                    "why_it_matters": "Top local directories establish geographic prominence and send trust signals to search engines.",
                    "recommended_solution": "Submit business details with exact canonical NAP to these authoritative directories.",
                    "action_type": "submit_citations",
                    "affected_url": pages[0].get("url", "") if pages else "",
                    "template_slug": "citation-nap-correction-task"
                })

        # =====================================================================
        # Cross-Module Bridge 3: Reviews & Reputation
        # =====================================================================
        if review_context:
            unanswered_count = review_context.get("unanswered_count", 0)
            avg_rating = review_context.get("average_rating", 0.0)
            total_reviews = review_context.get("total_reviews", 0)

            if unanswered_count > 0:
                warning_count += 1
                issues.append({
                    "category": "Reviews & Reputation",
                    "severity": IssueSeverity.WARNING.value,
                    "title": f"{unanswered_count} Unanswered Customer Reviews",
                    "evidence": f"{unanswered_count} Google reviews have not received a response.",
                    "why_it_matters": "Google officially states that responding to customer reviews improves local ranking visibility and consumer trust.",
                    "recommended_solution": "Apply the 'Positive Review Response' or 'Negative Review De-escalation' template to reply promptly.",
                    "action_type": "reply_reviews",
                    "affected_url": pages[0].get("url", "") if pages else "",
                    "template_slug": "positive-review-response"
                })

            if total_reviews > 0 and avg_rating < 4.4:
                warning_count += 1
                issues.append({
                    "category": "Reviews & Reputation",
                    "severity": IssueSeverity.WARNING.value,
                    "title": f"Average Review Rating Below 4.4★ ({avg_rating}★)",
                    "evidence": f"Current average rating across {total_reviews} reviews is {avg_rating}★.",
                    "why_it_matters": "A rating under 4.4★ negatively impacts click-through rate from the Google Local 3-Pack.",
                    "recommended_solution": "Implement an automated review request campaign targeting recent satisfied customers.",
                    "action_type": "request_reviews",
                    "affected_url": pages[0].get("url", "") if pages else "",
                    "template_slug": "positive-review-response"
                })

        # =====================================================================
        # Cross-Module Bridge 4: Local Rankings & Suburban Landing Page Gaps
        # =====================================================================
        if keyword_context:
            all_urls_text = " ".join([p.get("url", "") + " " + (p.get("title") or "") for p in pages]).lower()
            uncovered_suburbs = set()

            for kw in keyword_context:
                kw_text = kw.get("keyword", "").lower()
                suburb_match = re.search(r"(?:in|near|at)\s+([a-zA-Z\s]+)$", kw_text)
                if suburb_match:
                    suburb = suburb_match.group(1).strip()
                    if suburb and suburb not in all_urls_text and len(suburb) > 2:
                        uncovered_suburbs.add(suburb.title())

            if uncovered_suburbs:
                opportunity_count += 1
                suburb_list = ", ".join(list(uncovered_suburbs)[:3])
                issues.append({
                    "category": "Local Content Signals",
                    "severity": IssueSeverity.OPPORTUNITY.value,
                    "title": f"Missing Dedicated Suburban Landing Pages ({suburb_list})",
                    "evidence": f"Tracked target keywords reference suburbs ({suburb_list}) with no dedicated location landing page.",
                    "why_it_matters": "Dedicated suburb landing pages rank significantly higher for hyper-local queries than generic homepage listings.",
                    "recommended_solution": "Use the 'Suburban Location Landing Page Blueprint' to create dedicated service pages for each suburb.",
                    "action_type": "create_landing_page",
                    "affected_url": pages[0].get("url", "") if pages else "",
                    "template_slug": "location-landing-page-blueprint"
                })

        # =====================================================================
        # Calculate Evidence-Based Local SEO Pillar Scores & Overall Score
        # =====================================================================
        # 1. Crawl Health: based strictly on status codes and critical page crawl failures
        crawl_score = max(0, min(100, 100 - (critical_count * 20)))

        # 2. On-Page Content: based on title, h1, body content, and NAP presence
        onpage_score = max(0, min(100, 100 - (warning_count * 10)))

        # 3. Schema Structured Data: based on detected JSON-LD LocalBusiness markup
        schema_score = 100 if has_valid_local_schema else 0

        # 4. GBP Alignment: calculated only if GBP account is linked and context available
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

        # 5. Citations & NAP: calculated only from actual directory citation records
        cit_score: Optional[int] = None
        if citation_context and len(citation_context) > 0:
            total_cits = len(citation_context)
            consistent_cits = sum(1 for c in citation_context if c.get("nap_status") in ("consistent", "match") and c.get("status") in ("listed", "active"))
            cit_score = max(0, min(100, int((consistent_cits / total_cits) * 100)))

        # 6. Reviews & Reputation: calculated only if reviews exist
        rev_score: Optional[int] = None
        if review_context and review_context.get("total_reviews", 0) > 0:
            total_r = review_context["total_reviews"]
            unanswered_r = review_context.get("unanswered_count", 0)
            avg_r = review_context.get("average_rating", 0.0)
            rating_pts = (avg_r / 5.0) * 70.0
            response_pts = ((total_r - unanswered_r) / total_r) * 30.0
            rev_score = max(0, min(100, int(rating_pts + response_pts)))

        # Composite score: dynamically normalize across measured pillars only
        pillar_weights = {
            "crawl_health": (crawl_score, 0.25),
            "onpage_content": (onpage_score, 0.25),
            "schema_structured_data": (schema_score, 0.25),
            "gbp_alignment": (gbp_score, 0.15),
            "citations_nap": (cit_score, 0.10),
            "reviews_reputation": (rev_score, 0.10)
        }

        total_weight = 0.0
        weighted_sum = 0.0
        for pillar_name, (score_val, weight) in pillar_weights.items():
            if score_val is not None:
                total_weight += weight
                weighted_sum += (score_val * weight)

        composite_score = int(weighted_sum / total_weight) if total_weight > 0 else 0

        return {
            "score": composite_score,
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
            "issues": issues
        }

import json
import re
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple, Set

# -----------------------------------------------------------------------------
# Tier 1 & Industry Types Registry
# -----------------------------------------------------------------------------
TIER_1_SCHEMAS = [
    "Organization",
    "LocalBusiness",
    "WebSite",
    "WebPage",
    "BreadcrumbList",
    "Service",
    "Product",
    "Article",
    "BlogPosting",
    "Person",
    "Review",
    "AggregateRating",
    "Offer",
    "FAQPage",
    "Event",
    "JobPosting",
    "ImageObject",
    "VideoObject",
]

INDUSTRY_SCHEMAS = [
    "Restaurant",
    "Hotel",
    "Dentist",
    "MedicalClinic",
    "RealEstateAgent",
    "EducationalOrganization",
    "Course",
    "SoftwareApplication",
    "Recipe",
    "TouristAttraction",
    "Electrician",
    "Plumber",
    "HVACBusiness",
    "LegalService",
    "AutomotiveBusiness",
    "Store",
    "ProfessionalService",
    "GeneralContractor",
    "HealthAndBeautyBusiness",
    "FinancialService",
]

PAGE_TYPES = [
    "Homepage",
    "About",
    "Contact",
    "Service",
    "Service Location",
    "Product",
    "Blog Article",
    "Blog Listing",
    "FAQ",
    "Team/Profile",
    "Pricing",
    "Booking",
    "Menu",
    "Review/Testimonial",
    "Career/Job",
    "Other",
]

def _normalize_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("61") and len(digits) > 9:
        digits = digits[2:]
    elif digits.startswith("1") and len(digits) > 10:
        digits = digits[1:]
    if digits.startswith("0"):
        digits = digits[1:]
    return digits

class SchemaIntelligenceEngine:
    """
    Intelligent Schema.org Analysis, Extraction, Applicability, Validation,
    Quality Scoring, and Safe Generator Engine for LocalLift.
    """

    # -------------------------------------------------------------------------
    # 1. Page Type Detection
    # -------------------------------------------------------------------------
    @classmethod
    def detect_page_type(
        cls,
        url: str,
        title: Optional[str] = None,
        h1: Optional[str] = None,
        h2_list: Optional[List[str]] = None,
        body_text: Optional[str] = None,
        existing_schemas: Optional[List[str]] = None,
        has_map: bool = False
    ) -> Dict[str, Any]:
        url_lower = url.lower()
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.rstrip("/").lower()
        title_lower = (title or "").lower()
        h1_lower = (h1 or "").lower()
        h2_combined = " ".join(h2_list or []).lower()
        body_lower = (body_text or "").lower()[:2000]
        schemas_set = set(existing_schemas or [])

        reasons = []
        scores: Dict[str, int] = {pt: 0 for pt in PAGE_TYPES}

        # 1. Homepage Signals
        if path == "" or path == "/" or path in ["/index.html", "/home"]:
            scores["Homepage"] += 80
            reasons.append("Root URL or homepage path detected")
        if "home" in title_lower and len(path) <= 1:
            scores["Homepage"] += 20

        # 2. Contact Signals
        if any(w in path for w in ["contact", "get-in-touch", "reach-us", "find-us"]):
            scores["Contact"] += 60
            reasons.append("URL contains contact path keyword")
        if any(w in title_lower or w in h1_lower for w in ["contact", "get in touch", "call us", "our location"]):
            scores["Contact"] += 35
            reasons.append("Title/H1 indicates contact or business location")
        if has_map or "google.com/maps" in body_lower:
            scores["Contact"] += 15

        # 3. Service & Service Location Signals
        if any(w in path for w in ["/services", "/service", "/our-services", "/what-we-do"]):
            scores["Service"] += 50
            reasons.append("URL is within services hierarchy")
        if re.search(r"/(electrician|plumber|hvac|roofing|cleaning|locksmith|dentist|lawyer|repair|installation)-in-", path):
            scores["Service Location"] += 70
            reasons.append("Service + Suburb location page pattern in URL")
        elif "service" in path and any(loc in path for loc in ["brisbane", "logan", "sydney", "melbourne", "london", "ny", "austin"]):
            scores["Service Location"] += 55
            reasons.append("Service combined with city/suburb target in URL")
        if any(w in h1_lower for w in ["services", "repairs", "installation", "maintenance", "emergency", "solutions"]):
            scores["Service"] += 30
            reasons.append("H1 describes core commercial service offering")

        # 4. About & Team Signals
        if any(w in path for w in ["about", "our-story", "who-we-are", "company", "mission"]):
            scores["About"] += 60
            reasons.append("URL contains about/company pattern")
        if any(w in path for w in ["team", "staff", "doctors", "practitioners", "leadership", "founder"]):
            scores["Team/Profile"] += 65
            reasons.append("URL indicates team or staff directory")
        if any(w in title_lower or w in h1_lower for w in ["about us", "our story", "meet the team"]):
            scores["About"] += 30

        # 5. Blog / Article Signals
        if any(w in path for w in ["/blog/", "/news/", "/article/", "/posts/", "/insights/"]):
            if len(path.split("/")) > 2:
                scores["Blog Article"] += 70
                reasons.append("Individual blog post URL slug structure")
            else:
                scores["Blog Listing"] += 65
                reasons.append("Blog directory or news index URL structure")
        if "Article" in schemas_set or "BlogPosting" in schemas_set:
            scores["Blog Article"] += 40
            reasons.append("Existing BlogPosting/Article schema markup detected")

        # 6. Product Signals
        if any(w in path for w in ["/product/", "/products/", "/shop/", "/item/", "/buy/"]):
            scores["Product"] += 60
            reasons.append("E-commerce product path detected")
        if "Product" in schemas_set:
            scores["Product"] += 45

        # 7. FAQ Signals
        if any(w in path for w in ["faq", "frequently-asked-questions", "help-center", "questions"]):
            scores["FAQ"] += 70
            reasons.append("URL indicates dedicated FAQ resource")
        if "FAQPage" in schemas_set:
            scores["FAQ"] += 45
            reasons.append("FAQPage schema present on page")

        # 8. Pricing / Booking / Menu / Careers / Reviews
        if any(w in path for w in ["pricing", "rates", "cost", "plans"]):
            scores["Pricing"] += 60
        if any(w in path for w in ["book", "appointment", "schedule", "reserve"]):
            scores["Booking"] += 60
        if any(w in path for w in ["menu", "food", "drinks", "dining"]):
            scores["Menu"] += 60
        if any(w in path for w in ["reviews", "testimonials", "feedback", "case-studies"]):
            scores["Review/Testimonial"] += 60
        if any(w in path for w in ["careers", "jobs", "hiring", "work-with-us", "vacancies"]):
            scores["Career/Job"] += 60

        best_type = "Other"
        max_score = 0
        for pt, sc in scores.items():
            if sc > max_score:
                max_score = sc
                best_type = pt

        confidence = min(98, max(45, max_score)) if max_score > 0 else 40
        if not reasons:
            reasons.append("Classified based on general page structure and content keywords")

        return {
            "page_type": best_type,
            "confidence": confidence,
            "classification_reasons": reasons[:4]
        }

    # -------------------------------------------------------------------------
    # 2. Business Type Detection
    # -------------------------------------------------------------------------
    @classmethod
    def detect_business_type(
        cls,
        pages_data: List[Dict[str, Any]],
        project_category: Optional[str] = None,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        combined_text = ""
        schemas_found = set()
        for p in pages_data[:5]:
            combined_text += f" {p.get('title', '')} {p.get('h1', '')} {' '.join(p.get('h2_list', []))} {p.get('url', '')}"
            for st in p.get("schema_types", []):
                schemas_found.add(st)

        text_lower = (combined_text + " " + (project_category or "") + " " + (project_name or "")).lower()

        evidence = []
        type_scores: Dict[str, int] = {}

        type_keywords = {
            "Electrician": ["electrician", "electrical", "wiring", "switchboard", "ev charger", "emergency electrician"],
            "Plumber": ["plumber", "plumbing", "drain", "pipe", "hot water", "leak", "blocked drain"],
            "HVACBusiness": ["hvac", "air conditioning", "heating", "air con", "ventilation", "furnace", "duct"],
            "Dentist": ["dentist", "dental", "teeth", "orthodontist", "cosmetic dentistry", "dental clinic", "smile"],
            "MedicalClinic": ["medical clinic", "doctor", "physician", "health care", "general practice", "clinic", "patient"],
            "LegalService": ["attorney", "lawyer", "law firm", "legal", "litigation", "solicitor", "barrister"],
            "RealEstateAgent": ["real estate", "realtor", "property for sale", "rental property", "property management", "broker"],
            "Restaurant": ["restaurant", "dining", "menu", "cuisine", "bistro", "cafe", "takeaway", "pizza", "reservation"],
            "Hotel": ["hotel", "motel", "resort", "inn", "accommodation", "check-in", "rooms & suites"],
            "AutomotiveBusiness": ["auto repair", "mechanic", "car repair", "tire service", "brake repair", "car service"],
            "SoftwareApplication": ["saas", "software", "api", "app", "cloud platform", "developer", "analytics platform"],
            "Store": ["shop", "store", "buy online", "ecommerce", "cart", "products", "checkout"],
            "FinancialService": ["financial advisor", "accounting", "tax return", "bookkeeping", "cpa", "wealth management"],
            "EducationalOrganization": ["school", "college", "university", "academy", "training institute", "courses"],
        }

        for btype, kws in type_keywords.items():
            matched_kws = [kw for kw in kws if kw in text_lower]
            if matched_kws:
                type_scores[btype] = len(matched_kws) * 20
                if btype in schemas_found:
                    type_scores[btype] += 30

        # Check existing schemas for direct match
        for s in schemas_found:
            if s in type_keywords:
                type_scores[s] = type_scores.get(s, 0) + 40
                evidence.append(f"Existing {s} schema entity detected")

        if project_category:
            for btype in type_keywords:
                if btype.lower() in project_category.lower() or project_category.lower() in btype.lower():
                    type_scores[btype] = type_scores.get(btype, 0) + 35
                    evidence.append(f"Project category '{project_category}' matches {btype}")

        if type_scores:
            best_type = max(type_scores, key=type_scores.get)
            conf = min(95, max(50, type_scores[best_type]))
            evidence.append(f"Detected relevant keywords for {best_type}")
            return {
                "business_type": best_type,
                "confidence": conf,
                "evidence": evidence[:4]
            }

        return {
            "business_type": "LocalBusiness",
            "confidence": 60,
            "evidence": ["Defaulted to generic LocalBusiness entity based on local service indicators"]
        }

    # -------------------------------------------------------------------------
    # 3. Schema Extraction (JSON-LD, Microdata, RDFa)
    # -------------------------------------------------------------------------
    @classmethod
    def extract_structured_data(cls, soup: Any, url: str) -> Dict[str, Any]:
        json_ld_schemas = []
        raw_entities = []
        schema_types = []
        parse_errors = []
        formats_detected = set()

        # A. JSON-LD Extraction
        for script in soup.find_all("script", type="application/ld+json"):
            formats_detected.add("JSON-LD")
            raw_text = script.string or ""
            if not raw_text.strip():
                continue
            try:
                data = json.loads(raw_text)
                json_ld_schemas.append(data)
                cls._flatten_entities(data, raw_entities, source="JSON-LD")
            except Exception as e:
                parse_errors.append(f"JSON-LD syntax error in script tag: {str(e)[:80]}")

        # B. Microdata Extraction (Basic detection)
        microdata_items = soup.find_all(attrs={"itemscope": True})
        if microdata_items:
            formats_detected.add("Microdata")
            for item in microdata_items:
                item_type = item.get("itemtype", "")
                if item_type:
                    type_name = item_type.split("/")[-1].strip()
                    if type_name:
                        raw_entities.append({
                            "@type": type_name,
                            "source": "Microdata",
                            "raw": {"@type": type_name, "itemtype": item_type}
                        })

        # C. RDFa Extraction
        rdfa_items = soup.find_all(attrs={"typeof": True})
        if rdfa_items:
            formats_detected.add("RDFa")
            for item in rdfa_items:
                type_name = item.get("typeof", "").split(":")[-1].split("/")[-1].strip()
                if type_name:
                    raw_entities.append({
                        "@type": type_name,
                        "source": "RDFa",
                        "raw": {"@type": type_name}
                    })

        for ent in raw_entities:
            t = ent.get("@type")
            if isinstance(t, str) and t not in schema_types:
                schema_types.append(t)
            elif isinstance(t, list):
                for sub_t in t:
                    if isinstance(sub_t, str) and sub_t not in schema_types:
                        schema_types.append(sub_t)

        return {
            "json_ld_schemas": json_ld_schemas,
            "schema_entities": raw_entities,
            "schema_types": schema_types,
            "schema_formats": list(formats_detected),
            "schema_count": len(raw_entities),
            "schema_parse_errors": parse_errors
        }

    @classmethod
    def _flatten_entities(cls, obj: Any, out_list: List[Dict[str, Any]], source: str = "JSON-LD"):
        if isinstance(obj, dict):
            if "@graph" in obj and isinstance(obj["@graph"], list):
                for g_item in obj["@graph"]:
                    cls._flatten_entities(g_item, out_list, source=source)
            elif "@type" in obj:
                out_list.append({
                    "@type": obj["@type"],
                    "@id": obj.get("@id"),
                    "source": source,
                    "raw": obj
                })
                # Check nested children
                for k, v in obj.items():
                    if k not in ["@type", "@id", "@context"] and isinstance(v, (dict, list)):
                        cls._flatten_entities(v, out_list, source=source)
        elif isinstance(obj, list):
            for item in obj:
                cls._flatten_entities(item, out_list, source=source)

    # -------------------------------------------------------------------------
    # 4. Applicability Engine
    # -------------------------------------------------------------------------
    @classmethod
    def evaluate_applicability(
        cls,
        page_type: str,
        business_type: str,
        has_breadcrumbs: bool = True,
        has_reviews: bool = False,
        has_faq_content: bool = False,
        has_videos: bool = False,
        has_images: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        Determines applicability for all 18 Tier 1 schemas and industry types.
        Returns mapping: schema_type -> { status: "Applicable" | "Highly Applicable" | "Potentially Applicable" | "Not Applicable", reason: str }
        """
        results = {}

        # 1. WebSite
        if page_type == "Homepage":
            results["WebSite"] = {
                "applicability": "Highly Applicable",
                "reason": "Root WebSite entity should be declared on the homepage to establish the search presence."
            }
        else:
            results["WebSite"] = {
                "applicability": "Potentially Applicable",
                "reason": "Referenced as isPartOf entity for secondary site hierarchy."
            }

        # 2. WebPage
        results["WebPage"] = {
            "applicability": "Highly Applicable",
            "reason": "Every crawled indexable HTML document should declare its WebPage structured context."
        }

        # 3. Organization
        if page_type in ["Homepage", "About", "Contact"]:
            results["Organization"] = {
                "applicability": "Highly Applicable",
                "reason": "Core business identity and legal parent entity for brand recognition."
            }
        else:
            results["Organization"] = {
                "applicability": "Potentially Applicable",
                "reason": "Referenced as publisher or provider of content and services."
            }

        # 4. LocalBusiness
        if business_type in ["LocalBusiness", "Electrician", "Plumber", "HVACBusiness", "Dentist", "MedicalClinic", "Restaurant", "RealEstateAgent", "AutomotiveBusiness", "Store", "ProfessionalService", "GeneralContractor"]:
            if page_type in ["Homepage", "Contact", "Service Location", "About"]:
                results["LocalBusiness"] = {
                    "applicability": "Highly Applicable",
                    "reason": "Physical business presence requiring address, telephone, hours, and geo coordinates."
                }
            elif page_type == "Service":
                results["LocalBusiness"] = {
                    "applicability": "Applicable",
                    "reason": "Local business provider for the offered service."
                }
            else:
                results["LocalBusiness"] = {
                    "applicability": "Potentially Applicable",
                    "reason": "Local business entity linking back to parent brand."
                }
        else:
            results["LocalBusiness"] = {
                "applicability": "Not Applicable",
                "reason": f"Business is classified as pure digital/non-local {business_type}."
            }

        # 5. BreadcrumbList
        if page_type != "Homepage" or has_breadcrumbs:
            results["BreadcrumbList"] = {
                "applicability": "Highly Applicable",
                "reason": "Enables Google Breadcrumb rich snippets in search result URLs."
            }
        else:
            results["BreadcrumbList"] = {
                "applicability": "Potentially Applicable",
                "reason": "Optional on top-level root homepage."
            }

        # 6. Service
        if page_type in ["Service", "Service Location", "Homepage"]:
            results["Service"] = {
                "applicability": "Highly Applicable",
                "reason": "Page visibly details commercial service offerings for local customers."
            }
        else:
            results["Service"] = {
                "applicability": "Not Applicable",
                "reason": f"Page type '{page_type}' is informational/non-service content."
            }

        # 7. Product & 8. Offer
        if page_type in ["Product", "Pricing"]:
            results["Product"] = {
                "applicability": "Highly Applicable",
                "reason": "Dedicated product catalog item with commercial purchasing intent."
            }
            results["Offer"] = {
                "applicability": "Highly Applicable",
                "reason": "Price and availability details for products/services."
            }
        elif page_type in ["Service", "Service Location"]:
            results["Product"] = {
                "applicability": "Not Applicable",
                "reason": "Services should use Schema.org/Service rather than Product."
            }
            results["Offer"] = {
                "applicability": "Potentially Applicable",
                "reason": "Optional priceRange or fixed-rate service quotation offers."
            }
        else:
            results["Product"] = {
                "applicability": "Not Applicable",
                "reason": f"No e-commerce product catalog detected on {page_type} page."
            }
            results["Offer"] = {
                "applicability": "Not Applicable",
                "reason": "No commercial sales offer context on this page."
            }

        # 9. Article & 10. BlogPosting
        if page_type == "Blog Article":
            results["BlogPosting"] = {
                "applicability": "Highly Applicable",
                "reason": "Editorial or educational blog article with author and publish dates."
            }
            results["Article"] = {
                "applicability": "Applicable",
                "reason": "Alternative parent type for editorial content."
            }
        else:
            results["BlogPosting"] = {
                "applicability": "Not Applicable",
                "reason": f"Page type '{page_type}' is transactional/navigational rather than editorial."
            }
            results["Article"] = {
                "applicability": "Not Applicable",
                "reason": "Not an editorial article."
            }

        # 11. Person
        if page_type in ["About", "Team/Profile", "Blog Article"]:
            results["Person"] = {
                "applicability": "Applicable",
                "reason": "Staff member, practitioner, author, or business founder entity."
            }
        else:
            results["Person"] = {
                "applicability": "Not Applicable",
                "reason": "No primary individual profile focus on this page."
            }

        # 12. Review & 13. AggregateRating
        if has_reviews or page_type in ["Homepage", "Review/Testimonial", "Service Location"]:
            results["AggregateRating"] = {
                "applicability": "Applicable",
                "reason": "Verified Google/platform star ratings and review totals for social proof."
            }
            results["Review"] = {
                "applicability": "Potentially Applicable",
                "reason": "Individual authentic customer testimonials."
            }
        else:
            results["AggregateRating"] = {
                "applicability": "Not Applicable",
                "reason": "No customer review ratings present on this page."
            }
            results["Review"] = {
                "applicability": "Not Applicable",
                "reason": "No individual review quotations."
            }

        # 14. FAQPage
        if has_faq_content or page_type == "FAQ":
            results["FAQPage"] = {
                "applicability": "Highly Applicable",
                "reason": "Visible Question and Answer pairs present on the page."
            }
        else:
            results["FAQPage"] = {
                "applicability": "Not Applicable",
                "reason": "No visible Q&A accordion or FAQ content detected on page."
            }

        # 15. Event
        if page_type == "Event":
            results["Event"] = {
                "applicability": "Highly Applicable",
                "reason": "Live scheduled event with location and dates."
            }
        else:
            results["Event"] = {
                "applicability": "Not Applicable",
                "reason": "Page is not a scheduled event listing."
            }

        # 16. JobPosting
        if page_type == "Career/Job":
            results["JobPosting"] = {
                "applicability": "Highly Applicable",
                "reason": "Active employment vacancy with requirements and compensation."
            }
        else:
            results["JobPosting"] = {
                "applicability": "Not Applicable",
                "reason": "Not a career/job listing page."
            }

        # 17. ImageObject & 18. VideoObject
        results["ImageObject"] = {
            "applicability": "Applicable" if has_images else "Not Applicable",
            "reason": "Featured primary image or brand logo markup."
        }
        results["VideoObject"] = {
            "applicability": "Applicable" if has_videos else "Not Applicable",
            "reason": "Embedded video presentation with thumbnail and duration."
        }

        # Industry specific
        if business_type in INDUSTRY_SCHEMAS:
            if page_type in ["Homepage", "Contact", "Service Location", "About"]:
                results[business_type] = {
                    "applicability": "Highly Applicable",
                    "reason": f"Specialized Schema.org industry type for {business_type}."
                }

        return results

    # -------------------------------------------------------------------------
    # 5. Deep Property & NAP Consistency Validator
    # -------------------------------------------------------------------------
    @classmethod
    def validate_entity(
        cls,
        entity: Dict[str, Any],
        project_context: Optional[Dict[str, Any]] = None,
        page_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        st = entity.get("@type", "Unknown")
        raw = entity.get("raw", {})
        st_str = st if isinstance(st, str) else (st[0] if isinstance(st, list) else "Unknown")

        errors = []
        warnings = []
        missing_properties = []
        property_results = []
        nap_match_status = "Not Applicable"

        # Check @context
        if "@context" in raw:
            ctx = str(raw["@context"])
            if "schema.org" not in ctx.lower():
                errors.append("Invalid @context: must reference 'https://schema.org'")
            else:
                property_results.append({"property": "@context", "value": ctx, "status": "Verified", "confidence": 100})
        
        # Check @id
        entity_id = raw.get("@id")
        if entity_id:
            if not isinstance(entity_id, str) or not entity_id.startswith("http"):
                warnings.append("Entity @id should be a stable absolute URI (e.g. 'https://example.com/#localbusiness')")
            property_results.append({"property": "@id", "value": entity_id, "status": "Verified", "confidence": 95})

        canonical_phone = (project_context or {}).get("phone")
        canonical_name = (project_context or {}).get("name")
        canonical_domain = (project_context or {}).get("domain")

        # ---------------------------------------------------------------------
        # LocalBusiness / Specialized Subtypes
        # ---------------------------------------------------------------------
        is_local_biz = (
            st_str in ["LocalBusiness", "Organization"] or
            any(sub in st_str for sub in ["Electrician", "Plumber", "HVAC", "Dentist", "Medical", "Clinic", "Restaurant", "Store", "Legal", "Automotive", "Contractor", "Service"])
        )

        if is_local_biz:
            # Name
            name = raw.get("name")
            if not name:
                errors.append("Missing critical property: 'name'")
                missing_properties.append("name (Critical)")
            else:
                property_results.append({"property": "name", "value": name, "status": "Verified", "confidence": 98})
                if canonical_name and canonical_name.lower() not in name.lower() and name.lower() not in canonical_name.lower():
                    warnings.append(f"Business name '{name}' differs from project name '{canonical_name}'")

            # URL
            url = raw.get("url")
            if not url:
                warnings.append("Missing recommended property: 'url'")
                missing_properties.append("url (Recommended)")
            else:
                property_results.append({"property": "url", "value": url, "status": "Verified", "confidence": 98})

            # Telephone & NAP Check
            tel = raw.get("telephone")
            if not tel:
                warnings.append("Missing recommended property: 'telephone'")
                missing_properties.append("telephone (Recommended)")
            else:
                property_results.append({"property": "telephone", "value": tel, "status": "Verified", "confidence": 98})
                norm_schema_phone = _normalize_phone(tel)
                norm_canon_phone = _normalize_phone(canonical_phone)
                if norm_canon_phone:
                    if norm_canon_phone in norm_schema_phone or norm_schema_phone in norm_canon_phone:
                        nap_match_status = "Consistent"
                    else:
                        nap_match_status = "Mismatch"
                        errors.append(f"NAP Phone Mismatch: Schema phone '{tel}' differs from canonical '{canonical_phone}'")

            # PostalAddress
            addr = raw.get("address")
            if not addr:
                warnings.append("Missing recommended property: 'address' (PostalAddress)")
                missing_properties.append("address (Recommended)")
            elif isinstance(addr, dict):
                has_street = bool(addr.get("streetAddress"))
                has_locality = bool(addr.get("addressLocality"))
                has_country = bool(addr.get("addressCountry"))
                if not (has_street or has_locality):
                    errors.append("PostalAddress must include streetAddress or addressLocality")
                property_results.append({
                    "property": "address",
                    "value": f"{addr.get('streetAddress', '')}, {addr.get('addressLocality', '')} {addr.get('postalCode', '')} {addr.get('addressCountry', '')}".strip(" ,"),
                    "status": "Verified",
                    "confidence": 95
                })
            else:
                warnings.append("Property 'address' should be a structured PostalAddress object")

            # Geo Coordinates (Lat/Long)
            geo = raw.get("geo")
            if not geo:
                missing_properties.append("geo (Optional / Context)")
            elif isinstance(geo, dict):
                lat = geo.get("latitude")
                lng = geo.get("longitude")
                if lat is None or lng is None:
                    warnings.append("GeoCoordinates object missing latitude or longitude")
                else:
                    try:
                        f_lat, f_lng = float(lat), float(lng)
                        if not (-90.0 <= f_lat <= 90.0 and -180.0 <= f_lng <= 180.0):
                            errors.append(f"Invalid GeoCoordinates: lat {f_lat}, lng {f_lng} out of range")
                        elif f_lat == 0.0 and f_lng == 0.0:
                            warnings.append("Suspicious GeoCoordinates: lat/lng is (0, 0)")
                        else:
                            property_results.append({"property": "geo", "value": f"({f_lat}, {f_lng})", "status": "Verified", "confidence": 98})
                    except (ValueError, TypeError):
                        errors.append("GeoCoordinates latitude and longitude must be valid numeric values")

            # Opening Hours
            hours = raw.get("openingHoursSpecification") or raw.get("openingHours")
            if not hours:
                missing_properties.append("openingHoursSpecification (Recommended)")
            else:
                property_results.append({"property": "openingHoursSpecification", "value": "Defined", "status": "Verified", "confidence": 90})

            # Social Profiles / sameAs
            same_as = raw.get("sameAs")
            if same_as:
                property_results.append({"property": "sameAs", "value": same_as if isinstance(same_as, str) else f"{len(same_as)} profiles", "status": "Verified", "confidence": 95})

        # ---------------------------------------------------------------------
        # WebSite
        # ---------------------------------------------------------------------
        elif st_str == "WebSite":
            if not raw.get("name"):
                warnings.append("WebSite entity missing 'name'")
                missing_properties.append("name (Recommended)")
            if not raw.get("url"):
                warnings.append("WebSite entity missing 'url'")
                missing_properties.append("url (Recommended)")
            if not raw.get("publisher"):
                missing_properties.append("publisher (Recommended)")

        # ---------------------------------------------------------------------
        # Service
        # ---------------------------------------------------------------------
        elif st_str == "Service":
            if not raw.get("name"):
                errors.append("Service entity missing 'name'")
                missing_properties.append("name (Critical)")
            if not raw.get("provider"):
                missing_properties.append("provider (Recommended)")

        # ---------------------------------------------------------------------
        # BreadcrumbList
        # ---------------------------------------------------------------------
        elif st_str == "BreadcrumbList":
            items = raw.get("itemListElement")
            if not items or not isinstance(items, list):
                errors.append("BreadcrumbList missing 'itemListElement' array")
                missing_properties.append("itemListElement (Critical)")
            else:
                property_results.append({"property": "itemListElement", "value": f"{len(items)} items", "status": "Verified", "confidence": 98})

        # ---------------------------------------------------------------------
        # FAQPage
        # ---------------------------------------------------------------------
        elif st_str == "FAQPage":
            main_entity = raw.get("mainEntity")
            if not main_entity or not isinstance(main_entity, list):
                errors.append("FAQPage missing 'mainEntity' Question/Answer array")
                missing_properties.append("mainEntity (Critical)")
            else:
                property_results.append({"property": "mainEntity", "value": f"{len(main_entity)} Q&A pairs", "status": "Verified", "confidence": 98})

        is_valid = len(errors) == 0

        return {
            "schema_type": st_str,
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "missing_properties": missing_properties,
            "property_results": property_results,
            "nap_match_status": nap_match_status
        }

    # -------------------------------------------------------------------------
    # 6. Quality Scoring Engine
    # -------------------------------------------------------------------------
    @classmethod
    def calculate_quality_score(
        cls,
        page_analyses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculates explainable 100-point Schema Health Score:
        - Schema Detection:       20 pts
        - Validity:               20 pts
        - Property Completeness:  20 pts
        - Data Accuracy & NAP:    20 pts
        - Entity Relationships:   10 pts
        - Page Applicability:     10 pts
        """
        if not page_analyses:
            return {
                "health_score": 0,
                "breakdown": {
                    "detection": 0,
                    "validity": 0,
                    "completeness": 0,
                    "data_accuracy": 0,
                    "relationships": 0,
                    "applicability": 0,
                },
                "deductions": ["No pages analyzed or crawled yet"]
            }

        total_pages = len(page_analyses)
        pages_with_schema = sum(1 for p in page_analyses if p.get("detected_types"))
        detection_score = int((pages_with_schema / total_pages) * 20)

        total_schemas = sum(len(p.get("detected_types", [])) for p in page_analyses)
        invalid_schemas = sum(len(p.get("errors", [])) for p in page_analyses)
        validity_score = 20 if total_schemas == 0 else max(0, int(20 - (invalid_schemas * 5)))

        warnings_count = sum(len(p.get("warnings", [])) for p in page_analyses)
        completeness_score = max(5, int(20 - (warnings_count * 2)))

        has_nap_mismatch = any(p.get("nap_status") == "Mismatch" for p in page_analyses)
        data_accuracy_score = 10 if has_nap_mismatch else 20

        # Check entity relationships (@graph / isPartOf / mainEntity)
        has_linked_graph = any("WebSite" in p.get("detected_types", []) and "LocalBusiness" in p.get("detected_types", []) for p in page_analyses)
        relationships_score = 10 if has_linked_graph else 6

        # Check applicability match
        applicability_score = 10
        for p in page_analyses:
            if "Product" in p.get("detected_types", []) and p.get("page_type") in ["Service", "Service Location"]:
                applicability_score = max(4, applicability_score - 3)

        total_score = detection_score + validity_score + completeness_score + data_accuracy_score + relationships_score + applicability_score
        total_score = min(100, max(0, total_score))

        deductions = []
        if pages_with_schema < total_pages:
            deductions.append(f"{total_pages - pages_with_schema} pages missing Schema.org structured data (-{20 - detection_score} pts)")
        if invalid_schemas > 0:
            deductions.append(f"{invalid_schemas} schema validation errors detected (-{20 - validity_score} pts)")
        if warnings_count > 0:
            deductions.append(f"{warnings_count} missing recommended properties/warnings (-{20 - completeness_score} pts)")
        if has_nap_mismatch:
            deductions.append("On-page schema telephone does not match canonical project number (-10 pts)")
        if not has_linked_graph:
            deductions.append("Entities are isolated; recommended to connect via @graph (@id linking) (-4 pts)")

        return {
            "health_score": total_score,
            "breakdown": {
                "detection": detection_score,
                "validity": validity_score,
                "completeness": completeness_score,
                "data_accuracy": data_accuracy_score,
                "relationships": relationships_score,
                "applicability": applicability_score
            },
            "deductions": deductions
        }

    # -------------------------------------------------------------------------
    # 7. Recommendations Engine
    # -------------------------------------------------------------------------
    @classmethod
    def generate_recommendations(
        cls,
        page_analyses: List[Dict[str, Any]],
        project_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        recs = []

        # 1. NAP Mismatches (High)
        for p in page_analyses:
            if p.get("nap_status") == "Mismatch":
                recs.append({
                    "priority": "HIGH",
                    "title": "Fix LocalBusiness Phone Number Mismatch",
                    "affected_url": p.get("url"),
                    "why": "Google Knowledge Graph cross-references phone numbers across your website, Google Maps, and citations. Discrepancies reduce local ranking trust.",
                    "evidence": f"Schema phone on {p.get('url')} does not match canonical phone {(project_context or {}).get('phone')}.",
                    "expected_improvement": "+10 Quality Score & Verified Knowledge Panel eligibility",
                    "action_type": "fix_nap",
                    "action_label": "Update Telephone Attribute"
                })

        # 2. Missing Schema on Core Pages (High/Medium)
        for p in page_analyses:
            pt = p.get("page_type")
            schemas = p.get("detected_types", [])
            if pt in ["Homepage", "Contact"] and not any(s in schemas for s in ["LocalBusiness", "Organization", "Electrician", "Plumber", "Dentist", "Restaurant"]):
                recs.append({
                    "priority": "HIGH",
                    "title": f"Add LocalBusiness / Organization Schema to {pt}",
                    "affected_url": p.get("url"),
                    "why": f"The {pt} establishes your primary local business identity, opening hours, and address for search engines.",
                    "evidence": f"No LocalBusiness entity detected on {p.get('url')}.",
                    "expected_improvement": "+15 Quality Score & Local Pack snippet eligibility",
                    "action_type": "generate_localbusiness",
                    "action_label": "Generate LocalBusiness Schema"
                })
            elif pt == "Service" and "Service" not in schemas:
                recs.append({
                    "priority": "MEDIUM",
                    "title": "Add Service Schema to Service Landing Page",
                    "affected_url": p.get("url"),
                    "why": "Service schema explicitly tells Google which commercial offering is provided on this specific page.",
                    "evidence": f"Page type is Service but missing Schema.org/Service markup.",
                    "expected_improvement": "+8 Quality Score & Service snippet eligibility",
                    "action_type": "generate_service",
                    "action_label": "Generate Service Schema"
                })
            elif pt != "Homepage" and "BreadcrumbList" not in schemas:
                recs.append({
                    "priority": "LOW",
                    "title": "Add BreadcrumbList Structured Data",
                    "affected_url": p.get("url"),
                    "why": "BreadcrumbList replaces raw search result URLs with clean, navigable category breadcrumbs in Google SERPs.",
                    "evidence": f"No BreadcrumbList schema found on {p.get('url')}.",
                    "expected_improvement": "+5 Quality Score & SERP URL breadcrumbs",
                    "action_type": "generate_breadcrumbs",
                    "action_label": "Generate BreadcrumbList"
                })

        # 3. Missing Attributes on Existing Schemas (Medium)
        for p in page_analyses:
            for w in p.get("warnings", []):
                if "openingHoursSpecification" in w:
                    recs.append({
                        "priority": "MEDIUM",
                        "title": "Add Opening Hours to LocalBusiness Schema",
                        "affected_url": p.get("url"),
                        "why": "Explicit opening hours allow Google to display 'Open now' and working schedule directly in local search cards.",
                        "evidence": f"OpeningHoursSpecification missing on {p.get('url')}.",
                        "expected_improvement": "+6 Quality Score",
                        "action_type": "add_hours",
                        "action_label": "Add Operating Schedule"
                    })
                elif "geo" in w or "GeoCoordinates" in w:
                    recs.append({
                        "priority": "MEDIUM",
                        "title": "Add Precise Geographic Coordinates (Lat/Long)",
                        "affected_url": p.get("url"),
                        "why": "GeoCoordinates pin your business location to the exact map point for Google Maps verification.",
                        "evidence": f"Geo coordinates missing on {p.get('url')}.",
                        "expected_improvement": "+6 Quality Score",
                        "action_type": "add_geo",
                        "action_label": "Add GeoCoordinates"
                    })

        # Deduplicate recommendations by title + affected_url
        unique_recs = []
        seen_keys = set()
        for r in recs:
            key = (r["title"], r.get("affected_url", ""))
            if key not in seen_keys:
                seen_keys.add(key)
                unique_recs.append(r)

        return unique_recs[:10]

    # -------------------------------------------------------------------------
    # 8. Safe Data-Driven Schema Generator
    # -------------------------------------------------------------------------
    @classmethod
    def generate_safe_schema(
        cls,
        business_type: str = "LocalBusiness",
        business_name: str = "",
        url: str = "",
        phone: Optional[str] = None,
        street_address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        postal_code: Optional[str] = None,
        country: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        opening_hours: Optional[List[Dict[str, Any]]] = None,
        price_range: Optional[str] = None,
        social_profiles: Optional[List[str]] = None,
        service_name: Optional[str] = None,
        service_description: Optional[str] = None,
        breadcrumbs: Optional[List[Dict[str, str]]] = None,
        include_graph: bool = True
    ) -> Dict[str, Any]:
        """
        Generates clean, verified Schema.org JSON-LD without fake defaults.
        Produces interconnected @graph structure when include_graph is True.
        """
        clean_url = url.strip().rstrip("/") if url else "https://example.com"
        parsed = urllib.parse.urlparse(clean_url)
        base_domain_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else clean_url

        org_id = f"{base_domain_url}/#organization"
        biz_id = f"{base_domain_url}/#localbusiness"
        website_id = f"{base_domain_url}/#website"
        webpage_id = f"{clean_url}/#webpage"

        entities = []

        # 1. Organization Entity
        org_entity = {
            "@type": "Organization",
            "@id": org_id,
            "name": business_name,
            "url": base_domain_url
        }
        if social_profiles:
            org_entity["sameAs"] = [s.strip() for s in social_profiles if s.strip()]
        entities.append(org_entity)

        # 2. LocalBusiness Entity
        local_biz_entity: Dict[str, Any] = {
            "@type": business_type or "LocalBusiness",
            "@id": biz_id,
            "name": business_name,
            "url": clean_url,
            "parentOrganization": {"@id": org_id}
        }
        if phone and phone.strip():
            local_biz_entity["telephone"] = phone.strip()
        if price_range and price_range.strip():
            local_biz_entity["priceRange"] = price_range.strip()

        # Structured Address
        addr_dict = {}
        if street_address and street_address.strip():
            addr_dict["streetAddress"] = street_address.strip()
        if city and city.strip():
            addr_dict["addressLocality"] = city.strip()
        if state and state.strip():
            addr_dict["addressRegion"] = state.strip()
        if postal_code and postal_code.strip():
            addr_dict["postalCode"] = postal_code.strip()
        if country and country.strip():
            addr_dict["addressCountry"] = country.strip()
        if addr_dict:
            addr_dict["@type"] = "PostalAddress"
            local_biz_entity["address"] = addr_dict

        # Geo Coordinates (Only if valid numeric values provided)
        if latitude is not None and longitude is not None:
            try:
                f_lat, f_lng = float(latitude), float(longitude)
                if -90.0 <= f_lat <= 90.0 and -180.0 <= f_lng <= 180.0 and not (f_lat == 0.0 and f_lng == 0.0):
                    local_biz_entity["geo"] = {
                        "@type": "GeoCoordinates",
                        "latitude": f_lat,
                        "longitude": f_lng
                    }
            except (ValueError, TypeError):
                pass

        # Opening Hours
        if opening_hours:
            spec_list = []
            for item in opening_hours:
                if isinstance(item, dict) and item.get("dayOfWeek") and item.get("opens") and item.get("closes"):
                    spec_list.append({
                        "@type": "OpeningHoursSpecification",
                        "dayOfWeek": item["dayOfWeek"],
                        "opens": item["opens"],
                        "closes": item["closes"]
                    })
            if spec_list:
                local_biz_entity["openingHoursSpecification"] = spec_list

        entities.append(local_biz_entity)

        # 3. WebSite Entity
        website_entity = {
            "@type": "WebSite",
            "@id": website_id,
            "url": base_domain_url,
            "name": business_name,
            "publisher": {"@id": org_id}
        }
        entities.append(website_entity)

        # 4. WebPage Entity
        webpage_entity = {
            "@type": "WebPage",
            "@id": webpage_id,
            "url": clean_url,
            "name": f"{business_name} - {service_name or 'Home'}",
            "isPartOf": {"@id": website_id},
            "about": {"@id": biz_id}
        }
        entities.append(webpage_entity)

        # 5. Service Entity (if provided)
        if service_name and service_name.strip():
            service_id = f"{clean_url}/#service"
            service_entity = {
                "@type": "Service",
                "@id": service_id,
                "name": service_name.strip(),
                "provider": {"@id": biz_id}
            }
            if service_description and service_description.strip():
                service_entity["description"] = service_description.strip()
            entities.append(service_entity)
            webpage_entity["mainEntity"] = {"@id": service_id}

        # 6. BreadcrumbList (if provided)
        if breadcrumbs:
            list_items = []
            for idx, bc in enumerate(breadcrumbs, start=1):
                list_items.append({
                    "@type": "ListItem",
                    "position": idx,
                    "name": bc.get("name", f"Step {idx}"),
                    "item": bc.get("url", clean_url)
                })
            if list_items:
                breadcrumb_id = f"{clean_url}/#breadcrumb"
                breadcrumb_entity = {
                    "@type": "BreadcrumbList",
                    "@id": breadcrumb_id,
                    "itemListElement": list_items
                }
                entities.append(breadcrumb_entity)
                webpage_entity["breadcrumb"] = {"@id": breadcrumb_id}

        if include_graph:
            final_json_obj = {
                "@context": "https://schema.org",
                "@graph": entities
            }
        else:
            final_json_obj = {
                "@context": "https://schema.org",
                **local_biz_entity
            }

        formatted_json = json.dumps(final_json_obj, indent=2)
        html_tag = f'<script type="application/ld+json">\n{formatted_json}\n</script>'

        # Run internal validator
        val_res = cls.validate_json_ld_string(formatted_json)

        return {
            "schema_type": business_type,
            "json_ld": formatted_json,
            "html_tag": html_tag,
            "entities_count": len(entities),
            "is_valid": val_res["is_valid"],
            "validation_errors": val_res["errors"],
            "validation_warnings": val_res["warnings"]
        }

    # -------------------------------------------------------------------------
    # 9. Internal Validator
    # -------------------------------------------------------------------------
    @classmethod
    def validate_json_ld_string(cls, json_str: str) -> Dict[str, Any]:
        errors = []
        warnings = []
        detected_entities = []

        if not json_str or not json_str.strip():
            return {"is_valid": False, "errors": ["Empty JSON-LD content"], "warnings": [], "entities": []}

        try:
            # Strip script tags if passed
            clean_str = re.sub(r"^\s*<script[^>]*>", "", json_str, flags=re.IGNORECASE)
            clean_str = re.sub(r"</script>\s*$", "", clean_str, flags=re.IGNORECASE).strip()

            parsed = json.loads(clean_str)
        except Exception as e:
            return {
                "is_valid": False,
                "errors": [f"JSON Syntax Error: {str(e)}"],
                "warnings": [],
                "entities": []
            }

        entities_to_check = []
        if isinstance(parsed, dict):
            if "@graph" in parsed and isinstance(parsed["@graph"], list):
                entities_to_check.extend(parsed["@graph"])
            else:
                entities_to_check.append(parsed)
        elif isinstance(parsed, list):
            entities_to_check.extend(parsed)

        for ent in entities_to_check:
            if not isinstance(ent, dict):
                continue
            st = ent.get("@type", "Unknown")
            detected_entities.append(st if isinstance(st, str) else str(st))
            res = cls.validate_entity({"@type": st, "raw": ent})
            errors.extend(res["errors"])
            warnings.extend(res["warnings"])

        return {
            "is_valid": len(errors) == 0,
            "errors": list(dict.fromkeys(errors)),
            "warnings": list(dict.fromkeys(warnings)),
            "entities": list(dict.fromkeys(detected_entities))
        }

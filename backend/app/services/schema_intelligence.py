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

SCHEMA_METADATA: Dict[str, Dict[str, Any]] = {
    "Organization": {
        "definition": "Represents an umbrella organization, parent company, or brand identity.",
        "why_it_matters": "Establishes canonical brand authority in Google Knowledge Graph and links official social profiles via sameAs.",
        "recommended_page_types": ["Homepage", "About", "Contact"],
        "required_properties": ["@type", "name", "url"],
        "recommended_properties": ["logo", "sameAs", "contactPoint", "telephone", "address"]
    },
    "LocalBusiness": {
        "definition": "Represents a physical commercial location or service-area business offering local services.",
        "why_it_matters": "Directly feeds Google Local Pack, Maps search, and voice queries with verified address, geo, phone, and hours.",
        "recommended_page_types": ["Homepage", "Contact", "Service Location", "About"],
        "required_properties": ["@type", "name", "address", "telephone"],
        "recommended_properties": ["geo", "openingHoursSpecification", "priceRange", "image", "url", "areaServed"]
    },
    "WebSite": {
        "definition": "Represents the root website entity hosting the domain's web pages.",
        "why_it_matters": "Enables Google Sitelinks Search Box and establishes the canonical domain structure.",
        "recommended_page_types": ["Homepage"],
        "required_properties": ["@type", "name", "url"],
        "recommended_properties": ["potentialAction", "publisher", "description", "inLanguage"]
    },
    "WebPage": {
        "definition": "Represents an individual crawled indexable web document on the site.",
        "why_it_matters": "Provides page-level context, breadcrumb linkage, and isPartOf relations for rich snippet indexation.",
        "recommended_page_types": ["All Pages"],
        "required_properties": ["@type", "name", "url"],
        "recommended_properties": ["description", "isPartOf", "breadcrumb", "inLanguage", "datePublished", "dateModified"]
    },
    "BreadcrumbList": {
        "definition": "Represents the navigational hierarchy leading to the current page URL.",
        "why_it_matters": "Generates clean breadcrumb navigation trail in Google search results instead of raw URLs.",
        "recommended_page_types": ["All Subpages", "Service", "Blog Article", "Product"],
        "required_properties": ["@type", "itemListElement"],
        "recommended_properties": ["numberOfItems"]
    },
    "Service": {
        "definition": "Represents a specific commercial or trade service offered by the business.",
        "why_it_matters": "Improves organic ranking for transactional service searches (e.g. 'emergency electrical repair', 'switchboard upgrade').",
        "recommended_page_types": ["Service", "Service Location", "Homepage"],
        "required_properties": ["@type", "name", "provider"],
        "recommended_properties": ["description", "areaServed", "serviceType", "offers", "termsOfService", "hasOfferCatalog"]
    },
    "Product": {
        "definition": "Represents any tangible or digital product item available for purchase or inquiry.",
        "why_it_matters": "Unlocks Google rich snippets including pricing, availability, and merchant listing badges.",
        "recommended_page_types": ["Product", "Pricing"],
        "required_properties": ["@type", "name", "offers"],
        "recommended_properties": ["image", "description", "brand", "sku", "aggregateRating", "priceRange"]
    },
    "Article": {
        "definition": "Represents an editorial article, news report, or in-depth technical resource.",
        "why_it_matters": "Qualifies content for Google News, Discover, and headline rich snippet carousels.",
        "recommended_page_types": ["Blog Article", "News"],
        "required_properties": ["@type", "headline", "author", "publisher", "datePublished"],
        "recommended_properties": ["image", "dateModified", "mainEntityOfPage", "description"]
    },
    "BlogPosting": {
        "definition": "A specialized subtype of Article specifically designating a company blog post.",
        "why_it_matters": "Clarifies editorial freshness and author expertise (E-E-A-T) for informational queries.",
        "recommended_page_types": ["Blog Article"],
        "required_properties": ["@type", "headline", "author", "datePublished"],
        "recommended_properties": ["image", "dateModified", "publisher", "articleBody", "keywords"]
    },
    "Person": {
        "definition": "Represents an individual practitioner, founder, author, or licensed team member.",
        "why_it_matters": "Crucial for Google's E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) entity linking.",
        "recommended_page_types": ["About", "Team/Profile", "Blog Article"],
        "required_properties": ["@type", "name"],
        "recommended_properties": ["jobTitle", "worksFor", "sameAs", "image", "description"]
    },
    "Review": {
        "definition": "Represents an authentic individual user or customer review testimonial.",
        "why_it_matters": "Displays verified review snippets and customer credibility directly in search results.",
        "recommended_page_types": ["Review/Testimonial", "Homepage", "Service Location"],
        "required_properties": ["@type", "author", "reviewRating", "itemReviewed"],
        "recommended_properties": ["reviewBody", "datePublished", "publisher"]
    },
    "AggregateRating": {
        "definition": "Represents the overall composite star rating and total review count for a business or service.",
        "why_it_matters": "Enables the gold star rating rich snippet under your search result listing in SERP.",
        "recommended_page_types": ["Homepage", "Service", "Service Location"],
        "required_properties": ["@type", "ratingValue", "reviewCount", "itemReviewed"],
        "recommended_properties": ["bestRating", "worstRating"]
    },
    "Offer": {
        "definition": "Specifies commercial pricing terms, warranties, and availability for services or products.",
        "why_it_matters": "Displays price range and instant booking availability in rich search snippets.",
        "recommended_page_types": ["Pricing", "Service", "Product"],
        "required_properties": ["@type", "price", "priceCurrency"],
        "recommended_properties": ["availability", "validFrom", "priceValidUntil", "url", "seller"]
    },
    "FAQPage": {
        "definition": "Represents a list of frequently asked questions and official business answers.",
        "why_it_matters": "Can earn prominent collapsible FAQ accordion rich snippets directly under search listings.",
        "recommended_page_types": ["FAQ", "Service", "Homepage"],
        "required_properties": ["@type", "mainEntity"],
        "recommended_properties": ["name", "description"]
    },
    "Event": {
        "definition": "Represents an upcoming scheduled public or private event, webinar, or community workshop.",
        "why_it_matters": "Enables interactive Google Event search card with dates, location, and ticket options.",
        "recommended_page_types": ["Event", "Workshop"],
        "required_properties": ["@type", "name", "startDate", "location"],
        "recommended_properties": ["endDate", "description", "image", "offers", "organizer", "eventStatus"]
    },
    "JobPosting": {
        "definition": "Represents an open employment vacancy or apprenticeship listing.",
        "why_it_matters": "Directly feeds Google for Jobs specialized search portal.",
        "recommended_page_types": ["Career/Job"],
        "required_properties": ["@type", "title", "description", "datePosted", "hiringOrganization", "jobLocation"],
        "recommended_properties": ["employmentType", "baseSalary", "validThrough"]
    },
    "ImageObject": {
        "definition": "Represents a high-resolution logo, showroom photo, or featured work graphic.",
        "why_it_matters": "Powers Google Images rich previews and visual search inclusion.",
        "recommended_page_types": ["All Pages", "Gallery"],
        "required_properties": ["@type", "contentUrl"],
        "recommended_properties": ["name", "description", "width", "height", "caption"]
    },
    "VideoObject": {
        "definition": "Represents an embedded video tutorial, customer case study, or company overview.",
        "why_it_matters": "Generates Video search rich results with duration badge, thumbnail, and key moments.",
        "recommended_page_types": ["Service", "Homepage", "Blog Article"],
        "required_properties": ["@type", "name", "description", "thumbnailUrl", "uploadDate"],
        "recommended_properties": ["contentUrl", "embedUrl", "duration"]
    }
}

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
        raw_script_blocks = []

        # A. JSON-LD Extraction
        for script in soup.find_all("script", type=re.compile(r"application/ld\+json", re.I)):
            formats_detected.add("JSON-LD")
            raw_text = script.get_text() or script.string or ""
            raw_text = raw_text.strip()
            if not raw_text:
                continue

            # Strip CDATA and HTML comments
            clean_text = re.sub(r"^\s*<!\[CDATA\[", "", raw_text)
            clean_text = re.sub(r"\]\]>\s*$", "", clean_text)
            clean_text = re.sub(r"^\s*<!--", "", clean_text)
            clean_text = re.sub(r"-->\s*$", "", clean_text).strip()

            raw_script_blocks.append(clean_text)

            try:
                data = json.loads(clean_text)
                json_ld_schemas.append(data)
                cls._flatten_entities(data, raw_entities, source="JSON-LD", raw_script=clean_text)
            except Exception as e:
                # Attempt light sanitization for trailing commas
                sanitized = re.sub(r",\s*([\]}])", r"\1", clean_text)
                try:
                    data = json.loads(sanitized)
                    json_ld_schemas.append(data)
                    cls._flatten_entities(data, raw_entities, source="JSON-LD", raw_script=clean_text)
                except Exception:
                    parse_errors.append(f"JSON-LD syntax error in script tag: {str(e)[:120]}")

        # B. Microdata Extraction (Detection & property gathering)
        microdata_items = soup.find_all(attrs={"itemscope": True})
        if microdata_items:
            formats_detected.add("Microdata")
            for item in microdata_items:
                item_type = item.get("itemtype", "")
                if item_type:
                    type_name = item_type.split("/")[-1].strip()
                    if type_name:
                        props = {}
                        for prop_tag in item.find_all(attrs={"itemprop": True}):
                            prop_name = prop_tag.get("itemprop")
                            prop_val = prop_tag.get("content") or prop_tag.get("href") or prop_tag.get_text(strip=True)
                            if prop_name and prop_val:
                                props[prop_name] = prop_val
                        raw_entities.append({
                            "@type": type_name,
                            "source": "Microdata",
                            "properties": {"@type": type_name, "itemtype": item_type, **props},
                            "raw": {"@type": type_name, "itemtype": item_type, **props}
                        })

        # C. RDFa Extraction
        rdfa_items = soup.find_all(attrs={"typeof": True})
        if rdfa_items:
            formats_detected.add("RDFa")
            for item in rdfa_items:
                type_name = item.get("typeof", "").split(":")[-1].split("/")[-1].strip()
                if type_name:
                    props = {}
                    for prop_tag in item.find_all(attrs={"property": True}):
                        prop_name = prop_tag.get("property", "").split(":")[-1].strip()
                        prop_val = prop_tag.get("content") or prop_tag.get("href") or prop_tag.get_text(strip=True)
                        if prop_name and prop_val:
                            props[prop_name] = prop_val
                    raw_entities.append({
                        "@type": type_name,
                        "source": "RDFa",
                        "properties": {"@type": type_name, **props},
                        "raw": {"@type": type_name, **props}
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
            "raw_script_blocks": raw_script_blocks,
            "schema_entities": raw_entities,
            "schema_types": schema_types,
            "schema_formats": list(formats_detected),
            "schema_count": len(raw_entities),
            "schema_parse_errors": parse_errors
        }

    @classmethod
    def _flatten_entities(
        cls,
        obj: Any,
        out_list: List[Dict[str, Any]],
        source: str = "JSON-LD",
        raw_script: Optional[str] = None
    ):
        if isinstance(obj, dict):
            if "@graph" in obj and isinstance(obj["@graph"], list):
                for g_item in obj["@graph"]:
                    cls._flatten_entities(g_item, out_list, source=source, raw_script=raw_script)
            elif "@type" in obj:
                st = obj["@type"]
                clean_props = {k: v for k, v in obj.items() if k not in ["@context"]}
                out_list.append({
                    "@type": st,
                    "@id": obj.get("@id"),
                    "name": obj.get("name") or obj.get("headline") or obj.get("title"),
                    "source": source,
                    "properties": clean_props,
                    "raw": obj,
                    "raw_script": raw_script
                })
                # Check nested children
                for k, v in obj.items():
                    if k not in ["@type", "@id", "@context"]:
                        if isinstance(v, dict) and "@type" in v:
                            cls._flatten_entities(v, out_list, source=source, raw_script=raw_script)
                        elif isinstance(v, list):
                            for item in v:
                                if isinstance(item, dict) and "@type" in item:
                                    cls._flatten_entities(item, out_list, source=source, raw_script=raw_script)
        elif isinstance(obj, list):
            for item in obj:
                cls._flatten_entities(item, out_list, source=source, raw_script=raw_script)

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
        canonical_address = (project_context or {}).get("address")
        canonical_lat = (project_context or {}).get("latitude")
        canonical_lng = (project_context or {}).get("longitude")
        canonical_category = (project_context or {}).get("primary_category")
        canonical_source = (project_context or {}).get("canonical_source", "PROJECT_USER_INPUT")

        # ---------------------------------------------------------------------
        # LocalBusiness / Specialized Subtypes
        # ---------------------------------------------------------------------
        is_local_biz = (
            st_str in ["LocalBusiness", "Organization"] or
            any(sub in st_str for sub in ["Electrician", "Plumber", "HVAC", "Dentist", "Medical", "Clinic", "Restaurant", "Store", "Legal", "Automotive", "Contractor", "Service"])
        )

        comparison_details: Dict[str, Dict[str, Any]] = {}

        if is_local_biz:
            # 1. Name Comparison
            name = raw.get("name")
            if not name:
                errors.append("Missing critical property: 'name'")
                missing_properties.append("name (Critical)")
                name_status = "MISSING"
            elif not canonical_name:
                name_status = "NOT_VERIFIED"
                property_results.append({"property": "name", "value": name, "status": "Verified", "confidence": 98})
            elif canonical_name.strip().lower() == str(name).strip().lower() or canonical_name.strip().lower() in str(name).strip().lower() or str(name).strip().lower() in canonical_name.strip().lower():
                name_status = "MATCH"
                property_results.append({"property": "name", "value": name, "status": "Verified", "confidence": 98})
            else:
                name_status = "MISMATCH"
                property_results.append({"property": "name", "value": name, "status": "Verified", "confidence": 98})
                warnings.append(f"Business name '{name}' differs from canonical '{canonical_name}' ({canonical_source})")

            comparison_details["name"] = {
                "expected": canonical_name,
                "found": name,
                "status": name_status,
                "source": canonical_source
            }

            # 2. URL / Website Comparison
            url = raw.get("url")
            if not url:
                warnings.append("Missing recommended property: 'url'")
                missing_properties.append("url (Recommended)")
                web_status = "MISSING"
            elif not canonical_domain:
                web_status = "NOT_VERIFIED"
                property_results.append({"property": "url", "value": url, "status": "Verified", "confidence": 98})
            elif canonical_domain.replace("https://", "").replace("http://", "").rstrip("/").lower() in str(url).lower():
                web_status = "MATCH"
                property_results.append({"property": "url", "value": url, "status": "Verified", "confidence": 98})
            else:
                web_status = "MISMATCH"
                property_results.append({"property": "url", "value": url, "status": "Verified", "confidence": 98})

            comparison_details["website"] = {
                "expected": canonical_domain,
                "found": url,
                "status": web_status,
                "source": canonical_source
            }

            # 3. Telephone & Phone Comparison
            tel = raw.get("telephone")
            if not tel:
                warnings.append("Missing recommended property: 'telephone'")
                missing_properties.append("telephone (Recommended)")
                phone_status = "MISSING"
            elif not canonical_phone:
                phone_status = "NOT_VERIFIED"
                property_results.append({"property": "telephone", "value": tel, "status": "Verified", "confidence": 98})
            else:
                norm_schema_phone = _normalize_phone(tel)
                norm_canon_phone = _normalize_phone(canonical_phone)
                if norm_canon_phone and (norm_canon_phone in norm_schema_phone or norm_schema_phone in norm_canon_phone):
                    phone_status = "MATCH"
                    nap_match_status = "Consistent"
                else:
                    phone_status = "MISMATCH"
                    nap_match_status = "Mismatch"
                    errors.append(f"NAP Phone Mismatch: Schema phone '{tel}' differs from canonical '{canonical_phone}' ({canonical_source})")
                property_results.append({"property": "telephone", "value": tel, "status": "Verified", "confidence": 98})

            comparison_details["phone"] = {
                "expected": canonical_phone,
                "found": tel,
                "status": phone_status,
                "source": canonical_source
            }

            # 4. PostalAddress & Address Comparison
            addr = raw.get("address")
            found_addr_str = None
            if not addr:
                warnings.append("Missing recommended property: 'address' (PostalAddress)")
                missing_properties.append("address (Recommended)")
                addr_status = "MISSING"
            elif isinstance(addr, dict):
                has_street = bool(addr.get("streetAddress"))
                has_locality = bool(addr.get("addressLocality"))
                if not (has_street or has_locality):
                    errors.append("PostalAddress must include streetAddress or addressLocality")
                found_addr_str = f"{addr.get('streetAddress', '')}, {addr.get('addressLocality', '')} {addr.get('postalCode', '')} {addr.get('addressCountry', '')}".strip(" ,")
                property_results.append({
                    "property": "address",
                    "value": found_addr_str,
                    "status": "Verified",
                    "confidence": 95
                })
                if not canonical_address:
                    addr_status = "NOT_VERIFIED"
                elif addr.get("streetAddress", "").lower() in canonical_address.lower() or canonical_address.lower() in found_addr_str.lower():
                    addr_status = "MATCH"
                else:
                    addr_status = "MISMATCH"
            else:
                found_addr_str = str(addr)
                warnings.append("Property 'address' should be a structured PostalAddress object")
                addr_status = "MATCH" if (canonical_address and canonical_address.lower() in found_addr_str.lower()) else "MISMATCH"

            comparison_details["address"] = {
                "expected": canonical_address,
                "found": found_addr_str,
                "status": addr_status,
                "source": canonical_source
            }

            # 5. Geo Coordinates (Latitude & Longitude Comparison)
            geo = raw.get("geo")
            found_lat = None
            found_lng = None
            if not geo:
                missing_properties.append("geo (Optional / Context)")
                lat_status = "MISSING"
                lng_status = "MISSING"
            elif isinstance(geo, dict):
                lat = geo.get("latitude")
                lng = geo.get("longitude")
                if lat is None or lng is None:
                    warnings.append("GeoCoordinates object missing latitude or longitude")
                    lat_status = "MISSING" if lat is None else "NOT_VERIFIED"
                    lng_status = "MISSING" if lng is None else "NOT_VERIFIED"
                else:
                    try:
                        found_lat, found_lng = float(lat), float(lng)
                        if not (-90.0 <= found_lat <= 90.0 and -180.0 <= found_lng <= 180.0):
                            errors.append(f"Invalid GeoCoordinates: lat {found_lat}, lng {found_lng} out of range")
                            lat_status = "MISMATCH"
                            lng_status = "MISMATCH"
                        elif found_lat == 0.0 and found_lng == 0.0:
                            warnings.append("Suspicious GeoCoordinates: lat/lng is (0, 0)")
                            lat_status = "MISMATCH"
                            lng_status = "MISMATCH"
                        else:
                            property_results.append({"property": "geo", "value": f"({found_lat}, {found_lng})", "status": "Verified", "confidence": 98})
                            if canonical_lat is not None and canonical_lng is not None:
                                lat_diff = abs(float(canonical_lat) - found_lat)
                                lng_diff = abs(float(canonical_lng) - found_lng)
                                lat_status = "MATCH" if lat_diff <= 0.01 else "MISMATCH"
                                lng_status = "MATCH" if lng_diff <= 0.01 else "MISMATCH"
                            else:
                                lat_status = "NOT_VERIFIED"
                                lng_status = "NOT_VERIFIED"
                    except (ValueError, TypeError):
                        errors.append("GeoCoordinates latitude and longitude must be valid numeric values")
                        lat_status = "MISMATCH"
                        lng_status = "MISMATCH"
            else:
                lat_status = "NOT_VERIFIED"
                lng_status = "NOT_VERIFIED"

            comparison_details["latitude"] = {
                "expected": canonical_lat,
                "found": found_lat,
                "status": lat_status,
                "source": canonical_source
            }
            comparison_details["longitude"] = {
                "expected": canonical_lng,
                "found": found_lng,
                "status": lng_status,
                "source": canonical_source
            }

            # 6. Category Comparison
            if not canonical_category or canonical_category in ["Local Business", "LocalBusiness"]:
                cat_status = "NOT_VERIFIED"
            elif st_str.lower() in canonical_category.lower() or canonical_category.lower() in st_str.lower():
                cat_status = "MATCH"
            else:
                cat_status = "MISMATCH"

            comparison_details["category"] = {
                "expected": canonical_category,
                "found": st_str,
                "status": cat_status,
                "source": canonical_source
            }

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
            "nap_match_status": nap_match_status,
            "comparison_details": comparison_details
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

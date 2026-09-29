"""
Schema.org Vocabulary Registry, Type Hierarchy, Dynamic Property Definitions,
and Google Rich Results Eligibility Engine for LocalLift.
Vocabulary Version: Schema.org v28.0
"""

import re
import json
import urllib.parse
from typing import Dict, List, Any, Optional, Set, Tuple

# -----------------------------------------------------------------------------
# 1. Type Categories & Hierarchy Registry
# -----------------------------------------------------------------------------

SCHEMA_CATEGORIES = {
    "Local Business & Places": [
        "LocalBusiness", "Electrician", "Plumber", "HVACBusiness", "Dentist", 
        "Physician", "MedicalClinic", "LegalService", "RealEstateAgent", "Restaurant", 
        "CafeOrCoffeeShop", "Bakery", "BarOrPub", "AutoRepair", "AutoDealer", 
        "Store", "ClothingStore", "GroceryStore", "GeneralContractor", "RoofingContractor", 
        "Locksmith", "BeautySalon", "HairSalon", "DaySpa", "Hotel", "Motel", 
        "BedAndBreakfast", "FinancialService", "AccountingService", "InsuranceAgency",
        "VeterinaryCare", "ChildCare", "DryCleaningOrLaundry", "EmploymentAgency",
        "EntertainmentBusiness", "FoodEstablishment", "HomeAndConstructionBusiness",
        "LodgingBusiness", "ProfessionalService", "TouristInformationCenter"
    ],
    "Organizations & Brands": [
        "Organization", "Corporation", "EducationalOrganization", "School", 
        "CollegeOrUniversity", "GovernmentOrganization", "NGO", "SportsOrganization", 
        "OnlineBusiness", "MedicalOrganization", "NewsMediaOrganization", "PerformingGroup",
        "Project", "FundingAgency"
    ],
    "Content, Media & Creative Works": [
        "Article", "NewsArticle", "BlogPosting", "TechArticle", "ScholarlyArticle", 
        "Report", "CreativeWork", "DigitalDocument", "Book", "Chapter", "Recipe", 
        "HowTo", "HowToStep", "HowToSection", "Course", "SoftwareApplication", 
        "MobileApplication", "WebApplication", "VideoObject", "ImageObject", 
        "AudioObject", "Dataset", "MediaObject", "MusicRecording", "Movie"
    ],
    "Products, Offers & Commerce": [
        "Product", "ProductGroup", "ProductModel", "IndividualProduct", "Offer", 
        "AggregateOffer", "Service", "Brand", "Review", "UserReview", 
        "AggregateRating", "MerchantReturnPolicy", "OfferCatalog", "Order", 
        "Invoice", "Demand"
    ],
    "People, Events & Roles": [
        "Person", "Event", "BusinessEvent", "SocialEvent", "EducationEvent", 
        "SaleEvent", "ScreeningEvent", "CourseInstance", "JobPosting", 
        "Occupation", "Role", "ContactPoint", "PostalAddress"
    ],
    "Web Structure & Navigation": [
        "WebSite", "WebPage", "AboutPage", "ContactPage", "FAQPage", "QAPage", 
        "CheckoutPage", "ProfilePage", "ItemPage", "CollectionPage", 
        "SearchResultsPage", "BreadcrumbList", "ListItem", "SiteNavigationElement"
    ]
}

# Parent-child inheritance mapping
TYPE_PARENT_MAP: Dict[str, str] = {
    # LocalBusiness Subtypes
    "Electrician": "LocalBusiness",
    "Plumber": "LocalBusiness",
    "HVACBusiness": "LocalBusiness",
    "Dentist": "MedicalBusiness",
    "Physician": "MedicalBusiness",
    "MedicalClinic": "MedicalBusiness",
    "MedicalBusiness": "LocalBusiness",
    "LegalService": "LocalBusiness",
    "RealEstateAgent": "LocalBusiness",
    "Restaurant": "FoodEstablishment",
    "CafeOrCoffeeShop": "FoodEstablishment",
    "Bakery": "FoodEstablishment",
    "BarOrPub": "FoodEstablishment",
    "FoodEstablishment": "LocalBusiness",
    "AutoRepair": "AutomotiveBusiness",
    "AutoDealer": "AutomotiveBusiness",
    "AutomotiveBusiness": "LocalBusiness",
    "Store": "LocalBusiness",
    "ClothingStore": "Store",
    "GroceryStore": "Store",
    "GeneralContractor": "HomeAndConstructionBusiness",
    "RoofingContractor": "HomeAndConstructionBusiness",
    "Locksmith": "HomeAndConstructionBusiness",
    "HomeAndConstructionBusiness": "LocalBusiness",
    "BeautySalon": "HealthAndBeautyBusiness",
    "HairSalon": "HealthAndBeautyBusiness",
    "DaySpa": "HealthAndBeautyBusiness",
    "HealthAndBeautyBusiness": "LocalBusiness",
    "Hotel": "LodgingBusiness",
    "Motel": "LodgingBusiness",
    "BedAndBreakfast": "LodgingBusiness",
    "LodgingBusiness": "LocalBusiness",
    "FinancialService": "LocalBusiness",
    "AccountingService": "FinancialService",
    "InsuranceAgency": "FinancialService",
    "VeterinaryCare": "LocalBusiness",
    "ChildCare": "LocalBusiness",
    "DryCleaningOrLaundry": "LocalBusiness",
    "EmploymentAgency": "LocalBusiness",
    "EntertainmentBusiness": "LocalBusiness",
    "ProfessionalService": "LocalBusiness",
    "TouristInformationCenter": "LocalBusiness",
    "OnlineBusiness": "Organization",
    "LocalBusiness": "Organization",
    "Corporation": "Organization",
    "EducationalOrganization": "Organization",
    "School": "EducationalOrganization",
    "CollegeOrUniversity": "EducationalOrganization",
    "GovernmentOrganization": "Organization",
    "NGO": "Organization",
    "SportsOrganization": "Organization",
    "MedicalOrganization": "Organization",
    "NewsMediaOrganization": "Organization",
    "PerformingGroup": "Organization",
    "Organization": "Thing",

    # CreativeWork Subtypes
    "NewsArticle": "Article",
    "BlogPosting": "Article",
    "TechArticle": "Article",
    "ScholarlyArticle": "Article",
    "Report": "Article",
    "Article": "CreativeWork",
    "Recipe": "CreativeWork",
    "HowTo": "CreativeWork",
    "Course": "CreativeWork",
    "Book": "CreativeWork",
    "DigitalDocument": "CreativeWork",
    "SoftwareApplication": "CreativeWork",
    "MobileApplication": "SoftwareApplication",
    "WebApplication": "SoftwareApplication",
    "MediaObject": "CreativeWork",
    "VideoObject": "MediaObject",
    "ImageObject": "MediaObject",
    "AudioObject": "MediaObject",
    "Dataset": "CreativeWork",
    "FAQPage": "WebPage",
    "QAPage": "WebPage",
    "AboutPage": "WebPage",
    "ContactPage": "WebPage",
    "CheckoutPage": "WebPage",
    "ProfilePage": "WebPage",
    "ItemPage": "WebPage",
    "CollectionPage": "WebPage",
    "SearchResultsPage": "WebPage",
    "WebPage": "CreativeWork",
    "WebSite": "CreativeWork",
    "Review": "CreativeWork",
    "UserReview": "Review",
    "CreativeWork": "Thing",

    # Commerce & Products
    "ProductGroup": "Product",
    "IndividualProduct": "Product",
    "ProductModel": "Product",
    "Product": "Thing",
    "Service": "Thing",
    "Offer": "Intangible",
    "AggregateOffer": "Offer",
    "Brand": "Intangible",
    "AggregateRating": "Rating",
    "Rating": "Intangible",
    "MerchantReturnPolicy": "Intangible",
    "OfferCatalog": "Intangible",
    "BreadcrumbList": "ItemList",
    "ItemList": "Intangible",
    "ListItem": "Intangible",
    "PostalAddress": "ContactPoint",
    "ContactPoint": "Intangible",
    "GeoCoordinates": "Intangible",
    "OpeningHoursSpecification": "Intangible",
    "JobPosting": "Intangible",
    "Intangible": "Thing",

    # People & Events
    "Person": "Thing",
    "BusinessEvent": "Event",
    "SocialEvent": "Event",
    "EducationEvent": "Event",
    "SaleEvent": "Event",
    "ScreeningEvent": "Event",
    "CourseInstance": "Event",
    "Event": "Thing",
    "Thing": ""
}

# -----------------------------------------------------------------------------
# 2. Universal Schema Property Registry & Specifications
# -----------------------------------------------------------------------------

UNIVERSAL_PROPERTY_DEFS: Dict[str, List[Dict[str, Any]]] = {
    # ─── THING (Base Properties inherited by all Schema.org types) ───
    "Thing": [
        {"name": "name", "expected_type": "text", "description": "The name or title of the item.", "required": True, "recommended": True},
        {"name": "description", "expected_type": "text", "description": "A short description of the item.", "recommended": True},
        {"name": "url", "expected_type": "url", "description": "Canonical URL of the item.", "recommended": True},
        {"name": "image", "expected_type": "url", "description": "An image URL representing the item.", "recommended": True},
        {"name": "sameAs", "expected_type": "array_url", "description": "Official URLs that unambiguously indicate the item's identity (e.g. Wikipedia, LinkedIn, Google Maps, Facebook)."},
        {"name": "identifier", "expected_type": "text", "description": "The identifier property represents any unique identifier for this item."},
        {"name": "alternateName", "expected_type": "text", "description": "An alias or trading name for the item."}
    ],

    # ─── ORGANIZATION ───
    "Organization": [
        {"name": "legalName", "expected_type": "text", "description": "The official registered legal name of the organization."},
        {"name": "logo", "expected_type": "url", "description": "URL of the organization logo image.", "recommended": True, "google_rich_result": True},
        {"name": "telephone", "expected_type": "text", "description": "Primary canonical telephone number with international dial code.", "recommended": True},
        {"name": "email", "expected_type": "text", "description": "Official contact email address."},
        {"name": "address", "expected_type": "nested_address", "description": "Physical headquarters or registered business address.", "recommended": True},
        {"name": "foundingDate", "expected_type": "date", "description": "The date that this organization was founded."},
        {"name": "founders", "expected_type": "text", "description": "Person(s) who created this organization."},
        {"name": "vatID", "expected_type": "text", "description": "The Value-added Tax ID or ABN/tax number of the organization."},
        {"name": "contactPoint", "expected_type": "nested_contact_point", "description": "A contact point for a person or organization."}
    ],

    # ─── LOCAL BUSINESS ───
    "LocalBusiness": [
        {"name": "telephone", "expected_type": "text", "description": "Canonical telephone number (e.g. +61 7 3100 4500).", "required": True, "google_rich_result": True},
        {"name": "address", "expected_type": "nested_address", "description": "Physical street address including locality and postal code.", "required": True, "google_rich_result": True},
        {"name": "geo", "expected_type": "nested_geo", "description": "Exact geographic coordinates (latitude and longitude).", "recommended": True, "google_rich_result": True},
        {"name": "openingHoursSpecification", "expected_type": "nested_opening_hours", "description": "The operating opening hours schedule.", "recommended": True, "google_rich_result": True},
        {"name": "priceRange", "expected_type": "enum_price", "description": "Price range indicator (e.g. $, $$, $$$, $$$$).", "options": ["$", "$$", "$$$", "$$$$", "Free", "Contact for Quote"], "recommended": True},
        {"name": "areaServed", "expected_type": "text", "description": "Geographic area, city, or suburbs where services are provided.", "recommended": True},
        {"name": "paymentAccepted", "expected_type": "text", "description": "Payment methods accepted (e.g. Cash, Credit Card, Visa, Mastercard, EFT)."},
        {"name": "currenciesAccepted", "expected_type": "text", "description": "The currency accepted (e.g. AUD, USD, GBP, EUR)."},
        {"name": "hasMap", "expected_type": "url", "description": "A URL to a map of the place or Google Maps listing."},
        {"name": "parentOrganization", "expected_type": "id_reference", "description": "The larger organization that this local branch belongs to."}
    ],

    # ─── RESTAURANT / FOOD ───
    "Restaurant": [
        {"name": "servesCuisine", "expected_type": "text", "description": "The primary cuisine served (e.g. Italian, Modern Australian, Japanese, Mexican).", "recommended": True},
        {"name": "hasMenu", "expected_type": "url", "description": "URL to the food or drinks menu.", "recommended": True},
        {"name": "acceptsReservations", "expected_type": "boolean", "description": "Indicates whether reservations are accepted (True/False).", "options": ["True", "False"]},
        {"name": "starRating", "expected_type": "text", "description": "Official star rating or certification."}
    ],

    # ─── MEDICAL / CLINIC / DENTIST ───
    "MedicalBusiness": [
        {"name": "medicalSpecialty", "expected_type": "text", "description": "Medical specialty (e.g. Dentistry, Orthodontics, General Practice).", "recommended": True},
        {"name": "isAcceptingNewPatients", "expected_type": "boolean", "description": "Indicates whether the practice is currently accepting new patients.", "options": ["True", "False"]},
        {"name": "availableService", "expected_type": "text", "description": "Specific clinical services or procedures provided."}
    ],
    "MedicalClinic": [
        {"name": "medicalSpecialty", "expected_type": "text", "description": "Medical specialty of the clinic (e.g. Dentistry, General Practice, Physiotherapy).", "recommended": True},
        {"name": "isAcceptingNewPatients", "expected_type": "boolean", "description": "Indicates whether the clinic is currently accepting new patients.", "options": ["True", "False"]},
        {"name": "availableService", "expected_type": "text", "description": "Specific clinical services or treatments provided."}
    ],


    # ─── PRODUCT ───
    "Product": [
        {"name": "sku", "expected_type": "text", "description": "Stock Keeping Unit identifier for the product.", "recommended": True, "google_rich_result": True},
        {"name": "gtin", "expected_type": "text", "description": "Global Trade Item Number (GTIN-8, GTIN-12, GTIN-13, GTIN-14, ISBN).", "recommended": True, "google_rich_result": True},
        {"name": "mpn", "expected_type": "text", "description": "Manufacturer Part Number.", "recommended": True},
        {"name": "brand", "expected_type": "nested_brand", "description": "Brand name of the product.", "recommended": True, "google_rich_result": True},
        {"name": "offers", "expected_type": "nested_offer", "description": "Commercial pricing, currency, availability, and seller details.", "required": True, "google_rich_result": True},
        {"name": "aggregateRating", "expected_type": "nested_aggregate_rating", "description": "Overall composite rating score and review count.", "recommended": True, "google_rich_result": True},
        {"name": "review", "expected_type": "nested_review", "description": "An authentic user review of the item."},
        {"name": "itemCondition", "expected_type": "enum_condition", "description": "Product condition.", "options": ["https://schema.org/NewCondition", "https://schema.org/UsedCondition", "https://schema.org/RefurbishedCondition", "https://schema.org/DamagedCondition"]},
        {"name": "color", "expected_type": "text", "description": "Color of the product."},
        {"name": "category", "expected_type": "text", "description": "Product category hierarchy."}
    ],

    # ─── SERVICE ───
    "Service": [
        {"name": "serviceType", "expected_type": "text", "description": "Specific trade or industry category of the service (e.g. Switchboard Upgrade, Drain Relining).", "required": True},
        {"name": "provider", "expected_type": "id_reference", "description": "The organization or LocalBusiness providing the service.", "required": True, "recommended": True},
        {"name": "areaServed", "expected_type": "text", "description": "Geographic service area, cities, or postal codes.", "recommended": True},
        {"name": "offers", "expected_type": "nested_offer", "description": "Quotation terms, hourly rate, or package pricing.", "recommended": True},
        {"name": "termsOfService", "expected_type": "url", "description": "URL to service terms, guarantee, or warranty policies."},
        {"name": "hasOfferCatalog", "expected_type": "text", "description": "A catalog of sub-services or options."}
    ],

    # ─── ARTICLE / BLOG POSTING ───
    "Article": [
        {"name": "headline", "expected_type": "text", "description": "The headline or title of the article (max 110 characters recommended).", "required": True, "google_rich_result": True},
        {"name": "author", "expected_type": "nested_person_or_org", "description": "Author of the article (Person or Organization).", "required": True, "google_rich_result": True},
        {"name": "publisher", "expected_type": "nested_org_publisher", "description": "Publishing entity hosting the article.", "required": True, "google_rich_result": True},
        {"name": "datePublished", "expected_type": "datetime", "description": "Publication date and time (ISO 8601 format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ).", "required": True, "google_rich_result": True},
        {"name": "dateModified", "expected_type": "datetime", "description": "Date and time the article was most recently updated.", "recommended": True, "google_rich_result": True},
        {"name": "mainEntityOfPage", "expected_type": "url", "description": "Canonical URL of the web page.", "recommended": True, "google_rich_result": True},
        {"name": "articleBody", "expected_type": "textarea", "description": "The actual text body of the article."},
        {"name": "wordCount", "expected_type": "number", "description": "Total word count of the article body."}
    ],

    # ─── FAQ PAGE ───
    "FAQPage": [
        {"name": "mainEntity", "expected_type": "nested_qa_list", "description": "List of Question and Answer pairs.", "required": True, "google_rich_result": True}
    ],

    # ─── HOW TO ───
    "HowTo": [
        {"name": "step", "expected_type": "nested_howto_steps", "description": "Step-by-step instructions (HowToStep items).", "required": True, "google_rich_result": True},
        {"name": "totalTime", "expected_type": "text", "description": "Total duration in ISO 8601 duration format (e.g. PT30M for 30 minutes, PT1H for 1 hour).", "recommended": True},
        {"name": "estimatedCost", "expected_type": "text", "description": "Estimated monetary cost to complete the steps."},
        {"name": "supply", "expected_type": "array_text", "description": "Materials or supplies consumed during the task."},
        {"name": "tool", "expected_type": "array_text", "description": "Tools, equipment, or software required."}
    ],

    # ─── RECIPE ───
    "Recipe": [
        {"name": "author", "expected_type": "text", "description": "Author of the recipe.", "required": True, "google_rich_result": True},
        {"name": "recipeIngredient", "expected_type": "array_text", "description": "Single ingredient lines (e.g. '2 cups flour', '1 tsp salt').", "required": True, "google_rich_result": True},
        {"name": "recipeInstructions", "expected_type": "array_text", "description": "Step by step instructions for preparation.", "required": True, "google_rich_result": True},
        {"name": "cookTime", "expected_type": "text", "description": "Cooking duration in ISO 8601 (e.g. PT45M).", "recommended": True},
        {"name": "prepTime", "expected_type": "text", "description": "Preparation duration in ISO 8601 (e.g. PT15M).", "recommended": True},
        {"name": "recipeYield", "expected_type": "text", "description": "Number of servings or portions (e.g. '4 servings').", "recommended": True},
        {"name": "nutrition", "expected_type": "text", "description": "Nutritional details (e.g. calories per serving)."}
    ],

    # ─── EVENT ───
    "Event": [
        {"name": "startDate", "expected_type": "datetime", "description": "Start date and time (ISO 8601: YYYY-MM-DDTHH:MM:SSZ).", "required": True, "google_rich_result": True},
        {"name": "endDate", "expected_type": "datetime", "description": "End date and time.", "recommended": True, "google_rich_result": True},
        {"name": "location", "expected_type": "nested_event_location", "description": "Physical venue Place/PostalAddress or VirtualLocation URL.", "required": True, "google_rich_result": True},
        {"name": "eventAttendanceMode", "expected_type": "enum_attendance", "description": "Offline, online, or mixed.", "options": ["https://schema.org/OfflineEventAttendanceMode", "https://schema.org/OnlineEventAttendanceMode", "https://schema.org/MixedEventAttendanceMode"], "recommended": True},
        {"name": "eventStatus", "expected_type": "enum_status", "description": "Scheduled, cancelled, postponed, or rescheduled.", "options": ["https://schema.org/EventScheduled", "https://schema.org/EventCancelled", "https://schema.org/EventPostponed", "https://schema.org/EventRescheduled"]},
        {"name": "offers", "expected_type": "nested_offer", "description": "Admission ticket price, availability, and purchase URL.", "recommended": True, "google_rich_result": True},
        {"name": "organizer", "expected_type": "nested_person_or_org", "description": "Person or organization hosting the event.", "recommended": True}
    ],

    # ─── JOB POSTING ───
    "JobPosting": [
        {"name": "title", "expected_type": "text", "description": "Job vacancy title (e.g. Senior Electrician).", "required": True, "google_rich_result": True},
        {"name": "datePosted", "expected_type": "date", "description": "Date the job position was published.", "required": True, "google_rich_result": True},
        {"name": "validThrough", "expected_type": "datetime", "description": "Application deadline date/time.", "recommended": True, "google_rich_result": True},
        {"name": "employmentType", "expected_type": "enum_employment", "description": "Employment type.", "options": ["FULL_TIME", "PART_TIME", "CONTRACTOR", "TEMPORARY", "INTERN", "VOLUNTEER", "PER_DIEM", "OTHER"], "recommended": True, "google_rich_result": True},
        {"name": "hiringOrganization", "expected_type": "nested_org_publisher", "description": "Company hiring for the position.", "required": True, "google_rich_result": True},
        {"name": "jobLocation", "expected_type": "nested_address", "description": "Physical work location address.", "required": True, "google_rich_result": True},
        {"name": "baseSalary", "expected_type": "nested_salary", "description": "Compensation amount, currency, and pay interval (e.g. $85,000/YEAR).", "recommended": True, "google_rich_result": True}
    ],

    # ─── PERSON ───
    "Person": [
        {"name": "jobTitle", "expected_type": "text", "description": "Professional job title or designation (e.g. Master Electrician, Founder).", "recommended": True},
        {"name": "worksFor", "expected_type": "id_reference", "description": "Organization where this person is employed or partners with.", "recommended": True},
        {"name": "telephone", "expected_type": "text", "description": "Direct telephone contact."},
        {"name": "email", "expected_type": "text", "description": "Direct email address."},
        {"name": "knowsAbout", "expected_type": "array_text", "description": "Subjects, skills, or industry expertise of the person (E-E-A-T credentials)."},
        {"name": "alumniOf", "expected_type": "text", "description": "Educational institution graduated from."}
    ],

    # ─── BREADCRUMB LIST ───
    "BreadcrumbList": [
        {"name": "itemListElement", "expected_type": "nested_breadcrumbs", "description": "Ordered list of navigational breadcrumb steps with URLs and positions.", "required": True, "google_rich_result": True}
    ],

    # ─── SOFTWARE APPLICATION ───
    "SoftwareApplication": [
        {"name": "operatingSystem", "expected_type": "text", "description": "Target OS (e.g. Windows, macOS, Linux, iOS, Android, Web).", "required": True, "google_rich_result": True},
        {"name": "applicationCategory", "expected_type": "text", "description": "Category (e.g. BusinessApplication, DeveloperApplication, UtilitiesApplication).", "required": True, "google_rich_result": True},
        {"name": "offers", "expected_type": "nested_offer", "description": "Software license price or free tier.", "recommended": True, "google_rich_result": True},
        {"name": "aggregateRating", "expected_type": "nested_aggregate_rating", "description": "Software review rating and score.", "recommended": True, "google_rich_result": True},
        {"name": "downloadUrl", "expected_type": "url", "description": "Direct URL to download the software."}
    ],

    # ─── VIDEO OBJECT ───
    "VideoObject": [
        {"name": "thumbnailUrl", "expected_type": "array_url", "description": "High-resolution video thumbnail image URLs.", "required": True, "google_rich_result": True},
        {"name": "uploadDate", "expected_type": "datetime", "description": "Date and time the video was published (ISO 8601).", "required": True, "google_rich_result": True},
        {"name": "contentUrl", "expected_type": "url", "description": "Direct link to the video media file (.mp4, etc.).", "recommended": True, "google_rich_result": True},
        {"name": "embedUrl", "expected_type": "url", "description": "Player embed URL (e.g. YouTube embed link).", "recommended": True, "google_rich_result": True},
        {"name": "duration", "expected_type": "text", "description": "Video duration in ISO 8601 (e.g. PT2M30S for 2m 30s).", "recommended": True, "google_rich_result": True}
    ]
}

# -----------------------------------------------------------------------------
# 3. Google Rich Results Requirements Registry
# -----------------------------------------------------------------------------

GOOGLE_RICH_RESULTS_SPECS = {
    "LocalBusiness": {
        "title": "Google Local Business & Maps Card",
        "doc_url": "https://developers.google.com/search/docs/appearance/structured-data/local-business",
        "required_fields": ["@type", "name", "address"],
        "recommended_fields": ["telephone", "geo", "openingHoursSpecification", "image", "priceRange", "url"]
    },
    "Product": {
        "title": "Google Product & Merchant Listing",
        "doc_url": "https://developers.google.com/search/docs/appearance/structured-data/product",
        "required_fields": ["@type", "name", "offers"],
        "recommended_fields": ["image", "brand", "sku", "aggregateRating", "review", "description"]
    },
    "Article": {
        "title": "Google News, Discover & Top Stories Carousel",
        "doc_url": "https://developers.google.com/search/docs/appearance/structured-data/article",
        "required_fields": ["@type", "headline", "author", "datePublished", "publisher"],
        "recommended_fields": ["image", "dateModified", "mainEntityOfPage", "description"]
    },
    "FAQPage": {
        "title": "Google Collapsible FAQ Rich Snippet",
        "doc_url": "https://developers.google.com/search/docs/appearance/structured-data/faqpage",
        "required_fields": ["@type", "mainEntity"],
        "recommended_fields": []
    },
    "BreadcrumbList": {
        "title": "Google Navigational Breadcrumb URL Trail",
        "doc_url": "https://developers.google.com/search/docs/appearance/structured-data/breadcrumb",
        "required_fields": ["@type", "itemListElement"],
        "recommended_fields": []
    },
    "Event": {
        "title": "Google Interactive Event Search Card",
        "doc_url": "https://developers.google.com/search/docs/appearance/structured-data/event",
        "required_fields": ["@type", "name", "startDate", "location"],
        "recommended_fields": ["endDate", "description", "offers", "image", "eventAttendanceMode", "organizer"]
    },
    "JobPosting": {
        "title": "Google for Jobs Portal Listing",
        "doc_url": "https://developers.google.com/search/docs/appearance/structured-data/job-posting",
        "required_fields": ["@type", "title", "description", "datePosted", "hiringOrganization", "jobLocation"],
        "recommended_fields": ["validThrough", "employmentType", "baseSalary"]
    },
    "HowTo": {
        "title": "Google Step-by-Step HowTo Snippet",
        "doc_url": "https://developers.google.com/search/docs/appearance/structured-data/how-to",
        "required_fields": ["@type", "name", "step"],
        "recommended_fields": ["totalTime", "image", "estimatedCost", "supply", "tool"]
    },
    "Recipe": {
        "title": "Google Recipe Carousel & Badge",
        "doc_url": "https://developers.google.com/search/docs/appearance/structured-data/recipe",
        "required_fields": ["@type", "name", "image", "author", "recipeIngredient", "recipeInstructions"],
        "recommended_fields": ["cookTime", "prepTime", "recipeYield", "aggregateRating", "nutrition"]
    },
    "SoftwareApplication": {
        "title": "Google Software App Rich Snippet",
        "doc_url": "https://developers.google.com/search/docs/appearance/structured-data/software-app",
        "required_fields": ["@type", "name", "operatingSystem", "applicationCategory"],
        "recommended_fields": ["offers", "aggregateRating", "downloadUrl"]
    },
    "VideoObject": {
        "title": "Google Video Search & Key Moments Badge",
        "doc_url": "https://developers.google.com/search/docs/appearance/structured-data/video",
        "required_fields": ["@type", "name", "description", "thumbnailUrl", "uploadDate"],
        "recommended_fields": ["contentUrl", "embedUrl", "duration"]
    }
}

# -----------------------------------------------------------------------------
# 4. Vocabulary Helper Functions
# -----------------------------------------------------------------------------

class SchemaVocabulary:
    """
    Universal Schema.org vocabulary query, inheritance resolver, and validation engine.
    """

    @classmethod
    def get_all_types(cls) -> List[Dict[str, Any]]:
        """Returns all registered Schema.org types with category and parent info."""
        all_types = []
        for cat_name, types in SCHEMA_CATEGORIES.items():
            for t in types:
                parent = TYPE_PARENT_MAP.get(t, "Thing" if t != "Thing" else "")
                all_types.append({
                    "name": t,
                    "category": cat_name,
                    "parent_type": parent,
                    "has_google_rich_results": t in GOOGLE_RICH_RESULTS_SPECS or parent in GOOGLE_RICH_RESULTS_SPECS,
                    "is_local_seo_priority": cat_name == "Local Business & Places" or t in ["Organization", "Service", "WebSite", "BreadcrumbList"]
                })
        return sorted(all_types, key=lambda x: x["name"])

    @classmethod
    def resolve_lineage(cls, type_name: str) -> List[str]:
        """Resolves inheritance lineage from target type up to Thing."""
        lineage = []
        curr = type_name
        visited = set()
        while curr and curr not in visited:
            visited.add(curr)
            lineage.append(curr)
            curr = TYPE_PARENT_MAP.get(curr, "Thing" if curr != "Thing" and curr != "" else "")
        if "Thing" not in lineage and type_name != "Thing":
            lineage.append("Thing")
        return lineage

    @classmethod
    def get_properties_for_type(cls, type_name: str) -> List[Dict[str, Any]]:
        """
        Gathers all properties valid for the given type, including inherited
        properties from parent types (e.g. LocalBusiness inherits from Organization and Thing).
        """
        lineage = cls.resolve_lineage(type_name)
        merged_props: Dict[str, Dict[str, Any]] = {}

        # Merge in reverse order (Thing first, then Organization, then LocalBusiness, then specific)
        for ancestor in reversed(lineage):
            props = UNIVERSAL_PROPERTY_DEFS.get(ancestor, [])
            for p in props:
                merged_props[p["name"]] = {**p, "defined_in": ancestor}

        return list(merged_props.values())

    @classmethod

    def get_type_definition(cls, type_name: str) -> Optional[Dict[str, Any]]:
        """
        Returns complete type definition with properties, parent, category,
        lineage, and Google Rich Result specifications.
        """
        all_types = {t["name"]: t for t in cls.get_all_types()}
        if type_name not in all_types and type_name not in TYPE_PARENT_MAP:
            return None

        info = all_types.get(type_name, {})
        parent = TYPE_PARENT_MAP.get(type_name, "Thing" if type_name != "Thing" else "")
        category = info.get("category", "General Schema.org Types")
        props = cls.get_properties_for_type(type_name)

        lineage = cls.resolve_lineage(type_name)
        rr_eligible = any(anc in GOOGLE_RICH_RESULTS_SPECS for anc in lineage)
        rr_spec = None
        for anc in lineage:
            if anc in GOOGLE_RICH_RESULTS_SPECS:
                rr_spec = GOOGLE_RICH_RESULTS_SPECS[anc]
                break

        return {
            "name": type_name,
            "parent": parent,
            "category": category,
            "rich_result_eligible": rr_eligible,
            "rich_result_spec": rr_spec,
            "properties": props,
            "lineage": lineage
        }

    @classmethod
    def check_rich_results_eligibility(cls, entity_data: Dict[str, Any]) -> Dict[str, Any]:

        """
        Validates whether the given JSON-LD entity qualifies for Google Rich Results.
        """
        schema_type = entity_data.get("@type", "")
        if isinstance(schema_type, list):
            schema_type = schema_type[0] if schema_type else ""

        lineage = cls.resolve_lineage(schema_type)
        spec = None
        for ancestor in lineage:
            if ancestor in GOOGLE_RICH_RESULTS_SPECS:
                spec = GOOGLE_RICH_RESULTS_SPECS[ancestor]
                break

        if not spec:
            return {
                "eligible": False,
                "supported": False,
                "feature_name": None,
                "missing_required": [],
                "missing_recommended": [],
                "message": f"Schema.org type '{schema_type}' is valid vocabulary, but does not have a dedicated Google Rich Results card."
            }

        missing_req = []
        for req_field in spec["required_fields"]:
            if req_field not in entity_data or not entity_data[req_field]:
                missing_req.append(req_field)

        missing_rec = []
        for rec_field in spec.get("recommended_fields", []):
            if rec_field not in entity_data or not entity_data[rec_field]:
                missing_rec.append(rec_field)

        is_eligible = len(missing_req) == 0

        return {
            "eligible": is_eligible,
            "supported": True,
            "feature_name": spec["title"],
            "doc_url": spec["doc_url"],
            "missing_required": missing_req,
            "missing_recommended": missing_rec,
            "message": "Fully qualified for Google Rich Results features." if is_eligible else f"Missing required fields for {spec['title']}: {', '.join(missing_req)}."
        }

    @classmethod
    def deep_validate_json_ld(
        cls,
        json_input: Any,
        project_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive Schema.org semantic, vocabulary, syntax, Google Rich Results,
        and NAP consistency validator.
        """
        errors = []
        warnings = []
        detected_entities = []
        rich_results_reports = []

        if isinstance(json_input, str):
            clean_str = re.sub(r"^\s*<script[^>]*>", "", json_input.strip(), flags=re.IGNORECASE)
            clean_str = re.sub(r"</script>\s*$", "", clean_str, flags=re.IGNORECASE).strip()
            try:
                parsed = json.loads(clean_str)
            except Exception as e:
                return {
                    "is_valid": False,
                    "syntax_valid": False,
                    "errors": [f"JSON-LD Syntax Error: {str(e)}"],
                    "warnings": [],
                    "entities": [],
                    "rich_results": [],
                    "nap_status": "Not Applicable"
                }
        elif isinstance(json_input, (dict, list)):
            parsed = json_input
        else:
            return {
                "is_valid": False,
                "syntax_valid": False,
                "errors": ["Invalid input: expected JSON string, dict, or array"],
                "warnings": [],
                "entities": [],
                "rich_results": [],
                "nap_status": "Not Applicable"
            }

        # Collect entities from root, list, or @graph
        entities_to_check: List[Dict[str, Any]] = []
        if isinstance(parsed, dict):
            # Check @context
            ctx = parsed.get("@context")
            if not ctx:
                warnings.append("Missing '@context': recommended to declare '@context': 'https://schema.org'")
            elif "schema.org" not in str(ctx).lower():
                errors.append(f"Invalid '@context': must point to 'https://schema.org' (found '{ctx}')")

            if "@graph" in parsed and isinstance(parsed["@graph"], list):
                entities_to_check.extend([item for item in parsed["@graph"] if isinstance(item, dict)])
            else:
                entities_to_check.append(parsed)
        elif isinstance(parsed, list):
            entities_to_check.extend([item for item in parsed if isinstance(item, dict)])

        # Check @id reference integrity
        defined_ids: Set[str] = set()
        referenced_ids: List[Tuple[str, str]] = []  # (field_path, id_val)

        def _traverse_for_ids(obj: Any, path: str = "root"):
            if isinstance(obj, dict):
                if "@id" in obj and isinstance(obj["@id"], str):
                    defined_ids.add(obj["@id"])
                for k, v in obj.items():
                    sub_path = f"{path}.{k}"
                    if k == "@id" and isinstance(v, str):
                        pass
                    elif isinstance(v, dict) and len(v) == 1 and "@id" in v:
                        referenced_ids.append((sub_path, v["@id"]))
                    else:
                        _traverse_for_ids(v, sub_path)
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    _traverse_for_ids(item, f"{path}[{idx}]")

        _traverse_for_ids(parsed)

        for ref_path, ref_id in referenced_ids:
            if ref_id not in defined_ids and not ref_id.startswith("http"):
                warnings.append(f"Broken @id link at '{ref_path}': referenced ID '{ref_id}' is not declared in the @graph.")

        # Check each entity against vocabulary
        all_valid_types = {t["name"] for t in cls.get_all_types()}
        nap_status = "Consistent"

        for ent in entities_to_check:
            st = ent.get("@type")
            if not st:
                errors.append("Entity missing mandatory '@type' definition.")
                continue

            st_list = [st] if isinstance(st, str) else (st if isinstance(st, list) else [])
            for type_name in st_list:
                detected_entities.append(type_name)
                if type_name not in all_valid_types:
                    warnings.append(f"Entity type '{type_name}' is not in standard Schema.org vocabulary registry.")

                # Check rich result eligibility
                rr_report = cls.check_rich_results_eligibility(ent)
                if rr_report["supported"]:
                    rich_results_reports.append({
                        "entity_type": type_name,
                        "entity_name": ent.get("name") or ent.get("headline") or type_name,
                        **rr_report
                    })
                    for m_req in rr_report["missing_required"]:
                        if m_req != "@type":
                            errors.append(f"[{type_name}] Missing required Google Rich Result property: '{m_req}'")
                    for m_rec in rr_report["missing_recommended"][:3]:
                        warnings.append(f"[{type_name}] Missing recommended property: '{m_rec}'")

            # Check NAP if LocalBusiness or Organization
            if any(t in ["LocalBusiness", "Organization"] or "Business" in t for t in st_list):
                if project_context:
                    canon_phone = project_context.get("phone")
                    ent_phone = ent.get("telephone")
                    if canon_phone and ent_phone:
                        # Clean digits
                        p1 = re.sub(r"\D", "", canon_phone)
                        p2 = re.sub(r"\D", "", str(ent_phone))
                        if p1 and p2 and (p1 not in p2 and p2 not in p1):
                            nap_status = "Mismatch"
                            errors.append(f"NAP Phone Mismatch: Schema telephone '{ent_phone}' differs from verified canonical project phone '{canon_phone}'.")

        return {
            "is_valid": len(errors) == 0,
            "syntax_valid": True,
            "errors": list(dict.fromkeys(errors)),
            "warnings": list(dict.fromkeys(warnings)),
            "entities": list(dict.fromkeys(detected_entities)),
            "rich_results": rich_results_reports,
            "nap_status": nap_status
        }

    @classmethod
    def generate_universal_schema(
        cls,
        main_type: str,
        properties: Dict[str, Any],
        connected_entities: Optional[List[Dict[str, Any]]] = None,
        include_graph: bool = True,
        base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Universal generator supporting any Schema.org entity, nested entities, 
        and connected @graph networks.
        """
        def clean_val(v):
            if isinstance(v, dict):
                cleaned = {k: clean_val(sub_v) for k, sub_v in v.items() if sub_v not in [None, "", [], {}]}
                return cleaned if cleaned else None
            elif isinstance(v, list):
                cleaned = [clean_val(item) for item in v if item not in [None, "", [], {}]]
                return cleaned if cleaned else None
            elif isinstance(v, str):
                s = v.strip()
                return s if s else None
            return v

        main_obj: Dict[str, Any] = {"@type": main_type}
        
        # Determine ID if applicable
        url_val = properties.get("url") or base_url or ""
        if url_val and not properties.get("@id"):
            type_slug = main_type.lower()
            main_obj["@id"] = f"{url_val}#{type_slug}"

        for k, v in properties.items():
            cv = clean_val(v)
            if cv is not None:
                main_obj[k] = cv

        # Ensure @type is preserved
        main_obj["@type"] = main_type

        # Structure Graph or single entity
        graph_entities = [main_obj]
        if connected_entities:
            for ce in connected_entities:
                if isinstance(ce, dict) and ce.get("@type"):
                    c_clean = clean_val(ce)
                    if c_clean:
                        graph_entities.append(c_clean)

        if include_graph or len(graph_entities) > 1:
            schema_dict = {
                "@context": "https://schema.org",
                "@graph": graph_entities
            }
        else:
            schema_dict = {
                "@context": "https://schema.org",
                **main_obj
            }

        json_str = json.dumps(schema_dict, indent=2, ensure_ascii=False)
        return {
            "schema_json": json_str,
            "schema_dict": schema_dict,
            "entities": [e.get("@type") for e in graph_entities if isinstance(e, dict) and e.get("@type")]
        }


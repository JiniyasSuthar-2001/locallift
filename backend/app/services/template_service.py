import re
import json
from typing import Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.template import Template, TemplateUsage
from app.models.project import Project, Location
from app.models.gbp import GoogleBusinessProfile

SYSTEM_TEMPLATES = [
    {
        "name": "LocalBusiness Schema.org JSON-LD",
        "slug": "localbusiness-schema-jsonld",
        "category": "schema",
        "template_type": "schema_jsonld",
        "standard_type": "Schema.org / JSON-LD Standard",
        "description": "Google-compatible structured data markup for local business NAP, geo-coordinates, operating hours, and service categories.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"},
            {"name": "business_type", "label": "Schema @type", "required": True, "default": "LocalBusiness"},
            {"name": "website_url", "label": "Website URL", "required": True, "source": "project.domain"},
            {"name": "phone", "label": "Telephone", "required": True, "source": "location.phone"},
            {"name": "street_address", "label": "Street Address", "required": True, "source": "location.address"},
            {"name": "city", "label": "City / Suburb", "required": True, "source": "location.city"},
            {"name": "state", "label": "State / Province", "required": True, "source": "location.state"},
            {"name": "postal_code", "label": "Postal Code", "required": True, "source": "location.postal_code"},
            {"name": "country", "label": "Country Code", "required": True, "source": "project.country"},
            {"name": "latitude", "label": "Latitude", "required": False, "source": "location.latitude"},
            {"name": "longitude", "label": "Longitude", "required": False, "source": "location.longitude"},
        ],
        "required_fields": ["business_name", "street_address", "city", "phone"],
        "content": """{
  "@context": "https://schema.org",
  "@type": "{{business_type}}",
  "name": "{{business_name}}",
  "url": "https://{{website_url}}",
  "telephone": "{{phone}}",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "{{street_address}}",
    "addressLocality": "{{city}}",
    "addressRegion": "{{state}}",
    "postalCode": "{{postal_code}}",
    "addressCountry": "{{country}}"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": {{latitude}},
    "longitude": {{longitude}}
  },
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "opens": "08:00",
      "closes": "17:00"
    }
  ]
}"""
    },
    {
        "name": "5-Star Review Appreciation Response",
        "slug": "5-star-review-reply",
        "category": "review_response",
        "template_type": "review_reply",
        "standard_type": "Customer Reputation Standard",
        "description": "Personalized, professional response thanking customers for 5-star feedback while naturally highlighting the local service provided.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "reviewer_name", "label": "Customer Name", "required": True},
            {"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"},
            {"name": "service", "label": "Service Provided", "required": False, "default": "our team's services"},
            {"name": "city", "label": "City / Suburb", "required": False, "source": "location.city"},
        ],
        "required_fields": ["reviewer_name", "business_name"],
        "content": "Hi {{reviewer_name}},\n\nThank you so much for the 5-star review! The entire team at {{business_name}} is thrilled to hear about your great experience with {{service}} in {{city}}. We appreciate your trust in us and look forward to helping you again whenever you need assistance.\n\nBest regards,\nThe {{business_name}} Team"
    },
    {
        "name": "Critical Review Resolution Response (1-3 Stars)",
        "slug": "critical-review-resolution-reply",
        "category": "review_response",
        "template_type": "review_reply",
        "standard_type": "Customer Reputation Standard",
        "description": "Constructive, empathetic reply addressing customer concerns with an offline resolution path to protect local brand trust.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "reviewer_name", "label": "Customer Name", "required": True},
            {"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"},
            {"name": "phone", "label": "Support Phone", "required": True, "source": "location.phone"},
            {"name": "email", "label": "Support Email", "required": False, "default": "support@ourdomain.com"},
        ],
        "required_fields": ["reviewer_name", "business_name", "phone"],
        "content": "Hello {{reviewer_name}},\n\nThank you for sharing your honest feedback. At {{business_name}}, we pride ourselves on providing reliable, high-quality local service, and we are truly sorry to hear that your experience fell short of your expectations.\n\nWe would love the opportunity to make things right. Please reach out to our management team directly at {{phone}} or {{email}} so we can review the situation and resolve this for you immediately.\n\nSincerely,\nManagement at {{business_name}}"
    },
    {
        "name": "Suburban / Location Landing Page Blueprint",
        "slug": "suburban-location-landing-page",
        "category": "location_page",
        "template_type": "content_markdown",
        "standard_type": "Local Content Architecture",
        "description": "Structured outline for high-converting suburban and city service landing pages with local landmarks and NAP alignment.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "service", "label": "Primary Service", "required": True},
            {"name": "city", "label": "Target Suburb / City", "required": True, "source": "location.city"},
            {"name": "state", "label": "State", "required": True, "source": "location.state"},
            {"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"},
            {"name": "phone", "label": "Telephone", "required": True, "source": "location.phone"},
            {"name": "address", "label": "Physical Address", "required": False, "source": "location.address"},
        ],
        "required_fields": ["service", "city", "business_name", "phone"],
        "content": """# Top-Rated {{service}} in {{city}}, {{state}} | {{business_name}}

Looking for trusted, certified {{service}} in {{city}} and surrounding areas? {{business_name}} delivers prompt, professional solutions for residential and commercial clients across {{city}}.

## Why Choose {{business_name}} in {{city}}?
- **Fast Local Response:** Our certified technicians operate directly in {{city}} for fast dispatch.
- **Transparent Pricing:** Upfront quotes with zero hidden travel charges.
- **Fully Licensed & Insured:** Backed by 100% satisfaction guarantees.

## Comprehensive {{service}} Solutions We Provide in {{city}}
1. Emergency Repairs & Diagnostics
2. Scheduled Installations & Upgrades
3. Preventative Maintenance & Safety Inspections

## Serving {{city}} & Surrounding Communities
Our service coverage encompasses {{city}}, {{state}} and neighboring suburbs within a 25km radius.

### Contact Your Local {{city}} Specialists
- **Phone:** {{phone}}
- **Location:** {{address}}, {{city}}, {{state}}
- **Hours:** Monday – Friday: 8:00 AM – 5:00 PM (24/7 Emergency Available)
"""
    },
    {
        "name": "Google Business Profile Update Post",
        "slug": "gbp-update-post",
        "category": "gbp",
        "template_type": "gbp_post",
        "standard_type": "Google Business Profile Content Format",
        "description": "Engaging update post for Google Business Profile to boost local activity signals and promote special service offers.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "service", "label": "Featured Service", "required": True},
            {"name": "city", "label": "Target City", "required": True, "source": "location.city"},
            {"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"},
            {"name": "phone", "label": "Phone Number", "required": True, "source": "location.phone"},
            {"name": "offer", "label": "Seasonal Offer / Benefit", "required": False, "default": "Free safety check with every booking"},
        ],
        "required_fields": ["service", "city", "business_name", "phone"],
        "content": "Need reliable {{service}} in {{city}}? 📍\n\n{{business_name}} is here to help! Whether you require routine maintenance or emergency repair, our local experts are on call across {{city}}.\n\n✨ Special Highlight: {{offer}}.\n\n📞 Call our team today at {{phone}} or visit our website to book your appointment."
    },
    {
        "name": "Citation NAP Correction Task",
        "slug": "citation-nap-correction-task",
        "category": "task",
        "template_type": "task_blueprint",
        "standard_type": "Directory NAP Standard",
        "description": "Systematic task blueprint for standardizing conflicting Name, Address, and Phone directory listings.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"},
            {"name": "phone", "label": "Telephone", "required": True, "source": "location.phone"},
            {"name": "address", "label": "Address", "required": True, "source": "location.address"},
            {"name": "website_url", "label": "Domain", "required": True, "source": "project.domain"},
        ],
        "required_fields": ["business_name", "phone", "address"],
        "content": "Action: Correct Inconsistent Directory Listing\n\nTarget Business: {{business_name}}\nCanonical Phone: {{phone}}\nCanonical Address: {{address}}\nCanonical URL: https://{{website_url}}\n\nVerification Checklist:\n1. Log in to directory portal or submit claim request.\n2. Overwrite conflicting phone/address with exact canonical NAP.\n3. Ensure suite/unit formatting matches Google Business Profile.\n4. Mark citation as updated in LocalScope."
    },
    {
        "name": "LocalBusiness Schema Standard",
        "slug": "localbusiness-schema-standard",
        "category": "schema",
        "template_type": "schema_jsonld",
        "standard_type": "Schema.org / JSON-LD Standard",
        "description": "Standardized Google Local Knowledge Graph compliant JSON-LD structured data markup.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"},
            {"name": "business_type", "label": "Schema @type", "required": True, "default": "LocalBusiness"},
            {"name": "website_url", "label": "Website URL", "required": True, "source": "project.domain"},
            {"name": "phone", "label": "Telephone", "required": True, "source": "location.phone"},
            {"name": "street_address", "label": "Street Address", "required": True, "source": "location.address"},
            {"name": "city", "label": "City / Suburb", "required": True, "source": "location.city"},
            {"name": "state", "label": "State / Province", "required": True, "source": "location.state"},
            {"name": "postal_code", "label": "Postal Code", "required": True, "source": "location.postal_code"},
            {"name": "country", "label": "Country Code", "required": True, "source": "project.country"},
            {"name": "latitude", "label": "Latitude", "required": False, "source": "location.latitude"},
            {"name": "longitude", "label": "Longitude", "required": False, "source": "location.longitude"},
        ],
        "required_fields": ["business_name", "street_address", "city", "phone"],
        "content": """{
  "@context": "https://schema.org",
  "@type": "{{business_type}}",
  "name": "{{business_name}}",
  "url": "https://{{website_url}}",
  "telephone": "{{phone}}",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "{{street_address}}",
    "addressLocality": "{{city}}",
    "addressRegion": "{{state}}",
    "postalCode": "{{postal_code}}",
    "addressCountry": "{{country}}"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": {{latitude}},
    "longitude": {{longitude}}
  },
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "opens": "08:00",
      "closes": "17:00"
    }
  ]
}"""
    },
    {
        "name": "Service & Location Page Blueprint",
        "slug": "service-location-page-blueprint",
        "category": "service_location",
        "template_type": "content_markdown",
        "standard_type": "Local Content Architecture",
        "description": "High-converting service landing page blueprint optimized for hyper-local Google searches.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "service", "label": "Primary Service", "required": True},
            {"name": "city", "label": "City / Suburb", "required": True, "source": "location.city"},
            {"name": "state", "label": "State", "required": True, "source": "location.state"},
            {"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"},
            {"name": "phone", "label": "Telephone", "required": True, "source": "location.phone"},
            {"name": "address", "label": "Physical Address", "required": False, "source": "location.address"},
        ],
        "required_fields": ["service", "city", "business_name", "phone"],
        "content": """# Reliable {{service}} in {{city}}, {{state}} | {{business_name}}

When you need prompt, professional {{service}} in {{city}}, {{business_name}} is your trusted local choice.

## Why Choose Us in {{city}}?
- Prompt response times from local technicians
- Transparent upfront pricing
- Fully licensed, insured, and verified work

## Contact {{business_name}} Today
- **Phone:** {{phone}}
- **Address:** {{address}}, {{city}}, {{state}}
"""
    },
    {
        "name": "Suburban Location Landing Page Blueprint",
        "slug": "location-landing-page-blueprint",
        "category": "location_page",
        "template_type": "content_markdown",
        "standard_type": "Local Content Architecture",
        "description": "Dedicated location page structure designed to capture suburban local pack ranking queries.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "service", "label": "Primary Service", "required": True},
            {"name": "city", "label": "Target Suburb / City", "required": True, "source": "location.city"},
            {"name": "state", "label": "State", "required": True, "source": "location.state"},
            {"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"},
            {"name": "phone", "label": "Telephone", "required": True, "source": "location.phone"},
            {"name": "address", "label": "Physical Address", "required": False, "source": "location.address"},
        ],
        "required_fields": ["service", "city", "business_name", "phone"],
        "content": """# Top-Rated {{service}} in {{city}}, {{state}} | {{business_name}}

Looking for trusted, certified {{service}} in {{city}} and surrounding areas? {{business_name}} delivers prompt, professional solutions across {{city}}.

### Contact Your Local {{city}} Specialists
- **Phone:** {{phone}}
- **Location:** {{address}}, {{city}}, {{state}}
"""
    },
    {
        "name": "Positive Review Response",
        "slug": "positive-review-response",
        "category": "review_response",
        "template_type": "review_reply",
        "standard_type": "Customer Reputation Standard",
        "description": "Express appreciation for 5-star customer feedback while highlighting the local service provided.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "reviewer_name", "label": "Customer Name", "required": True},
            {"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"},
            {"name": "service", "label": "Service Provided", "required": False, "default": "our team's services"},
            {"name": "city", "label": "City / Suburb", "required": False, "source": "location.city"},
        ],
        "required_fields": ["reviewer_name", "business_name"],
        "content": "Hi {{reviewer_name}},\n\nThank you so much for the wonderful review! The entire team at {{business_name}} appreciates your support and is glad we could help with your {{service}} in {{city}}.\n\nBest regards,\nThe {{business_name}} Team"
    },
    {
        "name": "Negative Review De-escalation",
        "slug": "negative-review-deescalation",
        "category": "review_response",
        "template_type": "review_reply",
        "standard_type": "Customer Reputation Standard",
        "description": "Professional, de-escalating response offering direct management resolution.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "reviewer_name", "label": "Customer Name", "required": True},
            {"name": "business_name", "label": "Business Name", "required": True, "source": "project.name"},
            {"name": "phone", "label": "Support Phone", "required": True, "source": "location.phone"},
        ],
        "required_fields": ["reviewer_name", "business_name", "phone"],
        "content": "Hello {{reviewer_name}},\n\nThank you for sharing your feedback. At {{business_name}}, we take customer satisfaction very seriously and regret that your experience was not up to our standard.\n\nPlease contact us directly at {{phone}} so we can resolve this matter promptly.\n\nSincerely,\nManagement at {{business_name}}"
    },
    {
        "name": "GBP Weekly Update",
        "slug": "gbp-weekly-update",
        "category": "gbp",
        "template_type": "gbp_post",
        "standard_type": "Google Business Profile Content Format",
        "description": "Weekly local update post highlighting ongoing availability and active local customer service.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "service", "label": "Featured Service", "required": True},
            {"name": "city", "label": "City / Suburb", "required": True},
            {"name": "phone", "label": "Phone Number", "required": True},
        ],
        "required_fields": ["business_name", "service", "city", "phone"],
        "content": "📍 Weekly Update from {{business_name}} in {{city}}\n\nOur team is actively assisting customers with professional {{service}} this week across {{city}}.\n\nLooking for reliable service? Get in touch with {{business_name}} today at {{phone}} or visit our website for scheduling."
    },
    {
        "name": "GBP Business Update",
        "slug": "gbp-business-update",
        "category": "gbp",
        "template_type": "gbp_post",
        "standard_type": "Google Business Profile Content Format",
        "description": "Official company and operational update for Google Business Profile followers and local searchers.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "city", "label": "City / Suburb", "required": True},
            {"name": "phone", "label": "Phone Number", "required": True},
            {"name": "address", "label": "Address", "required": False},
        ],
        "required_fields": ["business_name", "city", "phone"],
        "content": "📢 Operational Announcement from {{business_name}}\n\nWe are proud to continue serving residential and commercial clients across {{city}}. Visit us at {{address}} or speak directly with our specialists at {{phone}}.\n\nThank you for supporting local business!"
    },
    {
        "name": "New Service Announcement",
        "slug": "gbp-new-service-announcement",
        "category": "gbp",
        "template_type": "gbp_post",
        "standard_type": "Google Business Profile Content Format",
        "description": "Engaging announcement introducing a newly launched service or expanded coverage area.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "service", "label": "New Service Name", "required": True},
            {"name": "city", "label": "City / Suburb", "required": True},
            {"name": "phone", "label": "Phone Number", "required": True},
        ],
        "required_fields": ["business_name", "service", "city", "phone"],
        "content": "🚀 Exciting News from {{business_name}}!\n\nWe have expanded our offerings to include {{service}} for our clients in {{city}} and surrounding regions.\n\nWhether you need an upfront estimate or quick consultation, call {{business_name}} at {{phone}}."
    },
    {
        "name": "Service Highlight",
        "slug": "gbp-service-highlight",
        "category": "gbp",
        "template_type": "gbp_post",
        "standard_type": "Google Business Profile Content Format",
        "description": "Detailed spotlight on a high-intent core service.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "service", "label": "Service Highlight", "required": True},
            {"name": "city", "label": "City", "required": True},
            {"name": "phone", "label": "Phone", "required": True},
        ],
        "required_fields": ["business_name", "service", "city", "phone"],
        "content": "⭐ Service Spotlight: {{service}}\n\nAt {{business_name}}, we specialize in comprehensive {{service}} tailored to {{city}} residents. Our licensed experts ensure guaranteed satisfaction.\n\n📞 Inquire today at {{phone}}."
    },
    {
        "name": "Seasonal Offer",
        "slug": "gbp-seasonal-offer",
        "category": "gbp",
        "template_type": "gbp_post",
        "standard_type": "Google Business Profile Content Format",
        "description": "Time-sensitive seasonal offer draft compliant with Google promotion policies.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "service", "label": "Service", "required": True},
            {"name": "city", "label": "City", "required": True},
            {"name": "phone", "label": "Phone", "required": True},
        ],
        "required_fields": ["business_name", "service", "city", "phone"],
        "content": "🎉 Limited-Time Seasonal Offer at {{business_name}}\n\nBook your {{service}} in {{city}} this season and take advantage of our promotional rates. Quality local workmanship you can rely on.\n\nCall {{phone}} or message us to secure your booking."
    },
    {
        "name": "Event Announcement",
        "slug": "gbp-event-announcement",
        "category": "gbp",
        "template_type": "gbp_post",
        "standard_type": "Google Business Profile Content Format",
        "description": "Community workshop, trade event, or storefront event announcement draft.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "city", "label": "City", "required": True},
            {"name": "address", "label": "Event Location", "required": False},
            {"name": "phone", "label": "Contact Phone", "required": True},
        ],
        "required_fields": ["business_name", "city", "phone"],
        "content": "📅 Upcoming Local Event with {{business_name}}\n\nJoin our team in {{city}} at {{address}} for our upcoming event. Meet our local team and discover what makes {{business_name}} the premier choice in the area.\n\nContact us at {{phone}} for details."
    },
    {
        "name": "Local Community Update",
        "slug": "gbp-local-community-update",
        "category": "gbp",
        "template_type": "gbp_post",
        "standard_type": "Google Business Profile Content Format",
        "description": "Local civic, sponsorship, and neighborhood community participation update.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "city", "label": "City / Community", "required": True},
            {"name": "website_url", "label": "Website", "required": False},
        ],
        "required_fields": ["business_name", "city"],
        "content": "🤝 Proud to Support the {{city}} Community!\n\n{{business_name}} is dedicated to empowering local initiatives and serving our neighbors across {{city}}.\n\nLearn more about our local involvement on our website: {{website_url}}."
    },
    {
        "name": "Product / Service Promotion",
        "slug": "gbp-product-service-promotion",
        "category": "gbp",
        "template_type": "gbp_post",
        "standard_type": "Google Business Profile Content Format",
        "description": "Targeted product or package promotion for local search traffic.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "service", "label": "Featured Package", "required": True},
            {"name": "phone", "label": "Phone Number", "required": True},
            {"name": "city", "label": "City", "required": True},
        ],
        "required_fields": ["business_name", "service", "phone", "city"],
        "content": "🔥 Featured Package: {{service}} by {{business_name}}\n\nGet top-tier solutions with transparent upfront pricing in {{city}}. Contact {{phone}} today to request your estimate."
    },
    {
        "name": "Neutral Review Response",
        "slug": "gbp-neutral-review-response",
        "category": "review_response",
        "template_type": "review_reply",
        "standard_type": "Customer Reputation Standard",
        "description": "Balanced, polite response acknowledging neutral 3-star customer feedback.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "reviewer_name", "label": "Reviewer Name", "required": True},
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "phone", "label": "Support Phone", "required": True},
        ],
        "required_fields": ["reviewer_name", "business_name", "phone"],
        "content": "Hello {{reviewer_name}},\n\nThank you for sharing your feedback with {{business_name}}. We appreciate your business and are always striving to deliver a 5-star experience.\n\nIf there is anything we can do to further improve your experience, please feel free to reach out to us directly at {{phone}}.\n\nBest regards,\nThe {{business_name}} Team"
    },
    {
        "name": "Negative Review Response",
        "slug": "gbp-negative-review-response",
        "category": "review_response",
        "template_type": "review_reply",
        "standard_type": "Customer Reputation Standard",
        "description": "De-escalating, professional response offering direct management resolution.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "reviewer_name", "label": "Reviewer Name", "required": True},
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "phone", "label": "Management Phone", "required": True},
        ],
        "required_fields": ["reviewer_name", "business_name", "phone"],
        "content": "Dear {{reviewer_name}},\n\nThank you for bringing this to our attention. At {{business_name}}, we hold our team to the highest standards of service and sincerely apologize that your experience did not meet expectations.\n\nWe would welcome the chance to address this directly with you. Please reach out to our management team at {{phone}} so we can resolve this immediately.\n\nSincerely,\nManagement at {{business_name}}"
    },
    {
        "name": "GBP Optimization Checklist",
        "slug": "gbp-optimization-checklist",
        "category": "task",
        "template_type": "task_blueprint",
        "standard_type": "Google Local SEO Standard",
        "description": "Actionable task blueprint for monthly Google Business Profile optimization.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "primary_category", "label": "Primary Category", "required": False},
            {"name": "phone", "label": "Phone", "required": True},
            {"name": "address", "label": "Address", "required": True},
        ],
        "required_fields": ["business_name", "phone", "address"],
        "content": "# Google Business Profile Monthly Optimization Checklist\n\nTarget Listing: {{business_name}}\nPrimary Category: {{primary_category}}\nCanonical NAP: {{address}} | {{phone}}\n\n## Monthly Tasks:\n1. [ ] Check and update operating hours and special holiday hours.\n2. [ ] Review and respond to all recent customer reviews.\n3. [ ] Upload 3-5 new high-resolution photos of projects, storefront, or team.\n4. [ ] Publish a new weekly GBP update post.\n5. [ ] Confirm primary and secondary categories match core high-intent offerings."
    },
    {
        "name": "GBP Profile Completeness Checklist",
        "slug": "gbp-completeness-checklist",
        "category": "task",
        "template_type": "task_blueprint",
        "standard_type": "Google Local SEO Standard",
        "description": "Comprehensive audit checklist for 100% Google Business Profile completeness.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "primary_category", "label": "Primary Category", "required": False},
            {"name": "additional_categories", "label": "Additional Categories", "required": False},
            {"name": "address", "label": "Address", "required": True},
            {"name": "phone", "label": "Phone", "required": True},
            {"name": "website_url", "label": "Website", "required": False},
        ],
        "required_fields": ["business_name", "address", "phone"],
        "content": "# GBP 100% Profile Completeness Checklist\n\nBusiness Name: {{business_name}}\nPrimary Category: {{primary_category}}\nAdditional Categories: {{additional_categories}}\nAddress: {{address}}\nPhone: {{phone}}\nWebsite: {{website_url}}\n\n## Verification Items:\n1. [ ] Claim and verify listing ownership.\n2. [ ] Accurate NAP aligned across website, schema, and citations.\n3. [ ] Business description filled with local keywords (750 chars max).\n4. [ ] Complete list of services and products populated.\n5. [ ] Business attributes configured (accessibility, amenities, payment types)."
    },
    {
        "name": "GBP Photo / Media Workflow",
        "slug": "gbp-photo-media-workflow",
        "category": "task",
        "template_type": "task_blueprint",
        "standard_type": "Google Media Standard",
        "description": "Standard operating procedure for regular photo and media uploads to Google Business Profile.",
        "is_system": True,
        "created_by": "System Standard",
        "variables": [
            {"name": "business_name", "label": "Business Name", "required": True},
            {"name": "city", "label": "City", "required": True},
        ],
        "required_fields": ["business_name", "city"],
        "content": "# Google Business Profile Photo / Media Standard Workflow\n\nBusiness: {{business_name}} ({{city}})\n\n## Photo Guidelines:\n1. Format: JPG or PNG, minimum 720px width and height.\n2. Size: Between 10KB and 5MB.\n3. Categories to maintain:\n   - Storefront & Exterior (day and night shots)\n   - Interior atmosphere & workstations\n   - High-quality completed projects\n   - Team and leadership in uniform\n4. Schedule: Upload at least 2 new photos weekly to signal ongoing business activity."
    }
]

class TemplateEngine:
    @staticmethod
    def extract_variables(text: str) -> List[str]:
        """Extract all {{variable_name}} tokens from template text."""
        return list(set(re.findall(r"\{\{([a-zA-Z0-9_]+)\}\}", text)))

    @staticmethod
    def validate_template(content: str, template_type: str, required_fields: List[str] = None) -> Tuple[bool, List[str], List[str], List[str]]:
        """Validate template syntax, variable presence, and JSON formatting."""
        errors = []
        warnings = []
        detected_vars = TemplateEngine.extract_variables(content)

        if not content.strip():
            errors.append("Template content cannot be empty.")
            return False, errors, warnings, detected_vars

        if required_fields:
            for rf in required_fields:
                if rf not in detected_vars:
                    warnings.append(f"Recommended variable '{{{{{rf}}}}}' is missing from template content.")

        # If schema_jsonld, validate valid JSON after dummy substitution
        if template_type == "schema_jsonld":
            dummy_content = content
            for v in detected_vars:
                if v in ["latitude", "longitude"]:
                    dummy_content = dummy_content.replace(f"{{{{{v}}}}}", "0.0")
                else:
                    dummy_content = dummy_content.replace(f"{{{{{v}}}}}", "sample_val")
            
            try:
                json.loads(dummy_content)
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON structure in Schema template: {str(e)[:100]}")

        is_valid = len(errors) == 0
        return is_valid, errors, warnings, detected_vars

    @staticmethod
    async def render_template(
        db: AsyncSession,
        template: Template,
        project_id: int,
        location_id: int = None,
        custom_variables: Dict[str, Any] = None
    ) -> Tuple[str, Dict[str, Any], List[str]]:
        """
        Populate template variables adhering strictly to Priority Hierarchy:
        1. Bound Google Business Profile (when connected)
        2. Project Location
        3. Project Data
        Never manufactures fake defaults.
        """
        # 1. Load Project with locations
        from sqlalchemy.orm import selectinload
        proj_result = await db.execute(select(Project).options(selectinload(Project.locations)).where(Project.id == project_id))
        project = proj_result.scalar_one_or_none()

        # 2. Load Location
        location = None
        # Load exact project-bound GBP Profile first
        gbp_res = await db.execute(
            select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == project_id)
        )
        gbp = gbp_res.scalars().first()

        if location_id:
            loc_result = await db.execute(select(Location).where(Location.id == location_id))
            location = loc_result.scalar_one_or_none()
        elif gbp and gbp.location_id and project and project.locations:
            location = next((l for l in project.locations if l.id == gbp.location_id), None)
        elif project and project.locations and len(project.locations) == 1:
            location = project.locations[0]

        # Build Context Values using strict priority: 1. Bound GBP -> 2. Location -> 3. Project
        business_name = (gbp.business_name if gbp else None) or (project.name if project else None)
        phone = (gbp.phone if gbp else None) or (location.phone if location else None)
        address = (gbp.address if gbp else None) or (location.address if location else None)
        city = (gbp.city if gbp else None) or (location.city if location else None)
        state = (gbp.state if gbp else None) or (location.state if location else None)
        postal_code = (gbp.postal_code if gbp else None) or (location.postal_code if location else None)
        country = (gbp.country if gbp else None) or (location.country if location else None) or (project.country if project else None)
        
        website_url = (gbp.website_url if gbp else None) or (f"https://{project.domain}" if project and project.domain else None)
        if website_url and website_url.startswith("https://"):
            clean_web = website_url.replace("https://", "").replace("http://", "").rstrip("/")
        else:
            clean_web = website_url

        primary_category = (gbp.primary_category if gbp else None) or (project.primary_category if project and project.primary_category else "LocalBusiness")
        additional_cats_str = ", ".join(gbp.additional_categories) if (gbp and gbp.additional_categories) else None

        # Coordinates resolution
        lat_val = None
        lng_val = None
        if gbp and gbp.latitude is not None and gbp.longitude is not None:
            lat_val = str(gbp.latitude)
            lng_val = str(gbp.longitude)
        elif location and location.latitude is not None and location.longitude is not None:
            lat_val = str(location.latitude)
            lng_val = str(location.longitude)

        context: Dict[str, Any] = {
            "business_name": business_name,
            "website_url": clean_web,
            "phone": phone,
            "address": address,
            "street_address": address,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": country,
            "primary_category": primary_category,
            "additional_categories": additional_cats_str,
            "business_type": primary_category,
            "service": primary_category,
            "latitude": lat_val,
            "longitude": lng_val,
            "reviewer_name": None,
            "rating": None,
            "offer": None
        }

        # Apply custom variable overrides
        if custom_variables:
            context.update(custom_variables)

        # Render Content
        rendered = template.content

        # If schema_jsonld and coordinates are missing, omit "geo" block cleanly
        if template.template_type == "schema_jsonld" and (context.get("latitude") is None or context.get("longitude") is None):
            geo_pattern_with_leading_comma = r',\s*"geo":\s*\{\s*"@type":\s*"GeoCoordinates",\s*"latitude":\s*(?:\{\{latitude\}\}|"[^"]*"|[\d.-]+),\s*"longitude":\s*(?:\{\{longitude\}\}|"[^"]*"|[\d.-]+)\s*\}'
            geo_pattern_without_leading_comma = r'"geo":\s*\{\s*"@type":\s*"GeoCoordinates",\s*"latitude":\s*(?:\{\{latitude\}\}|"[^"]*"|[\d.-]+),\s*"longitude":\s*(?:\{\{longitude\}\}|"[^"]*"|[\d.-]+)\s*\},\s*'
            rendered = re.sub(geo_pattern_with_leading_comma, '', rendered)
            rendered = re.sub(geo_pattern_without_leading_comma, '', rendered)

        detected_vars = TemplateEngine.extract_variables(rendered)
        used_vars = {}
        missing_vars = []

        for var_name in detected_vars:
            if var_name in context and context[var_name] is not None:
                val = str(context[var_name])
                rendered = rendered.replace(f"{{{{{var_name}}}}}", val)
                used_vars[var_name] = val
            else:
                missing_vars.append(var_name)

        return rendered, used_vars, missing_vars

    @staticmethod
    async def seed_system_templates(db: AsyncSession):
        """Seed system templates if not already present."""
        for t_data in SYSTEM_TEMPLATES:
            stmt = select(Template).where(Template.slug == t_data["slug"], Template.is_system == True)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if not existing:
                new_t = Template(
                    name=t_data["name"],
                    slug=t_data["slug"],
                    category=t_data["category"],
                    template_type=t_data["template_type"],
                    standard_type=t_data.get("standard_type", "Local SEO Standard"),
                    description=t_data["description"],
                    content=t_data["content"],
                    variables=t_data["variables"],
                    required_fields=t_data["required_fields"],
                    is_system=True,
                    version=1,
                    created_by=t_data["created_by"],
                    usage_count=0
                )
                db.add(new_t)
            else:
                # Keep content and metadata up-to-date
                existing.content = t_data["content"]
                existing.variables = t_data["variables"]
                existing.required_fields = t_data["required_fields"]
                existing.description = t_data["description"]
        await db.commit()

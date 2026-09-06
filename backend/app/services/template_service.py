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
        "name": "Google Business Profile Weekly Update Post",
        "slug": "gbp-weekly-update-post",
        "category": "gbp",
        "template_type": "gbp_post",
        "standard_type": "Google Business Profile Content Format",
        "description": "Weekly local engagement post for Google Business Profile highlighting seasonal services.",
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
        "content": "Need reliable {{service}} in {{city}}? 📍\n\n{{business_name}} is here to help! Our team is available across {{city}}.\n\n✨ Special Offer: {{offer}}.\n\n📞 Call us today at {{phone}} or visit our website to book."
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
                    dummy_content = dummy_content.replace(f"{{{{{v}}}}}", "-27.4698")
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
        """Populate template variables using live Project, Location, and GBP entities."""
        # Load Project with locations
        from sqlalchemy.orm import selectinload
        proj_result = await db.execute(select(Project).options(selectinload(Project.locations)).where(Project.id == project_id))
        project = proj_result.scalar_one_or_none()

        # Load Location
        location = None
        if location_id:
            loc_result = await db.execute(select(Location).where(Location.id == location_id))
            location = loc_result.scalar_one_or_none()
        elif project and project.locations:
            location = project.locations[0]

        # Load GBP via GoogleAccount
        from app.models.gbp import GoogleAccount
        acc_res = await db.execute(select(GoogleAccount).where(GoogleAccount.project_id == project_id))
        google_account = acc_res.scalar_one_or_none()
        gbp = None
        if google_account:
            gbp_result = await db.execute(select(GoogleBusinessProfile).where(GoogleBusinessProfile.google_account_id == google_account.id))
            gbp = gbp_result.scalar_one_or_none()

        # Build Context Values
        context: Dict[str, Any] = {
            "business_name": (gbp.business_name if gbp else None) or (project.name if project else "Local Business"),
            "website_url": project.domain if project else "example.com",
            "country": project.country if project else "United States",
            "business_type": "LocalBusiness",
            "service": project.primary_category if project else "Local Services",
            "phone": (location.phone if location else None) or (gbp.phone if gbp else "+1 555 123 4567"),
            "street_address": (location.address if location else None) or (gbp.address if gbp else "100 Main Street"),
            "address": (location.address if location else None) or (gbp.address if gbp else "100 Main Street"),
            "city": (location.city if location else None) or "Metro City",
            "state": (location.state if location else None) or "State",
            "postal_code": (location.postal_code if location else None) or "10001",
            "latitude": str(location.latitude if location and location.latitude else -27.4698),
            "longitude": str(location.longitude if location and location.longitude else 153.0251),
            "reviewer_name": "Valued Customer",
            "rating": "5",
            "offer": "Free inspection with every local booking"
        }

        # Apply custom variable overrides
        if custom_variables:
            context.update(custom_variables)

        # Render Content
        rendered = template.content
        detected_vars = TemplateEngine.extract_variables(template.content)
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
        await db.commit()

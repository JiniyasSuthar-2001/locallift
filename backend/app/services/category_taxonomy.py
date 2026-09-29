"""
LocalLift — Authoritative Business Category Taxonomy & Industry Catalog

Hierarchy:
Industry Parent Group -> Subcategory -> Business Category

Supports:
- 32 Parent Industry Groups
- Complete Information Technology (IT), Software, AI, Cybersecurity taxonomy
- Search by exact match, prefix, partial, keyword, aliases, subcategories, and parent group
- Curated Popular Categories across diverse industries
- Backward compatibility for all existing saved project categories
"""

import re
from typing import List, Dict, Any, Optional, Set

BUSINESS_CATEGORIES_DATA: List[Dict[str, Any]] = [
    # =========================================================================
    # 1. Information Technology (IT)
    # =========================================================================
    {
        "id": "it-services",
        "name": "IT Services",
        "slug": "it-services",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "IT Services & Infrastructure",
        "aliases": ["it", "information technology", "tech services", "it company", "tech company", "managed it", "it solutions", "business it"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer support and services",
        "is_popular": True,
        "display_order": 10,
        "icon_key": "laptop",
        "description": "Comprehensive corporate IT support, systems management, and technical solutions."
    },
    {
        "id": "it-services-consultant",
        "name": "IT Services and IT Consulting",
        "slug": "it-services-consultant",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "IT Consulting & Advisory",
        "aliases": ["it consultant", "it consulting", "information technology consultant", "tech consultant", "it advisory"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer consultant",
        "is_popular": True,
        "display_order": 11,
        "icon_key": "briefcase",
        "description": "Strategic technology planning, infrastructure architecture, and enterprise IT advisory."
    },
    {
        "id": "managed-it-services",
        "name": "Managed IT Services",
        "slug": "managed-it-services",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "IT Services & Infrastructure",
        "aliases": ["msp", "managed service provider", "outsourced it", "it outsourcing", "managed services", "it management"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer support and services",
        "is_popular": True,
        "display_order": 12,
        "icon_key": "server",
        "description": "Proactive 24/7 network monitoring, help desk, and managed workstation support."
    },
    {
        "id": "it-support-company",
        "name": "IT Support Company",
        "slug": "it-support-company",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "IT Services & Infrastructure",
        "aliases": ["it help desk", "tech support", "computer support", "desktop support", "it assistance"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer support and services",
        "is_popular": False,
        "display_order": 13,
        "icon_key": "help-circle",
        "description": "On-demand help desk, remote desktop support, and hardware assistance."
    },
    {
        "id": "cybersecurity-company",
        "name": "Cybersecurity Company",
        "slug": "cybersecurity-company",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "Cybersecurity & Protection",
        "aliases": ["cyber security", "cybersecurity", "infosec", "network security", "data security", "penetration testing", "soc"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer security service",
        "is_popular": True,
        "display_order": 14,
        "icon_key": "shield",
        "description": "Enterprise threat defense, vulnerability assessments, compliance, and SOC monitoring."
    },
    {
        "id": "cybersecurity-consultant",
        "name": "Cybersecurity Consultant",
        "slug": "cybersecurity-consultant",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "Cybersecurity & Protection",
        "aliases": ["security consultant", "ciso as a service", "soc2 consultant", "hipaa security", "infosec consultant"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer security service",
        "is_popular": False,
        "display_order": 15,
        "icon_key": "shield-check",
        "description": "Virtual CISO, regulatory compliance (SOC2, ISO27001), and security risk auditing."
    },
    {
        "id": "cloud-services",
        "name": "Cloud Services Provider",
        "slug": "cloud-services",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "Cloud & Infrastructure",
        "aliases": ["cloud", "cloud computing", "aws partner", "azure partner", "gcp", "cloud migration", "cloud hosting"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer support and services",
        "is_popular": True,
        "display_order": 16,
        "icon_key": "cloud",
        "description": "Public, private, and hybrid cloud architecture, migration, and optimization."
    },
    {
        "id": "cloud-consultant",
        "name": "Cloud Consultant",
        "slug": "cloud-consultant",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "Cloud & Infrastructure",
        "aliases": ["cloud architect", "aws consultant", "azure consultant", "cloud strategy", "finops"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer consultant",
        "is_popular": False,
        "display_order": 17,
        "icon_key": "cloud-rain",
        "description": "Cloud migration strategy, multi-cloud cost optimization, and Kubernetes consulting."
    },
    {
        "id": "network-services",
        "name": "Network Services",
        "slug": "network-services",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "IT Services & Infrastructure",
        "aliases": ["network cabling", "wifi installation", "lan wan", "firewall installation", "structured cabling"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Telecommunications service provider",
        "is_popular": False,
        "display_order": 18,
        "icon_key": "network",
        "description": "Structured cabling, enterprise Wi-Fi design, routers, firewalls, and SD-WAN."
    },
    {
        "id": "data-recovery-service",
        "name": "Data Recovery Service",
        "slug": "data-recovery-service",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "IT Services & Infrastructure",
        "aliases": ["hard drive recovery", "data retrieval", "raid recovery", "ssd recovery", "lost data"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Data recovery service",
        "is_popular": False,
        "display_order": 19,
        "icon_key": "database",
        "description": "Cleanroom hard drive restoration, RAID array rebuilds, and forensic data recovery."
    },
    {
        "id": "backup-disaster-recovery",
        "name": "Backup & Disaster Recovery",
        "slug": "backup-disaster-recovery",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "IT Services & Infrastructure",
        "aliases": ["bcdr", "cloud backup", "business continuity", "ransomware recovery", "disaster recovery"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer support and services",
        "is_popular": False,
        "display_order": 20,
        "icon_key": "hard-drive",
        "description": "Automated off-site cloud backups, business continuity testing, and rapid failover."
    },
    {
        "id": "computer-repair-service",
        "name": "Computer Repair Service",
        "slug": "computer-repair-service",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "Computer Hardware & Repair",
        "aliases": ["pc repair", "laptop repair", "mac repair", "screen replacement", "virus removal", "fix computer"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Computer repair service",
        "is_popular": True,
        "display_order": 21,
        "icon_key": "tool",
        "description": "Hardware diagnostics, motherboard soldering, OS reinstallation, and virus cleanup."
    },
    {
        "id": "computer-store",
        "name": "Computer Store",
        "slug": "computer-store",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "Computer Hardware & Repair",
        "aliases": ["custom pc", "pc parts", "gaming pc", "computer shop", "refurbished laptops"],
        "schema_type": "Store",
        "gbp_category": "Computer store",
        "is_popular": False,
        "display_order": 22,
        "icon_key": "monitor",
        "description": "Custom workstation assembly, desktop components, peripherals, and server hardware."
    },
    {
        "id": "data-center",
        "name": "Data Center",
        "slug": "data-center",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "Cloud & Infrastructure",
        "aliases": ["colocation", "server hosting", "colo facility", "dedicated servers", "rack space"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Internet service provider",
        "is_popular": False,
        "display_order": 23,
        "icon_key": "server",
        "description": "Tier III/IV secure colocation facilities, dedicated bare-metal hosting, and power redundancy."
    },
    {
        "id": "digital-transformation-consultant",
        "name": "Digital Transformation Consultant",
        "slug": "digital-transformation-consultant",
        "group": "Information Technology (IT)",
        "parent_group": "Information Technology (IT)",
        "subcategory": "IT Consulting & Advisory",
        "aliases": ["digital modernization", "workflow modernization", "erp consultant", "it strategy"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Management consultant",
        "is_popular": False,
        "display_order": 24,
        "icon_key": "activity",
        "description": "Legacy system modernization, paperless workflow migration, and enterprise agility."
    },

    # =========================================================================
    # 2. Software & SaaS
    # =========================================================================
    {
        "id": "software-company",
        "name": "Software Company",
        "slug": "software-company",
        "group": "Software & SaaS",
        "parent_group": "Software & SaaS",
        "subcategory": "Software Development",
        "aliases": ["software", "software developer", "software development", "tech software", "software house"],
        "schema_type": "SoftwareApplication",
        "gbp_category": "Software company",
        "is_popular": True,
        "display_order": 30,
        "icon_key": "code",
        "description": "Custom proprietary software engineering, enterprise applications, and platform architecture."
    },
    {
        "id": "software-development-company",
        "name": "Software Development Company",
        "slug": "software-development-company",
        "group": "Software & SaaS",
        "parent_group": "Software & SaaS",
        "subcategory": "Software Development",
        "aliases": ["custom software", "software engineering", "full stack development", "backend development", "api development"],
        "schema_type": "SoftwareApplication",
        "gbp_category": "Software company",
        "is_popular": True,
        "display_order": 31,
        "icon_key": "code-xml",
        "description": "Bespoke web application development, microservices, REST/GraphQL APIs, and architecture."
    },
    {
        "id": "web-development-company",
        "name": "Web Development Company",
        "slug": "web-development-company",
        "group": "Software & SaaS",
        "parent_group": "Software & SaaS",
        "subcategory": "Web & Mobile Development",
        "aliases": ["web developer", "website development", "web dev", "custom web app", "frontend developer"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Website designer",
        "is_popular": True,
        "display_order": 32,
        "icon_key": "globe",
        "description": "High-performance responsive websites, React/Next.js applications, and e-commerce portals."
    },
    {
        "id": "app-development-company",
        "name": "App Development Company",
        "slug": "app-development-company",
        "group": "Software & SaaS",
        "parent_group": "Software & SaaS",
        "subcategory": "Web & Mobile Development",
        "aliases": ["app developer", "mobile app development", "ios developer", "android developer", "flutter developer", "react native"],
        "schema_type": "SoftwareApplication",
        "gbp_category": "Software company",
        "is_popular": True,
        "display_order": 33,
        "icon_key": "smartphone",
        "description": "Native iOS, Android, and cross-platform mobile applications with offline sync and cloud APIs."
    },
    {
        "id": "saas-company",
        "name": "SaaS Company",
        "slug": "saas-company",
        "group": "Software & SaaS",
        "parent_group": "Software & SaaS",
        "subcategory": "Cloud Software",
        "aliases": ["software as a service", "cloud software", "b2b saas", "saas platform", "subscription software"],
        "schema_type": "SoftwareApplication",
        "gbp_category": "Software company",
        "is_popular": True,
        "display_order": 34,
        "icon_key": "cloud-lightning",
        "description": "Cloud-hosted multi-tenant software platforms, subscription billing, and enterprise tooling."
    },
    {
        "id": "ai-company",
        "name": "AI Company",
        "slug": "ai-company",
        "group": "Software & SaaS",
        "parent_group": "Software & SaaS",
        "subcategory": "Artificial Intelligence & ML",
        "aliases": ["artificial intelligence", "ai developer", "machine learning", "generative ai", "llm", "ai startups"],
        "schema_type": "SoftwareApplication",
        "gbp_category": "Software company",
        "is_popular": True,
        "display_order": 35,
        "icon_key": "bot",
        "description": "Machine learning model development, Generative AI integration, and predictive algorithms."
    },
    {
        "id": "ai-consultant",
        "name": "AI Consultant",
        "slug": "ai-consultant",
        "group": "Software & SaaS",
        "parent_group": "Software & SaaS",
        "subcategory": "Artificial Intelligence & ML",
        "aliases": ["ai consulting", "llm consultant", "ai strategy", "machine learning consultant", "prompt engineering"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer consultant",
        "is_popular": True,
        "display_order": 36,
        "icon_key": "cpu",
        "description": "AI feasibility studies, enterprise LLM implementation, agent workflows, and AI compliance."
    },
    {
        "id": "automation-company",
        "name": "Business Automation Company",
        "slug": "automation-company",
        "group": "Software & SaaS",
        "parent_group": "Software & SaaS",
        "subcategory": "Artificial Intelligence & ML",
        "aliases": ["rpa", "process automation", "zapier expert", "make automation", "workflow automation"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Business management consultant",
        "is_popular": False,
        "display_order": 37,
        "icon_key": "repeat",
        "description": "Robotic process automation (RPA), webhook integrations, and automated operational pipelines."
    },
    {
        "id": "database-consultant",
        "name": "Database Consultant",
        "slug": "database-consultant",
        "group": "Software & SaaS",
        "parent_group": "Software & SaaS",
        "subcategory": "Database & DevOps",
        "aliases": ["dba", "database administrator", "postgresql consultant", "sql optimization", "database migration"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer consultant",
        "is_popular": False,
        "display_order": 38,
        "icon_key": "database",
        "description": "Database clustering, query performance tuning, sharding, and high-availability setups."
    },
    {
        "id": "devops-consultant",
        "name": "DevOps Consultant",
        "slug": "devops-consultant",
        "group": "Software & SaaS",
        "parent_group": "Software & SaaS",
        "subcategory": "Database & DevOps",
        "aliases": ["ci cd", "kubernetes consultant", "docker", "terraform", "site reliability engineering", "sre"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer consultant",
        "is_popular": False,
        "display_order": 39,
        "icon_key": "git-branch",
        "description": "Automated CI/CD deployment pipelines, Infrastructure as Code, and Kubernetes orchestration."
    },

    # =========================================================================
    # 3. Healthcare & Medical
    # =========================================================================
    {
        "id": "doctor",
        "name": "Doctor",
        "slug": "doctor",
        "group": "Healthcare & Medical",
        "parent_group": "Healthcare & Medical",
        "subcategory": "Primary Medical Care",
        "aliases": ["physician", "general practitioner", "gp", "family doctor", "family practice", "md", "internist"],
        "schema_type": "Physician",
        "gbp_category": "Doctor",
        "is_popular": True,
        "display_order": 40,
        "icon_key": "stethoscope",
        "description": "Board-certified general medical practitioners, preventative checkups, and chronic disease management."
    },
    {
        "id": "medical-clinic",
        "name": "Medical Clinic",
        "slug": "medical-clinic",
        "group": "Healthcare & Medical",
        "parent_group": "Healthcare & Medical",
        "subcategory": "Primary Medical Care",
        "aliases": ["health clinic", "polyclinic", "medical center", "walk in clinic", "outpatient clinic"],
        "schema_type": "MedicalClinic",
        "gbp_category": "Medical clinic",
        "is_popular": True,
        "display_order": 41,
        "icon_key": "building",
        "description": "Outpatient primary and multi-specialty healthcare facilities."
    },
    {
        "id": "urgent-care-center",
        "name": "Urgent Care Center",
        "slug": "urgent-care-center",
        "group": "Healthcare & Medical",
        "parent_group": "Healthcare & Medical",
        "subcategory": "Emergency & Urgent Care",
        "aliases": ["walk in urgent care", "immediate care", "after hours clinic", "emergency walk in"],
        "schema_type": "MedicalClinic",
        "gbp_category": "Urgent care center",
        "is_popular": False,
        "display_order": 42,
        "icon_key": "activity",
        "description": "Same-day immediate non-life-threatening illness and injury treatment."
    },
    {
        "id": "hospital",
        "name": "Hospital",
        "slug": "hospital",
        "group": "Healthcare & Medical",
        "parent_group": "Healthcare & Medical",
        "subcategory": "Hospital & Emergency Care",
        "aliases": ["general hospital", "emergency room", "medical center hospital", "trauma center"],
        "schema_type": "Hospital",
        "gbp_category": "Hospital",
        "is_popular": False,
        "display_order": 43,
        "icon_key": "hospital",
        "description": "24/7 inpatient medical care, emergency departments, and surgical facilities."
    },
    {
        "id": "chiropractor",
        "name": "Chiropractor",
        "slug": "chiropractor",
        "group": "Healthcare & Medical",
        "parent_group": "Healthcare & Medical",
        "subcategory": "Physical Therapy & Rehabilitation",
        "aliases": ["chiropractic clinic", "back pain specialist", "spine adjustment", "neck pain doctor"],
        "schema_type": "Physician",
        "gbp_category": "Chiropractor",
        "is_popular": True,
        "display_order": 44,
        "icon_key": "user-check",
        "description": "Spinal alignment, posture correction, and musculoskeletal pain relief."
    },
    {
        "id": "physiotherapist",
        "name": "Physiotherapist",
        "slug": "physiotherapist",
        "group": "Healthcare & Medical",
        "parent_group": "Healthcare & Medical",
        "subcategory": "Physical Therapy & Rehabilitation",
        "aliases": ["physical therapy", "physical therapist", "pt clinic", "sports physiotherapy", "rehab clinic"],
        "schema_type": "MedicalClinic",
        "gbp_category": "Physiotherapist",
        "is_popular": True,
        "display_order": 45,
        "icon_key": "activity",
        "description": "Post-injury rehabilitation, mobility restoration, and sports recovery."
    },
    {
        "id": "optometrist",
        "name": "Optometrist",
        "slug": "optometrist",
        "group": "Healthcare & Medical",
        "parent_group": "Healthcare & Medical",
        "subcategory": "Eye & Vision Care",
        "aliases": ["eye doctor", "eye exam", "glasses clinic", "optometry clinic", "contact lenses", "ophthalmologist"],
        "schema_type": "Optician",
        "gbp_category": "Optometrist",
        "is_popular": True,
        "display_order": 46,
        "icon_key": "eye",
        "description": "Comprehensive vision testing, prescription eyewear, and glaucoma screenings."
    },
    {
        "id": "dermatologist",
        "name": "Dermatologist",
        "slug": "dermatologist",
        "group": "Healthcare & Medical",
        "parent_group": "Healthcare & Medical",
        "subcategory": "Specialized Medical",
        "aliases": ["skin doctor", "skin care clinic", "acne specialist", "mole removal", "skin cancer check"],
        "schema_type": "Physician",
        "gbp_category": "Dermatologist",
        "is_popular": False,
        "display_order": 47,
        "icon_key": "user",
        "description": "Clinical skin disease treatments, acne care, eczema, and skin cancer evaluations."
    },
    {
        "id": "psychologist",
        "name": "Psychologist",
        "slug": "psychologist",
        "group": "Healthcare & Medical",
        "parent_group": "Healthcare & Medical",
        "subcategory": "Mental Health & Counseling",
        "aliases": ["therapist", "mental health counselor", "counseling service", "psychotherapy", "marriage counselor", "psychiatrist"],
        "schema_type": "MedicalClinic",
        "gbp_category": "Psychologist",
        "is_popular": False,
        "display_order": 48,
        "icon_key": "heart",
        "description": "Cognitive behavioral therapy, mental health assessments, and family counseling."
    },
    {
        "id": "podiatrist",
        "name": "Podiatrist",
        "slug": "podiatrist",
        "group": "Healthcare & Medical",
        "parent_group": "Healthcare & Medical",
        "subcategory": "Specialized Medical",
        "aliases": ["foot doctor", "foot clinic", "orthotics specialist", "ankle specialist"],
        "schema_type": "Physician",
        "gbp_category": "Podiatrist",
        "is_popular": False,
        "display_order": 49,
        "icon_key": "user",
        "description": "Diagnosis and medical treatment of foot, ankle, and lower leg disorders."
    },
    {
        "id": "audiologist",
        "name": "Audiologist",
        "slug": "audiologist",
        "group": "Healthcare & Medical",
        "parent_group": "Healthcare & Medical",
        "subcategory": "Specialized Medical",
        "aliases": ["hearing clinic", "hearing aid store", "hearing test", "tinnitus treatment"],
        "schema_type": "MedicalClinic",
        "gbp_category": "Audiologist",
        "is_popular": False,
        "display_order": 50,
        "icon_key": "volume-2",
        "description": "Hearing loss diagnostics, digital hearing aid fittings, and balance evaluations."
    },

    # =========================================================================
    # 4. Dental & Oral Health
    # =========================================================================
    {
        "id": "dentist",
        "name": "Dentist",
        "slug": "dentist",
        "group": "Dental & Oral Health",
        "parent_group": "Dental & Oral Health",
        "subcategory": "General Dentistry",
        "aliases": ["dental clinic", "dental office", "teeth cleaning", "general dentist", "family dentist", "tooth extraction", "dental practice"],
        "schema_type": "Dentist",
        "gbp_category": "Dentist",
        "is_popular": True,
        "display_order": 51,
        "icon_key": "smile",
        "description": "Comprehensive dental exams, cleanings, cavity fillings, and oral healthcare."
    },
    {
        "id": "dental-clinic",
        "name": "Dental Clinic",
        "slug": "dental-clinic",
        "group": "Dental & Oral Health",
        "parent_group": "Dental & Oral Health",
        "subcategory": "General Dentistry",
        "aliases": ["dental center", "dental surgery", "dental hospital"],
        "schema_type": "Dentist",
        "gbp_category": "Dental clinic",
        "is_popular": True,
        "display_order": 52,
        "icon_key": "smile",
        "description": "Multi-chair oral surgery and family dental facilities."
    },
    {
        "id": "orthodontist",
        "name": "Orthodontist",
        "slug": "orthodontist",
        "group": "Dental & Oral Health",
        "parent_group": "Dental & Oral Health",
        "subcategory": "Specialized Dentistry",
        "aliases": ["braces", "invisalign", "teeth straightening", "orthodontic clinic"],
        "schema_type": "Dentist",
        "gbp_category": "Orthodontist",
        "is_popular": False,
        "display_order": 53,
        "icon_key": "smile",
        "description": "Clear aligners, traditional metal braces, and bite correction specialists."
    },
    {
        "id": "cosmetic-dentist",
        "name": "Cosmetic Dentist",
        "slug": "cosmetic-dentist",
        "group": "Dental & Oral Health",
        "parent_group": "Dental & Oral Health",
        "subcategory": "Cosmetic Dentistry",
        "aliases": ["teeth whitening", "veneers", "smile makeover", "dental implants"],
        "schema_type": "Dentist",
        "gbp_category": "Cosmetic dentist",
        "is_popular": False,
        "display_order": 54,
        "icon_key": "sparkles",
        "description": "Porcelain veneers, professional laser whitening, and smile design."
    },
    {
        "id": "pediatric-dentist",
        "name": "Pediatric Dentist",
        "slug": "pediatric-dentist",
        "group": "Dental & Oral Health",
        "parent_group": "Dental & Oral Health",
        "subcategory": "Specialized Dentistry",
        "aliases": ["childrens dentist", "kids dentist", "pediatric dental clinic"],
        "schema_type": "Dentist",
        "gbp_category": "Pediatric dentist",
        "is_popular": False,
        "display_order": 55,
        "icon_key": "smile",
        "description": "Gentle oral healthcare and preventative checkups tailored for infants and teens."
    },
    {
        "id": "emergency-dental-service",
        "name": "Emergency Dental Service",
        "slug": "emergency-dental-service",
        "group": "Dental & Oral Health",
        "parent_group": "Dental & Oral Health",
        "subcategory": "Emergency Dentistry",
        "aliases": ["24 hour dentist", "urgent dental care", "weekend dentist", "emergency tooth extraction"],
        "schema_type": "Dentist",
        "gbp_category": "Emergency dental service",
        "is_popular": False,
        "display_order": 56,
        "icon_key": "alert-circle",
        "description": "Immediate relief for severe toothaches, chipped teeth, and knocked-out crowns."
    },

    # =========================================================================
    # 5. Home Services & Trades
    # =========================================================================
    {
        "id": "plumber",
        "name": "Plumber",
        "slug": "plumber",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Plumbing & Drainage",
        "aliases": ["plumbing contractor", "emergency plumber", "drain cleaning", "water heater repair", "pipe repair", "leak detection"],
        "schema_type": "Plumber",
        "gbp_category": "Plumber",
        "is_popular": True,
        "display_order": 60,
        "icon_key": "wrench",
        "description": "Residential and commercial pipe repair, drain unclogging, and water heater installs."
    },
    {
        "id": "electrician",
        "name": "Electrician",
        "slug": "electrician",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Electrical & Wiring",
        "aliases": ["electrical contractor", "emergency electrician", "wiring repair", "lighting installation", "circuit breaker repair"],
        "schema_type": "Electrician",
        "gbp_category": "Electrician",
        "is_popular": True,
        "display_order": 61,
        "icon_key": "zap",
        "description": "Licensed electrical panel upgrades, EV chargers, lighting design, and rewiring."
    },
    {
        "id": "hvac-contractor",
        "name": "HVAC Contractor",
        "slug": "hvac-contractor",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Heating & Cooling",
        "aliases": ["air conditioning contractor", "heating contractor", "ac repair", "furnace repair", "hvac repair", "air conditioning repair service"],
        "schema_type": "HVACBusiness",
        "gbp_category": "HVAC contractor",
        "is_popular": True,
        "display_order": 62,
        "icon_key": "thermometer",
        "description": "Central AC installation, heat pump maintenance, duct cleaning, and furnace repair."
    },
    {
        "id": "roofing-contractor",
        "name": "Roofing Contractor",
        "slug": "roofing-contractor",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Roofing & Gutters",
        "aliases": ["roofer", "roof repair", "roof replacement", "gutter installation", "shingle repair", "commercial roofing"],
        "schema_type": "RoofingContractor",
        "gbp_category": "Roofing contractor",
        "is_popular": True,
        "display_order": 63,
        "icon_key": "home",
        "description": "Asphalt shingle replacements, metal roofs, storm damage repair, and gutter systems."
    },
    {
        "id": "locksmith",
        "name": "Locksmith",
        "slug": "locksmith",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Locks & Security",
        "aliases": ["emergency locksmith", "car locksmith", "door lock repair", "key duplication", "lockout service"],
        "schema_type": "Locksmith",
        "gbp_category": "Locksmith",
        "is_popular": True,
        "display_order": 64,
        "icon_key": "key",
        "description": "24/7 lockout response, smart deadbolt installation, and key rekeying."
    },
    {
        "id": "pest-control-service",
        "name": "Pest Control Service",
        "slug": "pest-control-service",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Pest Management",
        "aliases": ["exterminator", "termite treatment", "bed bug exterminator", "rodent control", "mosquito control"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Pest control service",
        "is_popular": False,
        "display_order": 65,
        "icon_key": "shield-alert",
        "description": "Safe residential extermination for termites, rodents, insects, and wildlife."
    },
    {
        "id": "landscaper",
        "name": "Landscaper",
        "slug": "landscaper",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Lawn & Landscaping",
        "aliases": ["landscaping contractor", "lawn care", "lawn mowing", "garden design", "hardscaping", "irrigation system"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Landscape designer",
        "is_popular": False,
        "display_order": 66,
        "icon_key": "sun",
        "description": "Custom patio stone hardscaping, sod installation, lawn mowing, and irrigation."
    },
    {
        "id": "tree-service",
        "name": "Tree Service",
        "slug": "tree-service",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Lawn & Landscaping",
        "aliases": ["tree removal", "tree trimming", "arborist", "stump grinding", "emergency tree service"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Tree service",
        "is_popular": False,
        "display_order": 67,
        "icon_key": "tree",
        "description": "Certified arborist assessments, hazardous tree removal, trimming, and stump grinding."
    },
    {
        "id": "painter",
        "name": "Painter",
        "slug": "painter",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Painting & Finishing",
        "aliases": ["painting contractor", "house painter", "interior painter", "exterior painter", "commercial painter"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Painter",
        "is_popular": False,
        "display_order": 68,
        "icon_key": "pen-tool",
        "description": "Interior and exterior house painting, cabinet refinishing, and drywall patching."
    },
    {
        "id": "carpenter",
        "name": "Carpenter",
        "slug": "carpenter",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Carpentry & Woodwork",
        "aliases": ["custom carpentry", "cabinet maker", "framing carpenter", "trim carpentry", "woodworker"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Carpenter",
        "is_popular": False,
        "display_order": 69,
        "icon_key": "hammer",
        "description": "Custom cabinetry, crown molding, deck building, and structural wood framing."
    },
    {
        "id": "flooring-contractor",
        "name": "Flooring Contractor",
        "slug": "flooring-contractor",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Flooring & Tile",
        "aliases": ["hardwood floor installation", "tile contractor", "carpet installer", "laminate flooring", "floor refinishing"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Flooring contractor",
        "is_popular": False,
        "display_order": 70,
        "icon_key": "layers",
        "description": "Hardwood floor sanding, luxury vinyl plank (LVP), and ceramic tile installation."
    },
    {
        "id": "garage-door-supplier",
        "name": "Garage Door Supplier",
        "slug": "garage-door-supplier",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Garage & Doors",
        "aliases": ["garage door repair", "garage door installation", "garage door opener", "broken spring repair"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Garage door supplier",
        "is_popular": False,
        "display_order": 71,
        "icon_key": "archive",
        "description": "Overhead garage door repairs, torsion spring replacements, and smart openers."
    },
    {
        "id": "handyman",
        "name": "Handyman",
        "slug": "handyman",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "General Maintenance",
        "aliases": ["handyman service", "home repairs", "odd jobs", "fixture installation"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Handyman/Handywoman/Handyperson",
        "is_popular": True,
        "display_order": 72,
        "icon_key": "tool",
        "description": "General home repairs, furniture assembly, TV mounting, and maintenance."
    },
    {
        "id": "solar-energy-company",
        "name": "Solar Energy Company",
        "slug": "solar-energy-company",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Renewable Energy",
        "aliases": ["solar installer", "solar panels", "solar power", "battery storage", "solar contractor"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Solar energy company",
        "is_popular": False,
        "display_order": 73,
        "icon_key": "sun",
        "description": "Rooftop photovoltaic solar panel installation and battery backup storage."
    },
    {
        "id": "swimming-pool-repair-service",
        "name": "Swimming Pool Repair Service",
        "slug": "swimming-pool-repair-service",
        "group": "Home Services & Trades",
        "parent_group": "Home Services & Trades",
        "subcategory": "Pool & Spa",
        "aliases": ["pool cleaning", "pool contractor", "pool maintenance", "pool leak repair"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Swimming pool repair service",
        "is_popular": False,
        "display_order": 74,
        "icon_key": "droplet",
        "description": "Weekly pool water balancing, pump repairs, liner replacements, and opening/closing."
    },

    # =========================================================================
    # 6. Construction & Building
    # =========================================================================
    {
        "id": "general-contractor",
        "name": "General Contractor",
        "slug": "general-contractor",
        "group": "Construction & Building",
        "parent_group": "Construction & Building",
        "subcategory": "General Construction",
        "aliases": ["construction company", "construction contractor", "builder", "home remodeler", "kitchen remodeling", "bathroom remodeling", "home addition", "custom home builder"],
        "schema_type": "GeneralContractor",
        "gbp_category": "General contractor",
        "is_popular": True,
        "display_order": 80,
        "icon_key": "hard-hat",
        "description": "Turnkey home building, major kitchen/bath renovations, and commercial tenant build-outs."
    },
    {
        "id": "home-builder",
        "name": "Home Builder",
        "slug": "home-builder",
        "group": "Construction & Building",
        "parent_group": "Construction & Building",
        "subcategory": "Residential Construction",
        "aliases": ["custom home builder", "residential builder", "new home construction"],
        "schema_type": "GeneralContractor",
        "gbp_category": "Custom home builder",
        "is_popular": False,
        "display_order": 81,
        "icon_key": "home",
        "description": "Custom luxury home design, architectural drafting, and ground-up builds."
    },
    {
        "id": "commercial-construction",
        "name": "Commercial Construction Company",
        "slug": "commercial-construction",
        "group": "Construction & Building",
        "parent_group": "Construction & Building",
        "subcategory": "Commercial Construction",
        "aliases": ["commercial builder", "commercial contractor", "retail construction", "warehouse builder"],
        "schema_type": "GeneralContractor",
        "gbp_category": "Commercial real estate inspector",
        "is_popular": False,
        "display_order": 82,
        "icon_key": "building",
        "description": "Industrial warehouse, retail shopping center, and corporate office build-outs."
    },
    {
        "id": "demolition-contractor",
        "name": "Demolition Contractor",
        "slug": "demolition-contractor",
        "group": "Construction & Building",
        "parent_group": "Construction & Building",
        "subcategory": "Specialized Construction",
        "aliases": ["building demolition", "concrete removal", "excavation company"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Demolition contractor",
        "is_popular": False,
        "display_order": 83,
        "icon_key": "trash-2",
        "description": "Safe structural demolition, concrete breaking, and site preparation excavation."
    },

    # =========================================================================
    # 7. Legal & Law
    # =========================================================================
    {
        "id": "law-firm",
        "name": "Law Firm",
        "slug": "law-firm",
        "group": "Legal & Law",
        "parent_group": "Legal & Law",
        "subcategory": "General Legal Practice",
        "aliases": ["lawyer", "attorney", "legal services", "legal practice", "attorneys", "law office"],
        "schema_type": "LegalService",
        "gbp_category": "Law firm",
        "is_popular": True,
        "display_order": 90,
        "icon_key": "scale",
        "description": "Comprehensive legal representation, client advocacy, and litigation counsel."
    },
    {
        "id": "personal-injury-attorney",
        "name": "Personal Injury Attorney",
        "slug": "personal-injury-attorney",
        "group": "Legal & Law",
        "parent_group": "Legal & Law",
        "subcategory": "Personal Injury Law",
        "aliases": ["accident lawyer", "car accident attorney", "injury lawyer", "slip and fall lawyer", "wrongful death attorney"],
        "schema_type": "LegalService",
        "gbp_category": "Personal injury attorney",
        "is_popular": True,
        "display_order": 91,
        "icon_key": "scale",
        "description": "Dedicated representation for motor vehicle collisions and severe accident injury claims."
    },
    {
        "id": "family-law-attorney",
        "name": "Family Law Attorney",
        "slug": "family-law-attorney",
        "group": "Legal & Law",
        "parent_group": "Legal & Law",
        "subcategory": "Family & Divorce Law",
        "aliases": ["divorce lawyer", "child custody lawyer", "family lawyer", "prenup attorney"],
        "schema_type": "LegalService",
        "gbp_category": "Family law attorney",
        "is_popular": False,
        "display_order": 92,
        "icon_key": "users",
        "description": "Compassionate divorce mediation, child custody, alimony, and asset division."
    },
    {
        "id": "criminal-defense-attorney",
        "name": "Criminal Defense Attorney",
        "slug": "criminal-defense-attorney",
        "group": "Legal & Law",
        "parent_group": "Legal & Law",
        "subcategory": "Criminal Defense",
        "aliases": ["dui lawyer", "criminal lawyer", "defense attorney", "traffic ticket lawyer"],
        "schema_type": "LegalService",
        "gbp_category": "Criminal justice attorney",
        "is_popular": False,
        "display_order": 93,
        "icon_key": "shield",
        "description": "Aggressive defense for DUI charges, state and federal felonies, and misdemeanors."
    },
    {
        "id": "estate-planning-attorney",
        "name": "Estate Planning Attorney",
        "slug": "estate-planning-attorney",
        "group": "Legal & Law",
        "parent_group": "Legal & Law",
        "subcategory": "Estate & Probate Law",
        "aliases": ["probate lawyer", "wills and trusts", "living will attorney", "asset protection lawyer"],
        "schema_type": "LegalService",
        "gbp_category": "Estate planning attorney",
        "is_popular": False,
        "display_order": 94,
        "icon_key": "file-text",
        "description": "Revocable living trusts, last will and testaments, and probate administration."
    },
    {
        "id": "real-estate-attorney",
        "name": "Real Estate Attorney",
        "slug": "real-estate-attorney",
        "group": "Legal & Law",
        "parent_group": "Legal & Law",
        "subcategory": "Property & Real Estate Law",
        "aliases": ["property lawyer", "closing attorney", "title dispute lawyer", "commercial lease attorney"],
        "schema_type": "LegalService",
        "gbp_category": "Real estate attorney",
        "is_popular": False,
        "display_order": 95,
        "icon_key": "home",
        "description": "Residential/commercial closings, title examinations, and zoning dispute resolution."
    },
    {
        "id": "immigration-attorney",
        "name": "Immigration Attorney",
        "slug": "immigration-attorney",
        "group": "Legal & Law",
        "parent_group": "Legal & Law",
        "subcategory": "Immigration Law",
        "aliases": ["visa lawyer", "green card attorney", "citizenship lawyer", "asylum attorney"],
        "schema_type": "LegalService",
        "gbp_category": "Immigration attorney",
        "is_popular": False,
        "display_order": 96,
        "icon_key": "globe",
        "description": "Employment visas (H-1B, L-1), family green cards, and naturalization filings."
    },
    {
        "id": "employment-attorney",
        "name": "Employment Attorney",
        "slug": "employment-attorney",
        "group": "Legal & Law",
        "parent_group": "Legal & Law",
        "subcategory": "Corporate & Labor Law",
        "aliases": ["labor lawyer", "wrongful termination lawyer", "workplace discrimination attorney"],
        "schema_type": "LegalService",
        "gbp_category": "Employment attorney",
        "is_popular": False,
        "display_order": 97,
        "icon_key": "briefcase",
        "description": "Labor law compliance, wage & hour claims, and wrongful termination litigation."
    },
    {
        "id": "bankruptcy-attorney",
        "name": "Bankruptcy Attorney",
        "slug": "bankruptcy-attorney",
        "group": "Legal & Law",
        "parent_group": "Legal & Law",
        "subcategory": "Financial Legal Practice",
        "aliases": ["debt relief lawyer", "chapter 7 lawyer", "chapter 13 attorney"],
        "schema_type": "LegalService",
        "gbp_category": "Bankruptcy attorney",
        "is_popular": False,
        "display_order": 98,
        "icon_key": "dollar-sign",
        "description": "Chapter 7 liquidation, Chapter 13 reorganization, and debt relief counsel."
    },

    # =========================================================================
    # 8. Professional Services & Consulting
    # =========================================================================
    {
        "id": "accountant",
        "name": "Accountant",
        "slug": "accountant",
        "group": "Professional Services",
        "parent_group": "Professional Services",
        "subcategory": "Accounting & Bookkeeping",
        "aliases": ["cpa", "certified public accountant", "accounting firm", "bookkeeper", "tax accountant", "business accounting"],
        "schema_type": "AccountingService",
        "gbp_category": "Accountant",
        "is_popular": True,
        "display_order": 100,
        "icon_key": "calculator",
        "description": "Corporate financial statements, auditing, QuickBooks bookkeeping, and fractional CFO."
    },
    {
        "id": "tax-preparation-service",
        "name": "Tax Preparation Service",
        "slug": "tax-preparation-service",
        "group": "Professional Services",
        "parent_group": "Professional Services",
        "subcategory": "Accounting & Bookkeeping",
        "aliases": ["tax preparer", "irs tax help", "tax filing", "income tax return"],
        "schema_type": "AccountingService",
        "gbp_category": "Tax preparation service",
        "is_popular": False,
        "display_order": 101,
        "icon_key": "file-text",
        "description": "Individual and corporate income tax return preparation and IRS audit representation."
    },
    {
        "id": "financial-planner",
        "name": "Financial Planner",
        "slug": "financial-planner",
        "group": "Professional Services",
        "parent_group": "Professional Services",
        "subcategory": "Financial Advisory",
        "aliases": ["wealth management", "financial advisor", "retirement planner", "investment advisor"],
        "schema_type": "FinancialService",
        "gbp_category": "Financial planner",
        "is_popular": False,
        "display_order": 102,
        "icon_key": "trending-up",
        "description": "Fiduciary wealth management, 401(k) rollover strategies, and retirement planning."
    },
    {
        "id": "insurance-agency",
        "name": "Insurance Agency",
        "slug": "insurance-agency",
        "group": "Professional Services",
        "parent_group": "Professional Services",
        "subcategory": "Insurance Services",
        "aliases": ["insurance broker", "auto insurance", "home insurance", "business insurance", "life insurance", "commercial insurance"],
        "schema_type": "InsuranceAgency",
        "gbp_category": "Insurance agency",
        "is_popular": True,
        "display_order": 103,
        "icon_key": "shield",
        "description": "Independent brokerage comparing commercial general liability, auto, home, and life."
    },
    {
        "id": "business-consultant",
        "name": "Business Consultant",
        "slug": "business-consultant",
        "group": "Professional Services",
        "parent_group": "Professional Services",
        "subcategory": "Business Advisory",
        "aliases": ["management consultant", "strategy consultant", "business advisor", "business coach"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Business management consultant",
        "is_popular": False,
        "display_order": 104,
        "icon_key": "briefcase",
        "description": "Operational efficiency auditing, executive leadership coaching, and scaling strategies."
    },
    {
        "id": "notary-public",
        "name": "Notary Public",
        "slug": "notary-public",
        "group": "Professional Services",
        "parent_group": "Professional Services",
        "subcategory": "Legal & Notary Support",
        "aliases": ["mobile notary", "notarization service", "loan signing agent"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Notary public",
        "is_popular": False,
        "display_order": 105,
        "icon_key": "check-square",
        "description": "Document verification, mobile mortgage signing services, and apostille certification."
    },

    # =========================================================================
    # 9. Digital Marketing & Advertising
    # =========================================================================
    {
        "id": "marketing-agency",
        "name": "Marketing Agency",
        "slug": "marketing-agency",
        "group": "Digital Marketing & Advertising",
        "parent_group": "Digital Marketing & Advertising",
        "subcategory": "Digital Marketing",
        "aliases": ["digital marketing", "advertising agency", "seo agency", "social media marketing", "ppc agency", "local seo", "lead generation"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Marketing agency",
        "is_popular": True,
        "display_order": 110,
        "icon_key": "trending-up",
        "description": "Full-funnel Google Ads, Local SEO optimization, social campaigns, and brand growth."
    },
    {
        "id": "web-designer",
        "name": "Web Designer",
        "slug": "web-designer",
        "group": "Digital Marketing & Advertising",
        "parent_group": "Digital Marketing & Advertising",
        "subcategory": "Creative & Branding",
        "aliases": ["website design", "ui ux design", "graphic designer", "logo design", "brand identity"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Website designer",
        "is_popular": False,
        "display_order": 111,
        "icon_key": "layout",
        "description": "Modern UX/UI wireframing, conversion rate optimization, and brand style guides."
    },
    {
        "id": "seo-agency",
        "name": "SEO Agency",
        "slug": "seo-agency",
        "group": "Digital Marketing & Advertising",
        "parent_group": "Digital Marketing & Advertising",
        "subcategory": "Digital Marketing",
        "aliases": ["search engine optimization", "seo company", "organic search", "local search agency"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Marketing agency",
        "is_popular": True,
        "display_order": 112,
        "icon_key": "search",
        "description": "Technical search optimization, backlink acquisition, and GBP ranking acceleration."
    },

    # =========================================================================
    # 10. Real Estate & Property
    # =========================================================================
    {
        "id": "real-estate-agency",
        "name": "Real Estate Agency",
        "slug": "real-estate-agency",
        "group": "Real Estate & Property",
        "parent_group": "Real Estate & Property",
        "subcategory": "Real Estate Brokerage",
        "aliases": ["real estate broker", "realtor", "realty", "property sales", "homes for sale", "commercial real estate"],
        "schema_type": "RealEstateAgent",
        "gbp_category": "Real estate agency",
        "is_popular": True,
        "display_order": 120,
        "icon_key": "home",
        "description": "Residential home listings, buyer representation, and market valuation reports."
    },
    {
        "id": "real-estate-agent",
        "name": "Real Estate Agent",
        "slug": "real-estate-agent",
        "group": "Real Estate & Property",
        "parent_group": "Real Estate & Property",
        "subcategory": "Real Estate Brokerage",
        "aliases": ["realtor agent", "buying agent", "listing agent", "property specialist"],
        "schema_type": "RealEstateAgent",
        "gbp_category": "Real estate agent",
        "is_popular": False,
        "display_order": 121,
        "icon_key": "user",
        "description": "Licensed residential realtor guiding negotiations, open houses, and contract closing."
    },
    {
        "id": "property-management-company",
        "name": "Property Management Company",
        "slug": "property-management-company",
        "group": "Real Estate & Property",
        "parent_group": "Real Estate & Property",
        "subcategory": "Property Management",
        "aliases": ["rental property manager", "landlord services", "hoa management", "tenant screening"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Property management company",
        "is_popular": False,
        "display_order": 122,
        "icon_key": "building",
        "description": "Tenant rent collection, 24/7 maintenance dispatch, and HOA association governance."
    },
    {
        "id": "home-inspector",
        "name": "Home Inspector",
        "slug": "home-inspector",
        "group": "Real Estate & Property",
        "parent_group": "Real Estate & Property",
        "subcategory": "Property Inspection",
        "aliases": ["building inspection", "property inspector", "roof inspection", "pre-purchase inspection"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Home inspector",
        "is_popular": False,
        "display_order": 123,
        "icon_key": "check-circle",
        "description": "Comprehensive pre-closing structural, electrical, plumbing, and thermal inspections."
    },
    {
        "id": "real-estate-appraiser",
        "name": "Real Estate Appraiser",
        "slug": "real-estate-appraiser",
        "group": "Real Estate & Property",
        "parent_group": "Real Estate & Property",
        "subcategory": "Property Valuation",
        "aliases": ["property appraiser", "home valuation", "commercial appraisal"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Real estate appraiser",
        "is_popular": False,
        "display_order": 124,
        "icon_key": "dollar-sign",
        "description": "Certified real estate appraisals for mortgage underwriting and tax assessments."
    },

    # =========================================================================
    # 11. Automotive & Transportation
    # =========================================================================
    {
        "id": "auto-repair-shop",
        "name": "Auto Repair Shop",
        "slug": "auto-repair-shop",
        "group": "Automotive & Transportation",
        "parent_group": "Automotive & Transportation",
        "subcategory": "Auto Repair & Maintenance",
        "aliases": ["mechanic", "car repair", "auto service", "brake repair", "engine diagnostics", "transmission repair", "oil change"],
        "schema_type": "AutoRepair",
        "gbp_category": "Auto repair shop",
        "is_popular": True,
        "display_order": 130,
        "icon_key": "tool",
        "description": "ASE-certified engine diagnostics, brakes, suspension, and routine manufacturer maintenance."
    },
    {
        "id": "car-dealer",
        "name": "Car Dealer",
        "slug": "car-dealer",
        "group": "Automotive & Transportation",
        "parent_group": "Automotive & Transportation",
        "subcategory": "Auto Dealerships",
        "aliases": ["auto dealership", "new car dealer", "car sales", "vehicle dealership", "car showroom"],
        "schema_type": "AutoDealer",
        "gbp_category": "Car dealer",
        "is_popular": True,
        "display_order": 131,
        "icon_key": "truck",
        "description": "Authorized franchise new car sales, lease specials, and certified warranty service."
    },
    {
        "id": "used-car-dealer",
        "name": "Used Car Dealer",
        "slug": "used-car-dealer",
        "group": "Automotive & Transportation",
        "parent_group": "Automotive & Transportation",
        "subcategory": "Auto Dealerships",
        "aliases": ["pre-owned cars", "second hand cars", "used vehicles"],
        "schema_type": "AutoDealer",
        "gbp_category": "Used car dealer",
        "is_popular": False,
        "display_order": 132,
        "icon_key": "truck",
        "description": "Multi-point inspected pre-owned sedans, SUVs, trucks, and trade-in financing."
    },
    {
        "id": "auto-body-shop",
        "name": "Auto Body Shop",
        "slug": "auto-body-shop",
        "group": "Automotive & Transportation",
        "parent_group": "Automotive & Transportation",
        "subcategory": "Auto Body & Detailing",
        "aliases": ["collision repair", "dent repair", "car paint shop", "auto collision"],
        "schema_type": "AutoRepair",
        "gbp_category": "Auto body shop",
        "is_popular": False,
        "display_order": 133,
        "icon_key": "tool",
        "description": "Insurance collision repair, computerized frame alignment, and color-matched paint."
    },
    {
        "id": "tire-shop",
        "name": "Tire Shop",
        "slug": "tire-shop",
        "group": "Automotive & Transportation",
        "parent_group": "Automotive & Transportation",
        "subcategory": "Tires & Alignment",
        "aliases": ["tire dealer", "wheel alignment", "tire replacement", "flat tire repair"],
        "schema_type": "AutoRepair",
        "gbp_category": "Tire shop",
        "is_popular": False,
        "display_order": 134,
        "icon_key": "disc",
        "description": "Brand-name tire replacements, wheel balancing, and computerized 4-wheel alignment."
    },
    {
        "id": "car-wash",
        "name": "Car Wash",
        "slug": "car-wash",
        "group": "Automotive & Transportation",
        "parent_group": "Automotive & Transportation",
        "subcategory": "Auto Body & Detailing",
        "aliases": ["auto detailing", "car cleaning", "hand car wash", "ceramic coating"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Car wash",
        "is_popular": False,
        "display_order": 135,
        "icon_key": "droplet",
        "description": "Automated tunnel wash, interior shampooing, and hydrophobic ceramic coating."
    },
    {
        "id": "towing-service",
        "name": "Towing Service",
        "slug": "towing-service",
        "group": "Automotive & Transportation",
        "parent_group": "Automotive & Transportation",
        "subcategory": "Roadside Assistance",
        "aliases": ["roadside assistance", "tow truck", "emergency towing", "flatbed towing", "jump start"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Towing service",
        "is_popular": False,
        "display_order": 136,
        "icon_key": "truck",
        "description": "24/7 flatbed emergency recovery, roadside battery jump starts, and lockout service."
    },
    {
        "id": "oil-change-service",
        "name": "Oil Change Service",
        "slug": "oil-change-service",
        "group": "Automotive & Transportation",
        "parent_group": "Automotive & Transportation",
        "subcategory": "Auto Repair & Maintenance",
        "aliases": ["quick lube", "synthetic oil change", "filter replacement"],
        "schema_type": "AutoRepair",
        "gbp_category": "Oil change service",
        "is_popular": False,
        "display_order": 137,
        "icon_key": "droplet",
        "description": "15-minute drive-thru conventional & full synthetic oil and filter replacements."
    },

    # =========================================================================
    # 12. Restaurants & Food
    # =========================================================================
    {
        "id": "restaurant",
        "name": "Restaurant",
        "slug": "restaurant",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Dining & Eateries",
        "aliases": ["dining", "food", "eatery", "bistro", "family restaurant", "dine in", "takeout food"],
        "schema_type": "Restaurant",
        "gbp_category": "Restaurant",
        "is_popular": True,
        "display_order": 140,
        "icon_key": "utensils",
        "description": "Full-service dining, chef specials, reservations, and takeout."
    },
    {
        "id": "cafe",
        "name": "Cafe",
        "slug": "cafe",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Cafes & Coffee",
        "aliases": ["coffee shop", "espresso bar", "coffee roaster", "breakfast cafe"],
        "schema_type": "CafeOrCoffeeShop",
        "gbp_category": "Cafe",
        "is_popular": True,
        "display_order": 141,
        "icon_key": "coffee",
        "description": "Artisan roasted espresso, specialty lattes, cold brew, and fresh breakfast pastries."
    },
    {
        "id": "bakery",
        "name": "Bakery",
        "slug": "bakery",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Bakery & Desserts",
        "aliases": ["cake shop", "pastry shop", "custom cakes", "bread bakery"],
        "schema_type": "Bakery",
        "gbp_category": "Bakery",
        "is_popular": False,
        "display_order": 142,
        "icon_key": "shopping-bag",
        "description": "Artisan sourdough bread, custom wedding cakes, and European pastries."
    },
    {
        "id": "pizza-restaurant",
        "name": "Pizza Restaurant",
        "slug": "pizza-restaurant",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Dining & Eateries",
        "aliases": ["pizzeria", "pizza delivery", "wood fired pizza", "slice shop"],
        "schema_type": "Restaurant",
        "gbp_category": "Pizza restaurant",
        "is_popular": False,
        "display_order": 143,
        "icon_key": "pie-chart",
        "description": "Wood-fired Neapolitan and New York style hand-tossed pizzas."
    },
    {
        "id": "italian-restaurant",
        "name": "Italian Restaurant",
        "slug": "italian-restaurant",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Ethnic Cuisine",
        "aliases": ["pasta restaurant", "trattoria", "italian dining"],
        "schema_type": "Restaurant",
        "gbp_category": "Italian restaurant",
        "is_popular": False,
        "display_order": 144,
        "icon_key": "utensils",
        "description": "Fresh handmade pasta, regional Italian wines, and classic desserts."
    },
    {
        "id": "mexican-restaurant",
        "name": "Mexican Restaurant",
        "slug": "mexican-restaurant",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Ethnic Cuisine",
        "aliases": ["taqueria", "tacos", "burritos", "authentic mexican"],
        "schema_type": "Restaurant",
        "gbp_category": "Mexican restaurant",
        "is_popular": False,
        "display_order": 145,
        "icon_key": "utensils",
        "description": "Street tacos, enchiladas, house-crafted margaritas, and chips & salsa."
    },
    {
        "id": "indian-restaurant",
        "name": "Indian Restaurant",
        "slug": "indian-restaurant",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Ethnic Cuisine",
        "aliases": ["curry house", "tandoori", "biryani", "indian food"],
        "schema_type": "Restaurant",
        "gbp_category": "Indian restaurant",
        "is_popular": False,
        "display_order": 146,
        "icon_key": "utensils",
        "description": "Clay-oven tandoori grills, aromatic curries, and garlic naan."
    },
    {
        "id": "sushi-restaurant",
        "name": "Sushi Restaurant",
        "slug": "sushi-restaurant",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Ethnic Cuisine",
        "aliases": ["japanese restaurant", "sashimi bar", "omakase", "ramen"],
        "schema_type": "Restaurant",
        "gbp_category": "Sushi restaurant",
        "is_popular": False,
        "display_order": 147,
        "icon_key": "utensils",
        "description": "Fresh sashimi, signature maki rolls, and chef-curated omakase dining."
    },
    {
        "id": "chinese-restaurant",
        "name": "Chinese Restaurant",
        "slug": "chinese-restaurant",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Ethnic Cuisine",
        "aliases": ["dim sum", "sichuan food", "cantonese restaurant", "noodle shop"],
        "schema_type": "Restaurant",
        "gbp_category": "Chinese restaurant",
        "is_popular": False,
        "display_order": 148,
        "icon_key": "utensils",
        "description": "Authentic wok-fried specialties, dumplings, Peking duck, and dim sum."
    },
    {
        "id": "fast-food-restaurant",
        "name": "Fast Food Restaurant",
        "slug": "fast-food-restaurant",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Quick Service",
        "aliases": ["drive thru", "burgers", "quick service restaurant", "fast casual"],
        "schema_type": "FastFoodRestaurant",
        "gbp_category": "Fast food restaurant",
        "is_popular": False,
        "display_order": 149,
        "icon_key": "zap",
        "description": "Speedy counter & drive-thru burgers, fried chicken, fries, and shakes."
    },
    {
        "id": "catering-service",
        "name": "Catering Service",
        "slug": "catering-service",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Catering & Events",
        "aliases": ["event catering", "wedding catering", "corporate catering", "buffet service"],
        "schema_type": "FoodEstablishment",
        "gbp_category": "Catering food and drink supplier",
        "is_popular": False,
        "display_order": 150,
        "icon_key": "package",
        "description": "Custom banquet menus, corporate luncheons, and full-service event staffing."
    },
    {
        "id": "bar-and-grill",
        "name": "Bar & Grill",
        "slug": "bar-and-grill",
        "group": "Restaurants & Food",
        "parent_group": "Restaurants & Food",
        "subcategory": "Dining & Eateries",
        "aliases": ["sports bar", "pub", "gastropub", "tavern", "cocktail bar"],
        "schema_type": "BarOrPub",
        "gbp_category": "Bar & grill",
        "is_popular": False,
        "display_order": 151,
        "icon_key": "wine",
        "description": "Craft beers on tap, cocktail mixology, wings, burgers, and live sports screening."
    },

    # =========================================================================
    # 13. Beauty & Personal Care
    # =========================================================================
    {
        "id": "hair-salon",
        "name": "Hair Salon",
        "slug": "hair-salon",
        "group": "Beauty & Personal Care",
        "parent_group": "Beauty & Personal Care",
        "subcategory": "Hair Care",
        "aliases": ["hairdresser", "hair stylist", "haircut", "hair coloring", "balayage", "hair extensions"],
        "schema_type": "HairSalon",
        "gbp_category": "Hair salon",
        "is_popular": True,
        "display_order": 160,
        "icon_key": "scissors",
        "description": "Precision haircuts, custom balayage color, blowouts, and keratin smoothing."
    },
    {
        "id": "barber-shop",
        "name": "Barber Shop",
        "slug": "barber-shop",
        "group": "Beauty & Personal Care",
        "parent_group": "Beauty & Personal Care",
        "subcategory": "Hair Care",
        "aliases": ["barber", "mens haircut", "beard trim", "hot towel shave", "fade haircut"],
        "schema_type": "HairSalon",
        "gbp_category": "Barber shop",
        "is_popular": True,
        "display_order": 161,
        "icon_key": "scissors",
        "description": "Traditional hot lather straight-razor shaves, skin fades, and beard sculpting."
    },
    {
        "id": "nail-salon",
        "name": "Nail Salon",
        "slug": "nail-salon",
        "group": "Beauty & Personal Care",
        "parent_group": "Beauty & Personal Care",
        "subcategory": "Nails & Esthetics",
        "aliases": ["manicure", "pedicure", "gel nails", "acrylic nails", "nail art", "dip powder"],
        "schema_type": "BeautySalon",
        "gbp_category": "Nail salon",
        "is_popular": False,
        "display_order": 162,
        "icon_key": "sparkles",
        "description": "Luxury spa pedicures, acrylic full sets, gel-X extensions, and intricate nail art."
    },
    {
        "id": "day-spa",
        "name": "Day Spa",
        "slug": "day-spa",
        "group": "Beauty & Personal Care",
        "parent_group": "Beauty & Personal Care",
        "subcategory": "Spa & Massage",
        "aliases": ["spa", "massage therapist", "facial spa", "deep tissue massage", "relaxation massage"],
        "schema_type": "DaySpa",
        "gbp_category": "Day spa",
        "is_popular": False,
        "display_order": 163,
        "icon_key": "sun",
        "description": "Swedish & deep tissue massage therapy, organic body scrubs, and steam rooms."
    },
    {
        "id": "medical-spa",
        "name": "Medical Spa",
        "slug": "medical-spa",
        "group": "Beauty & Personal Care",
        "parent_group": "Beauty & Personal Care",
        "subcategory": "Aesthetic Medicine",
        "aliases": ["med spa", "botox clinic", "laser hair removal", "dermal fillers", "microneedling", "hydrafacial"],
        "schema_type": "MedicalClinic",
        "gbp_category": "Medical spa",
        "is_popular": False,
        "display_order": 164,
        "icon_key": "sparkles",
        "description": "Botox, Juvederm dermal fillers, laser skin resurfacing, and medical-grade facials."
    },
    {
        "id": "tattoo-shop",
        "name": "Tattoo Shop",
        "slug": "tattoo-shop",
        "group": "Beauty & Personal Care",
        "parent_group": "Beauty & Personal Care",
        "subcategory": "Body Art",
        "aliases": ["tattoo studio", "tattoo artist", "custom tattoos", "body piercing"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Tattoo shop",
        "is_popular": False,
        "display_order": 165,
        "icon_key": "pen-tool",
        "description": "Custom illustrative tattoo art, sterile body piercings, and cover-up designs."
    },

    # =========================================================================
    # 14. Health, Fitness & Wellness
    # =========================================================================
    {
        "id": "gym",
        "name": "Gym",
        "slug": "gym",
        "group": "Health, Fitness & Wellness",
        "parent_group": "Health, Fitness & Wellness",
        "subcategory": "Fitness Centers",
        "aliases": ["fitness center", "health club", "workout", "crossfit", "strength training", "24 hour gym"],
        "schema_type": "ExerciseGym",
        "gbp_category": "Gym",
        "is_popular": True,
        "display_order": 170,
        "icon_key": "activity",
        "description": "Full free-weight floor, cardio machines, group classes, and locker amenities."
    },
    {
        "id": "personal-trainer",
        "name": "Personal Trainer",
        "slug": "personal-trainer",
        "group": "Health, Fitness & Wellness",
        "parent_group": "Health, Fitness & Wellness",
        "subcategory": "Personal Coaching",
        "aliases": ["fitness coach", "personal training", "private workout", "weight loss coach"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Personal trainer",
        "is_popular": False,
        "display_order": 171,
        "icon_key": "user",
        "description": "One-on-one tailored fitness programming, form coaching, and body composition tracking."
    },
    {
        "id": "yoga-studio",
        "name": "Yoga Studio",
        "slug": "yoga-studio",
        "group": "Health, Fitness & Wellness",
        "parent_group": "Health, Fitness & Wellness",
        "subcategory": "Mind & Body",
        "aliases": ["yoga classes", "hot yoga", "vinyasa yoga", "pilates studio", "meditation"],
        "schema_type": "ExerciseGym",
        "gbp_category": "Yoga studio",
        "is_popular": False,
        "display_order": 172,
        "icon_key": "sun",
        "description": "Vinyasa flow, hot Bikram yoga, breathwork meditation, and reformer Pilates."
    },
    {
        "id": "martial-arts-school",
        "name": "Martial Arts School",
        "slug": "martial-arts-school",
        "group": "Health, Fitness & Wellness",
        "parent_group": "Health, Fitness & Wellness",
        "subcategory": "Combat & Defense",
        "aliases": ["karate school", "bjj", "brazilian jiu jitsu", "taekwondo", "boxing gym", "mma"],
        "schema_type": "School",
        "gbp_category": "Martial arts school",
        "is_popular": False,
        "display_order": 173,
        "icon_key": "shield",
        "description": "Youth and adult Brazilian Jiu-Jitsu, Karate, Muay Thai kickboxing, and self-defense."
    },

    # =========================================================================
    # 15. Hotels & Hospitality
    # =========================================================================
    {
        "id": "hotel",
        "name": "Hotel",
        "slug": "hotel",
        "group": "Hotels & Hospitality",
        "parent_group": "Hotels & Hospitality",
        "subcategory": "Lodging",
        "aliases": ["motel", "boutique hotel", "resort", "lodging", "hotel rooms", "extended stay"],
        "schema_type": "Hotel",
        "gbp_category": "Hotel",
        "is_popular": True,
        "display_order": 180,
        "icon_key": "building",
        "description": "Guest suites with room service, swimming pools, fitness centers, and meeting spaces."
    },
    {
        "id": "bed-and-breakfast",
        "name": "Bed & Breakfast",
        "slug": "bed-and-breakfast",
        "group": "Hotels & Hospitality",
        "parent_group": "Hotels & Hospitality",
        "subcategory": "Lodging",
        "aliases": ["b&b", "inn", "guest house", "country inn"],
        "schema_type": "BedAndBreakfast",
        "gbp_category": "Bed & breakfast",
        "is_popular": False,
        "display_order": 181,
        "icon_key": "home",
        "description": "Charming boutique rooms, personalized hospitality, and gourmet homemade breakfast."
    },

    # =========================================================================
    # 16. Travel & Tourism
    # =========================================================================
    {
        "id": "travel-agency",
        "name": "Travel Agency",
        "slug": "travel-agency",
        "group": "Travel & Tourism",
        "parent_group": "Travel & Tourism",
        "subcategory": "Travel Services",
        "aliases": ["travel agent", "tour operator", "vacation planner", "cruise booking"],
        "schema_type": "TravelAgency",
        "gbp_category": "Travel agency",
        "is_popular": False,
        "display_order": 185,
        "icon_key": "navigation",
        "description": "Curated international vacation packages, flight bookings, and luxury cruise itineraries."
    },

    # =========================================================================
    # 17. Pets & Veterinary
    # =========================================================================
    {
        "id": "veterinarian",
        "name": "Veterinarian",
        "slug": "veterinarian",
        "group": "Pets & Veterinary",
        "parent_group": "Pets & Veterinary",
        "subcategory": "Animal Healthcare",
        "aliases": ["vet clinic", "animal hospital", "vet", "pet doctor", "emergency vet", "pet care"],
        "schema_type": "VeterinaryCare",
        "gbp_category": "Veterinarian",
        "is_popular": True,
        "display_order": 190,
        "icon_key": "heart",
        "description": "Comprehensive pet wellness, vaccinations, dental care, surgery, and diagnostics."
    },
    {
        "id": "pet-groomer",
        "name": "Pet Groomer",
        "slug": "pet-groomer",
        "group": "Pets & Veterinary",
        "parent_group": "Pets & Veterinary",
        "subcategory": "Pet Care Services",
        "aliases": ["dog grooming", "cat grooming", "pet salon", "mobile pet grooming"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Pet groomer",
        "is_popular": False,
        "display_order": 191,
        "icon_key": "scissors",
        "description": "Full-service dog bathing, breed-standard haircuts, nail clipping, and deshedding."
    },
    {
        "id": "pet-boarding-service",
        "name": "Pet Boarding Service",
        "slug": "pet-boarding-service",
        "group": "Pets & Veterinary",
        "parent_group": "Pets & Veterinary",
        "subcategory": "Pet Care Services",
        "aliases": ["dog boarding", "dog daycare", "pet hotel", "kennel", "cat boarding"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Pet boarding service",
        "is_popular": False,
        "display_order": 192,
        "icon_key": "home",
        "description": "Overnight pet lodging with supervised play yards, private suites, and cameras."
    },

    # =========================================================================
    # 18. Retail & E-Commerce
    # =========================================================================
    {
        "id": "clothing-store",
        "name": "Clothing Store",
        "slug": "clothing-store",
        "group": "Retail & E-Commerce",
        "parent_group": "Retail & E-Commerce",
        "subcategory": "Apparel & Fashion",
        "aliases": ["boutique", "apparel store", "fashion store", "mens clothing", "womens clothing"],
        "schema_type": "ClothingStore",
        "gbp_category": "Clothing store",
        "is_popular": False,
        "display_order": 200,
        "icon_key": "shopping-bag",
        "description": "Curated fashion apparel, designer collections, footwear, and accessories."
    },
    {
        "id": "jewelry-store",
        "name": "Jewelry Store",
        "slug": "jewelry-store",
        "group": "Retail & E-Commerce",
        "parent_group": "Retail & E-Commerce",
        "subcategory": "Luxury & Jewelry",
        "aliases": ["jeweler", "diamond rings", "engagement rings", "watch repair", "custom jewelry"],
        "schema_type": "JewelryStore",
        "gbp_category": "Jewelry store",
        "is_popular": False,
        "display_order": 201,
        "icon_key": "sparkles",
        "description": "Custom diamond engagement rings, fine gold jewelry, and luxury watch repairs."
    },
    {
        "id": "furniture-store",
        "name": "Furniture Store",
        "slug": "furniture-store",
        "group": "Retail & E-Commerce",
        "parent_group": "Retail & E-Commerce",
        "subcategory": "Home Furnishings",
        "aliases": ["home furniture", "mattress store", "sofas", "dining room furniture", "office furniture"],
        "schema_type": "FurnitureStore",
        "gbp_category": "Furniture store",
        "is_popular": False,
        "display_order": 202,
        "icon_key": "home",
        "description": "Living room sectionals, solid wood dining tables, and orthotic mattress showrooms."
    },
    {
        "id": "florist",
        "name": "Florist",
        "slug": "florist",
        "group": "Retail & E-Commerce",
        "parent_group": "Retail & E-Commerce",
        "subcategory": "Specialty Retail",
        "aliases": ["flower shop", "flower delivery", "wedding flowers", "bouquets", "floral arrangements"],
        "schema_type": "Florist",
        "gbp_category": "Florist",
        "is_popular": False,
        "display_order": 203,
        "icon_key": "sun",
        "description": "Same-day floral arrangements, wedding centerpiece bouquets, and sympathy sprays."
    },
    {
        "id": "grocery-store",
        "name": "Grocery Store",
        "slug": "grocery-store",
        "group": "Retail & E-Commerce",
        "parent_group": "Retail & E-Commerce",
        "subcategory": "Food & Beverage Retail",
        "aliases": ["supermarket", "organic grocery", "food market", "produce market"],
        "schema_type": "GroceryStore",
        "gbp_category": "Grocery store",
        "is_popular": False,
        "display_order": 204,
        "icon_key": "shopping-cart",
        "description": "Fresh organic farm produce, butcher cuts, international imports, and pantry staples."
    },

    # =========================================================================
    # 19. Events & Entertainment
    # =========================================================================
    {
        "id": "event-venue",
        "name": "Event Venue",
        "slug": "event-venue",
        "group": "Events & Entertainment",
        "parent_group": "Events & Entertainment",
        "subcategory": "Venues & Spaces",
        "aliases": ["wedding venue", "banquet hall", "party hall", "conference center", "reception hall"],
        "schema_type": "EventVenue",
        "gbp_category": "Event venue",
        "is_popular": True,
        "display_order": 210,
        "icon_key": "calendar",
        "description": "Picturesque indoor and outdoor banquet spaces for weddings, galas, and corporate retreats."
    },
    {
        "id": "wedding-photographer",
        "name": "Wedding Photographer",
        "slug": "wedding-photographer",
        "group": "Events & Entertainment",
        "parent_group": "Events & Entertainment",
        "subcategory": "Photography & Video",
        "aliases": ["wedding photography", "bridal photos", "engagement photographer"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Wedding photographer",
        "is_popular": False,
        "display_order": 211,
        "icon_key": "camera",
        "description": "Cinematic high-resolution wedding photography, drone footage, and printed heirloom albums."
    },
    {
        "id": "photographer",
        "name": "Photographer",
        "slug": "photographer",
        "group": "Events & Entertainment",
        "parent_group": "Events & Entertainment",
        "subcategory": "Photography & Video",
        "aliases": ["portrait photographer", "commercial photographer", "headshots", "photo studio"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Photographer",
        "is_popular": True,
        "display_order": 212,
        "icon_key": "camera",
        "description": "Studio corporate executive headshots, family portraits, and commercial product shoots."
    },

    # =========================================================================
    # 20. Logistics & Transportation
    # =========================================================================
    {
        "id": "moving-company",
        "name": "Moving Company",
        "slug": "moving-company",
        "group": "Logistics & Transportation",
        "parent_group": "Logistics & Transportation",
        "subcategory": "Moving & Relocation",
        "aliases": ["movers", "relocation service", "long distance movers", "commercial movers", "packing service"],
        "schema_type": "MovingCompany",
        "gbp_category": "Moving company",
        "is_popular": True,
        "display_order": 220,
        "icon_key": "truck",
        "description": "Insured residential and corporate moving crews, packing supplies, and nationwide freight."
    },
    {
        "id": "self-storage-facility",
        "name": "Self-Storage Facility",
        "slug": "self-storage-facility",
        "group": "Logistics & Transportation",
        "parent_group": "Logistics & Transportation",
        "subcategory": "Warehousing & Storage",
        "aliases": ["storage units", "storage facility", "climate controlled storage", "rv storage", "boat storage"],
        "schema_type": "SelfStorage",
        "gbp_category": "Self-storage facility",
        "is_popular": False,
        "display_order": 221,
        "icon_key": "archive",
        "description": "Secure climate-controlled storage units, 24/7 keypad access, and RV parking."
    },
    {
        "id": "courier-service",
        "name": "Courier & Delivery Service",
        "slug": "courier-service",
        "group": "Logistics & Transportation",
        "parent_group": "Logistics & Transportation",
        "subcategory": "Courier & Freight",
        "aliases": ["courier", "same day delivery", "freight forwarder", "parcel delivery"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Delivery service",
        "is_popular": False,
        "display_order": 222,
        "icon_key": "package",
        "description": "Same-day on-demand parcel dispatch, medical specimen transport, and freight forwarding."
    },

    # =========================================================================
    # 21. Cleaning & Facility Services
    # =========================================================================
    {
        "id": "house-cleaning-service",
        "name": "House Cleaning Service",
        "slug": "house-cleaning-service",
        "group": "Cleaning & Facility Services",
        "parent_group": "Cleaning & Facility Services",
        "subcategory": "Residential Cleaning",
        "aliases": ["maid service", "residential cleaning", "deep cleaning", "move out cleaning"],
        "schema_type": "LocalBusiness",
        "gbp_category": "House cleaning service",
        "is_popular": True,
        "display_order": 230,
        "icon_key": "sparkles",
        "description": "Recurring background-checked maid visits, deep scrubbing, and move-in/move-out details."
    },
    {
        "id": "commercial-cleaning",
        "name": "Commercial Cleaning & Janitorial",
        "slug": "commercial-cleaning",
        "group": "Cleaning & Facility Services",
        "parent_group": "Cleaning & Facility Services",
        "subcategory": "Commercial Janitorial",
        "aliases": ["janitorial service", "office cleaning", "commercial cleaners", "building maintenance"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Janitorial service",
        "is_popular": False,
        "display_order": 231,
        "icon_key": "briefcase",
        "description": "Nightly office sanitization, floor buffing, trash removal, and facility hygiene."
    },
    {
        "id": "window-cleaning-service",
        "name": "Window Cleaning Service",
        "slug": "window-cleaning-service",
        "group": "Cleaning & Facility Services",
        "parent_group": "Cleaning & Facility Services",
        "subcategory": "Specialized Cleaning",
        "aliases": ["window washer", "pressure washing", "power washing", "gutter cleaning"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Window cleaning service",
        "is_popular": False,
        "display_order": 232,
        "icon_key": "sun",
        "description": "Pure-water streak-free exterior window washing, screen wiping, and driveway pressure washing."
    },

    # =========================================================================
    # 22. Education & Training
    # =========================================================================
    {
        "id": "preschool",
        "name": "Preschool",
        "slug": "preschool",
        "group": "Education & Training",
        "parent_group": "Education & Training",
        "subcategory": "Early Childhood Education",
        "aliases": ["daycare", "child care", "early learning center", "nursery school"],
        "schema_type": "Preschool",
        "gbp_category": "Preschool",
        "is_popular": False,
        "display_order": 240,
        "icon_key": "smile",
        "description": "Accredited early childhood curriculum, social development, and full-day daycare."
    },
    {
        "id": "tutoring-service",
        "name": "Tutoring Service",
        "slug": "tutoring-service",
        "group": "Education & Training",
        "parent_group": "Education & Training",
        "subcategory": "Academic Tutoring",
        "aliases": ["tutor", "math tutor", "sat prep", "act prep", "reading tutor"],
        "schema_type": "EducationalOrganization",
        "gbp_category": "Tutoring service",
        "is_popular": False,
        "display_order": 241,
        "icon_key": "book-open",
        "description": "K-12 individualized subject tutoring, SAT/ACT test prep, and homework support."
    },
    {
        "id": "driving-school",
        "name": "Driving School",
        "slug": "driving-school",
        "group": "Education & Training",
        "parent_group": "Education & Training",
        "subcategory": "Vocational & Practical Skills",
        "aliases": ["driving instructor", "behind the wheel training", "drivers ed"],
        "schema_type": "School",
        "gbp_category": "Driving school",
        "is_popular": False,
        "display_order": 242,
        "icon_key": "navigation",
        "description": "State-certified defensive driving courses and behind-the-wheel road test preparation."
    },
    {
        "id": "it-training",
        "name": "IT Training School",
        "slug": "it-training",
        "group": "Education & Training",
        "parent_group": "Education & Training",
        "subcategory": "Technical Education",
        "aliases": ["computer training", "coding bootcamp", "software training", "tech certifications"],
        "schema_type": "School",
        "gbp_category": "Technical school",
        "is_popular": False,
        "display_order": 243,
        "icon_key": "code",
        "description": "Full-stack coding bootcamps, AWS/Cisco certification prep, and tech upskilling."
    },

    # =========================================================================
    # 23. Manufacturing & Industrial
    # =========================================================================
    {
        "id": "manufacturer",
        "name": "Manufacturer",
        "slug": "manufacturer",
        "group": "Manufacturing & Industrial",
        "parent_group": "Manufacturing & Industrial",
        "subcategory": "Industrial Manufacturing",
        "aliases": ["manufacturing company", "factory", "machinery manufacturer", "industrial supplier", "metal fabricator"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Manufacturer",
        "is_popular": False,
        "display_order": 250,
        "icon_key": "cpu",
        "description": "Precision metal fabrication, custom assembly lines, and industrial product manufacturing."
    },

    # =========================================================================
    # 24. Security & Protection
    # =========================================================================
    {
        "id": "security-service",
        "name": "Security Guard & Alarm Service",
        "slug": "security-service",
        "group": "Security & Protection",
        "parent_group": "Security & Protection",
        "subcategory": "Physical Security",
        "aliases": ["security company", "security guard", "cctv installation", "burglar alarm"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Security service",
        "is_popular": False,
        "display_order": 260,
        "icon_key": "shield",
        "description": "CCTV camera installation, central 24/7 alarm monitoring, and uniformed security patrols."
    },

    # =========================================================================
    # 25. Agriculture & Rural Services
    # =========================================================================
    {
        "id": "farm-service",
        "name": "Farm & Agricultural Service",
        "slug": "farm-service",
        "group": "Agriculture & Rural Services",
        "parent_group": "Agriculture & Rural Services",
        "subcategory": "Farming & Agriculture",
        "aliases": ["agriculture supplier", "tractor repair", "nursery", "farm supply"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Agricultural service",
        "is_popular": False,
        "display_order": 270,
        "icon_key": "sun",
        "description": "Agricultural equipment maintenance, soil nutrient testing, and bulk seed supply."
    },

    # =========================================================================
    # 26. Nonprofit & Community
    # =========================================================================
    {
        "id": "nonprofit-organization",
        "name": "Nonprofit Organization",
        "slug": "nonprofit-organization",
        "group": "Nonprofit & Community",
        "parent_group": "Nonprofit & Community",
        "subcategory": "Charity & Community",
        "aliases": ["charity", "ngo", "community foundation", "non-profit"],
        "schema_type": "Organization",
        "gbp_category": "Non-profit organization",
        "is_popular": False,
        "display_order": 280,
        "icon_key": "heart",
        "description": "Tax-exempt 501(c)(3) community outreach, charitable programs, and fundraising initiatives."
    },

    # =========================================================================
    # 27. Other Specialized Businesses
    # =========================================================================
    {
        "id": "local-business",
        "name": "Local Business",
        "slug": "local-business",
        "group": "Other Specialized Businesses",
        "parent_group": "Other Specialized Businesses",
        "subcategory": "General Business",
        "aliases": ["general business", "other business", "commercial entity"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Commercial entity",
        "is_popular": False,
        "display_order": 999,
        "icon_key": "building",
        "description": "General local commercial enterprise with customized service offerings."
    }
]


class CategoryTaxonomy:
    """
    Authoritative taxonomy engine supporting:
    - Hierarchical Industry Group -> Subcategory -> Category classification
    - Deep Information Technology (IT) category ecosystem
    - Multi-rank fuzzy/alias searching
    - Fast group filtering and backward compatibility
    """

    @classmethod
    def get_all(cls) -> List[Dict[str, Any]]:
        """Returns all categories in the taxonomy."""
        return list(BUSINESS_CATEGORIES_DATA)

    @classmethod
    def get_by_name(cls, name: str) -> Optional[Dict[str, Any]]:
        """Resolves a category by exact or case-insensitive name match."""
        if not name or not name.strip():
            return None
        clean = name.strip().lower()
        for cat in BUSINESS_CATEGORIES_DATA:
            if cat["name"].lower() == clean:
                return cat
        # Try alias match
        for cat in BUSINESS_CATEGORIES_DATA:
            if any(a.lower() == clean for a in cat.get("aliases", [])):
                return cat
        return None

    @classmethod
    def get_by_id(cls, category_id: str) -> Optional[Dict[str, Any]]:
        """Lookup by unique ID or slug."""
        if not category_id:
            return None
        clean = category_id.strip().lower()
        for cat in BUSINESS_CATEGORIES_DATA:
            if cat["id"].lower() == clean or cat.get("slug", "").lower() == clean:
                return cat
        return None

    @classmethod
    def get_by_id_or_name(cls, identifier: str) -> Optional[Dict[str, Any]]:
        """Lookup category by ID, slug, alias, or exact canonical name."""
        if not identifier:
            return None
        clean = identifier.strip().lower().replace("categories/", "").replace("gcid:", "")
        for c in BUSINESS_CATEGORIES_DATA:
            c_id = c.get("id", "").lower().replace("-", "_")
            c_slug = c.get("slug", "").lower()
            c_name = c.get("name", "").lower()
            if clean in [c_id, c.get("id", "").lower(), c_name, c_slug]:
                res = dict(c)
                res["category_id"] = c.get("id")
                res["display_name"] = res.get("name")
                res["source"] = "LOCALLIFT_TAXONOMY"
                res["is_official_google"] = False
                return res
        # Check aliases
        for c in BUSINESS_CATEGORIES_DATA:
            if any(a.lower() == clean for a in c.get("aliases", [])):
                res = dict(c)
                res["category_id"] = c.get("id")
                res["display_name"] = res.get("name")
                res["source"] = "LOCALLIFT_TAXONOMY"
                res["is_official_google"] = False
                return res
        return None

    @classmethod
    def normalize_category_name(cls, raw_category: Optional[str]) -> str:
        """Normalizes any legacy category string into canonical display name."""
        if not raw_category or not raw_category.strip():
            return "Local Business"
        clean = raw_category.strip()
        matched = cls.get_by_name(clean)
        if matched:
            return matched["name"]
        return clean

    @classmethod
    def get_schema_type_for_category(cls, category_name: Optional[str]) -> str:
        """Resolves specialized Schema.org @type for a business category."""
        matched = cls.get_by_name(category_name or "")
        if matched and matched.get("schema_type"):
            return matched["schema_type"]
        return "LocalBusiness"

    @classmethod
    def search(
        cls,
        query: Optional[str] = None,
        group: Optional[str] = None,
        parent_group: Optional[str] = None,
        popular_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Ranked category search supporting:
        1. Exact canonical name match (rank 100)
        2. Name starts with query (rank 85)
        3. Word boundary query match in name (rank 75)
        4. Name contains query (rank 60)
        5. Exact alias match (rank 55)
        6. Alias starts with query (rank 45)
        7. Alias contains query (rank 35)
        8. Subcategory match (rank 25)
        9. Parent group match (rank 15)
        """
        items = BUSINESS_CATEGORIES_DATA

        # Filter by group or parent_group
        if group and group.strip():
            g_clean = group.strip().lower()
            items = [c for c in items if c.get("group", "").lower() == g_clean or c.get("parent_group", "").lower() == g_clean]

        if parent_group and parent_group.strip():
            pg_clean = parent_group.strip().lower()
            items = [c for c in items if c.get("parent_group", "").lower() == pg_clean]

        q = (query or "").strip().lower()
        if not q:
            if popular_only:
                res = [c for c in items if c.get("is_popular", False)]
                res.sort(key=lambda x: x.get("display_order", 999))
                return [dict(c) for c in res[:limit]]
            res = list(items)
            res.sort(key=lambda x: x.get("display_order", 999))
            return [dict(c) for c in res[:limit]]

        scored_results = []
        for cat in items:
            name_lower = cat["name"].lower()
            group_lower = cat.get("group", "").lower()
            parent_lower = cat.get("parent_group", "").lower()
            subcat_lower = cat.get("subcategory", "").lower()
            aliases = [a.lower() for a in cat.get("aliases", [])]

            score = 0
            if name_lower == q:
                score = 100
            elif name_lower.startswith(q):
                score = 85
            elif re.search(r'\b' + re.escape(q), name_lower):
                score = 75
            elif q in name_lower:
                score = 60
            elif any(a == q for a in aliases):
                score = 55
            elif any(a.startswith(q) for a in aliases):
                score = 45
            elif any(q in a for a in aliases):
                score = 35
            elif q in subcat_lower:
                score = 25
            elif q in group_lower or q in parent_lower:
                score = 15

            if score > 0:
                scored_results.append((score, cat.get("display_order", 999), cat))

        # Sort by score descending, then display_order ascending, then name
        scored_results.sort(key=lambda x: (-x[0], x[1], x[2]["name"]))
        results = [dict(item[2]) for item in scored_results[:limit]]
        for r in results:
            r["category_id"] = r.get("id")
            r["display_name"] = r.get("name")
            r["source"] = "LOCALLIFT_TAXONOMY"
            r["is_official_google"] = False
        return results

    @classmethod
    def get_groups(cls) -> List[str]:
        """Returns unique ordered parent industry groups."""
        groups: List[str] = []
        for c in BUSINESS_CATEGORIES_DATA:
            g = c.get("group")
            if g and g not in groups:
                groups.append(g)
        return groups

    @classmethod
    def get_hierarchical_catalog(cls) -> Dict[str, Any]:
        """
        Builds complete hierarchical catalog:
        Industry Group -> Subcategories -> Categories
        """
        catalog: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for c in BUSINESS_CATEGORIES_DATA:
            grp = c.get("group", "Other Specialized Businesses")
            subcat = c.get("subcategory", "General")
            if grp not in catalog:
                catalog[grp] = {}
            if subcat not in catalog[grp]:
                catalog[grp][subcat] = []
            catalog[grp][subcat].append(dict(c))

        # Format as clean structured JSON
        groups_list = []
        for grp_name, subcats in catalog.items():
            subcat_list = []
            total_items = 0
            for sub_name, items in subcats.items():
                total_items += len(items)
                subcat_list.append({
                    "name": sub_name,
                    "count": len(items),
                    "categories": items
                })
            groups_list.append({
                "name": grp_name,
                "total_categories": total_items,
                "subcategories": subcat_list
            })

        return {
            "total_groups": len(groups_list),
            "total_categories": len(BUSINESS_CATEGORIES_DATA),
            "groups": groups_list
        }

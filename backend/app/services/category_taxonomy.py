import re
from typing import List, Dict, Any, Optional

# Structured Category Item Definition:
# - id: unique slug
# - name: canonical display name
# - slug: identifier
# - group: category group / industry sector
# - aliases: list of synonyms & search keywords
# - schema_type: Schema.org JSON-LD @type
# - gbp_category: Google Business Profile official category
# - is_popular: featured on empty search state

BUSINESS_CATEGORIES_DATA: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # 1. Healthcare & Medical
    # -------------------------------------------------------------
    {
        "id": "dentist",
        "name": "Dentist",
        "slug": "dentist",
        "group": "Healthcare & Medical",
        "aliases": ["dental clinic", "dental office", "teeth cleaning", "general dentist", "family dentist", "tooth extraction", "dental practice"],
        "schema_type": "Dentist",
        "gbp_category": "Dentist",
        "is_popular": True
    },
    {
        "id": "dental-clinic",
        "name": "Dental Clinic",
        "slug": "dental-clinic",
        "group": "Healthcare & Medical",
        "aliases": ["dental center", "dental surgery", "dental hospital"],
        "schema_type": "Dentist",
        "gbp_category": "Dental clinic",
        "is_popular": True
    },
    {
        "id": "orthodontist",
        "name": "Orthodontist",
        "slug": "orthodontist",
        "group": "Healthcare & Medical",
        "aliases": ["braces", "invisalign", "teeth straightening", "orthodontic clinic"],
        "schema_type": "Dentist",
        "gbp_category": "Orthodontist",
        "is_popular": False
    },
    {
        "id": "cosmetic-dentist",
        "name": "Cosmetic Dentist",
        "slug": "cosmetic-dentist",
        "group": "Healthcare & Medical",
        "aliases": ["teeth whitening", "veneers", "smile makeover", "dental implants"],
        "schema_type": "Dentist",
        "gbp_category": "Cosmetic dentist",
        "is_popular": False
    },
    {
        "id": "pediatric-dentist",
        "name": "Pediatric Dentist",
        "slug": "pediatric-dentist",
        "group": "Healthcare & Medical",
        "aliases": ["childrens dentist", "kids dentist", "pediatric dental clinic"],
        "schema_type": "Dentist",
        "gbp_category": "Pediatric dentist",
        "is_popular": False
    },
    {
        "id": "emergency-dental-service",
        "name": "Emergency Dental Service",
        "slug": "emergency-dental-service",
        "group": "Healthcare & Medical",
        "aliases": ["24 hour dentist", "urgent dental care", "weekend dentist", "emergency tooth extraction"],
        "schema_type": "Dentist",
        "gbp_category": "Emergency dental service",
        "is_popular": False
    },
    {
        "id": "doctor",
        "name": "Doctor",
        "slug": "doctor",
        "group": "Healthcare & Medical",
        "aliases": ["physician", "general practitioner", "gp", "family doctor", "family practice"],
        "schema_type": "Physician",
        "gbp_category": "Doctor",
        "is_popular": True
    },
    {
        "id": "medical-clinic",
        "name": "Medical Clinic",
        "slug": "medical-clinic",
        "group": "Healthcare & Medical",
        "aliases": ["health clinic", "polyclinic", "medical center", "walk in clinic", "outpatient clinic"],
        "schema_type": "MedicalClinic",
        "gbp_category": "Medical clinic",
        "is_popular": True
    },
    {
        "id": "urgent-care-center",
        "name": "Urgent Care Center",
        "slug": "urgent-care-center",
        "group": "Healthcare & Medical",
        "aliases": ["walk in urgent care", "immediate care", "after hours clinic"],
        "schema_type": "MedicalClinic",
        "gbp_category": "Urgent care center",
        "is_popular": False
    },
    {
        "id": "hospital",
        "name": "Hospital",
        "slug": "hospital",
        "group": "Healthcare & Medical",
        "aliases": ["general hospital", "emergency room", "medical center hospital"],
        "schema_type": "Hospital",
        "gbp_category": "Hospital",
        "is_popular": False
    },
    {
        "id": "chiropractor",
        "name": "Chiropractor",
        "slug": "chiropractor",
        "group": "Healthcare & Medical",
        "aliases": ["chiropractic clinic", "back pain specialist", "spine adjustment", "neck pain doctor"],
        "schema_type": "Physician",
        "gbp_category": "Chiropractor",
        "is_popular": True
    },
    {
        "id": "physiotherapist",
        "name": "Physiotherapist",
        "slug": "physiotherapist",
        "group": "Healthcare & Medical",
        "aliases": ["physical therapy", "physical therapist", "pt clinic", "sports physiotherapy", "rehab clinic"],
        "schema_type": "MedicalClinic",
        "gbp_category": "Physiotherapist",
        "is_popular": True
    },
    {
        "id": "optometrist",
        "name": "Optometrist",
        "slug": "optometrist",
        "group": "Healthcare & Medical",
        "aliases": ["eye doctor", "eye exam", "glasses clinic", "optometry clinic", "contact lenses"],
        "schema_type": "Optician",
        "gbp_category": "Optometrist",
        "is_popular": True
    },
    {
        "id": "dermatologist",
        "name": "Dermatologist",
        "slug": "dermatologist",
        "group": "Healthcare & Medical",
        "aliases": ["skin doctor", "skin care clinic", "acne specialist", "mole removal"],
        "schema_type": "Physician",
        "gbp_category": "Dermatologist",
        "is_popular": False
    },
    {
        "id": "psychologist",
        "name": "Psychologist",
        "slug": "psychologist",
        "group": "Healthcare & Medical",
        "aliases": ["therapist", "mental health counselor", "counseling service", "psychotherapy", "marriage counselor"],
        "schema_type": "MedicalClinic",
        "gbp_category": "Psychologist",
        "is_popular": False
    },
    {
        "id": "podiatrist",
        "name": "Podiatrist",
        "slug": "podiatrist",
        "group": "Healthcare & Medical",
        "aliases": ["foot doctor", "foot clinic", "orthotics specialist"],
        "schema_type": "Physician",
        "gbp_category": "Podiatrist",
        "is_popular": False
    },
    {
        "id": "audiologist",
        "name": "Audiologist",
        "slug": "audiologist",
        "group": "Healthcare & Medical",
        "aliases": ["hearing clinic", "hearing aid store", "hearing test"],
        "schema_type": "MedicalClinic",
        "gbp_category": "Audiologist",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 2. Home Services & Contractors
    # -------------------------------------------------------------
    {
        "id": "plumber",
        "name": "Plumber",
        "slug": "plumber",
        "group": "Home Services",
        "aliases": ["plumbing contractor", "emergency plumber", "drain cleaning", "water heater repair", "pipe repair", "leak detection"],
        "schema_type": "Plumber",
        "gbp_category": "Plumber",
        "is_popular": True
    },
    {
        "id": "electrician",
        "name": "Electrician",
        "slug": "electrician",
        "group": "Home Services",
        "aliases": ["electrical contractor", "emergency electrician", "wiring repair", "lighting installation", "circuit breaker repair"],
        "schema_type": "Electrician",
        "gbp_category": "Electrician",
        "is_popular": True
    },
    {
        "id": "hvac-contractor",
        "name": "HVAC Contractor",
        "slug": "hvac-contractor",
        "group": "Home Services",
        "aliases": ["air conditioning contractor", "heating contractor", "ac repair", "furnace repair", "hvac repair", "air conditioning repair service"],
        "schema_type": "HVACBusiness",
        "gbp_category": "HVAC contractor",
        "is_popular": True
    },
    {
        "id": "roofing-contractor",
        "name": "Roofing Contractor",
        "slug": "roofing-contractor",
        "group": "Home Services",
        "aliases": ["roofer", "roof repair", "roof replacement", "gutter installation", "shingle repair", "commercial roofing"],
        "schema_type": "RoofingContractor",
        "gbp_category": "Roofing contractor",
        "is_popular": True
    },
    {
        "id": "general-contractor",
        "name": "General Contractor",
        "slug": "general-contractor",
        "group": "Home Services",
        "aliases": ["builder", "home remodeler", "kitchen remodeling", "bathroom remodeling", "home addition", "custom home builder"],
        "schema_type": "GeneralContractor",
        "gbp_category": "General contractor",
        "is_popular": True
    },
    {
        "id": "locksmith",
        "name": "Locksmith",
        "slug": "locksmith",
        "group": "Home Services",
        "aliases": ["emergency locksmith", "car locksmith", "door lock repair", "key duplication", "lockout service"],
        "schema_type": "Locksmith",
        "gbp_category": "Locksmith",
        "is_popular": True
    },
    {
        "id": "pest-control-service",
        "name": "Pest Control Service",
        "slug": "pest-control-service",
        "group": "Home Services",
        "aliases": ["exterminator", "termite control", "bed bug treatment", "rodent removal", "ant control"],
        "schema_type": "HomeAndConstructionBusiness",
        "gbp_category": "Pest control service",
        "is_popular": True
    },
    {
        "id": "landscaper",
        "name": "Landscaper",
        "slug": "landscaper",
        "group": "Home Services",
        "aliases": ["landscaping service", "lawn care service", "gardener", "lawn mowing", "tree trimming", "irrigation system contractor"],
        "schema_type": "HomeAndConstructionBusiness",
        "gbp_category": "Landscaper",
        "is_popular": True
    },
    {
        "id": "house-cleaning-service",
        "name": "House Cleaning Service",
        "slug": "house-cleaning-service",
        "group": "Home Services",
        "aliases": ["maid service", "residential cleaning", "deep cleaning", "move out cleaning"],
        "schema_type": "HousePainter",
        "gbp_category": "House cleaning service",
        "is_popular": True
    },
    {
        "id": "painter",
        "name": "Painter",
        "slug": "painter",
        "group": "Home Services",
        "aliases": ["painting contractor", "house painter", "interior painter", "exterior painter", "commercial painter"],
        "schema_type": "HousePainter",
        "gbp_category": "Painter",
        "is_popular": False
    },
    {
        "id": "carpenter",
        "name": "Carpenter",
        "slug": "carpenter",
        "group": "Home Services",
        "aliases": ["cabinet maker", "woodworking", "custom carpentry", "deck builder", "framing contractor"],
        "schema_type": "HomeAndConstructionBusiness",
        "gbp_category": "Carpenter",
        "is_popular": False
    },
    {
        "id": "flooring-contractor",
        "name": "Flooring Contractor",
        "slug": "flooring-contractor",
        "group": "Home Services",
        "aliases": ["hardwood floor installation", "carpet installer", "tile contractor", "vinyl plank flooring"],
        "schema_type": "HomeAndConstructionBusiness",
        "gbp_category": "Flooring contractor",
        "is_popular": False
    },
    {
        "id": "garage-door-supplier",
        "name": "Garage Door Supplier",
        "slug": "garage-door-supplier",
        "group": "Home Services",
        "aliases": ["garage door repair", "overhead door", "garage spring repair", "garage opener installation"],
        "schema_type": "HomeAndConstructionBusiness",
        "gbp_category": "Garage door supplier",
        "is_popular": False
    },
    {
        "id": "handyman",
        "name": "Handyman",
        "slug": "handyman",
        "group": "Home Services",
        "aliases": ["handyman service", "home repairs", "odd jobs", "furniture assembly", "drywall repair"],
        "schema_type": "HomeAndConstructionBusiness",
        "gbp_category": "Handyman",
        "is_popular": False
    },
    {
        "id": "solar-energy-company",
        "name": "Solar Energy Company",
        "slug": "solar-energy-company",
        "group": "Home Services",
        "aliases": ["solar panel installation", "solar contractor", "solar installer", "clean energy"],
        "schema_type": "HomeAndConstructionBusiness",
        "gbp_category": "Solar energy company",
        "is_popular": False
    },
    {
        "id": "tree-service",
        "name": "Tree Service",
        "slug": "tree-service",
        "group": "Home Services",
        "aliases": ["tree removal", "tree trimming", "arborist", "stump grinding"],
        "schema_type": "HomeAndConstructionBusiness",
        "gbp_category": "Tree service",
        "is_popular": False
    },
    {
        "id": "swimming-pool-repair-service",
        "name": "Swimming Pool Repair Service",
        "slug": "swimming-pool-repair-service",
        "group": "Home Services",
        "aliases": ["pool cleaning service", "pool maintenance", "pool contractor", "pool service"],
        "schema_type": "HomeAndConstructionBusiness",
        "gbp_category": "Swimming pool repair service",
        "is_popular": False
    },
    {
        "id": "window-cleaning-service",
        "name": "Window Cleaning Service",
        "slug": "window-cleaning-service",
        "group": "Home Services",
        "aliases": ["window washer", "commercial window cleaning", "pressure washing"],
        "schema_type": "HomeAndConstructionBusiness",
        "gbp_category": "Window cleaning service",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 3. Legal Services
    # -------------------------------------------------------------
    {
        "id": "law-firm",
        "name": "Law Firm",
        "slug": "law-firm",
        "group": "Legal",
        "aliases": ["attorney", "lawyer", "legal services", "legal office", "law practice", "counselor at law"],
        "schema_type": "LegalService",
        "gbp_category": "Law firm",
        "is_popular": True
    },
    {
        "id": "personal-injury-attorney",
        "name": "Personal Injury Attorney",
        "slug": "personal-injury-attorney",
        "group": "Legal",
        "aliases": ["car accident lawyer", "injury lawyer", "accident attorney", "slip and fall lawyer", "medical malpractice attorney"],
        "schema_type": "LegalService",
        "gbp_category": "Personal injury attorney",
        "is_popular": True
    },
    {
        "id": "family-law-attorney",
        "name": "Family Law Attorney",
        "slug": "family-law-attorney",
        "group": "Legal",
        "aliases": ["divorce lawyer", "child custody lawyer", "adoption attorney", "family lawyer"],
        "schema_type": "LegalService",
        "gbp_category": "Family law attorney",
        "is_popular": False
    },
    {
        "id": "criminal-defense-attorney",
        "name": "Criminal Defense Attorney",
        "slug": "criminal-defense-attorney",
        "group": "Legal",
        "aliases": ["dwi lawyer", "dui attorney", "criminal lawyer", "defense counsel"],
        "schema_type": "LegalService",
        "gbp_category": "Criminal defense attorney",
        "is_popular": False
    },
    {
        "id": "estate-planning-attorney",
        "name": "Estate Planning Attorney",
        "slug": "estate-planning-attorney",
        "group": "Legal",
        "aliases": ["wills and trusts lawyer", "probate attorney", "living will lawyer"],
        "schema_type": "LegalService",
        "gbp_category": "Estate planning attorney",
        "is_popular": False
    },
    {
        "id": "real-estate-attorney",
        "name": "Real Estate Attorney",
        "slug": "real-estate-attorney",
        "group": "Legal",
        "aliases": ["property lawyer", "closing attorney", "commercial real estate lawyer"],
        "schema_type": "LegalService",
        "gbp_category": "Real estate attorney",
        "is_popular": False
    },
    {
        "id": "immigration-attorney",
        "name": "Immigration Attorney",
        "slug": "immigration-attorney",
        "group": "Legal",
        "aliases": ["visa lawyer", "green card attorney", "citizenship lawyer"],
        "schema_type": "LegalService",
        "gbp_category": "Immigration attorney",
        "is_popular": False
    },
    {
        "id": "employment-attorney",
        "name": "Employment Attorney",
        "slug": "employment-attorney",
        "group": "Legal",
        "aliases": ["labor lawyer", "workplace harassment attorney", "wrongful termination lawyer"],
        "schema_type": "LegalService",
        "gbp_category": "Employment attorney",
        "is_popular": False
    },
    {
        "id": "bankruptcy-attorney",
        "name": "Bankruptcy Attorney",
        "slug": "bankruptcy-attorney",
        "group": "Legal",
        "aliases": ["chapter 7 lawyer", "chapter 13 attorney", "debt relief attorney"],
        "schema_type": "LegalService",
        "gbp_category": "Bankruptcy attorney",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 4. Restaurants & Food
    # -------------------------------------------------------------
    {
        "id": "restaurant",
        "name": "Restaurant",
        "slug": "restaurant",
        "group": "Restaurants & Food",
        "aliases": ["dining", "eatery", "food place", "fine dining", "family restaurant", "bistro"],
        "schema_type": "Restaurant",
        "gbp_category": "Restaurant",
        "is_popular": True
    },
    {
        "id": "cafe",
        "name": "Cafe",
        "slug": "cafe",
        "group": "Restaurants & Food",
        "aliases": ["coffee shop", "espresso bar", "breakfast cafe", "brunch spot"],
        "schema_type": "CafeOrCoffeeShop",
        "gbp_category": "Cafe",
        "is_popular": True
    },
    {
        "id": "bakery",
        "name": "Bakery",
        "slug": "bakery",
        "group": "Restaurants & Food",
        "aliases": ["cake shop", "pastry shop", "bread bakery", "custom cakes", "cupcake shop"],
        "schema_type": "Bakery",
        "gbp_category": "Bakery",
        "is_popular": True
    },
    {
        "id": "pizza-restaurant",
        "name": "Pizza Restaurant",
        "slug": "pizza-restaurant",
        "group": "Restaurants & Food",
        "aliases": ["pizzeria", "pizza delivery", "wood fired pizza", "slice shop"],
        "schema_type": "Restaurant",
        "gbp_category": "Pizza restaurant",
        "is_popular": True
    },
    {
        "id": "italian-restaurant",
        "name": "Italian Restaurant",
        "slug": "italian-restaurant",
        "group": "Restaurants & Food",
        "aliases": ["pasta restaurant", "trattoria", "authentic italian"],
        "schema_type": "Restaurant",
        "gbp_category": "Italian restaurant",
        "is_popular": False
    },
    {
        "id": "mexican-restaurant",
        "name": "Mexican Restaurant",
        "slug": "mexican-restaurant",
        "group": "Restaurants & Food",
        "aliases": ["taqueria", "taco shop", "burrito spot", "cantina"],
        "schema_type": "Restaurant",
        "gbp_category": "Mexican restaurant",
        "is_popular": False
    },
    {
        "id": "indian-restaurant",
        "name": "Indian Restaurant",
        "slug": "indian-restaurant",
        "group": "Restaurants & Food",
        "aliases": ["curry house", "tandoori restaurant", "biryani"],
        "schema_type": "Restaurant",
        "gbp_category": "Indian restaurant",
        "is_popular": False
    },
    {
        "id": "sushi-restaurant",
        "name": "Sushi Restaurant",
        "slug": "sushi-restaurant",
        "group": "Restaurants & Food",
        "aliases": ["japanese restaurant", "sushi bar", "ramen shop"],
        "schema_type": "Restaurant",
        "gbp_category": "Sushi restaurant",
        "is_popular": False
    },
    {
        "id": "chinese-restaurant",
        "name": "Chinese Restaurant",
        "slug": "chinese-restaurant",
        "group": "Restaurants & Food",
        "aliases": ["dim sum", "noodle house", "asian cuisine", "cantonese restaurant"],
        "schema_type": "Restaurant",
        "gbp_category": "Chinese restaurant",
        "is_popular": False
    },
    {
        "id": "fast-food-restaurant",
        "name": "Fast Food Restaurant",
        "slug": "fast-food-restaurant",
        "group": "Restaurants & Food",
        "aliases": ["burger joint", "drive thru", "quick service restaurant"],
        "schema_type": "FastFoodRestaurant",
        "gbp_category": "Fast food restaurant",
        "is_popular": False
    },
    {
        "id": "catering-service",
        "name": "Catering Food and Drink Supplier",
        "slug": "catering-service",
        "group": "Restaurants & Food",
        "aliases": ["caterer", "wedding catering", "corporate catering", "event caterer"],
        "schema_type": "FoodEstablishment",
        "gbp_category": "Caterer",
        "is_popular": False
    },
    {
        "id": "bar-and-grill",
        "name": "Bar & Grill",
        "slug": "bar-and-grill",
        "group": "Restaurants & Food",
        "aliases": ["pub", "sports bar", "tavern", "gastropub", "cocktail lounge"],
        "schema_type": "BarOrPub",
        "gbp_category": "Bar & grill",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 5. Automotive
    # -------------------------------------------------------------
    {
        "id": "auto-repair-shop",
        "name": "Auto Repair Shop",
        "slug": "auto-repair-shop",
        "group": "Automotive",
        "aliases": ["mechanic", "car repair", "auto mechanic", "brake repair", "transmission repair", "engine diagnostics"],
        "schema_type": "AutoRepair",
        "gbp_category": "Auto repair shop",
        "is_popular": True
    },
    {
        "id": "car-dealer",
        "name": "Car Dealer",
        "slug": "car-dealer",
        "group": "Automotive",
        "aliases": ["dealership", "new car dealer", "auto dealer", "vehicle sales"],
        "schema_type": "AutoDealer",
        "gbp_category": "Car dealer",
        "is_popular": True
    },
    {
        "id": "used-car-dealer",
        "name": "Used Car Dealer",
        "slug": "used-car-dealer",
        "group": "Automotive",
        "aliases": ["pre owned cars", "used car lot", "second hand cars"],
        "schema_type": "AutoDealer",
        "gbp_category": "Used car dealer",
        "is_popular": False
    },
    {
        "id": "auto-body-shop",
        "name": "Auto Body Shop",
        "slug": "auto-body-shop",
        "group": "Automotive",
        "aliases": ["collision center", "car body repair", "dent repair", "car painting"],
        "schema_type": "AutoBodyShop",
        "gbp_category": "Auto body shop",
        "is_popular": False
    },
    {
        "id": "tire-shop",
        "name": "Tire Shop",
        "slug": "tire-shop",
        "group": "Automotive",
        "aliases": ["tire dealer", "wheel alignment", "flat tire repair", "tire replacement"],
        "schema_type": "AutoPartsStore",
        "gbp_category": "Tire shop",
        "is_popular": False
    },
    {
        "id": "car-wash",
        "name": "Car Wash",
        "slug": "car-wash",
        "group": "Automotive",
        "aliases": ["auto detailing", "car detailer", "touchless car wash", "hand car wash"],
        "schema_type": "AutoWash",
        "gbp_category": "Car wash",
        "is_popular": False
    },
    {
        "id": "towing-service",
        "name": "Towing Service",
        "slug": "towing-service",
        "group": "Automotive",
        "aliases": ["tow truck", "roadside assistance", "flatbed towing", "emergency towing"],
        "schema_type": "AutoRepair",
        "gbp_category": "Towing service",
        "is_popular": False
    },
    {
        "id": "oil-change-service",
        "name": "Oil Change Service",
        "slug": "oil-change-service",
        "group": "Automotive",
        "aliases": ["quick lube", "express oil change", "car maintenance"],
        "schema_type": "AutoRepair",
        "gbp_category": "Oil change service",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 6. Real Estate & Property
    # -------------------------------------------------------------
    {
        "id": "real-estate-agency",
        "name": "Real Estate Agency",
        "slug": "real-estate-agency",
        "group": "Real Estate & Property",
        "aliases": ["realtor", "real estate broker", "property agency", "commercial real estate", "residential real estate", "home buying agency"],
        "schema_type": "RealEstateAgent",
        "gbp_category": "Real estate agency",
        "is_popular": True
    },
    {
        "id": "real-estate-agent",
        "name": "Real Estate Agent",
        "slug": "real-estate-agent",
        "group": "Real Estate & Property",
        "aliases": ["realtor agent", "buying agent", "listing agent"],
        "schema_type": "RealEstateAgent",
        "gbp_category": "Real estate agent",
        "is_popular": False
    },
    {
        "id": "property-management-company",
        "name": "Property Management Company",
        "slug": "property-management-company",
        "group": "Real Estate & Property",
        "aliases": ["rental property manager", "landlord service", "hoa management"],
        "schema_type": "RealEstateAgent",
        "gbp_category": "Property management company",
        "is_popular": False
    },
    {
        "id": "home-inspector",
        "name": "Home Inspector",
        "slug": "home-inspector",
        "group": "Real Estate & Property",
        "aliases": ["property inspection", "building inspector", "termite inspector"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Home inspector",
        "is_popular": False
    },
    {
        "id": "real-estate-appraiser",
        "name": "Real Estate Appraiser",
        "slug": "real-estate-appraiser",
        "group": "Real Estate & Property",
        "aliases": ["property valuation", "home appraiser", "commercial appraiser"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Real estate appraiser",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 7. Professional Services
    # -------------------------------------------------------------
    {
        "id": "accountant",
        "name": "Accountant",
        "slug": "accountant",
        "group": "Professional Services",
        "aliases": ["cpa", "certified public accountant", "accounting firm", "bookkeeper", "tax accountant", "audit firm"],
        "schema_type": "AccountingService",
        "gbp_category": "Accountant",
        "is_popular": True
    },
    {
        "id": "tax-preparation-service",
        "name": "Tax Preparation Service",
        "slug": "tax-preparation-service",
        "group": "Professional Services",
        "aliases": ["tax consultant", "tax return preparer", "income tax service"],
        "schema_type": "AccountingService",
        "gbp_category": "Tax preparation service",
        "is_popular": False
    },
    {
        "id": "financial-planner",
        "name": "Financial Planner",
        "slug": "financial-planner",
        "group": "Professional Services",
        "aliases": ["wealth manager", "financial advisor", "retirement planner", "investment advisor"],
        "schema_type": "FinancialService",
        "gbp_category": "Financial planner",
        "is_popular": False
    },
    {
        "id": "insurance-agency",
        "name": "Insurance Agency",
        "slug": "insurance-agency",
        "group": "Professional Services",
        "aliases": ["insurance broker", "auto insurance", "home insurance", "life insurance", "business insurance"],
        "schema_type": "InsuranceAgency",
        "gbp_category": "Insurance agency",
        "is_popular": True
    },
    {
        "id": "marketing-agency",
        "name": "Marketing Agency",
        "slug": "marketing-agency",
        "group": "Professional Services",
        "aliases": ["digital marketing agency", "seo agency", "advertising agency", "social media marketing", "pr agency", "brand consultant"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Marketing agency",
        "is_popular": True
    },
    {
        "id": "web-designer",
        "name": "Web Designer",
        "slug": "web-designer",
        "group": "Professional Services",
        "aliases": ["website design", "web development company", "ui ux design", "wordpress developer"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Web designer",
        "is_popular": False
    },
    {
        "id": "notary-public",
        "name": "Notary Public",
        "slug": "notary-public",
        "group": "Professional Services",
        "aliases": ["mobile notary", "signing agent", "document apostille"],
        "schema_type": "Notary",
        "gbp_category": "Notary public",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 8. Beauty & Personal Care
    # -------------------------------------------------------------
    {
        "id": "hair-salon",
        "name": "Hair Salon",
        "slug": "hair-salon",
        "group": "Beauty & Personal Care",
        "aliases": ["hairdresser", "hair stylist", "haircut", "hair coloring", "balayage", "hair extensions"],
        "schema_type": "HairSalon",
        "gbp_category": "Hair salon",
        "is_popular": True
    },
    {
        "id": "barber-shop",
        "name": "Barber Shop",
        "slug": "barber-shop",
        "group": "Beauty & Personal Care",
        "aliases": ["barber", "mens haircut", "beard trim", "hot towel shave"],
        "schema_type": "HairSalon",
        "gbp_category": "Barber shop",
        "is_popular": True
    },
    {
        "id": "nail-salon",
        "name": "Nail Salon",
        "slug": "nail-salon",
        "group": "Beauty & Personal Care",
        "aliases": ["manicure", "pedicure", "gel nails", "acrylic nails", "nail art"],
        "schema_type": "BeautySalon",
        "gbp_category": "Nail salon",
        "is_popular": True
    },
    {
        "id": "day-spa",
        "name": "Day Spa",
        "slug": "day-spa",
        "group": "Beauty & Personal Care",
        "aliases": ["massage spa", "facials", "skin clinic", "wellness center", "body treatments"],
        "schema_type": "DaySpa",
        "gbp_category": "Day spa",
        "is_popular": True
    },
    {
        "id": "medical-spa",
        "name": "Medical Spa",
        "slug": "medical-spa",
        "group": "Beauty & Personal Care",
        "aliases": ["med spa", "botox clinic", "laser hair removal", "dermal fillers", "microneedling"],
        "schema_type": "HealthAndBeautyBusiness",
        "gbp_category": "Medical spa",
        "is_popular": False
    },
    {
        "id": "tattoo-shop",
        "name": "Tattoo Shop",
        "slug": "tattoo-shop",
        "group": "Beauty & Personal Care",
        "aliases": ["tattoo parlor", "custom tattoos", "body piercing"],
        "schema_type": "HealthAndBeautyBusiness",
        "gbp_category": "Tattoo shop",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 9. Fitness & Sports
    # -------------------------------------------------------------
    {
        "id": "gym",
        "name": "Gym",
        "slug": "gym",
        "group": "Fitness & Sports",
        "aliases": ["fitness center", "health club", "workout facility", "24 hour gym", "weight training"],
        "schema_type": "ExerciseGym",
        "gbp_category": "Gym",
        "is_popular": True
    },
    {
        "id": "personal-trainer",
        "name": "Personal Trainer",
        "slug": "personal-trainer",
        "group": "Fitness & Sports",
        "aliases": ["fitness coach", "private workout", "weight loss training"],
        "schema_type": "ExerciseGym",
        "gbp_category": "Personal trainer",
        "is_popular": False
    },
    {
        "id": "yoga-studio",
        "name": "Yoga Studio",
        "slug": "yoga-studio",
        "group": "Fitness & Sports",
        "aliases": ["hot yoga", "pilates studio", "vinyasa yoga", "meditation center"],
        "schema_type": "ExerciseGym",
        "gbp_category": "Yoga studio",
        "is_popular": False
    },
    {
        "id": "martial-arts-school",
        "name": "Martial Arts School",
        "slug": "martial-arts-school",
        "group": "Fitness & Sports",
        "aliases": ["karate dojo", "brazilian jiu jitsu", "taekwondo", "mma gym", "boxing club"],
        "schema_type": "ExerciseGym",
        "gbp_category": "Martial arts school",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 10. Hotels & Accommodation
    # -------------------------------------------------------------
    {
        "id": "hotel",
        "name": "Hotel",
        "slug": "hotel",
        "group": "Hotels & Accommodation",
        "aliases": ["lodging", "resort", "motel", "boutique hotel", "extended stay hotel", "inn"],
        "schema_type": "Hotel",
        "gbp_category": "Hotel",
        "is_popular": True
    },
    {
        "id": "bed-and-breakfast",
        "name": "Bed & Breakfast",
        "slug": "bed-and-breakfast",
        "group": "Hotels & Accommodation",
        "aliases": ["b&b", "guest house", "country inn"],
        "schema_type": "BedAndBreakfast",
        "gbp_category": "Bed & breakfast",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 11. Pets & Animals
    # -------------------------------------------------------------
    {
        "id": "veterinarian",
        "name": "Veterinarian",
        "slug": "veterinarian",
        "group": "Pets & Animals",
        "aliases": ["vet clinic", "animal hospital", "emergency vet", "pet doctor", "cat and dog vet"],
        "schema_type": "VeterinaryCare",
        "gbp_category": "Veterinarian",
        "is_popular": True
    },
    {
        "id": "pet-groomer",
        "name": "Pet Groomer",
        "slug": "pet-groomer",
        "group": "Pets & Animals",
        "aliases": ["dog groomer", "mobile dog grooming", "pet salon", "dog bath"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Pet groomer",
        "is_popular": False
    },
    {
        "id": "pet-boarding-service",
        "name": "Pet Boarding Service",
        "slug": "pet-boarding-service",
        "group": "Pets & Animals",
        "aliases": ["dog daycare", "dog boarding kennel", "cat boarding", "pet hotel"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Pet boarding service",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 12. Retail & Shopping
    # -------------------------------------------------------------
    {
        "id": "clothing-store",
        "name": "Clothing Store",
        "slug": "clothing-store",
        "group": "Retail",
        "aliases": ["apparel store", "boutique", "menswear", "womens clothing", "fashion boutique"],
        "schema_type": "ClothingStore",
        "gbp_category": "Clothing store",
        "is_popular": True
    },
    {
        "id": "jewelry-store",
        "name": "Jewelry Store",
        "slug": "jewelry-store",
        "group": "Retail",
        "aliases": ["jeweler", "engagement rings", "diamonds", "custom jewelry", "watch repair"],
        "schema_type": "JewelryStore",
        "gbp_category": "Jewelry store",
        "is_popular": False
    },
    {
        "id": "furniture-store",
        "name": "Furniture Store",
        "slug": "furniture-store",
        "group": "Retail",
        "aliases": ["home furnishings", "mattress store", "couch store", "living room furniture"],
        "schema_type": "FurnitureStore",
        "gbp_category": "Furniture store",
        "is_popular": False
    },
    {
        "id": "florist",
        "name": "Florist",
        "slug": "florist",
        "group": "Retail",
        "aliases": ["flower shop", "flower delivery", "wedding flowers", "floral designer"],
        "schema_type": "Florist",
        "gbp_category": "Florist",
        "is_popular": False
    },
    {
        "id": "grocery-store",
        "name": "Grocery Store",
        "slug": "grocery-store",
        "group": "Retail",
        "aliases": ["supermarket", "organic grocery", "convenience store", "food market"],
        "schema_type": "GroceryStore",
        "gbp_category": "Grocery store",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 13. Events, Entertainment & Weddings
    # -------------------------------------------------------------
    {
        "id": "event-venue",
        "name": "Event Venue",
        "slug": "event-venue",
        "group": "Events & Entertainment",
        "aliases": ["wedding venue", "banquet hall", "conference center", "reception hall", "party venue"],
        "schema_type": "EventVenue",
        "gbp_category": "Event venue",
        "is_popular": True
    },
    {
        "id": "wedding-photographer",
        "name": "Wedding Photographer",
        "slug": "wedding-photographer",
        "group": "Events & Entertainment",
        "aliases": ["wedding photography", "engagement photographer", "bridal portrait"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Wedding photographer",
        "is_popular": False
    },
    {
        "id": "photographer",
        "name": "Photographer",
        "slug": "photographer",
        "group": "Events & Entertainment",
        "aliases": ["photo studio", "portrait photographer", "headshot photographer", "family photos"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Photographer",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 14. Transportation & Logistics
    # -------------------------------------------------------------
    {
        "id": "moving-company",
        "name": "Moving Company",
        "slug": "moving-company",
        "group": "Transportation & Logistics",
        "aliases": ["movers", "local movers", "long distance movers", "packing service", "relocation service"],
        "schema_type": "MovingCompany",
        "gbp_category": "Moving company",
        "is_popular": True
    },
    {
        "id": "self-storage-facility",
        "name": "Self-Storage Facility",
        "slug": "self-storage-facility",
        "group": "Transportation & Logistics",
        "aliases": ["storage units", "climate controlled storage", "mini storage"],
        "schema_type": "SelfStorage",
        "gbp_category": "Self-storage facility",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 15. Education & Child Services
    # -------------------------------------------------------------
    {
        "id": "preschool",
        "name": "Preschool",
        "slug": "preschool",
        "group": "Education",
        "aliases": ["daycare", "child care agency", "nursery school", "early learning center"],
        "schema_type": "Preschool",
        "gbp_category": "Preschool",
        "is_popular": True
    },
    {
        "id": "tutoring-service",
        "name": "Tutoring Service",
        "slug": "tutoring-service",
        "group": "Education",
        "aliases": ["math tutor", "sat prep", "learning center", "academic tutor"],
        "schema_type": "EducationalOrganization",
        "gbp_category": "Tutoring service",
        "is_popular": False
    },
    {
        "id": "driving-school",
        "name": "Driving School",
        "slug": "driving-school",
        "group": "Education",
        "aliases": ["driving instructor", "drivers ed", "behind the wheel training"],
        "schema_type": "EducationalOrganization",
        "gbp_category": "Driving school",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 16. Technology & Digital
    # -------------------------------------------------------------
    {
        "id": "computer-repair-service",
        "name": "Computer Repair Service",
        "slug": "computer-repair-service",
        "group": "Technology & Digital",
        "aliases": ["laptop repair", "pc repair", "macbook repair", "data recovery", "screen replacement"],
        "schema_type": "ComputerStore",
        "gbp_category": "Computer repair service",
        "is_popular": False
    },
    {
        "id": "it-services-consultant",
        "name": "IT Services and IT Consulting",
        "slug": "it-services-consultant",
        "group": "Technology & Digital",
        "aliases": ["managed it services", "network setup", "cybersecurity", "cloud consulting"],
        "schema_type": "ProfessionalService",
        "gbp_category": "Computer support and services",
        "is_popular": False
    },

    # -------------------------------------------------------------
    # 17. General Fallback
    # -------------------------------------------------------------
    {
        "id": "local-business",
        "name": "Local Business",
        "slug": "local-business",
        "group": "Other / Specialized Businesses",
        "aliases": ["small business", "commercial establishment", "local enterprise"],
        "schema_type": "LocalBusiness",
        "gbp_category": "Corporate office",
        "is_popular": False
    }
]

# Legacy string mapping to canonical category entries for backward compatibility
LEGACY_CATEGORY_MAP: Dict[str, str] = {
    "local contractor / service": "general-contractor",
    "electrical contractor": "electrician",
    "plumbing contractor": "plumber",
    "hvac / air conditioning": "hvac-contractor",
    "roofing contractor": "roofing-contractor",
    "dentist / dental clinic": "dentist",
    "law firm / attorney": "law-firm",
    "automotive repair shop": "auto-repair-shop",
    "local business": "local-business"
}


class CategoryTaxonomy:
    """
    Search-first, extensible, and normalized Business Category Taxonomy Service.
    """

    _BY_ID: Dict[str, Dict[str, Any]] = {c["id"]: c for c in BUSINESS_CATEGORIES_DATA}
    _BY_NAME_LOWER: Dict[str, Dict[str, Any]] = {c["name"].lower(): c for c in BUSINESS_CATEGORIES_DATA}

    @classmethod
    def get_all(cls) -> List[Dict[str, Any]]:
        return BUSINESS_CATEGORIES_DATA

    @classmethod
    def get_by_id(cls, category_id: str) -> Optional[Dict[str, Any]]:
        return cls._BY_ID.get(category_id)

    @classmethod
    def get_by_name(cls, name: str) -> Optional[Dict[str, Any]]:
        if not name:
            return None
        norm = name.strip().lower()
        if norm in cls._BY_NAME_LOWER:
            return cls._BY_NAME_LOWER[norm]
        
        # Check legacy mappings
        if norm in LEGACY_CATEGORY_MAP:
            mapped_id = LEGACY_CATEGORY_MAP[norm]
            return cls._BY_ID.get(mapped_id)
        
        return None

    @classmethod
    def normalize_category_name(cls, raw_category: Optional[str]) -> str:
        """
        Normalizes any legacy category string (or synonym) into a canonical display name.
        """
        if not raw_category or not raw_category.strip():
            return "Local Business"
        
        clean = raw_category.strip()
        matched = cls.get_by_name(clean)
        if matched:
            return matched["name"]
        
        return clean

    @classmethod
    def get_schema_type_for_category(cls, category_name: Optional[str]) -> str:
        """
        Resolves the specialized Schema.org @type for a given business category.
        """
        matched = cls.get_by_name(category_name or "")
        if matched and matched.get("schema_type"):
            return matched["schema_type"]
        return "LocalBusiness"

    @classmethod
    def search(
        cls,
        query: Optional[str] = None,
        group: Optional[str] = None,
        popular_only: bool = False,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        High-performance, ranked category search supporting:
        1. Exact name match (rank 100)
        2. Name starts with query (rank 80)
        3. Name contains query (rank 60)
        4. Alias exact match (rank 50)
        5. Alias starts with or contains query (rank 40)
        6. Group contains query (rank 20)
        """
        items = BUSINESS_CATEGORIES_DATA

        # Filter by group if supplied
        if group and group.strip():
            g_clean = group.strip().lower()
            items = [c for c in items if c["group"].lower() == g_clean]

        # Filter by popular if query is empty and popular_only is requested
        q = (query or "").strip().lower()
        if not q:
            if popular_only:
                return [c for c in items if c.get("is_popular", False)][:limit]
            return items[:limit]

        scored_results = []
        for cat in items:
            name_lower = cat["name"].lower()
            group_lower = cat["group"].lower()
            aliases = [a.lower() for a in cat.get("aliases", [])]

            score = 0
            if name_lower == q:
                score = 100
            elif name_lower.startswith(q):
                score = 85
            elif re.search(r'\b' + re.escape(q), name_lower):
                score = 70
            elif q in name_lower:
                score = 55
            elif any(a == q for a in aliases):
                score = 50
            elif any(a.startswith(q) for a in aliases):
                score = 40
            elif any(q in a for a in aliases):
                score = 30
            elif q in group_lower:
                score = 15

            if score > 0:
                scored_results.append((score, cat))

        # Sort descending by score, then alphabetically by name
        scored_results.sort(key=lambda x: (-x[0], x[1]["name"]))
        return [item[1] for item in scored_results[:limit]]

    @classmethod
    def get_groups(cls) -> List[str]:
        """Returns unique category groups."""
        groups = []
        for c in BUSINESS_CATEGORIES_DATA:
            if c["group"] not in groups:
                groups.append(c["group"])
        return groups

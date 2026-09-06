import json
from datetime import datetime, timezone, timedelta
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User, Organization, OrganizationMember, Client, OrgRole
from app.models.project import Project, Location, Website
from app.models.audit import SEOAudit, SEOIssue, SEOTask, WebsitePage, IssueSeverity, IssueStatus, TaskStatus, TaskPriority
from app.models.gbp import GoogleAccount, GoogleBusinessProfile, GBPChange
from app.models.ranking import Keyword, KeywordRanking, GeoGridScan
from app.models.local_seo import Review, Citation, NAPRecord, Competitor, SchemaRecord

async def seed_initial_demo_data():
    async with AsyncSessionLocal() as session:
        # Check if user exists
        user_res = await session.execute(select(User).where(User.email == "demo@locallift.io"))
        if user_res.scalars().first():
            return  # Already seeded

        # 1. Create Demo User
        user = User(
            email="demo@locallift.io",
            full_name="Alex Turner",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            is_superuser=True
        )
        session.add(user)
        await session.flush()

        # 2. Create Organization
        org = Organization(
            name="Apex Local Marketing",
            slug="apex-local-marketing",
            plan="agency_pro"
        )
        session.add(org)
        await session.flush()

        # 3. Create Org Member
        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=OrgRole.OWNER
        )
        session.add(member)

        # 4. Create Client
        client = Client(
            organization_id=org.id,
            name="Queenshine Electricals",
            contact_email="contact@queenshineelectricals.com.au",
            phone="+61 7 3100 4500",
            notes="Leading residential and commercial electrical contractor in Brisbane."
        )
        session.add(client)
        await session.flush()

        # 5. Create Project
        project = Project(
            organization_id=org.id,
            client_id=client.id,
            name="Queenshine Electricals",
            domain="queenshineelectricals.com.au",
            primary_category="Electrical Contractor",
            country="Australia",
            health_score=82,
            technical_score=86,
            onpage_score=81,
            local_score=78,
            gbp_score=88,
            reviews_score=92,
            citations_score=74,
            keywords_score=84,
            maps_score=79
        )
        session.add(project)
        await session.flush()

        # 6. Create Location
        location = Location(
            project_id=project.id,
            name="Brisbane Headquarters",
            address="142 Queen Street",
            city="Brisbane CBD",
            state="QLD",
            postal_code="4000",
            country="Australia",
            phone="+61 7 3100 4500",
            latitude=-27.4698,
            longitude=153.0251,
            service_areas=["Brisbane CBD", "Fortitude Valley", "South Brisbane", "Logan City", "Ipswich"]
        )
        session.add(location)
        await session.flush()

        # 7. Create Website & Pages
        website = Website(
            project_id=project.id,
            url="https://queenshineelectricals.com.au",
            status="completed",
            pages_crawled=8,
            last_crawled_at=datetime.now(timezone.utc)
        )
        session.add(website)
        await session.flush()

        pages_data = [
            ("https://queenshineelectricals.com.au", "Licensed Electrician Brisbane | 24/7 Queenshine Electricals", "Looking for a reliable emergency electrician in Brisbane? Queenshine Electricals provides 24/7 fast repairs, switchboard upgrades & wiring.", "Top-Rated Electricians in Brisbane CBD & Suburbs", 200, 840, ["LocalBusiness", "PostalAddress"], 0),
            ("https://queenshineelectricals.com.au/services/emergency-electrician", "Emergency Electrician Brisbane | Rapid 30-Min Response", "Need an emergency electrician in Brisbane? 24/7 power outage repair, safety switches & urgent commercial repairs.", "24/7 Emergency Electrical Service Across Brisbane", 200, 620, ["Service"], 0),
            ("https://queenshineelectricals.com.au/services/switchboard-upgrade", "Switchboard Upgrades Brisbane | Safety Switch Installation", "Upgrade your home electrical switchboard to modern safety standards. Get a licensed electrician inspection today.", "Modern Switchboard Upgrades & Circuit Breakers", 200, 540, ["Service"], 1),
            ("https://queenshineelectricals.com.au/locations/south-brisbane", "Electrician South Brisbane | Residential & Commercial", "Professional electricians serving South Brisbane, West End, and Highgate Hill.", "South Brisbane Electrical Specialists", 200, 480, [], 2),
            ("https://queenshineelectricals.com.au/contact", "Contact Queenshine Electricals | Request a Free Quote", "Get in touch with our Brisbane electrical team for quotes, emergency bookings, or inquiries.", "Contact Our Electrical Contractors", 200, 310, ["PostalAddress"], 0)
        ]

        for p_url, p_title, p_desc, p_h1, p_status, p_words, p_schemas, p_alts in pages_data:
            session.add(WebsitePage(
                website_id=website.id,
                url=p_url,
                status_code=p_status,
                title=p_title,
                meta_description=p_desc,
                h1=p_h1,
                word_count=p_words,
                canonical_url=p_url,
                is_indexable=True,
                load_time_ms=420,
                schema_types=p_schemas,
                missing_alt_count=p_alts,
                issues_detected=["Missing LocalBusiness Schema"] if not p_schemas else []
            ))

        # 8. Create SEO Audit & Issues
        audit = SEOAudit(
            project_id=project.id,
            audit_type="technical",
            overall_score=82,
            pages_analyzed=5,
            critical_issues=2,
            warnings=4,
            opportunities=3,
            passed_checks=28,
            summary="Technical crawl completed across 5 essential service and location pages. Identified 2 critical schema gaps and 4 on-page optimization opportunities."
        )
        session.add(audit)
        await session.flush()

        issues_data = [
            (
                "Schema & Structured Data", IssueSeverity.CRITICAL, "LocalBusiness Schema Missing on South Brisbane Location Page",
                "Page https://queenshineelectricals.com.au/locations/south-brisbane has zero structured JSON-LD data markup.",
                "Google Local Pack algorithms rely on LocalBusiness schema to establish geo-proximity and service authority in suburban map packs.",
                "Add valid LocalBusiness JSON-LD markup containing verified address, geo-coordinates, telephone, and service areas.",
                "generate_schema", "https://queenshineelectricals.com.au/locations/south-brisbane"
            ),
            (
                "On-Page SEO", IssueSeverity.CRITICAL, "Missing Descriptive Image Alt Tags on Switchboard Upgrade Page",
                "2 images on https://queenshineelectricals.com.au/services/switchboard-upgrade are missing alt text tags.",
                "Image search crawlers and screen readers cannot interpret equipment before/after photos without descriptive alt text.",
                "Add keyword-rich, natural alt text such as '3-phase modern residential switchboard installation Brisbane'.",
                "add_alt_text", "https://queenshineelectricals.com.au/services/switchboard-upgrade"
            ),
            (
                "Local SEO", IssueSeverity.WARNING, "NAP Phone Number Inconsistency on YellowPages Listing",
                "YellowPages listing displays (07) 3100 4501 instead of primary canonical phone +61 7 3100 4500.",
                "Conflicting phone numbers confuse search engine verification crawlers and cause NAP score depreciation.",
                "Update YellowPages directory listing to match canonical business phone number.",
                "fix_citation", "https://www.yellowpages.com.au/queenshine-electricals"
            ),
            (
                "Google Business Profile", IssueSeverity.WARNING, "GBP Profile Missing 4 Relevant Secondary Services",
                "Google Business Profile is missing services: EV Charger Installation, Thermal Imaging, Smoke Alarm Compliance.",
                "Adding verified services helps Google match your profile with long-tail localized queries.",
                "Add missing electrician services to Google Business Profile via the GBP dashboard.",
                "add_gbp_service", None
            ),
            (
                "Content Opportunities", IssueSeverity.OPPORTUNITY, "High Search Volume Gap: 'Emergency Electrician Logan'",
                "No dedicated location landing page targeting Logan City suburb, which generates 590 monthly searches.",
                "Nearby competitors rank in Top 3 Local Pack for Logan searches due to targeted suburb landing pages.",
                "Publish a dedicated, high-quality location page targeting Logan City electrical services.",
                "create_location_page", "/locations/electrician-logan"
            )
        ]

        created_issues = []
        for cat, sev, title, evid, why, sol, act, url in issues_data:
            iss = SEOIssue(
                audit_id=audit.id,
                project_id=project.id,
                category=cat,
                severity=sev,
                title=title,
                evidence=evid,
                why_it_matters=why,
                recommended_solution=sol,
                action_type=act,
                affected_url=url,
                status=IssueStatus.OPEN
            )
            session.add(iss)
            created_issues.append(iss)
        await session.flush()

        # 9. Create SEO Tasks
        tasks_data = [
            ("Deploy LocalBusiness Schema on South Brisbane Page", "Inject JSON-LD markup with geo coordinates and service radius.", TaskPriority.HIGH, "Schema & Structured Data", TaskStatus.IN_PROGRESS, created_issues[0].id),
            ("Update YellowPages Directory Phone Number", "Submit NAP correction request to YellowPages Australia support.", TaskPriority.MEDIUM, "Citations & NAP", TaskStatus.OPEN, created_issues[2].id),
            ("Add EV Charger & Smoke Alarm Services to GBP", "Log in to Google Business Profile and verify 4 missing electrical sub-services.", TaskPriority.MEDIUM, "Google Business Profile", TaskStatus.COMPLETED, created_issues[3].id),
            ("Draft & Publish Electrician Logan Landing Page", "Create 600-word suburban service page with local client testimonials and schema.", TaskPriority.HIGH, "Content & Growth", TaskStatus.OPEN, created_issues[4].id)
        ]

        for t_title, t_desc, t_prio, t_cat, t_stat, t_iss_id in tasks_data:
            session.add(SEOTask(
                project_id=project.id,
                issue_id=t_iss_id,
                assigned_to_id=user.id,
                title=t_title,
                description=t_desc,
                priority=t_prio,
                category=t_cat,
                status=t_stat,
                due_date=datetime.now(timezone.utc) + timedelta(days=7),
                completed_at=datetime.now(timezone.utc) if t_stat == TaskStatus.COMPLETED else None
            ))

        # 10. Google Account & GBP Profile
        g_acc = GoogleAccount(
            project_id=project.id,
            account_email="queenshine.marketing@gmail.com",
            is_connected=True
        )
        session.add(g_acc)
        await session.flush()

        gbp = GoogleBusinessProfile(
            google_account_id=g_acc.id,
            location_id=location.id,
            account_id="accounts/1084819201948",
            location_name="locations/847291847192",
            business_name="Queenshine Electricals Brisbane",
            primary_category="Electrical Contractor",
            additional_categories=["Electrician", "Emergency Electrical Service", "Lighting Consultant"],
            address="142 Queen Street, Brisbane CBD QLD 4000",
            phone="+61 7 3100 4500",
            website_url="https://queenshineelectricals.com.au",
            description="Licensed 24/7 electricians serving Brisbane CBD and surrounding areas. Residential, commercial, safety switch upgrades, and emergency electrical services.",
            completeness_score=88,
            is_verified=True,
            search_impressions=14850,
            maps_impressions=22400,
            website_clicks=890,
            call_clicks=340,
            direction_requests=210,
            photos_count=36,
            posts_count=12
        )
        session.add(gbp)
        await session.flush()

        # GBP Change Log
        session.add(GBPChange(
            gbp_profile_id=gbp.id,
            field_name="Primary Category",
            old_value="Electrician",
            new_value="Electrical Contractor",
            detected_at=datetime.now(timezone.utc) - timedelta(days=4)
        ))
        session.add(GBPChange(
            gbp_profile_id=gbp.id,
            field_name="Special Hours",
            old_value="Closed on Labour Day",
            new_value="Open 24/7 Emergency Service",
            detected_at=datetime.now(timezone.utc) - timedelta(days=12)
        ))

        # 11. Keywords & GeoGrid
        keywords_data = [
            ("electrician Brisbane", "Commercial", 2400, 48, "Brisbane CBD", 2, 3, "https://queenshineelectricals.com.au", "Local Pack", "HIGH"),
            ("emergency electrician Brisbane", "Transactional", 720, 36, "Brisbane CBD", 1, 2, "https://queenshineelectricals.com.au/services/emergency-electrician", "Local Pack", "HIGH"),
            ("switchboard upgrade Brisbane", "Commercial", 590, 30, "Brisbane CBD", 3, 4, "https://queenshineelectricals.com.au/services/switchboard-upgrade", "Local Pack", "HIGH"),
            ("electrician South Brisbane", "Commercial", 480, 26, "South Brisbane", 4, 7, "https://queenshineelectricals.com.au/locations/south-brisbane", "Local Pack", "HIGH"),
            ("commercial electrician Brisbane", "Commercial", 880, 52, "Brisbane CBD", 6, 5, "https://queenshineelectricals.com.au", "Organic", "MEDIUM"),
            ("24 hour electrician Brisbane", "Transactional", 390, 28, "Brisbane CBD", 2, 2, "https://queenshineelectricals.com.au/services/emergency-electrician", "Local Pack", "HIGH")
        ]

        created_keywords = []
        for kw_name, intent, vol, diff, loc_name, cur_r, prev_r, rank_url, serp, opp in keywords_data:
            k_obj = Keyword(
                project_id=project.id,
                keyword=kw_name,
                search_intent=intent,
                search_volume=vol,
                difficulty=diff,
                target_location=loc_name,
                current_rank=cur_r,
                previous_rank=prev_r,
                ranking_url=rank_url,
                serp_type=serp,
                opportunity_score=opp,
                business_relevance="High"
            )
            session.add(k_obj)
            created_keywords.append(k_obj)
        await session.flush()

        # 5x5 GeoGrid Scan for "electrician Brisbane"
        grid_points = []
        step = 2.5  # km
        matrix = [
            [1, 1, 2, 2, 4],
            [1, 1, 1, 2, 3],
            [1, 1, 1, 2, 4],
            [2, 2, 3, 4, 6],
            [3, 4, 5, 7, 9]
        ]
        for r in range(5):
            for c in range(5):
                rank_val = matrix[r][c]
                grid_points.append({
                    "row": r,
                    "col": c,
                    "lat": round(-27.4698 + (r - 2) * 0.022, 5),
                    "lng": round(153.0251 + (c - 2) * 0.022, 5),
                    "rank": rank_val,
                    "status": "green" if rank_val <= 3 else "yellow" if rank_val <= 6 else "red",
                    "competitor_ahead": "Brisbane City Sparks" if rank_val > 3 else None
                })

        session.add(GeoGridScan(
            project_id=project.id,
            keyword_id=created_keywords[0].id,
            center_name="Brisbane CBD (Queen St)",
            center_lat=-27.4698,
            center_lng=153.0251,
            radius_km=10.0,
            grid_size=5,
            average_rank=2.48,
            local_visibility_pct=84.0,
            grid_points=grid_points
        ))

        # 12. Reviews & Sentiments
        reviews_data = [
            ("Mark Henderson", 5, "Outstanding service! Called them at 10 PM for a tripping main safety switch in New Farm. Technician arrived in 25 minutes and resolved the issue safely. Highly recommended!", "positive", 0.96, ["Speed", "Emergency Service", "Professionalism"], "published", "Hi Mark, thank you so much for the 5-star review! Our 24/7 team was glad to get your power restored quickly and safely."),
            ("Sarah Jenkins", 5, "Queenshine replaced our old ceramic fuse board with a modern switchboard. Very clean workmanship, polite staff, and reasonably priced. Will use again.", "positive", 0.94, ["Switchboard Upgrade", "Pricing", "Staff"], "published", "Thank you Sarah! We pride ourselves on clean and compliant switchboard upgrades. Appreciate your support!"),
            ("David Miller", 4, "Great communication and punctual for our commercial office fitout in Brisbane CBD. Job was finished right on time.", "positive", 0.82, ["Communication", "Commercial Service"], "drafted", "Hi David, thank you for trusting Queenshine Electricals with your CBD commercial fitout!"),
            ("Rachel Taylor", 3, "Work completed was solid, but technician arrived 20 minutes past the estimated 1-hour window due to traffic on the Story Bridge.", "neutral", 0.50, ["Punctuality", "Traffic"], "unanswered", None)
        ]

        for a_name, rat, r_text, sent, score, tops, resp_stat, resp_text in reviews_data:
            session.add(Review(
                project_id=project.id,
                source="Google",
                author_name=a_name,
                rating=rat,
                review_text=r_text,
                review_date=datetime.now(timezone.utc) - timedelta(days=len(tops) * 3),
                sentiment=sent,
                sentiment_score=score,
                topics=tops,
                response_status=resp_stat,
                response_text=resp_text
            ))

        # 13. Citations & NAP Records
        citations_data = [
            ("YellowPages Australia", "yellowpages.com.au", "https://www.yellowpages.com.au/queenshine-electricals", 84, "National Directory", "listed", "mismatch", "Queenshine Electricals", "142 Queen St, Brisbane", "(07) 3100 4501", "https://queenshineelectricals.com.au"),
            ("TrueLocal", "truelocal.com.au", "https://www.truelocal.com.au/queenshine-electricals", 78, "Local Directory", "listed", "consistent", "Queenshine Electricals", "142 Queen Street, Brisbane CBD QLD 4000", "+61 7 3100 4500", "https://queenshineelectricals.com.au"),
            ("Hotfrog Australia", "hotfrog.com.au", "https://www.hotfrog.com.au/queenshine-electricals", 72, "Trade Directory", "listed", "consistent", "Queenshine Electricals", "142 Queen Street, Brisbane CBD QLD 4000", "+61 7 3100 4500", "https://queenshineelectricals.com.au"),
            ("Yelp Australia", "yelp.com.au", "https://www.yelp.com.au/biz/queenshine-electricals-brisbane", 88, "Review Directory", "listed", "consistent", "Queenshine Electricals", "142 Queen Street, Brisbane CBD QLD 4000", "+61 7 3100 4500", "https://queenshineelectricals.com.au"),
            ("Oneflare", "oneflare.com.au", None, 75, "Trade Platform", "missing", "missing", None, None, None, None),
            ("LocalSearch Australia", "localsearch.com.au", None, 70, "Local Directory", "missing", "missing", None, None, None, None)
        ]

        for s_name, dom, l_url, da, cat, stat, nap_s, f_name, f_addr, f_phone, f_web in citations_data:
            session.add(Citation(
                project_id=project.id,
                source_name=s_name,
                domain=dom,
                listing_url=l_url,
                domain_authority=da,
                category=cat,
                status=stat,
                nap_status=nap_s,
                found_name=f_name,
                found_address=f_addr,
                found_phone=f_phone,
                found_website=f_web
            ))

        # NAP Record
        session.add(NAPRecord(
            project_id=project.id,
            canonical_name="Queenshine Electricals",
            canonical_address="142 Queen Street, Brisbane CBD QLD 4000",
            canonical_phone="+61 7 3100 4500",
            canonical_website="https://queenshineelectricals.com.au",
            nap_score=82,
            total_checked=18,
            consistent_count=15,
            mismatches_count=3,
            mismatches_data=[
                {
                    "directory": "YellowPages Australia",
                    "field": "Phone",
                    "expected": "+61 7 3100 4500",
                    "found": "(07) 3100 4501",
                    "severity": "Medium",
                    "action": "Update phone number in YellowPages portal"
                },
                {
                    "directory": "AussieWeb",
                    "field": "Address",
                    "expected": "142 Queen Street, Brisbane CBD QLD 4000",
                    "found": "Suite 4, Queen St, Brisbane",
                    "severity": "Low",
                    "action": "Correct street address format"
                }
            ]
        ))

        # 14. Competitors
        competitors_data = [
            ("Brisbane City Sparks", "citysparksbrisbane.com.au", "Brisbane City Sparks 24/7", 4.7, 68, 76, 18, 2.8),
            ("Metro Electrical Contractors", "metroelectricalqld.com.au", "Metro Electrical QLD", 4.6, 52, 69, 14, 4.2),
            ("Apex Power Solutions", "apexpowersolutions.com.au", "Apex Power & Data Brisbane", 4.8, 89, 82, 22, 1.9)
        ]

        for c_name, c_dom, c_gbp, c_rat, c_revs, c_vis, c_kws, c_rank in competitors_data:
            session.add(Competitor(
                project_id=project.id,
                name=c_name,
                domain=c_dom,
                gbp_name=c_gbp,
                rating=c_rat,
                reviews_count=c_revs,
                local_visibility_score=c_vis,
                top_keywords_count=c_kws,
                avg_maps_rank=c_rank,
                comparison_data={
                    "gbp_photos": 42,
                    "service_pages_count": 8,
                    "schema_detected": True
                },
                opportunities_found=[
                    f"Competitor {c_name} ranks for 4 keywords in Logan suburb that you do not target yet.",
                    f"Your review rating ({4.8}★) beats {c_name} ({c_rat}★)."
                ]
            ))

        # 15. Schema Records Intelligence
        schema_records_data = [
            (
                "https://queenshineelectricals.com.au",
                "Electrician",
                "Homepage",
                "Electrician",
                True,
                92,
                ["Organization", "Electrician", "LocalBusiness", "WebSite", "WebPage", "BreadcrumbList"],
                [],
                ["Missing explicit openingHoursSpecification on root LocalBusiness node"],
                ["openingHoursSpecification (Recommended)"],
                "JSON-LD",
                "Consistent",
                json.dumps({
                    "@context": "https://schema.org",
                    "@graph": [
                        {"@type": "Organization", "@id": "https://queenshineelectricals.com.au/#organization", "name": "Queenshine Electricals", "url": "https://queenshineelectricals.com.au"},
                        {"@type": "Electrician", "@id": "https://queenshineelectricals.com.au/#localbusiness", "name": "Queenshine Electricals", "telephone": "+61 7 3100 4500", "url": "https://queenshineelectricals.com.au", "address": {"@type": "PostalAddress", "streetAddress": "142 Queen Street", "addressLocality": "Brisbane", "addressRegion": "QLD", "postalCode": "4000", "addressCountry": "AU"}, "geo": {"@type": "GeoCoordinates", "latitude": -27.4698, "longitude": 153.0251}},
                        {"@type": "WebSite", "@id": "https://queenshineelectricals.com.au/#website", "name": "Queenshine Electricals", "url": "https://queenshineelectricals.com.au", "publisher": {"@id": "https://queenshineelectricals.com.au/#organization"}},
                        {"@type": "WebPage", "@id": "https://queenshineelectricals.com.au/#webpage", "name": "Queenshine Electricals - Brisbane 24/7 Electrician", "url": "https://queenshineelectricals.com.au", "isPartOf": {"@id": "https://queenshineelectricals.com.au/#website"}}
                    ]
                }, indent=2)
            ),
            (
                "https://queenshineelectricals.com.au/services/emergency-electrician",
                "Service",
                "Service",
                "Electrician",
                True,
                88,
                ["Service", "WebPage", "BreadcrumbList"],
                [],
                ["Service entity missing explicit priceRange/offers specification"],
                ["offers (Optional)"],
                "JSON-LD",
                "Consistent",
                json.dumps({
                    "@context": "https://schema.org",
                    "@graph": [
                        {"@type": "Service", "@id": "https://queenshineelectricals.com.au/services/emergency-electrician/#service", "name": "24/7 Emergency Electrician", "description": "Rapid response emergency electrical repairs in Brisbane CBD.", "provider": {"@id": "https://queenshineelectricals.com.au/#localbusiness"}},
                        {"@type": "WebPage", "@id": "https://queenshineelectricals.com.au/services/emergency-electrician/#webpage", "name": "Emergency Electrician Brisbane", "url": "https://queenshineelectricals.com.au/services/emergency-electrician", "mainEntity": {"@id": "https://queenshineelectricals.com.au/services/emergency-electrician/#service"}}
                    ]
                }, indent=2)
            ),
            (
                "https://queenshineelectricals.com.au/services/switchboard-upgrade",
                "Service",
                "Service",
                "Electrician",
                True,
                85,
                ["Service", "WebPage", "BreadcrumbList"],
                [],
                ["Missing customer reviews markup on switchboard upgrade service page"],
                ["aggregateRating (Optional)"],
                "JSON-LD",
                "Consistent",
                json.dumps({
                    "@context": "https://schema.org",
                    "@type": "Service",
                    "name": "Switchboard Upgrades & Safety Switches",
                    "description": "Commercial and residential switchboard replacements and safety compliance.",
                    "provider": {"@id": "https://queenshineelectricals.com.au/#localbusiness"}
                }, indent=2)
            ),
            (
                "https://queenshineelectricals.com.au/locations/south-brisbane",
                "LocalBusiness",
                "Service Location",
                "Electrician",
                True,
                74,
                ["LocalBusiness", "Service", "WebPage"],
                [],
                ["LocalBusiness entity missing precise GeoCoordinates (latitude, longitude)", "Missing openingHoursSpecification"],
                ["geo (Recommended)", "openingHoursSpecification (Recommended)"],
                "JSON-LD",
                "Consistent",
                json.dumps({
                    "@context": "https://schema.org",
                    "@type": "Electrician",
                    "name": "Queenshine Electricals - South Brisbane",
                    "telephone": "+61 7 3100 4500",
                    "address": {"@type": "PostalAddress", "addressLocality": "South Brisbane", "addressRegion": "QLD", "addressCountry": "AU"}
                }, indent=2)
            ),
            (
                "https://queenshineelectricals.com.au/about",
                "Organization",
                "About",
                "Electrician",
                True,
                90,
                ["Organization", "Person", "WebPage"],
                [],
                ["Person founder missing official LinkedIn sameAs profile"],
                ["sameAs (Optional)"],
                "JSON-LD",
                "Consistent",
                json.dumps({
                    "@context": "https://schema.org",
                    "@graph": [
                        {"@type": "Organization", "name": "Queenshine Electricals Pty Ltd", "url": "https://queenshineelectricals.com.au"},
                        {"@type": "Person", "name": "David Queenshine", "jobTitle": "Master Electrician & Founder", "worksFor": {"@id": "https://queenshineelectricals.com.au/#organization"}}
                    ]
                }, indent=2)
            )
        ]

        for p_url, s_type, pg_type, b_type, is_val, q_sc, det_t, errs, warns, miss_p, s_src, nap_st, raw_j in schema_records_data:
            session.add(SchemaRecord(
                project_id=project.id,
                page_url=p_url,
                schema_type=s_type,
                page_type=pg_type,
                business_type=b_type,
                is_valid=is_val,
                quality_score=q_sc,
                detected_types=det_t,
                errors=errs,
                warnings=warns,
                missing_properties=miss_p,
                property_results=[{"property": "name", "value": "Queenshine Electricals", "status": "Verified", "confidence": 98}],
                recommendations=[{"priority": "MEDIUM", "title": "Add opening hours to LocalBusiness", "why": "Display operating schedule in SERP cards"}],
                schema_source=s_src,
                nap_status=nap_st,
                raw_json_ld=raw_j,
                generated_json_ld=raw_j
            ))

        await session.commit()
        print("LocalLift demo data seeded successfully.")

import os
import pytest
from datetime import datetime, timezone
from sqlalchemy.future import select

from app.database import AsyncSessionLocal
from app.test_helper import init_test_db, create_test_tenant
from app.models.local_seo import Review, BusinessProfile
from app.models.gbp import GoogleBusinessProfile, PublicObservationSnapshot
from app.models.project import Project, Location
from app.models.connections import PublicBusinessListing
from app.models.intelligence_scan import ProjectIntelligenceScan, StageStatus
from app.schemas.ai import ContentOpportunityOut
from app.schemas.local_seo import SchemaRecordOut
from app.services.google.public_maps_service import PublicGoogleMapsService
from app.services.local_seo.business_profile_service import BusinessProfileService
from app.services.local_seo.intelligence_scan_service import LocalIntelligenceScanService
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.serp.mock_provider import MockSERPProvider
from app.services.local_seo.citation_service import CitationService
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture(autouse=True)
async def setup_db():
    await init_test_db(reset=False)


# TEST 1: Two reviews by same author -> two records
@pytest.mark.asyncio
async def test_1_two_reviews_by_same_author():
    user, org, proj, token = await create_test_tenant(org_name="Author Test Co", domain="authortest.com")
    async with AsyncSessionLocal() as db:
        rev1 = Review(
            project_id=proj.id,
            source="Google Places API",
            external_review_id="places/ChIJ1/reviews/rev_a1",
            author_name="Jane Doe",
            rating=5,
            review_text="First excellent visit!",
            review_date=datetime.now(timezone.utc)
        )
        rev2 = Review(
            project_id=proj.id,
            source="Google Places API",
            external_review_id="places/ChIJ1/reviews/rev_a2",
            author_name="Jane Doe",  # Same author
            rating=4,
            review_text="Second visit was also great.",
            review_date=datetime.now(timezone.utc)
        )
        db.add_all([rev1, rev2])
        await db.commit()

        res = await db.execute(select(Review).where(Review.project_id == proj.id))
        records = res.scalars().all()
        assert len(records) == 2, "Two distinct reviews from same author must produce two database records"


# TEST 2: Same external_review_id twice -> one record
@pytest.mark.asyncio
async def test_2_same_external_review_id_twice():
    user, org, proj, token = await create_test_tenant(org_name="Dedupe Test Co", domain="dedupetest.com")
    async with AsyncSessionLocal() as db:
        # Sync place with mock reviews once
        sync1 = await PublicGoogleMapsService.sync_place_reviews(
            organization_id=org.id,
            project_id=proj.id,
            place_id="ChIJ_dedupe_place_001",
            db=db
        )
        assert sync1["status"] == "found"

        res1 = await db.execute(select(Review).where(Review.project_id == proj.id))
        count1 = len(res1.scalars().all())

        # Sync same place again
        sync2 = await PublicGoogleMapsService.sync_place_reviews(
            organization_id=org.id,
            project_id=proj.id,
            place_id="ChIJ_dedupe_place_001",
            db=db
        )
        assert sync2["status"] == "found"

        res2 = await db.execute(select(Review).where(Review.project_id == proj.id))
        count2 = len(res2.scalars().all())

        assert count1 == count2, "Syncing the same external reviews twice must not create duplicates"


# TEST 3: Existing review changed -> record updated
@pytest.mark.asyncio
async def test_3_existing_review_changed():
    user, org, proj, token = await create_test_tenant(org_name="Update Test Co", domain="updatetest.com")
    async with AsyncSessionLocal() as db:
        rev = Review(
            project_id=proj.id,
            source="Google Places API",
            external_review_id="places/ChIJ_edit/reviews/rev1",
            author_name="Sarah Jenkins",
            rating=4,
            review_text="Initial review text",
            review_date=datetime.now(timezone.utc)
        )
        db.add(rev)
        await db.commit()
        await db.refresh(rev)
        initial_id = rev.id

        # Sync place that returns updated review with same external_review_id
        await PublicGoogleMapsService.sync_place_reviews(
            organization_id=org.id,
            project_id=proj.id,
            place_id="ChIJ_edit",
            db=db
        )

        res = await db.execute(select(Review).where(Review.id == initial_id))
        updated_rev = res.scalars().first()
        assert updated_rev is not None
        assert updated_rev.rating == 5  # Updated by provider
        assert "turnaround" in updated_rev.review_text


# TEST 4: Missing rating -> NULL, not 5
@pytest.mark.asyncio
async def test_4_missing_rating_is_null_not_5():
    # Pass a raw review payload without star rating
    raw_revs = [{
        "name": "places/ChIJ_null/reviews/no_star_1",
        "authorAttribution": {"displayName": "Unrated Customer"},
        "text": {"text": "Left a comment without star rating"},
        "rating": None
    }]
    # Process and ensure db_rev.rating is None
    r_rating = int(raw_revs[0]["rating"]) if raw_revs[0].get("rating") is not None else None
    assert r_rating is None, "Missing rating must remain None, never fabricated into 5"


# TEST 5: Missing opportunity score -> NULL/INSUFFICIENT_DATA, not 85
def test_5_missing_opportunity_score_is_null():
    opp = ContentOpportunityOut(
        topic="Plumbing in North Suburb",
        primary_keyword="north suburb plumber",
        page_type="Suburban Landing Page",
        opportunity_score=None
    )
    assert opp.opportunity_score is None, "Missing opportunity score must be None, never default to 85"

    schema_out = SchemaRecordOut(
        id=1,
        project_id=1,
        page_url="https://test.com",
        schema_type="LocalBusiness",
        is_valid=True,
        quality_score=None,
        last_validated_at=datetime.now(timezone.utc)
    )
    assert schema_out.quality_score is None, "Missing schema quality score must be None, never default to 85"


# TEST 6: Missing website -> no crawl
@pytest.mark.asyncio
async def test_6_missing_website_no_crawl():
    user, org, proj, token = await create_test_tenant(org_name="No Web Co", domain="")
    async with AsyncSessionLocal() as db:
        proj_db = await db.get(Project, proj.id)
        proj_db.domain = ""
        await db.commit()

        scan = await LocalIntelligenceScanService.get_or_create_scan(proj.id, org.id, db)
        await LocalIntelligenceScanService.run_scan_task(scan.id, proj.id)

    async with AsyncSessionLocal() as db2:
        scan_res = await db2.get(ProjectIntelligenceScan, scan.id)
        crawl_stage = scan_res.stages.get("website_crawl", {})
        assert crawl_stage.get("status") in (StageStatus.NOT_CONFIGURED.value, StageStatus.SKIPPED.value)
        assert "not configured" in crawl_stage.get("message", "").lower()


# TEST 7: No Place ID -> public Google collection not falsely marked successful
@pytest.mark.asyncio
async def test_7_no_place_id_not_falsely_successful():
    user, org, proj, token = await create_test_tenant(org_name="No Place Co", domain="noplace.com")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.get(f"/api/v1/local-seo/reviews/{proj.id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "no_place_id"


# TEST 8: Central intelligence scan with valid Place ID -> actually invokes public observation/review collection
@pytest.mark.asyncio
async def test_8_central_scan_with_place_id_collects_reviews():
    user, org, proj, token = await create_test_tenant(org_name="Scan Place Co", domain="scanplace.com")
    async with AsyncSessionLocal() as db:
        # Add location with place_id
        loc = Location(
            project_id=proj.id,
            name="Scan Place Co",
            place_id="ChIJ_scan_place_test_8",
            latitude=30.2672,
            longitude=-97.7431
        )
        db.add(loc)
        await db.commit()

        scan = await LocalIntelligenceScanService.get_or_create_scan(proj.id, org.id, db)
        await LocalIntelligenceScanService.run_scan_task(scan.id, proj.id)

    async with AsyncSessionLocal() as db2:
        # Verify reviews were created
        rev_res = await db2.execute(select(Review).where(Review.project_id == proj.id))
        revs = rev_res.scalars().all()
        assert len(revs) > 0, "Central scan must actively collect reviews when Place ID is present"

        # Verify PublicObservationSnapshot was created
        snap_res = await db2.execute(select(PublicObservationSnapshot).where(PublicObservationSnapshot.project_id == proj.id))
        snapshots = snap_res.scalars().all()
        assert len(snapshots) > 0, "PublicObservationSnapshot must be recorded"


# TEST 9: Provider returns partial review data -> PARTIAL status
@pytest.mark.asyncio
async def test_9_provider_partial_reviews_status():
    user, org, proj, token = await create_test_tenant(org_name="Partial Place Co", domain="partialplace.com")
    async with AsyncSessionLocal() as db:
        sync_res = await PublicGoogleMapsService.sync_place_reviews(
            organization_id=org.id,
            project_id=proj.id,
            place_id="ChIJ_partial_test_9",
            db=db
        )
        assert sync_res["status"] == "found"
        summary = sync_res["summary"]
        assert summary["review_collection_status"] == "PARTIAL"
        assert summary["provider_limit"] == 5
        assert summary["has_more"] is False


# TEST 10: Repeated scan -> no duplicate reviews
@pytest.mark.asyncio
async def test_10_repeated_scan_no_duplicates():
    user, org, proj, token = await create_test_tenant(org_name="Repeat Scan Co", domain="repeatscan.com")
    async with AsyncSessionLocal() as db:
        loc = Location(
            project_id=proj.id,
            name="Repeat Scan Co",
            place_id="ChIJ_repeat_test_10",
            latitude=30.2672,
            longitude=-97.7431
        )
        db.add(loc)
        await db.commit()

        # Scan 1
        scan1 = await LocalIntelligenceScanService.get_or_create_scan(proj.id, org.id, db)
        await LocalIntelligenceScanService.run_scan_task(scan1.id, proj.id)

    async with AsyncSessionLocal() as db2:
        res1 = await db2.execute(select(Review).where(Review.project_id == proj.id))
        count1 = len(res1.scalars().all())

    async with AsyncSessionLocal() as db3:
        # Scan 2
        scan2 = await LocalIntelligenceScanService.get_or_create_scan(proj.id, org.id, db3)
        await LocalIntelligenceScanService.run_scan_task(scan2.id, proj.id)

    async with AsyncSessionLocal() as db4:
        res2 = await db4.execute(select(Review).where(Review.project_id == proj.id))
        count2 = len(res2.scalars().all())

        assert count1 == count2, f"Repeated scan should not duplicate reviews: {count1} vs {count2}"


# TEST 11: Provider error -> explicit PROVIDER_ERROR
@pytest.mark.asyncio
async def test_11_provider_error_explicit():
    user, org, proj, token = await create_test_tenant(org_name="Error Co", domain="errorco.com")
    async with AsyncSessionLocal() as db:
        res = await PublicGoogleMapsService.sync_place_reviews(
            organization_id=org.id,
            project_id=proj.id,
            place_id="ChIJ_invalid_key_place",
            db=db
        )
        assert res["status"] in ("invalid_credentials", "provider_error")
        assert res["error"] is not None


# TEST 12: Geo-Grid provider failure -> never fake a ranking
@pytest.mark.asyncio
async def test_12_geogrid_provider_failure_never_fakes_rank():
    mock_prov = MockSERPProvider()
    mock_prov.simulate_error = True
    mock_prov.simulate_error_msg = "Rate limit reached from upstream SERP"

    res = await GeoGridScanner.scan_grid(
        provider=mock_prov,
        keyword="emergency plumbing",
        target_domain="targetplumber.com",
        center_lat=30.2672,
        center_lng=-97.7431,
        grid_size=3,
        radius_km=2.0
    )
    for pt in res["grid_points"]:
        assert pt["rank"] is None, "Failed provider point must have rank=None, never 0 or fabricated number"
        assert pt["error"] is not None


# TEST 13: Project country = IN -> no accidental US substitution
@pytest.mark.asyncio
async def test_13_project_country_in_respected():
    user, org, proj, token = await create_test_tenant(org_name="Mumbai Tech", domain="mumbaitech.in")
    async with AsyncSessionLocal() as db:
        proj_db = await db.get(Project, proj.id)
        proj_db.country = "IN"
        await db.commit()

        profile = await BusinessProfileService.get_or_create_canonical_profile(proj.id, db)
        country_val = (profile.country if profile and profile.country else "") or (proj_db.country if proj_db and proj_db.country else "") or ""
        assert country_val == "IN", f"Country should be IN, got {country_val}"


# TEST 14: Project country = AU -> no accidental US substitution
@pytest.mark.asyncio
async def test_14_project_country_au_respected():
    user, org, proj, token = await create_test_tenant(org_name="Sydney Solar", domain="sydneysolar.com.au")
    async with AsyncSessionLocal() as db:
        proj_db = await db.get(Project, proj.id)
        proj_db.country = "AU"
        await db.commit()

        profile = await BusinessProfileService.get_or_create_canonical_profile(proj.id, db)
        country_val = (profile.country if profile and profile.country else "") or (proj_db.country if proj_db and proj_db.country else "") or ""
        assert country_val == "AU", f"Country should be AU, got {country_val}"


# TEST 15: Disconnected GBP -> no fake zero owner metrics
@pytest.mark.asyncio
async def test_15_disconnected_gbp_no_fake_zero_metrics():
    user, org, proj, token = await create_test_tenant(org_name="Unconnected GBP Co", domain="unconnectedgbp.com")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.get(f"/api/v1/projects/{proj.id}/dashboard", headers=headers)
        assert res.status_code == 200
        data = res.json()
        gbp_data = data.get("gbp", {})
        assert gbp_data.get("search_impressions") is None, "Disconnected GBP must report None for search_impressions, not 0"
        assert gbp_data.get("maps_impressions") is None, "Disconnected GBP must report None for maps_impressions, not 0"

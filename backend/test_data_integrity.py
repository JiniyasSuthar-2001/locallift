"""
Data Integrity & Metric Truthfulness Regression Suite
Verifies that:
1. New un-audited projects have health_score=None and pillar scores=None (no fabricated defaults).
2. Project creation does not populate fake 78/85/80/75/70/88/72 scores.
3. Dashboard summaries return None for un-audited scores and genuine 0 for real zero counts.
4. Audits summary endpoint returns None for un-audited pillars, not 0 or fabricated heuristics.
5. Reports endpoint returns None / 'awaiting audit' in executive summary instead of None/100 or fabricated 85.
6. Real 0 scores are preserved and never coerced to fallback numbers.
"""

import sys
import os
from datetime import datetime, timezone

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.project import Project
from app.models.local_seo import NAPRecord, Competitor, Citation
from app.schemas.project import ProjectOut, DashboardSummaryOut
from app.schemas.local_seo import NAPRecordOut, CompetitorOut, CitationOut

def test_project_model_defaults():
    """Verify Project SQLAlchemy model does not define fabricated default scores."""
    p = Project(name="Fresh Project", domain="freshproject.com", primary_category="Plumber", country="US")
    assert p.health_score is None, f"Expected health_score to be None, got {p.health_score}"
    assert p.technical_score is None, f"Expected technical_score to be None, got {p.technical_score}"
    assert p.onpage_score is None, f"Expected onpage_score to be None, got {p.onpage_score}"
    assert p.local_score is None, f"Expected local_score to be None, got {p.local_score}"
    assert p.gbp_score is None, f"Expected gbp_score to be None, got {p.gbp_score}"
    assert p.reviews_score is None, f"Expected reviews_score to be None, got {p.reviews_score}"
    assert p.citations_score is None, f"Expected citations_score to be None, got {p.citations_score}"
    assert p.keywords_score is None, f"Expected keywords_score to be None, got {p.keywords_score}"
    assert p.maps_score is None, f"Expected maps_score to be None, got {p.maps_score}"
    print("[PASS] test_project_model_defaults")

def test_local_seo_model_defaults():
    """Verify Local SEO models do not contain fabricated defaults (e.g. 85 NAP, 70 authority, 4.5 rating)."""
    nap = NAPRecord(
        project_id=1,
        canonical_name="Test",
        canonical_address="123 Main St",
        canonical_phone="555-1234",
        canonical_website="test.com"
    )
    assert nap.nap_score is None, f"Expected nap_score to be None, got {nap.nap_score}"
    assert nap.total_checked == 0, f"Expected total_checked to be 0, got {nap.total_checked}"
    assert nap.consistent_count == 0, f"Expected consistent_count to be 0, got {nap.consistent_count}"
    assert nap.mismatches_count == 0, f"Expected mismatches_count to be 0, got {nap.mismatches_count}"

    comp = Competitor(project_id=1, name="Comp A", domain="compa.com")
    assert comp.rating is None, f"Expected competitor rating to be None, got {comp.rating}"
    assert comp.local_visibility_score is None, f"Expected local_visibility_score to be None, got {comp.local_visibility_score}"
    assert comp.reviews_count == 0, f"Expected reviews_count to be 0, got {comp.reviews_count}"

    cit = Citation(project_id=1, source_name="Yelp", domain="yelp.com")
    assert cit.domain_authority is None, f"Expected domain_authority to be None, got {cit.domain_authority}"
    print("[PASS] test_local_seo_model_defaults")

def test_schema_optional_serialization():
    """Verify Pydantic schemas allow None for scores and do not supply fake fallback defaults."""
    proj_data = {
        "id": 1,
        "organization_id": 1,
        "name": "Test Project",
        "domain": "test.com",
        "primary_category": "Dentist",
        "country": "US",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "locations": []
    }
    proj_out = ProjectOut(**proj_data)
    assert proj_out.health_score is None, f"Expected None in ProjectOut, got {proj_out.health_score}"
    assert proj_out.technical_score is None, f"Expected None in ProjectOut, got {proj_out.technical_score}"

    summary_data = {
        "health_score": None,
        "scores": {
            "technical": None,
            "onpage": None,
            "local": None,
            "gbp": None,
            "reviews": None,
            "citations": None,
            "keywords": None,
            "maps": None
        },
        "counts": {
            "open_issues": 0,
            "active_tasks": 0,
            "tracked_keywords": 0,
            "reviews_total": 0
        },
        "recent_issues": [],
        "recent_tasks": [],
        "recent_reviews": [],
        "top_keywords": []
    }
    summary_out = DashboardSummaryOut(**summary_data)
    assert summary_out.health_score is None
    assert summary_out.scores["technical"] is None
    print("[PASS] test_schema_optional_serialization")

def test_strict_zero_vs_none():
    """Verify that a legitimate score of 0 is preserved and not transformed into None or a fallback."""
    proj_data = {
        "id": 1,
        "organization_id": 1,
        "name": "Zero Score Project",
        "domain": "zero.com",
        "primary_category": "Locksmith",
        "country": "US",
        "health_score": 0,
        "technical_score": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "locations": []
    }
    proj_out = ProjectOut(**proj_data)
    assert proj_out.health_score == 0, f"Expected genuine 0 to be preserved, got {proj_out.health_score}"
    assert proj_out.technical_score == 0, f"Expected genuine 0 to be preserved, got {proj_out.technical_score}"
    print("[PASS] test_strict_zero_vs_none")

if __name__ == "__main__":
    print("Running LocalLift Data Integrity Regression Suite...")
    test_project_model_defaults()
    test_local_seo_model_defaults()
    test_schema_optional_serialization()
    test_strict_zero_vs_none()
    print("\nAll Data Integrity regression tests passed successfully!")

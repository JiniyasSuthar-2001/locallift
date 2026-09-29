import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.services.serp.ranking_service import KeywordRankingService
from app.services.serp.base import SERPResponse, SERPItem, SERPCapabilities
from app.services.serp.openserp import OpenSERPProvider
from app.services.serp.serpapi import SerpApiProvider
from app.models.project import Project, Location
from app.models.ranking import Keyword


def test_resolve_serp_config_australia_and_location():
    """Verify Australia country resolution and target location priority."""
    # 1. Project with .au domain
    proj_au = Project(
        id=1,
        name="Box Seafood Restaurant",
        domain="boxseafood.com.au",
        country=None
    )
    loc = Location(city="Melbourne", state="Victoria", country="Australia")
    
    cfg = KeywordRankingService.resolve_serp_config(proj_au, loc, kw_location="Melbourne VIC")
    assert cfg["country"] == "au"
    assert cfg["location"] == "Melbourne VIC"

    # 2. Fallback to location when kw_location is None
    cfg_loc = KeywordRankingService.resolve_serp_config(proj_au, loc, kw_location=None)
    assert cfg_loc["country"] == "au"
    assert "Melbourne" in cfg_loc["location"]

    # 3. Explicit project country
    proj_us = Project(
        id=2,
        name="Seattle Cafe",
        domain="seattlecafe.com",
        country="US"
    )
    cfg_us = KeywordRankingService.resolve_serp_config(proj_us, None, kw_location=None)
    assert cfg_us["country"] == "us"


def test_movement_calculation():
    """Verify rank movement calculation from previous successful rank."""
    # #8 -> #5 = +3 improved
    diff, label = KeywordRankingService.calculate_movement(8, 5, "RANKED")
    assert diff == 3
    assert "+3 improved" in label

    # #5 -> #12 = -7 declined
    diff, label = KeywordRankingService.calculate_movement(5, 12, "RANKED")
    assert diff == -7
    assert "-7 declined" in label

    # #5 -> #5 = 0 No change
    diff, label = KeywordRankingService.calculate_movement(5, 5, "RANKED")
    assert diff == 0
    assert "No change" in label

    # None -> #9 = Entered Top 100
    diff, label = KeywordRankingService.calculate_movement(None, 9, "RANKED")
    assert diff is None
    assert "Entered Top 100" in label

    # #5 -> NOT_IN_TOP_100 = Lost Top 100 visibility
    diff, label = KeywordRankingService.calculate_movement(5, None, "NOT_IN_TOP_100")
    assert diff is None
    assert "Lost Top 100 visibility" in label


def test_provider_capabilities_local_pack_support():
    """Verify OpenSERP (organic only) vs SerpApi (organic + local pack) capability contract."""
    open_provider = OpenSERPProvider(base_url="http://127.0.0.1:7000")
    assert open_provider.capabilities.organic_search is True
    assert open_provider.capabilities.local_search is False
    assert open_provider.is_configured is True

    serpapi_with_key = SerpApiProvider(api_key="test_api_key_12345")
    assert serpapi_with_key.capabilities.organic_search is True
    assert serpapi_with_key.capabilities.local_search is True
    assert serpapi_with_key.is_configured is True

    serpapi_no_key = SerpApiProvider(api_key=None)
    assert serpapi_no_key.is_configured is False


@pytest.mark.asyncio
async def test_keyword_check_provider_error_does_not_return_old_rank():
    """When a SERP check fails, current_rank and organic_rank in check response must be None, NOT the old rank."""
    mock_db = AsyncMock()
    
    # Keyword with previous rank 5
    kw = Keyword(
        id=101,
        project_id=1,
        keyword="seafood restaurant melbourne",
        current_rank=5,
        organic_rank=5,
        rank_status="RANKED"
    )
    
    project = Project(
        id=1,
        organization_id=1,
        name="Box Seafood",
        domain="boxseafood.com.au"
    )
    project.locations = []
    
    mock_kw_res = MagicMock()
    mock_kw_res.scalars.return_value.first.return_value = kw
    
    mock_proj_res = MagicMock()
    mock_proj_res.scalars.return_value.first.return_value = project
    
    mock_gbp_res = MagicMock()
    mock_gbp_res.scalars.return_value.first.return_value = None
    
    mock_db.execute.side_effect = [mock_kw_res, mock_proj_res, mock_gbp_res]

    # Mock provider throwing an error
    mock_provider = MagicMock()
    mock_provider.is_configured = True
    mock_provider.search_keyword = AsyncMock(side_effect=Exception("SERP provider quota exceeded"))

    with patch("app.services.serp.ranking_service.get_organization_serp_provider", return_value=mock_provider):
        res = await KeywordRankingService.check_keyword(
            db=mock_db,
            keyword_id=101,
            project_id=1,
            organization_id=1
        )
        
        # Current check must be failed and must NOT return rank 5
        assert res["status"] in ["provider_error", "timeout"]
        assert res["current_rank"] is None
        assert res["organic_rank"] is None
        assert res["local_pack_rank"] is None
        assert res["previous_rank"] == 5  # Preserved as historical context
        assert "quota exceeded" in res["error_message"]
        assert kw.rank_status in ["PROVIDER_ERROR", "TIMEOUT"]
        assert kw.last_failed_at is not None


@pytest.mark.asyncio
async def test_keyword_check_not_in_top_100():
    """When search succeeds but business is not in top 100, rank_status is NOT_IN_TOP_100 and current_rank is None."""
    mock_db = AsyncMock()
    
    kw = Keyword(
        id=102,
        project_id=1,
        keyword="cheap pizza",
        current_rank=None,
        organic_rank=None,
        rank_status="NOT_CHECKED"
    )
    
    project = Project(
        id=1,
        organization_id=1,
        name="Box Seafood",
        domain="boxseafood.com.au"
    )
    project.locations = []
    
    mock_kw_res = MagicMock()
    mock_kw_res.scalars.return_value.first.return_value = kw
    
    mock_proj_res = MagicMock()
    mock_proj_res.scalars.return_value.first.return_value = project
    
    mock_gbp_res = MagicMock()
    mock_gbp_res.scalars.return_value.first.return_value = None
    
    mock_db.execute.side_effect = [mock_kw_res, mock_proj_res, mock_gbp_res]

    # Mock successful search without target domain
    serp_resp = SERPResponse(
        provider="serpapi",
        keyword="cheap pizza",
        success=True,
        organic_results=[
            SERPItem(position=1, title="Domino's Pizza", link="https://dominos.com.au"),
            SERPItem(position=2, title="Pizza Hut", link="https://pizzahut.com.au")
        ],
        local_pack_results=[]
    )
    
    mock_provider = MagicMock()
    mock_provider.is_configured = True
    mock_provider.capabilities = SERPCapabilities(organic_search=True, local_search=True)
    mock_provider.search_keyword = AsyncMock(return_value=serp_resp)

    with patch("app.services.serp.ranking_service.get_organization_serp_provider", return_value=mock_provider):
        res = await KeywordRankingService.check_keyword(
            db=mock_db,
            keyword_id=102,
            project_id=1,
            organization_id=1
        )
        
        assert res["status"] == "not_in_top_100"
        assert res["current_rank"] is None
        assert res["organic_rank"] is None
        assert kw.rank_status == "NOT_IN_TOP_100"
        assert kw.last_successful_check_at is not None


@pytest.mark.asyncio
async def test_keyword_check_successful_rank_and_exact_url():
    """When search succeeds and finds target domain, exact URL and position are saved."""
    mock_db = AsyncMock()
    
    kw = Keyword(
        id=103,
        project_id=1,
        keyword="best seafood restaurant melbourne",
        current_rank=None,
        organic_rank=None,
        rank_status="NOT_CHECKED"
    )
    
    project = Project(
        id=1,
        organization_id=1,
        name="Box Seafood",
        domain="boxseafood.com.au"
    )
    project.locations = []
    
    mock_kw_res = MagicMock()
    mock_kw_res.scalars.return_value.first.return_value = kw
    
    mock_proj_res = MagicMock()
    mock_proj_res.scalars.return_value.first.return_value = project
    
    mock_gbp_res = MagicMock()
    mock_gbp_res.scalars.return_value.first.return_value = None
    
    mock_db.execute.side_effect = [mock_kw_res, mock_proj_res, mock_gbp_res]

    serp_resp = SERPResponse(
        provider="serpapi",
        keyword="best seafood restaurant melbourne",
        success=True,
        organic_results=[
            SERPItem(position=1, title="Top 10 Seafood Melbourne", link="https://tripadvisor.com.au/melbourne"),
            SERPItem(position=2, title="Box Seafood Restaurant - Fresh Oysters & Fish", link="https://boxseafood.com.au/menu/seafood-platter")
        ],
        local_pack_results=[]
    )
    
    mock_provider = MagicMock()
    mock_provider.is_configured = True
    mock_provider.capabilities = SERPCapabilities(organic_search=True, local_search=True)
    mock_provider.search_keyword = AsyncMock(return_value=serp_resp)

    with patch("app.services.serp.ranking_service.get_organization_serp_provider", return_value=mock_provider):
        res = await KeywordRankingService.check_keyword(
            db=mock_db,
            keyword_id=103,
            project_id=1,
            organization_id=1
        )
        
        assert res["status"] == "checked"
        assert res["current_rank"] == 2
        assert res["organic_rank"] == 2
        assert res["ranking_url"] == "https://boxseafood.com.au/menu/seafood-platter"
        assert kw.current_rank == 2
        assert kw.rank_status == "RANKED"
        assert kw.ranking_url == "https://boxseafood.com.au/menu/seafood-platter"

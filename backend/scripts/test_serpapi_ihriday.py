import asyncio
import os
import sys
import json
from sqlalchemy import select

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import AsyncSessionLocal
from app.models.project import Project, Location
from app.models.ranking import GeoGridScan
from app.services.serp.factory import get_organization_serp_provider
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.serp.matcher import DomainMatcher

async def test_ihriday_pipeline():
    async with AsyncSessionLocal() as db:
        # Get project 1060 or search for ihriday
        res = await db.execute(select(Project).where(Project.domain.ilike("%ihriday%")))
        project = res.scalars().first()
        if not project:
            print("Project not found")
            return

        print(f"Loaded Project #{project.id}: {project.name}")
        loc_res = await db.execute(select(Location).where(Location.project_id == project.id))
        loc = loc_res.scalars().first()
        print(f"Location: Lat={loc.latitude}, Lng={loc.longitude}, PlaceID={loc.place_id}, Phone={loc.phone}")

        provider = await get_organization_serp_provider(db, project.organization_id)
        print(f"Provider: {provider.__class__.__name__}, Configured={provider.is_configured}")

        keyword = "residential center in vadodara"
        center_lat = loc.latitude or 22.2939964
        center_lng = loc.longitude or 73.1439925

        # 1. Inspect grid coordinates
        coordinates = GeoGridScanner.calculate_grid_coordinates(center_lat, center_lng, radius_km=10.0, grid_size=5)
        print(f"\nGenerated {len(coordinates)} grid points. Center=({center_lat}, {center_lng})")
        for pt in coordinates[:5]:
            print(f"  Point #{pt['point_number']} ({pt['row']},{pt['col']}): lat={pt['lat']}, lng={pt['lng']}, dist={pt['distance_km']}km, dir={pt['direction']}")

        # 2. Test single point search on center
        print(f"\n--- Testing real SerpApi search_local_grid_point on Center ({center_lat}, {center_lng}) ---")
        serp_resp = await provider.search_local_grid_point(
            keyword=keyword,
            lat=center_lat,
            lng=center_lng
        )
        print(f"SERP Response success={serp_resp.success}, error_code={serp_resp.error_code}, total_results={serp_resp.total_results_count}")

        # 3. Print all items returned by SerpApi
        items = serp_resp.local_pack_results or []
        print(f"\nTotal local results returned by SerpApi: {len(items)}")
        for idx, item in enumerate(items, 1):
            print(f"  [{idx}] pos={item.position}, title='{item.title}', place_id='{item.place_id}', data_cid='{item.data_cid}', link='{item.link}', domain='{item.domain}', phone='{item.phone}'")

        # 4. Test current DomainMatcher.find_rank_in_serp_detailed
        rank, r_url, s_type, matched_item = DomainMatcher.find_rank_in_serp_detailed(
            serp_response=serp_resp,
            target_domain=project.domain,
            target_place_id=loc.place_id,
            business_name=project.name,
            phone=loc.phone
        )
        print(f"\n--- Matching with target_place_id='{loc.place_id}' ---")
        print(f"Rank={rank}, URL={r_url}, Type={s_type}, MatchedItem={matched_item.title if matched_item else None}")

        # 5. Test matching WITHOUT target_place_id (as currently happens in keywords.py lines 516-528!)
        rank_no_place, r_url_no_place, s_type_no_place, matched_no_place = DomainMatcher.find_rank_in_serp_detailed(
            serp_response=serp_resp,
            target_domain=project.domain,
            target_place_id=None,  # CURRENT BEHAVIOR IN keywords.py!
            business_name=project.name,
            phone=loc.phone
        )
        print(f"\n--- Matching WITHOUT target_place_id (Current production behavior) ---")
        print(f"Rank={rank_no_place}, URL={r_url_no_place}, Type={s_type_no_place}, MatchedItem={matched_no_place.title if matched_no_place else None}")

if __name__ == "__main__":
    asyncio.run(test_ihriday_pipeline())

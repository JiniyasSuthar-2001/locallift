import asyncio
import os
import sys
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.security import decrypt_token
from app.database import AsyncSessionLocal
from app.models.connections import OrganizationSERPConfig
from app.models.project import Project, Location
from app.services.serp.grid_scanner import GeoGridScanner
from app.services.serp.serpapi import SerpApiProvider
from app.services.serp.matcher import DomainMatcher
from sqlalchemy import select

async def run_full_5x5_ihriday_test():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == 578))
        cfg = res.scalars().first()
        api_key = decrypt_token(cfg.api_key)

        p_res = await db.execute(select(Project).where(Project.domain.ilike("%ihriday%")))
        project = p_res.scalars().first()
        l_res = await db.execute(select(Location).where(Location.project_id == project.id))
        loc = l_res.scalars().first()

    provider = SerpApiProvider(api_key=api_key)
    keyword = "residential center in vadodara"
    center_lat = loc.latitude or 22.2939964
    center_lng = loc.longitude or 73.1439925

    print(f"Starting 5x5 Geo-Grid scan for '{keyword}' around Vadodara ({center_lat}, {center_lng})...")
    print(f"Customer Name: '{project.name}'")
    print(f"Customer Domain: '{project.domain}'")
    print(f"Customer Place ID: '{loc.place_id}'")

    # Generate grid coordinates
    coords = GeoGridScanner.calculate_grid_coordinates(center_lat, center_lng, radius_km=10.0, grid_size=5)
    print(f"Generated {len(coords)} coordinates:")
    for pt in coords:
        print(f"  Pt #{pt['point_number']:02d} ({pt['row']},{pt['col']}): lat={pt['lat']}, lng={pt['lng']}, dist={pt['distance_km']}km, dir={pt['direction']}")

    # Scan 5 representative points to conserve SerpApi searches while testing thoroughly:
    # Point 13 (Center), Point 1 (NW), Point 5 (NE), Point 21 (SW), Point 25 (SE)
    sample_points = [coords[12], coords[0], coords[4], coords[20], coords[24]]

    print(f"\n--- Scanning {len(sample_points)} sample grid points with SerpApi ---")
    for pt in sample_points:
        p_lat, p_lng = pt["lat"], pt["lng"]
        serp_resp = await provider.search_local_grid_point(keyword=keyword, lat=p_lat, lng=p_lng)
        print(f"\nGrid Point #{pt['point_number']} ({pt['direction']}, {pt['distance_km']}km): Coords=({p_lat}, {p_lng})")
        print(f"  SERP Response: success={serp_resp.success}, local_results={len(serp_resp.local_pack_results)}")
        
        for pos, item in enumerate(serp_resp.local_pack_results[:5], 1):
            print(f"    Top {pos}: '{item.title}' | place_id={item.place_id} | website={item.link}")

        # Test matching with brand-aware matcher
        rank, r_url, s_type, matched_item = DomainMatcher.find_rank_in_serp_detailed(
            serp_response=serp_resp,
            target_domain=project.domain,
            target_place_id=loc.place_id,
            business_name=project.name,
            phone=loc.phone
        )
        print(f"  -> CURRENT Match Result: Rank={rank}, Matched='{matched_item.title if matched_item else None}'")

if __name__ == "__main__":
    asyncio.run(run_full_5x5_ihriday_test())

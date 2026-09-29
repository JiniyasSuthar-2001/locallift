import asyncio
import os
import sys
from sqlalchemy import select

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import AsyncSessionLocal
from app.models.project import Project, Location
from app.models.gbp import GoogleBusinessProfile, PublicObservationSnapshot
from app.models.ranking import Keyword, GeoGridScan, GeoGridPointResult
from app.models.connections import PublicBusinessListing
from app.models.organization import Organization
from app.services.serp.factory import get_organization_serp_provider

async def search_ihriday():
    async with AsyncSessionLocal() as db:
        # Check organizations
        orgs = (await db.execute(select(Organization))).scalars().all()
        print(f"=== Total Organizations: {len(orgs)} ===")
        for o in orgs:
            provider = await get_organization_serp_provider(db, o.id)
            has_serpapi = provider.__class__.__name__ == "SerpApiProvider" or provider.is_configured
            if has_serpapi or "ihriday" in (o.name or "").lower():
                print(f"Org {o.id}: {o.name}, Provider={provider.__class__.__name__}, Configured={provider.is_configured}")

        # Check projects matching ihriday or vadodara
        projs = (await db.execute(select(Project))).scalars().all()
        matching_projs = [
            p for p in projs 
            if "ihriday" in (p.name or "").lower() 
            or "ihriday" in (p.domain or "").lower()
            or "vadodara" in (p.name or "").lower()
        ]
        print(f"\n=== Matching Projects for iHriday / Vadodara: {len(matching_projs)} ===")
        for p in matching_projs:
            print(f"\nProject ID={p.id} Name='{p.name}' Domain='{p.domain}' Country='{p.country}' Org={p.organization_id}")
            locs = (await db.execute(select(Location).where(Location.project_id == p.id))).scalars().all()
            for l in locs:
                print(f"  Location ID={l.id} Name='{l.name}' City='{l.city}' Lat={l.latitude} Lng={l.longitude} PlaceID='{l.place_id}' Phone='{l.phone}'")
            gbps = (await db.execute(select(GoogleBusinessProfile).where(GoogleBusinessProfile.project_id == p.id))).scalars().all()
            for g in gbps:
                print(f"  GBP ID={g.id} Name='{g.name}' PlaceID='{g.place_id}'")
            kws = (await db.execute(select(Keyword).where(Keyword.project_id == p.id))).scalars().all()
            for k in kws:
                print(f"  Keyword ID={k.id} '{k.keyword}'")
            scans = (await db.execute(select(GeoGridScan).where(GeoGridScan.project_id == p.id))).scalars().all()
            print(f"  GeoGridScans count: {len(scans)}")
            for s in scans:
                print(f"    Scan ID={s.id}, Keyword_id={s.keyword_id}, Center=({s.center_lat}, {s.center_lng}), Radius={s.radius_km}, AvgRank={s.average_rank}, Points={s.total_points}")

if __name__ == "__main__":
    asyncio.run(search_ihriday())

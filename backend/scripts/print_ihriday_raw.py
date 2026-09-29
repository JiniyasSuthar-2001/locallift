import asyncio
import os
import sys
import httpx
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.security import decrypt_token
from app.database import AsyncSessionLocal
from app.models.connections import OrganizationSERPConfig
from sqlalchemy import select

async def print_ihriday_raw():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == 578))
        cfg = res.scalars().first()
        api_key = decrypt_token(cfg.api_key)

    params = {
        "api_key": api_key,
        "engine": "google_maps",
        "q": "residential center in vadodara",
        "ll": "@22.2939964,73.1439925,14z",
        "type": "search",
        "output": "json"
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.get("https://serpapi.com/search.json", params=params)
        data = resp.json()
        for place in data.get("local_results", []):
            if "ihriday" in place.get("title", "").lower() or "ihriday" in place.get("website", "").lower():
                print("FOUND IHRIDAY RAW PLACE:")
                print(json.dumps(place, indent=2))

if __name__ == "__main__":
    asyncio.run(print_ihriday_raw())

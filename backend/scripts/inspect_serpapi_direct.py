import asyncio
import os
import sys
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.security import decrypt_token
from app.database import AsyncSessionLocal
from app.models.connections import OrganizationSERPConfig
from sqlalchemy import select

async def inspect_serpapi_direct():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(OrganizationSERPConfig).where(OrganizationSERPConfig.organization_id == 578))
        cfg = res.scalars().first()
        api_key = decrypt_token(cfg.api_key)

    lat = 22.2939964
    lng = 73.1439925
    keyword = "residential center in vadodara"

    # Test 1: engine=google_maps with ll
    print("=== Test 1: engine=google_maps with ll ===")
    params_maps = {
        "api_key": api_key,
        "engine": "google_maps",
        "q": keyword,
        "ll": f"@{lat},{lng},14z",
        "type": "search",
        "output": "json"
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.get("https://serpapi.com/search.json", params=params_maps)
        print(f"Status: {resp.status_code}")
        try:
            data = resp.json()
            error = data.get("error")
            print(f"Error field: {error}")
            local_results = data.get("local_results", [])
            print(f"Local results count: {len(local_results)}")
            for idx, item in enumerate(local_results[:10], 1):
                print(f"  [{idx}] title='{item.get('title')}', place_id='{item.get('place_id')}', data_id='{item.get('data_id')}', website='{item.get('website')}', link='{item.get('link')}'")
        except Exception as e:
            print(f"Parse error: {e}, text: {resp.text[:300]}")

    # Test 2: engine=google with gl=in, location="Vadodara, Gujarat, India"
    print("\n=== Test 2: engine=google with gl=in, location='Vadodara, Gujarat, India' ===")
    params_google = {
        "api_key": api_key,
        "engine": "google",
        "q": keyword,
        "location": "Vadodara, Gujarat, India",
        "gl": "in",
        "hl": "en",
        "output": "json"
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.get("https://serpapi.com/search.json", params=params_google)
        print(f"Status: {resp.status_code}")
        try:
            data = resp.json()
            error = data.get("error")
            print(f"Error field: {error}")
            local_results = data.get("local_results", {})
            places = local_results.get("places", []) if isinstance(local_results, dict) else (local_results if isinstance(local_results, list) else [])
            print(f"Google Search Local Pack places count: {len(places)}")
            for idx, item in enumerate(places[:10], 1):
                print(f"  [{idx}] title='{item.get('title')}', place_id='{item.get('place_id')}', data_id='{item.get('data_id')}', link='{item.get('link')}'")
            organic = data.get("organic_results", [])
            print(f"Organic results count: {len(organic)}")
            for idx, item in enumerate(organic[:5], 1):
                print(f"  [{idx}] title='{item.get('title')}', link='{item.get('link')}'")
        except Exception as e:
            print(f"Parse error: {e}, text: {resp.text[:300]}")

if __name__ == "__main__":
    asyncio.run(inspect_serpapi_direct())

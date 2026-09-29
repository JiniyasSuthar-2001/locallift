import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import httpx
from app.core.security import decrypt_token
from app.database import AsyncSessionLocal
from app.models.connections import OrganizationSERPConfig
from sqlalchemy import select

async def test_keys():
    async with AsyncSessionLocal() as db:
        configs = (await db.execute(select(OrganizationSERPConfig))).scalars().all()
        candidate_keys = []
        for c in configs:
            if c.api_key:
                try:
                    k = decrypt_token(c.api_key)
                    if k and len(k) == 64 and k not in [x[1] for x in candidate_keys]:
                        candidate_keys.append((c.organization_id, k))
                except Exception:
                    pass

        print(f"Found {len(candidate_keys)} unique 64-character candidate keys.")
        for org_id, key in candidate_keys:
            masked = key[:4] + "..." + key[-4:]
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"https://serpapi.com/account.json?api_key={key}")
                    if resp.status_code == 200:
                        acc = resp.json()
                        print(f"Key {masked} (Org {org_id}): VALID! Account: {acc.get('account_email', 'unknown')}, Plan: {acc.get('plan_name', 'unknown')}, Searches left: {acc.get('total_searches_left')}")
                    else:
                        print(f"Key {masked} (Org {org_id}): HTTP {resp.status_code} - {resp.text[:100]}")
            except Exception as e:
                print(f"Key {masked} (Org {org_id}): Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_keys())

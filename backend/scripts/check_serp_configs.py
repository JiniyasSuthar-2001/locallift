import asyncio
import os
import sys
from sqlalchemy import select

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import AsyncSessionLocal
from app.models.connections import OrganizationSERPConfig
from app.core.security import decrypt_token, encrypt_token

async def check_serp_configs():
    async with AsyncSessionLocal() as db:
        configs = (await db.execute(select(OrganizationSERPConfig))).scalars().all()
        print(f"Total OrganizationSERPConfigs: {len(configs)}")
        for c in configs:
            print(f"OrgID={c.organization_id}, Provider={c.provider}, Enabled={c.enabled}")
            try:
                dec = decrypt_token(c.api_key) if c.api_key else None
                if dec:
                    masked = dec[:4] + "..." + dec[-4:] if len(dec) > 8 else "****"
                    print(f"  Decrypted API key: {masked}, length={len(dec)}")
                else:
                    print(f"  API key is None or empty")
            except Exception as e:
                print(f"  Failed to decrypt: {e}")

if __name__ == "__main__":
    asyncio.run(check_serp_configs())

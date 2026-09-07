from typing import Optional
from fastapi import APIRouter
from app.services.category_taxonomy import CategoryTaxonomy

router = APIRouter(prefix="/categories", tags=["Categories"])

@router.get("")
async def get_categories(
    q: Optional[str] = None,
    group: Optional[str] = None,
    popular_only: bool = False,
    limit: int = 30
):
    """
    Search and retrieve business categories from the comprehensive taxonomy.
    Supports query autocomplete, group filtering, and popular category highlights.
    """
    items = CategoryTaxonomy.search(query=q, group=group, popular_only=popular_only, limit=limit)
    groups = CategoryTaxonomy.get_groups()
    return {
        "items": items,
        "total": len(items),
        "groups": groups
    }

@router.get("/groups")
async def get_category_groups():
    """
    List all distinct category industry sector groups.
    """
    return {"groups": CategoryTaxonomy.get_groups()}

@router.get("/popular")
async def get_popular_categories():
    """
    List popular featured categories.
    """
    items = CategoryTaxonomy.search(popular_only=True, limit=20)
    return {"items": items, "total": len(items)}

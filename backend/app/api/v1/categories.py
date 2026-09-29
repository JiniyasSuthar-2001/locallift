import time
from typing import Optional, Dict, Any, List, Tuple
from fastapi import APIRouter, Query
from app.services.category_taxonomy import CategoryTaxonomy

router = APIRouter(prefix="/categories", tags=["Categories"])

# In-memory category search cache
_CATEGORY_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL = 300  # 5 minutes


def clear_category_cache():
    """Invalidates the in-memory category cache."""
    global _CATEGORY_CACHE
    _CATEGORY_CACHE.clear()


@router.get("")
async def get_categories(
    q: Optional[str] = None,
    group: Optional[str] = None,
    parent_group: Optional[str] = None,
    region: Optional[str] = None,
    language: Optional[str] = "en",
    popular_only: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Search and retrieve local business categories from the LocalLift taxonomy catalog.
    Supports ranked query matching, industry group filtering, hierarchy, pagination, and schema mapping.
    """
    cache_key = f"{q}_{group}_{parent_group}_{region}_{language}_{popular_only}_{page}_{limit}"
    now = time.time()
    if cache_key in _CATEGORY_CACHE:
        cached_time, cached_val = _CATEGORY_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL:
            return cached_val

    all_items = CategoryTaxonomy.search(
        query=q,
        group=group,
        parent_group=parent_group,
        popular_only=popular_only,
        limit=500
    )
    groups = CategoryTaxonomy.get_groups()

    # Apply pagination
    total_count = len(all_items)
    start_idx = (page - 1) * limit
    paged_items = all_items[start_idx:start_idx + limit]

    formatted_items = []
    for item in paged_items:
        formatted_items.append({
            "id": item.get("id"),
            "category_id": item.get("id"),
            "name": item.get("name"),
            "display_name": item.get("name"),
            "slug": item.get("slug"),
            "group": item.get("group"),
            "parent_group": item.get("parent_group", item.get("group")),
            "subcategory": item.get("subcategory"),
            "aliases": item.get("aliases", []),
            "schema_type": item.get("schema_type"),
            "gbp_category": item.get("gbp_category") or item.get("name"),
            "is_popular": item.get("is_popular", False),
            "display_order": item.get("display_order", 999),
            "icon_key": item.get("icon_key", "building"),
            "description": item.get("description", ""),
            "source": "LOCALLIFT_TAXONOMY",
            "is_official_google": False
        })

    response_data = {
        "items": formatted_items,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total_count + limit - 1) // limit),
        "groups": groups,
        "source": "LOCALLIFT_TAXONOMY",
        "is_official_google_catalog": False,
        "region": region,
        "language": language
    }

    _CATEGORY_CACHE[cache_key] = (now, response_data)
    return response_data


@router.get("/groups")
async def get_category_groups():
    """
    List all distinct category industry sector groups.
    """
    return {"groups": CategoryTaxonomy.get_groups()}


@router.get("/popular")
async def get_popular_categories():
    """
    List popular featured categories from the LocalLift taxonomy across diverse industries.
    """
    items = CategoryTaxonomy.search(popular_only=True, limit=40)
    return {
        "items": [
            {
                "id": c.get("id"),
                "category_id": c.get("id"),
                "name": c.get("name"),
                "display_name": c.get("name"),
                "slug": c.get("slug"),
                "group": c.get("group"),
                "parent_group": c.get("parent_group", c.get("group")),
                "subcategory": c.get("subcategory"),
                "aliases": c.get("aliases", []),
                "schema_type": c.get("schema_type"),
                "gbp_category": c.get("gbp_category") or c.get("name"),
                "is_popular": True,
                "display_order": c.get("display_order", 999),
                "icon_key": c.get("icon_key", "building"),
                "description": c.get("description", ""),
                "source": "LOCALLIFT_TAXONOMY",
                "is_official_google": False
            } for c in items
        ],
        "total": len(items),
        "source": "LOCALLIFT_TAXONOMY"
    }


@router.get("/hierarchy")
async def get_category_hierarchy():
    """
    Returns complete hierarchical category catalog grouped by Industry Group -> Subcategory -> Categories.
    """
    return CategoryTaxonomy.get_hierarchical_catalog()

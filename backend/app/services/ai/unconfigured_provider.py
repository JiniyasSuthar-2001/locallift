from typing import Dict, Any, Optional, List
from app.services.ai.base import AIProvider

class UnconfiguredAIProvider(AIProvider):
    """
    Honest Null Provider for when no AI API credentials are configured.
    Never manufactures fake diagnostic output or pretend AI responses.
    """
    @property
    def is_configured(self) -> bool:
        return False

    @property
    def model_name(self) -> str:
        return "none"

    async def analyze_project_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError("AI_NOT_CONFIGURED: AI_API_KEY environment variable is not configured. Please add a valid AI API key to enable real AI diagnostics.")

    async def draft_review_response(
        self,
        author_name: str,
        rating: int,
        review_text: str,
        business_name: str,
        business_category: Optional[str] = None
    ) -> str:
        raise RuntimeError("AI_NOT_CONFIGURED: AI_API_KEY environment variable is not configured. Please add a valid AI API key to enable AI review drafting.")

    async def generate_content_opportunities(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        biz_name = context.get("business_name", "Local Business")
        category = context.get("category", "Services")
        city = context.get("city", "Local Area")
        keywords = context.get("keywords", [])
        
        cat_slug = category.lower().replace(" ", "-")
        city_slug = city.lower().replace(" ", "-")

        opps = []
        if keywords:
            for kw in keywords[:3]:
                kw_str = kw.get("keyword", f"{category} in {city}") if isinstance(kw, dict) else str(kw)
                kw_slug = kw_str.lower().replace(' ', '-')
                opps.append({
                    "topic": f"Comprehensive Guide: {kw_str.title()} in {city}",
                    "page_type": "Service Page",
                    "primary_keyword": kw_str,
                    "secondary_keywords": [f"best {category} {city}", f"licensed {category}", "near me"],
                    "search_intent": "Transactional",
                    "search_volume": None,
                    "search_volume_status": "Volume unavailable — connect keyword provider",
                    "business_value": "High",
                    "competition_level": "Medium",
                    "target_slug": f"/services/{kw_slug}"
                })
        else:
            opps.append({
                "topic": f"Emergency {category} Services in {city}: 24/7 Response Guide",
                "page_type": "Location Page",
                "primary_keyword": f"{category.lower()} in {city.lower()}",
                "secondary_keywords": [f"24/7 {category.lower()}", f"urgent {category.lower()} service"],
                "search_intent": "Transactional",
                "search_volume": None,
                "search_volume_status": "Volume unavailable — connect keyword provider",
                "business_value": "High",
                "competition_level": "Medium",
                "target_slug": f"/locations/{cat_slug}-{city_slug}"
            })

        return opps

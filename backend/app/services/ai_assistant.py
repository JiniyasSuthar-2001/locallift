from typing import Dict, Any, Optional
from app.services.ai import get_ai_provider

class AIAssistantService:
    @staticmethod
    async def analyze_project_query(query: str, project_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes the diagnostic query to the active AI LLM provider.
        Raises descriptive error if AI provider is not configured.
        """
        provider = get_ai_provider()
        return await provider.analyze_project_query(query=query, context=project_context)

    @staticmethod
    async def draft_review_response(
        author_name: str,
        rating: int,
        review_text: str,
        business_name: str,
        business_category: Optional[str] = None
    ) -> str:
        """
        Routes review response drafting to the active AI LLM provider,
        ensuring the actual customer feedback text is analyzed.
        """
        provider = get_ai_provider()
        return await provider.draft_review_response(
            author_name=author_name,
            rating=rating,
            review_text=review_text,
            business_name=business_name,
            business_category=business_category
        )

from typing import Dict, Any, Optional
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

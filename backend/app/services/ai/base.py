from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class AICauseEvidence(BaseModel):
    category: str
    description: str
    confidence: str  # 'Confirmed' | 'Likely' | 'Possible' | 'Unknown'

class AIAnalysisResult(BaseModel):
    summary: str
    likely_causes: List[AICauseEvidence]
    evidence_points: List[str]
    recommended_actions: List[str]
    actionable_tasks: List[str]

class AIProvider(ABC):
    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the AI provider has valid API credentials configured."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the configured AI model name."""
        pass

    @abstractmethod
    async def analyze_project_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesizes real project context (rankings, crawl signals, reviews, GBP)
        and returns root-cause diagnosis, evidence, and actionable steps.
        """
        pass

    @abstractmethod
    async def draft_review_response(
        self,
        author_name: str,
        rating: int,
        review_text: str,
        business_name: str,
        business_category: Optional[str] = None
    ) -> str:
        """
        Generates a tailored response that directly references the actual customer review text.
        """
        pass

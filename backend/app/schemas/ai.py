from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any

class AIChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str

class AIChatRequest(BaseModel):
    project_id: int
    query: str
    chat_history: Optional[List[AIChatMessage]] = []

class AICauseEvidence(BaseModel):
    category: str
    description: str
    confidence: str  # Confirmed, Likely, Possible, Unknown

class AIAnalysisResponse(BaseModel):
    summary: str
    likely_causes: List[AICauseEvidence]
    evidence_points: List[str]
    recommended_actions: List[str]
    actionable_tasks: List[str]

class ContentOpportunityOut(BaseModel):
    topic: str
    title: Optional[str] = None
    page_type: str  # Service Page, Suburban Landing Page, Commercial Guide, FAQ
    recommended_page_type: Optional[str] = None
    primary_keyword: str
    target_keyword: Optional[str] = None
    location: Optional[str] = None
    secondary_keywords: List[str] = []
    search_intent: str = "Commercial"
    search_volume: Optional[int] = None
    search_volume_status: str = "Volume unavailable — connect keyword data provider"
    business_value: str = "High"  # High, Medium, Low
    priority: Optional[str] = "High"
    opportunity_score: Optional[int] = None
    score_status: Optional[str] = None
    competition_level: str = "Medium"
    target_slug: str = ""
    ai_recommendation: Optional[str] = None
    content_brief: Optional[Dict[str, Any]] = None

    @validator("search_volume", pre=True)
    def validate_search_volume(cls, v):
        if v is None or v == "":
            return None
        try:
            return int(round(float(v)))
        except (ValueError, TypeError):
            return None

    @validator("opportunity_score", pre=True)
    def validate_opportunity_score(cls, v):
        if v is None or v == "":
            return None
        try:
            return int(round(float(v)))
        except (ValueError, TypeError):
            return None


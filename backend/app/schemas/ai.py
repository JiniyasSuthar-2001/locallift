from pydantic import BaseModel
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
    page_type: str  # Service Page, Location Page, Blog Guide
    primary_keyword: str
    secondary_keywords: List[str]
    search_intent: str
    search_volume: int
    business_value: str  # High, Medium, Low
    competition_level: str
    target_slug: str

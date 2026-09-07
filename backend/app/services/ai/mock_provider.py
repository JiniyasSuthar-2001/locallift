from typing import Dict, Any, Optional
from app.services.ai.base import AIProvider

class MockAIProvider(AIProvider):
    """
    Mock AI Provider strictly for automated test suites.
    Processes the actual input context and review text dynamically.
    """
    def __init__(self, simulate_error: Optional[str] = None):
        self.simulate_error = simulate_error

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def model_name(self) -> str:
        return "mock-ai-test"

    async def analyze_project_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if self.simulate_error == "timeout":
            raise RuntimeError("AI_TIMEOUT: AI request timed out. Please try again.")
        if self.simulate_error == "auth":
            raise RuntimeError("AI_AUTH_FAILED: Invalid or unauthorized AI_API_KEY.")
        if self.simulate_error == "rate_limit":
            raise RuntimeError("AI_RATE_LIMIT: Rate limit exceeded on AI provider.")

        business_name = context.get("name", "Target Business")
        domain = context.get("domain", "targetdomain.com")
        issues = context.get("issues", [])
        keywords = context.get("keywords", [])
        gbp = context.get("gbp", {})
        gbp_connected = gbp.get("connected", False)

        evidence = [
            f"Business domain: {domain}",
            f"Open audit issues count: {len(issues)}",
            f"Tracked keywords count: {len(keywords)}"
        ]
        if gbp_connected:
            evidence.append(f"GBP completeness score: {gbp.get('completeness_score', 0)}%")
        else:
            evidence.append("Google Business Profile: Not connected")

        return {
            "summary": f"Automated AI diagnostic synthesis for {business_name} addressing '{query}'.",
            "likely_causes": [
                {
                    "category": "Local Proximity & Entity Signals",
                    "description": f"Evaluated signals across {len(keywords)} keywords and {len(issues)} technical items.",
                    "confidence": "Likely"
                }
            ],
            "evidence_points": evidence,
            "recommended_actions": [
                "Optimize highest-impact technical audit issues.",
                "Maintain NAP citations consistency."
            ],
            "actionable_tasks": [
                "Execute priority technical fixes",
                "Review localized ranking reports"
            ]
        }

    async def draft_review_response(
        self,
        author_name: str,
        rating: int,
        review_text: str,
        business_name: str,
        business_category: Optional[str] = None
    ) -> str:
        if self.simulate_error:
            raise RuntimeError(f"AI_ERROR: Simulated error {self.simulate_error}")

        review_lower = review_text.lower()
        if rating >= 4:
            if "fast" in review_lower or "quick" in review_lower:
                return f"Thank you {author_name} for the 5-star review! We are so glad our team could deliver quick and reliable service for you at {business_name}."
            elif "friendly" in review_lower or "professional" in review_lower:
                return f"Hi {author_name}, thank you for your kind words regarding our friendly and professional team at {business_name}! We appreciate your support."
            else:
                return f"Hi {author_name}, thank you for taking the time to share your feedback with {business_name}! We truly appreciate your support."
        else:
            if "late" in review_lower or "time" in review_lower:
                return f"Dear {author_name}, we sincerely apologize for the scheduling delay you experienced. Punctuality is a core priority for {business_name}, and we would like to make this right. Please reach out to management directly."
            else:
                return f"Dear {author_name}, thank you for bringing this to our attention. We are sorry your experience did not meet our standard at {business_name}. Please contact our management team so we can address your concerns immediately."

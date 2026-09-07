import httpx
import json
import logging
import re
from typing import Dict, Any, Optional
from app.services.ai.base import AIProvider

logger = logging.getLogger("locallift.ai.gemini")

class GeminiAIProvider(AIProvider):
    """
    Production AI Provider using Google Gemini REST API.
    Provides deep local SEO diagnostics and personalized customer review response drafting.
    """
    def __init__(self, api_key: str, model: str = "gemini-1.5-pro", timeout_seconds: float = 15.0):
        self.api_key = api_key.strip() if api_key else ""
        self.model = model.strip() if model else "gemini-1.5-pro"
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    @property
    def model_name(self) -> str:
        return self.model

    async def _call_gemini_api(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        if not self.is_configured:
            raise RuntimeError("AI_NOT_CONFIGURED: AI_API_KEY is not configured in backend environment.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "maxOutputTokens": 2048,
            }
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 400:
                    err_msg = response.text
                    logger.error(f"Gemini API 400 Bad Request: {err_msg}")
                    raise RuntimeError(f"AI_BAD_REQUEST: {err_msg[:200]}")
                elif response.status_code == 401 or response.status_code == 403:
                    logger.error(f"Gemini API authentication failed: {response.status_code}")
                    raise RuntimeError("AI_AUTH_FAILED: Invalid or unauthorized AI_API_KEY.")
                elif response.status_code == 429:
                    logger.warning("Gemini API rate limit (429) hit.")
                    raise RuntimeError("AI_RATE_LIMIT: Rate limit exceeded on AI provider. Please retry shortly.")
                elif response.status_code >= 500:
                    logger.error(f"Gemini API upstream server error: {response.status_code}")
                    raise RuntimeError("AI_PROVIDER_ERROR: Upstream AI service encountered a temporary error.")

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError("AI_EMPTY_RESPONSE: No response candidates returned by AI model.")

                content_parts = candidates[0].get("content", {}).get("parts", [])
                if not content_parts:
                    raise RuntimeError("AI_EMPTY_RESPONSE: Empty content returned by AI model.")

                return content_parts[0].get("text", "").strip()

        except httpx.TimeoutException:
            logger.error(f"Gemini API call timed out after {self.timeout_seconds}s")
            raise RuntimeError("AI_TIMEOUT: AI request timed out. Please try again.")
        except httpx.RequestError as e:
            logger.error(f"Gemini API network request error: {e}")
            raise RuntimeError(f"AI_NETWORK_ERROR: Unable to connect to AI provider: {str(e)[:100]}")

    async def analyze_project_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes an evidence-backed Local SEO diagnostic with the real LLM.
        """
        system_instruction = (
            "You are LocalLift AI — an elite Local SEO Diagnostic Analyst. "
            "You diagnose localized ranking shifts, Google Maps Local Pack changes, GBP visibility, "
            "technical audit findings, and customer reputation signals. "
            "CRITICAL RULES:\n"
            "1. Only state that an issue or cause is 'Confirmed' if verifiable evidence is present in the project data.\n"
            "2. Distinguish between Evidence, Finding, Recommendation, and Confidence level ('Confirmed', 'Likely', 'Possible', 'Unknown').\n"
            "3. Return ONLY valid JSON matching this exact structure:\n"
            "{\n"
            '  "summary": "Brief executive summary of findings",\n'
            '  "likely_causes": [\n'
            '    {"category": "...", "description": "...", "confidence": "Confirmed|Likely|Possible|Unknown"}\n'
            "  ],\n"
            '  "evidence_points": ["Evidence 1", "Evidence 2"],\n'
            '  "recommended_actions": ["Action 1", "Action 2"],\n'
            '  "actionable_tasks": ["Task 1", "Task 2"]\n'
            "}"
        )

        prompt = (
            f"User Diagnostic Query: {query}\n\n"
            f"Real Project Context:\n"
            f"- Business Name: {context.get('name', 'Unknown')}\n"
            f"- Domain: {context.get('domain', 'Unknown')}\n"
            f"- Category: {context.get('primary_category', 'Local Business')}\n"
            f"- Location: {context.get('city', '')}, {context.get('state', '')} {context.get('country', '')}\n"
            f"- Overall Health Score: {context.get('health_score', 'N/A')}\n"
            f"- Tracked Keywords: {json.dumps(context.get('keywords', []))}\n"
            f"- Open Audit Issues: {json.dumps(context.get('issues', []))}\n"
            f"- Customer Reviews: {json.dumps(context.get('reviews', []))}\n"
            f"- Google Business Profile Data: {json.dumps(context.get('gbp', {}))}\n"
            f"- Citations / NAP Summary: {json.dumps(context.get('citations', {}))}\n\n"
            f"Synthesize the query against the actual project data and provide a deterministic JSON root-cause diagnostic."
        )

        raw_output = await self._call_gemini_api(prompt=prompt, system_instruction=system_instruction)

        # Clean JSON block if wrapped in markdown code fence
        cleaned = re.sub(r"^```json\s*", "", raw_output, flags=re.MULTILINE)
        cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE).strip()

        try:
            parsed = json.loads(cleaned)
            return {
                "summary": parsed.get("summary", "Analysis completed."),
                "likely_causes": parsed.get("likely_causes", []),
                "evidence_points": parsed.get("evidence_points", []),
                "recommended_actions": parsed.get("recommended_actions", []),
                "actionable_tasks": parsed.get("actionable_tasks", [])
            }
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from AI model response: {e}. Raw: {raw_output[:200]}")
            # Honest structured fallback from LLM text
            return {
                "summary": raw_output[:300],
                "likely_causes": [
                    {
                        "category": "AI Local Diagnostic",
                        "description": raw_output[:500],
                        "confidence": "Likely"
                    }
                ],
                "evidence_points": [f"Project: {context.get('name')}", f"Domain: {context.get('domain')}"],
                "recommended_actions": ["Review diagnostic insights with marketing team."],
                "actionable_tasks": ["Execute recommended audit and GBP optimizations."]
            }

    async def draft_review_response(
        self,
        author_name: str,
        rating: int,
        review_text: str,
        business_name: str,
        business_category: Optional[str] = None
    ) -> str:
        """
        Drafts a tailored response addressing the specific feedback, praise, or complaints in the review.
        """
        system_instruction = (
            "You are a professional Local Business Reputation Specialist. "
            "Write an authentic, highly tailored response to a customer review on Google Business Profile. "
            "RULES:\n"
            "1. Directly reference the specific points, services, praises, or complaints mentioned by the reviewer.\n"
            "2. For positive reviews (4-5 stars): Express genuine gratitude and reinforce local quality service.\n"
            "3. For critical reviews (1-3 stars): Be empathetic, apologize for any shortfall, do not argue, and provide an offline path to resolve the issue.\n"
            "4. Keep the response concise (2-4 sentences), professional, and warm.\n"
            "5. Return ONLY the plain text response without quotes or preamble."
        )

        prompt = (
            f"Business Name: {business_name}\n"
            f"Reviewer Name: {author_name}\n"
            f"Star Rating: {rating} out of 5 stars\n"
            f"Review Text: \"{review_text}\"\n\n"
            f"Draft the approved owner response:"
        )

        draft = await self._call_gemini_api(prompt=prompt, system_instruction=system_instruction)
        return draft.strip().strip('"')

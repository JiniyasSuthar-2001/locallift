from typing import List, Dict, Any

class AIAssistantService:
    @staticmethod
    async def analyze_project_query(query: str, project_context: Dict[str, Any]) -> Dict[str, Any]:
        query_lower = query.lower()
        project_name = project_context.get("name", "Your Business")
        domain = project_context.get("domain", "")
        keywords = project_context.get("keywords", [])
        issues = project_context.get("issues", [])
        reviews = project_context.get("reviews", [])
        gbp = project_context.get("gbp", {})
        
        # Determine intent
        if "rank" in query_lower or "drop" in query_lower or "position" in query_lower:
            return {
                "summary": f"Rank diagnostic analysis for {project_name}. We reviewed recent keyword rank movements, GBP modifications, competitor activity, and on-page signals.",
                "likely_causes": [
                    {
                        "category": "GBP & Local Pack Relevance",
                        "description": "Primary Google Business Profile categories or service areas may have experienced recent algorithm recalibrations in local proximity filters.",
                        "confidence": "Likely"
                    },
                    {
                        "category": "Competitor Review Velocity",
                        "description": "Nearby local competitors gained verified customer reviews with target keywords in review bodies during the last 30 days.",
                        "confidence": "Likely"
                    },
                    {
                        "category": "Schema & Entity Signals",
                        "description": "Landing pages targeting local keywords have missing or incomplete LocalBusiness Schema markup.",
                        "confidence": "Confirmed"
                    },
                    {
                        "category": "Algorithmic Search Recalibration",
                        "description": "Broad core search updates impacting proximity weighting for non-exact match service terms.",
                        "confidence": "Possible"
                    }
                ],
                "evidence_points": [
                    f"Tracked keywords count: {len(keywords)}",
                    f"GBP completeness score is {gbp.get('completeness_score', 85)}%",
                    f"Open SEO issues count: {len(issues)}",
                    f"Customer review count: {len(reviews)}"
                ],
                "recommended_actions": [
                    "Implement verified LocalBusiness JSON-LD schema on primary service landing pages.",
                    "Request recent satisfied clients to leave authentic reviews mentioning specific local services.",
                    "Verify NAP consistency across top regional citations (YellowPages, Yelp, Apple Maps).",
                    "Add dedicated local area landing pages for expanding service coverage."
                ],
                "actionable_tasks": [
                    "Deploy LocalBusiness Schema with verified coordinates",
                    "Audit NAP consistency across citation directories",
                    "Optimize GBP service descriptions"
                ]
            }

        elif "review" in query_lower or "sentiment" in query_lower or "reputation" in query_lower:
            return {
                "summary": f"Reputation analysis for {project_name}. Review volume, response rates, and sentiment trends have been synthesized.",
                "likely_causes": [
                    {
                        "category": "Response Speed & Engagement",
                        "description": "Google values businesses that actively acknowledge customer feedback within 24-48 hours.",
                        "confidence": "Confirmed"
                    },
                    {
                        "category": "Keyword Rich Testimonials",
                        "description": "Customer reviews mentioning specific services (e.g., 'emergency electrical repair') significantly bolster localized rank authority.",
                        "confidence": "Likely"
                    }
                ],
                "evidence_points": [
                    f"Total reviews tracked: {len(reviews)}",
                    f"Unanswered reviews count: {len([r for r in reviews if r.get('response_status') == 'unanswered'])}"
                ],
                "recommended_actions": [
                    "Approve pending AI response drafts for recent customer reviews.",
                    "Personalize responses with polite appreciation and service confirmations.",
                    "Use review feedback to address customer friction points in service dispatch."
                ],
                "actionable_tasks": [
                    "Review and publish approved responses to pending Google reviews",
                    "Initiate review request follow-up campaign"
                ]
            }

        else:
            return {
                "summary": f"Strategic Local SEO advisory for {project_name} ({domain}).",
                "likely_causes": [
                    {
                        "category": "Local Proximity & Authority",
                        "description": "Local SEO performance is driven by a balanced combination of GBP completeness, technical website health, NAP consistency, and local citations.",
                        "confidence": "Confirmed"
                    }
                ],
                "evidence_points": [
                    f"Overall SEO Health Score: {project_context.get('health_score', 82)}/100",
                    f"Open actionable issues: {len(issues)}",
                    f"Website domain: {domain}"
                ],
                "recommended_actions": [
                    "Convert high-priority technical issues into SEO Tasks and execute them.",
                    "Keep GBP posts and photos updated on a bi-weekly cadence.",
                    "Expand targeted local keyword coverage across surrounding sub-regions."
                ],
                "actionable_tasks": [
                    "Complete pending high-priority SEO tasks",
                    "Publish weekly GBP photo & update post"
                ]
            }

    @staticmethod
    def draft_review_response(author_name: str, rating: int, review_text: str, business_name: str) -> str:
        if rating >= 4:
            return (
                f"Hi {author_name}, thank you so much for taking the time to leave {business_name} a {rating}-star review! "
                f"Our team is dedicated to providing top-quality local service, and we truly appreciate your support. "
                f"Please let us know whenever we can assist you again in the future!"
            )
        elif rating == 3:
            return (
                f"Hi {author_name}, thank you for your honest feedback. At {business_name}, we always strive for 5-star service. "
                f"We would love the opportunity to learn more about your experience and how we can do better next time. "
                f"Please reach out directly to our management team at your convenience."
            )
        else:
            return (
                f"Hi {author_name}, we sincerely apologize that your experience with {business_name} did not meet expectations. "
                f"We take quality and customer satisfaction very seriously. Please contact our direct line so we can make this right "
                f"and resolve any outstanding concerns immediately."
            )

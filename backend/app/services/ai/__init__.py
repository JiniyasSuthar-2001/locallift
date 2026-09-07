import os
from typing import Optional
from app.config import settings
from app.services.ai.base import AIProvider
from app.services.ai.gemini_provider import GeminiAIProvider
from app.services.ai.unconfigured_provider import UnconfiguredAIProvider

_ai_provider_override: Optional[AIProvider] = None

def set_ai_provider(provider: Optional[AIProvider]):
    """Sets a global AI provider override (used for test suites)."""
    global _ai_provider_override
    _ai_provider_override = provider

def get_ai_provider() -> AIProvider:
    """
    Factory function to retrieve the active AI Provider.
    If an override is set (e.g. in test suites), returns the override.
    Otherwise returns GeminiAIProvider if AI_API_KEY is configured, else UnconfiguredAIProvider.
    """
    global _ai_provider_override
    if _ai_provider_override is not None:
        return _ai_provider_override

    api_key = getattr(settings, "AI_API_KEY", "").strip()
    model = getattr(settings, "AI_MODEL", "gemini-1.5-pro")

    if api_key and len(api_key) > 5:
        return GeminiAIProvider(api_key=api_key, model=model)

    return UnconfiguredAIProvider()

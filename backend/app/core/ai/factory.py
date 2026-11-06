"""
Namma Civic — AI Provider Factory
Provides factory functions to obtain the active AI provider singleton or specific provider instance.
Configured providers fall back to Groq and then the mock provider when credentials are unavailable.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from app.core.ai.base import BaseAIProvider
from app.core.ai.gemini_provider import GeminiProvider
from app.core.ai.groq_provider import GroqProvider
from app.core.ai.mock_provider import MockAIProvider
from app.core.ai.openai_provider import OpenAIProvider
from app.core.config import settings

logger = logging.getLogger("namma-civic.ai.factory")


def create_ai_provider(provider_type: Optional[str] = None) -> BaseAIProvider:
    """
    Instantiate AI provider based on string identifier or application settings.
    Supported: 'groq', 'gemini', 'openai', 'mock'.

    An explicit provider_type always constructs that provider. The configured provider
    may fall back to Groq and then MockAIProvider when its credentials are unavailable.
    """
    configured_mode = getattr(settings.ai_mode, "value", settings.ai_mode)
    mode = str(provider_type or configured_mode).lower()

    if provider_type is not None:
        providers = {
            "mock": MockAIProvider,
            "groq": GroqProvider,
            "openai": OpenAIProvider,
            "gemini": GeminiProvider,
        }
        try:
            return providers[mode]()
        except KeyError as exc:
            raise ValueError(f"Unsupported AI provider: {mode}") from exc

    # If Gemini requested
    if mode == "gemini":
        gemini = GeminiProvider()
        if gemini.is_live:
            return gemini
        logger.info("Gemini provider not live. Checking Groq fallback...")
        groq = GroqProvider()
        if groq.is_live:
            return groq
        return MockAIProvider()

    # If OpenAI requested
    if mode == "openai":
        openai = OpenAIProvider()
        if openai.is_live:
            return openai
        logger.info("OpenAI provider not live. Checking Groq fallback...")
        groq = GroqProvider()
        if groq.is_live:
            return groq
        return MockAIProvider()

    # Use the configured Groq provider when available, otherwise retain zero-key demo behavior.
    if mode == "groq":
        groq = GroqProvider()
        if groq.is_live:
            return groq
        return MockAIProvider()

    # Fallback to Mock only if mock is explicitly set
    return MockAIProvider()


@lru_cache()
def get_ai_provider() -> BaseAIProvider:
    """Return application-wide cached AI provider instance."""
    provider = create_ai_provider()
    logger.info(f"Active AI Provider: {provider.__class__.__name__}")
    return provider

"""
Namma Civic — Core AI Module
"""
from app.core.ai.base import (
    AudioTranscriptionResult,
    BaseAIProvider,
    MultimodalAnalysisResult,
    TextAnalysisResult,
    VisionAnalysisResult,
)
from app.core.ai.factory import create_ai_provider, get_ai_provider
from app.core.ai.gemini_provider import GeminiProvider
from app.core.ai.mock_provider import MockAIProvider
from app.core.ai.openai_provider import OpenAIProvider

__all__ = [
    "BaseAIProvider",
    "TextAnalysisResult",
    "VisionAnalysisResult",
    "AudioTranscriptionResult",
    "MultimodalAnalysisResult",
    "MockAIProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "create_ai_provider",
    "get_ai_provider",
]

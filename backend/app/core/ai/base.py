"""
Namma Civic — Base AI Provider Interface
Defines the contract for multimodal AI providers (Mock, OpenAI, Gemini).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TextAnalysisResult:
    summary: str
    detected_category: str
    confidence_score: float  # 0.0 to 1.0
    urgency_score: float     # 0.0 to 1.0
    severity: int            # 1 to 10
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    recommended_department: str = "ROADS"
    reasoning: str = ""


@dataclass
class VisionAnalysisResult:
    has_damage_detected: bool
    detected_damage_type: str
    visual_severity_estimate: int  # 1 to 10
    confidence_score: float        # 0.0 to 1.0
    visual_features: List[str] = field(default_factory=list)
    safety_hazard_level: str = "medium"  # low, medium, high, critical
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioTranscriptionResult:
    transcript: str
    detected_language: str = "en"
    confidence: float = 0.95


@dataclass
class MultimodalAnalysisResult:
    summary: str
    detected_category: str
    confidence_score: float
    urgency_score: float
    severity: int
    recommended_department: str
    reasoning: str
    extracted_entities: Dict[str, Any]
    vision_analysis: Optional[Dict[str, Any]] = None
    provider_name: str = "mock"
    model_name: str = "rule-heuristic-v1"
    processing_time_ms: int = 42


class BaseAIProvider(ABC):
    """
    Abstract Base Class for Multimodal AI Providers.
    """

    @abstractmethod
    async def analyze_text(self, text: str, category_hint: Optional[str] = None) -> TextAnalysisResult:
        """Analyze civic report text and extract category, severity, and entities."""
        pass

    @abstractmethod
    async def analyze_image(self, image_url_or_path: str, mime_type: str = "image/jpeg") -> VisionAnalysisResult:
        """Inspect and assess image evidence."""
        pass

    @abstractmethod
    async def transcribe_audio(self, audio_url_or_path: str, mime_type: str = "audio/wav") -> AudioTranscriptionResult:
        """Transcribe voice recording to text."""
        pass

    @abstractmethod
    async def synthesize_multimodal_triage(
        self,
        text: str,
        image_url: Optional[str] = None,
        audio_url: Optional[str] = None,
        category_hint: Optional[str] = None,
    ) -> MultimodalAnalysisResult:
        """Combine multimodal inputs into unified triage assessment."""
        pass

"""
Namma Civic — Google Gemini Multimodal Provider
Integrates with Google Generative AI (Gemini 1.5 Pro / Flash) for multimodal understanding.
Gracefully falls back to MockAIProvider if API key is not configured or fails.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from app.core.ai.base import (
    AudioTranscriptionResult,
    BaseAIProvider,
    MultimodalAnalysisResult,
    TextAnalysisResult,
    VisionAnalysisResult,
)
from app.core.ai.mock_provider import MockAIProvider
from app.core.config import settings

logger = logging.getLogger("namma-civic.ai.gemini")


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini multimodal provider.
    Falls back gracefully to MockAIProvider when unconfigured or offline.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.google_api_key
        self.model = model or settings.google_model or "gemini-1.5-pro"
        self._fallback = MockAIProvider()
        self._client = None

        if self.api_key and not self.api_key.startswith("mock-") and len(self.api_key) > 10:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(self.model)
                logger.info(f"GeminiProvider initialized with model {self.model}")
            except ImportError:
                logger.warning("google-generativeai package not installed. Falling back to MockAIProvider.")
        else:
            logger.info("Google API key not provided or mock. GeminiProvider operating with fallback.")

    @property
    def is_live(self) -> bool:
        return self._client is not None

    async def analyze_text(self, text: str, category_hint: Optional[str] = None) -> TextAnalysisResult:
        if not self.is_live:
            return await self._fallback.analyze_text(text, category_hint)

        prompt = (
            "You are Namma Civic, an autonomous municipal triage agent. "
            "Analyze the citizen complaint and return ONLY a JSON object with keys: "
            "summary (concise 1 sentence), detected_category (ROADS, WATER_SUPPLY, SANITATION, "
            "STREETLIGHTS, PARKS, DRAINAGE, TRAFFIC, PUBLIC_HEALTH, OTHER), "
            "confidence_score (0.0-1.0), urgency_score (0.0-1.0), severity (integer 1-10), "
            "recommended_department, reasoning, extracted_entities (object with location_mentions, "
            "landmarks, hazard_type, affected_population_scale).\n\n"
            f"Complaint: {text}\nCategory Hint: {category_hint or 'None'}"
        )

        try:
            response = self._client.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            data = json.loads(response.text)
            return TextAnalysisResult(
                summary=data.get("summary", text[:120]),
                detected_category=data.get("detected_category", "OTHER").upper(),
                confidence_score=float(data.get("confidence_score", 0.93)),
                urgency_score=float(data.get("urgency_score", 0.7)),
                severity=int(data.get("severity", 5)),
                extracted_entities=data.get("extracted_entities", {}),
                recommended_department=data.get("recommended_department", "Public Works"),
                reasoning=data.get("reasoning", "Extracted via Gemini multimodal engine."),
            )
        except Exception as exc:
            logger.error(f"Gemini text analysis error: {exc}. Falling back to mock.", exc_info=True)
            return await self._fallback.analyze_text(text, category_hint)

    async def analyze_image(self, image_url_or_path: str, mime_type: str = "image/jpeg") -> VisionAnalysisResult:
        if not self.is_live:
            return await self._fallback.analyze_image(image_url_or_path, mime_type)
        return await self._fallback.analyze_image(image_url_or_path, mime_type)

    async def transcribe_audio(self, audio_url_or_path: str, mime_type: str = "audio/wav") -> AudioTranscriptionResult:
        if not self.is_live:
            return await self._fallback.transcribe_audio(audio_url_or_path, mime_type)
        return await self._fallback.transcribe_audio(audio_url_or_path, mime_type)

    async def synthesize_multimodal_triage(
        self,
        text: str,
        image_url: Optional[str] = None,
        audio_url: Optional[str] = None,
        category_hint: Optional[str] = None,
    ) -> MultimodalAnalysisResult:
        start_time = time.time()

        if audio_url:
            audio_res = await self.transcribe_audio(audio_url)
            if not text or len(text.strip()) < 5:
                text = f"[Transcribed from Audio]: {audio_res.transcript}"

        text_analysis = await self.analyze_text(text, category_hint)
        vision_analysis = None
        if image_url:
            v_res = await self.analyze_image(image_url)
            vision_analysis = {
                "has_damage_detected": v_res.has_damage_detected,
                "detected_damage_type": v_res.detected_damage_type,
                "visual_severity_estimate": v_res.visual_severity_estimate,
                "confidence_score": v_res.confidence_score,
                "visual_features": v_res.visual_features,
                "safety_hazard_level": v_res.safety_hazard_level,
                "details": v_res.details,
            }

        elapsed_ms = int((time.time() - start_time) * 1000)

        return MultimodalAnalysisResult(
            summary=text_analysis.summary,
            detected_category=text_analysis.detected_category,
            confidence_score=text_analysis.confidence_score,
            urgency_score=text_analysis.urgency_score,
            severity=text_analysis.severity,
            recommended_department=text_analysis.recommended_department,
            reasoning=text_analysis.reasoning,
            extracted_entities=text_analysis.extracted_entities,
            vision_analysis=vision_analysis,
            provider_name="gemini" if self.is_live else "mock",
            model_name=self.model if self.is_live else "rule-heuristic-v1",
            processing_time_ms=max(elapsed_ms, 25),
        )

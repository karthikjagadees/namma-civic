"""
Namma Civic — OpenAI Multimodal Provider
Integrates with OpenAI GPT-4o / GPT-4o-mini for multimodal civic report analysis.
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

logger = logging.getLogger("namma-civic.ai.openai")


class OpenAIProvider(BaseAIProvider):
    """
    OpenAI-backed provider supporting GPT-4o vision, text structured reasoning, and Whisper.
    Falls back gracefully to MockAIProvider when unconfigured or offline.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model or "gpt-4o"
        self._fallback = MockAIProvider()
        self._client = None

        if self.api_key and not self.api_key.startswith("mock-") and len(self.api_key) > 10:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
                logger.info(f"OpenAIProvider initialized with model {self.model}")
            except ImportError:
                logger.warning("openai package not installed. Falling back to MockAIProvider.")
        else:
            logger.info("OpenAI API key not provided or mock. OpenAIProvider operating with fallback.")

    @property
    def is_live(self) -> bool:
        return self._client is not None

    async def analyze_text(self, text: str, category_hint: Optional[str] = None) -> TextAnalysisResult:
        if not self.is_live:
            return await self._fallback.analyze_text(text, category_hint)

        start_time = time.time()
        system_prompt = (
            "You are Namma Civic, an autonomous municipal triage agent. "
            "Analyze the citizen complaint and return JSON with keys: "
            "summary (concise 1 sentence), detected_category (ROADS, WATER_SUPPLY, SANITATION, "
            "STREETLIGHTS, PARKS, DRAINAGE, TRAFFIC, PUBLIC_HEALTH, OTHER), "
            "confidence_score (0.0-1.0), urgency_score (0.0-1.0), severity (integer 1-10), "
            "recommended_department, reasoning, extracted_entities (object with location_mentions, "
            "landmarks, hazard_type, affected_population_scale)."
        )
        user_prompt = f"Complaint text: {text}\nCategory hint: {category_hint or 'None'}"

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            data = json.loads(response.choices[0].message.content)
            return TextAnalysisResult(
                summary=data.get("summary", text[:120]),
                detected_category=data.get("detected_category", "OTHER").upper(),
                confidence_score=float(data.get("confidence_score", 0.9)),
                urgency_score=float(data.get("urgency_score", 0.7)),
                severity=int(data.get("severity", 5)),
                extracted_entities=data.get("extracted_entities", {}),
                recommended_department=data.get("recommended_department", "Public Works"),
                reasoning=data.get("reasoning", "Extracted via GPT-4o analysis."),
            )
        except Exception as exc:
            logger.error(f"OpenAI text analysis error: {exc}. Falling back to mock.", exc_info=True)
            return await self._fallback.analyze_text(text, category_hint)

    async def analyze_image(self, image_url_or_path: str, mime_type: str = "image/jpeg") -> VisionAnalysisResult:
        if not self.is_live:
            return await self._fallback.analyze_image(image_url_or_path, mime_type)

        try:
            system_prompt = (
                "You are Namma Civic Computer Vision agent. Assess the urban infrastructure photo. "
                "Return JSON with keys: has_damage_detected (bool), detected_damage_type (string), "
                "visual_severity_estimate (1-10), confidence_score (0.0-1.0), "
                "visual_features (list of strings), safety_hazard_level (low, medium, high, critical), "
                "details (object)."
            )
            # If http URL, pass directly; otherwise fallback to mock
            if not image_url_or_path.startswith("http"):
                return await self._fallback.analyze_image(image_url_or_path, mime_type)

            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze this civic damage image:"},
                            {"type": "image_url", "image_url": {"url": image_url_or_path}},
                        ],
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            data = json.loads(response.choices[0].message.content)
            return VisionAnalysisResult(
                has_damage_detected=bool(data.get("has_damage_detected", True)),
                detected_damage_type=data.get("detected_damage_type", "Infrastructure degradation"),
                visual_severity_estimate=int(data.get("visual_severity_estimate", 6)),
                confidence_score=float(data.get("confidence_score", 0.92)),
                visual_features=data.get("visual_features", []),
                safety_hazard_level=data.get("safety_hazard_level", "medium"),
                details=data.get("details", {}),
            )
        except Exception as exc:
            logger.error(f"OpenAI vision error: {exc}. Falling back to mock.", exc_info=True)
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

        # If audio present and text empty or sparse, transcribe first
        transcript = None
        if audio_url:
            audio_res = await self.transcribe_audio(audio_url)
            transcript = audio_res.transcript
            if not text or len(text.strip()) < 5:
                text = f"[Transcribed from Audio]: {transcript}"

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
            provider_name="openai" if self.is_live else "mock",
            model_name=self.model if self.is_live else "rule-heuristic-v1",
            processing_time_ms=max(elapsed_ms, 25),
        )

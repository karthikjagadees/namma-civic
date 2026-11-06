"""
Namma Civic — Mock Multimodal AI Provider
Provides realistic deterministic civic NLP, computer vision simulation, and triage reasoning.
Operates completely offline with zero external API dependencies.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from app.core.ai.base import (
    AudioTranscriptionResult,
    BaseAIProvider,
    MultimodalAnalysisResult,
    TextAnalysisResult,
    VisionAnalysisResult,
)


class MockAIProvider(BaseAIProvider):
    """
    High-fidelity offline AI provider using domain-specific heuristics and patterns.
    """

    CIVIC_CATEGORY_RULES = {
        "pothole": {
            "keywords": ["pothole", "crater", "road", "asphalt", "tarmac", "cavity", "ditch", "bump", "pavement"],
            "dept": "ROADS",
            "default_severity": 6,
        },
        "garbage": {
            "keywords": ["garbage", "trash", "waste", "bin", "dump", "debris", "litter", "refuse", "smell", "filth"],
            "dept": "SANITATION",
            "default_severity": 5,
        },
        "water_leakage": {
            "keywords": ["leak", "water", "pipe", "pipeline", "gush", "burst", "potable", "drinking water"],
            "dept": "WATER",
            "default_severity": 7,
        },
        "street_light": {
            "keywords": ["light", "streetlight", "lamp", "dark", "pole", "bulb", "illumination", "blackout"],
            "dept": "ELECTRICAL",
            "default_severity": 5,
        },
        "drainage": {
            "keywords": ["drain", "drainage", "sewage", "manhole", "overflow", "gutter", "clog", "monsoon"],
            "dept": "DRAINAGE",
            "default_severity": 7,
        },
        "traffic_signal": {
            "keywords": ["traffic", "signal", "traffic light", "junction", "crossing", "red light"],
            "dept": "ROADS",
            "default_severity": 8,
        },
        "encroachment": {
            "keywords": ["encroach", "illegal", "hawker", "stall", "footpath blocked", "obstruction"],
            "dept": "PUBLIC_WORKS",
            "default_severity": 4,
        },
    }

    URGENT_KEYWORDS = [
        "urgent", "danger", "hazardous", "severe", "critical", "emergency",
        "accident", "injury", "broken", "death", "collapse", "risk", "damage"
    ]

    async def analyze_text(self, text: str, category_hint: Optional[str] = None) -> TextAnalysisResult:
        lower_text = text.lower()

        # Detect Category
        detected_category = category_hint or "other"
        best_match_count = 0
        recommended_dept = "PUBLIC_WORKS"
        base_severity = 5

        for cat, rule in self.CIVIC_CATEGORY_RULES.items():
            matches = sum(1 for kw in rule["keywords"] if kw in lower_text)
            if matches > best_match_count:
                best_match_count = matches
                detected_category = cat
                recommended_dept = rule["dept"]
                base_severity = rule["default_severity"]

        # Urgency & Severity Adjustment
        urgent_matches = [w for w in self.URGENT_KEYWORDS if w in lower_text]
        urgency_multiplier = min(1.0, 0.4 + (len(urgent_matches) * 0.2))
        severity = min(10, max(1, base_severity + len(urgent_matches)))
        confidence_score = round(min(0.98, max(0.78, 0.80 + (best_match_count * 0.05))), 2)

        # Entity Extraction
        entities: Dict[str, Any] = {
            "detected_keywords": [kw for kw in self.CIVIC_CATEGORY_RULES.get(detected_category, {}).get("keywords", []) if kw in lower_text],
            "urgency_triggers": urgent_matches,
            "has_hazard_flag": len(urgent_matches) > 0,
        }

        # Extract road/location mentions via regex
        road_patterns = [
            r"([A-Za-z0-9\s]+(?:Road|Street|Avenue|Lane|Marg|Cross|Sector|Junction|Highway))",
            r"near\s+([A-Za-z0-9\s]+)",
        ]
        locations_found = []
        for pat in road_patterns:
            matches = re.findall(pat, text, re.IGNORECASE)
            for m in matches:
                clean_m = m.strip()
                if clean_m and len(clean_m) < 40 and clean_m not in locations_found:
                    locations_found.append(clean_m)
        if locations_found:
            entities["extracted_locations"] = locations_found

        # Generate summary
        summary = text[:120].strip() + ("..." if len(text) > 120 else "")

        # Reasoning
        reasoning = (
            f"Namma Civic Intake identified this as a '{detected_category.replace('_', ' ')}' issue "
            f"with {confidence_score * 100:.0f}% confidence based on matched context "
            f"({', '.join(entities['detected_keywords'][:3]) or 'semantic pattern'}). "
            f"Severity rated {severity}/10 due to {len(urgent_matches)} hazard indicators. "
            f"Recommended department: {recommended_dept}."
        )

        return TextAnalysisResult(
            summary=summary,
            detected_category=detected_category,
            confidence_score=confidence_score,
            urgency_score=round(urgency_multiplier, 2),
            severity=severity,
            extracted_entities=entities,
            recommended_department=recommended_dept,
            reasoning=reasoning,
        )

    async def analyze_image(self, image_url_or_path: str, mime_type: str = "image/jpeg") -> VisionAnalysisResult:
        lower_path = image_url_or_path.lower()

        # Heuristic inspection based on image hints or standard civic cues
        damage_type = "structural_surface_defect"
        features = ["cracking", "surface_irregularity"]
        severity = 6
        hazard = "medium"

        if "pothole" in lower_path:
            damage_type = "pavement_cavity_pothole"
            features = ["asphalt_depression", "exposed_gravel_bed", "water_accumulation"]
            severity = 7
            hazard = "high"
        elif "garbage" in lower_path or "trash" in lower_path:
            damage_type = "solid_waste_accumulation"
            features = ["overflowing_refuse", "public_passage_encroachment", "sanitary_risk"]
            severity = 6
            hazard = "medium"
        elif "leak" in lower_path or "water" in lower_path:
            damage_type = "water_pipe_rupture"
            features = ["surface_water_pooling", "flow_stream", "erosion_risk"]
            severity = 8
            hazard = "high"

        details = {
            "inspection_algorithm": "Multimodal-CivicVision-v2",
            "detected_objects": features,
            "dimensions_estimate": "Estimated area ~0.8m², depth approx 10-15cm",
            "traffic_obstruction": hazard in ("high", "critical"),
        }

        return VisionAnalysisResult(
            has_damage_detected=True,
            detected_damage_type=damage_type,
            visual_severity_estimate=severity,
            confidence_score=0.92,
            visual_features=features,
            safety_hazard_level=hazard,
            details=details,
        )

    async def transcribe_audio(self, audio_url_or_path: str, mime_type: str = "audio/wav") -> AudioTranscriptionResult:
        return AudioTranscriptionResult(
            transcript="Large pothole near the intersection causing traffic slowdowns and damage to two-wheelers.",
            detected_language="en",
            confidence=0.96,
        )

    async def synthesize_multimodal_triage(
        self,
        text: str,
        image_url: Optional[str] = None,
        audio_url: Optional[str] = None,
        category_hint: Optional[str] = None,
    ) -> MultimodalAnalysisResult:
        start_time = time.perf_counter()

        # Text Analysis
        text_res = await self.analyze_text(text, category_hint=category_hint)

        # Vision Analysis (if present)
        vision_dict = None
        severity = text_res.severity
        confidence = text_res.confidence_score

        if image_url:
            vision_res = await self.analyze_image(image_url)
            vision_dict = {
                "has_damage_detected": vision_res.has_damage_detected,
                "damage_type": vision_res.detected_damage_type,
                "visual_severity": vision_res.visual_severity_estimate,
                "hazard_level": vision_res.safety_hazard_level,
                "features": vision_res.visual_features,
                "details": vision_res.details,
            }
            # Multimodal synergy: fuse visual and textual severity
            severity = max(severity, vision_res.visual_severity_estimate)
            confidence = round(min(0.99, (confidence + vision_res.confidence_score) / 2.0 + 0.05), 2)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # Build combined reasoning
        reasoning = text_res.reasoning
        if vision_dict:
            reasoning += (
                f" Vision analysis confirmed {vision_dict['damage_type'].replace('_', ' ')} "
                f"with {vision_dict['hazard_level']} safety hazard level. "
                f"Combined confidence elevated to {confidence * 100:.0f}%."
            )

        return MultimodalAnalysisResult(
            summary=text_res.summary,
            detected_category=text_res.detected_category,
            confidence_score=confidence,
            urgency_score=text_res.urgency_score,
            severity=severity,
            recommended_department=text_res.recommended_department,
            reasoning=reasoning,
            extracted_entities=text_res.extracted_entities,
            vision_analysis=vision_dict,
            provider_name="mock",
            model_name="namma-civic-heuristic-v1",
            processing_time_ms=max(15, elapsed_ms),
        )

"""Deterministic lexical similarity used when no embedding model is available."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter


def normalize_text(text: str) -> str:
    """Apply Unicode compatibility normalization and stable case/punctuation rules."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"\w+", normalized, flags=re.UNICODE))


def token_jaccard_similarity(first: str, second: str) -> float:
    """Return Jaccard overlap of normalized word tokens."""
    tokens_a = set(normalize_text(first).split())
    tokens_b = set(normalize_text(second).split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _character_ngrams(text: str, minimum: int = 3, maximum: int = 5) -> Counter[str]:
    """Count character n-grams over normalized text with spaces removed."""
    compact = normalize_text(text).replace(" ", "")
    return Counter(
        compact[index:index + size]
        for size in range(minimum, maximum + 1)
        for index in range(max(0, len(compact) - size + 1))
    )


def character_ngram_similarity(first: str, second: str) -> float:
    """Return cosine similarity of 3-, 4-, and 5-character n-gram counts."""
    grams_a = _character_ngrams(first)
    grams_b = _character_ngrams(second)
    if not grams_a or not grams_b:
        return 0.0
    common = grams_a.keys() & grams_b.keys()
    dot = sum(grams_a[key] * grams_b[key] for key in common)
    norm_a = math.sqrt(sum(count * count for count in grams_a.values()))
    norm_b = math.sqrt(sum(count * count for count in grams_b.values()))
    return dot / (norm_a * norm_b)

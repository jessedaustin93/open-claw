"""
Open-Claw Ingest
Handles raw memory ingestion, importance scoring, and promotion
to episodic/semantic layers.
"""

import re
from typing import Optional

from .config import Config, get_config
from .memory_store import MemoryStore
from .exceptions import CoreMemoryProtectedError


class ImportanceScorer:
    """
    Rule-based importance scorer. Returns a float between 0.0 and 1.0.
    Score is based on:
      - Keyword presence (keyword_weight)
      - Text length relative to a target (length_weight)
      - Signal words like questions, negations, numbers (signal_weight)
    """

    TARGET_LENGTH = 200  # characters considered "substantial"

    SIGNAL_PATTERNS = [
        r"\?",                          # Questions
        r"\b(not|never|no|fail|error|wrong|broken|bug)\b",
        r"\b(always|must|critical|urgent|important)\b",
        r"\d+",                         # Contains numbers
        r"\b(because|therefore|thus|hence|so)\b",  # Causal language
    ]

    def __init__(self, config: Optional[Config] = None):
        self.cfg = config or get_config()

    def score(self, text: str, tags: Optional[list] = None) -> float:
        text_lower = text.lower()

        keyword_score = self._keyword_score(text_lower)
        length_score = self._length_score(text)
        signal_score = self._signal_score(text_lower)

        raw = (
            keyword_score * self.cfg.keyword_weight +
            length_score * self.cfg.length_weight +
            signal_score * self.cfg.signal_weight
        )

        return round(min(max(raw, 0.0), 1.0), 4)

    def _keyword_score(self, text_lower: str) -> float:
        hits = sum(1 for kw in self.cfg.importance_keywords if kw in text_lower)
        return min(hits / max(len(self.cfg.importance_keywords) * 0.3, 1), 1.0)

    def _length_score(self, text: str) -> float:
        return min(len(text) / self.TARGET_LENGTH, 1.0)

    def _signal_score(self, text_lower: str) -> float:
        hits = sum(
            1 for p in self.SIGNAL_PATTERNS
            if re.search(p, text_lower)
        )
        return min(hits / len(self.SIGNAL_PATTERNS), 1.0)


class Ingestor:
    """
    Entry point for adding new memories to Open-Claw.

    Flow:
      1. Text is stored as raw memory (always)
      2. Importance is scored
      3. If score >= episodic_threshold → also stored as episodic
      4. If score >= semantic_threshold → also stored as semantic
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        config: Optional[Config] = None,
    ):
        self.cfg = config or get_config()
        self.store = store or MemoryStore(self.cfg)
        self.scorer = ImportanceScorer(self.cfg)

    def ingest(
        self,
        text: str,
        tags: Optional[list] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """
        Ingest a new memory. Always creates a raw entry.
        Promotes to episodic and/or semantic based on importance score.

        Returns a dict with keys:
          raw       - the raw memory dict
          episodic  - episodic memory dict or None
          semantic  - semantic memory dict or None
          score     - importance score
        """
        tags = tags or []
        score = self.scorer.score(text, tags)

        # Always write raw
        raw = self.store.save(
            text=text,
            memory_type="raw",
            tags=tags,
            importance=score,
            extra=extra,
        )

        result = {"raw": raw, "episodic": None, "semantic": None, "score": score}

        # Promote to episodic
        if score >= self.cfg.episodic_threshold:
            episodic = self.store.save(
                text=text,
                memory_type="episodic",
                tags=tags,
                importance=score,
                extra={**(extra or {}), "promoted_from": raw["id"]},
            )
            result["episodic"] = episodic

        # Promote to semantic
        if score >= self.cfg.semantic_threshold:
            semantic = self.store.save(
                text=text,
                memory_type="semantic",
                tags=tags,
                importance=score,
                extra={**(extra or {}), "promoted_from": raw["id"]},
            )
            result["semantic"] = semantic

        return result

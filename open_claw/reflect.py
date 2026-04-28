"""
Open-Claw Reflect
Layer 2 reflection engine.

Architecture:
  _analyse()            → structured analysis dict (pure logic, no LLM)
  _generate_reflection() → Markdown from analysis (LLM swap point)

Guarantees:
  - Reflections are NEVER written to vault/core/
  - Reflections are NEVER re-reflected (configurable)
  - Duplicate source sets are skipped (configurable)
  - All metadata is stored in reflection JSON
"""

import re
from datetime import datetime, timezone
from typing import Optional

from .config import Config, get_config
from .memory_store import MemoryStore
from .exceptions import CoreMemoryProtectedError


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Reflector:
    """
    Produces structured reflections over episodic and semantic memories.

    Two-step process:
      1. _analyse(memories)          → analysis dict
      2. _generate_reflection(analysis) → Markdown string

    _generate_reflection is the ONLY LLM swap point. Currently rule-based.
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        config: Optional[Config] = None,
    ):
        self.cfg = config or get_config()
        self.store = store or MemoryStore(self.cfg)

    # ── Public API ─────────────────────────────────────────────────────────

    def run(self) -> Optional[dict]:
        """
        Run a reflection pass over episodic + semantic memories.
        Returns the saved reflection memory dict, or None if skipped.
        """
        memories = self._gather_memories()

        if len(memories) < self.cfg.min_reflection_sources:
            return None

        if self.cfg.skip_duplicate_reflections and self._is_duplicate(memories):
            return None

        analysis = self._analyse(memories)

        if not self.cfg.allow_low_value_reflections and analysis["confidence"] < 0.2:
            return None

        md_content = self._generate_reflection(analysis)

        extra = {
            "source_ids": analysis["source_ids"],
            "source_titles": analysis["source_titles"],
            "source_types": analysis["source_types"],
            "generated_at": _now_iso(),
            "confidence": analysis["confidence"],
            "suggested_tasks": analysis["suggested_tasks"],
            "suggested_core_updates": analysis["suggested_core_updates"],
            "detected_patterns": analysis["detected_patterns"],
            "uncertainty_notes": analysis["uncertainty_signals"],
        }

        reflection = self.store.save(
            text=md_content,
            memory_type="reflections",
            tags=list(analysis["tag_counts"].keys())[:10],
            importance=analysis["confidence"],
            extra=extra,
        )

        return reflection

    # ── Memory gathering ───────────────────────────────────────────────────

    def _gather_memories(self) -> list:
        """
        Gather episodic + semantic memories.
        Excludes reflections (no reflection-on-reflection by default).
        Caps at max_memories_per_reflection.
        """
        memories = []

        for t in ("episodic", "semantic"):
            memories.extend(self.store.load_all(t))

        if self.cfg.allow_reflection_on_reflections:
            memories.extend(self.store.load_all("reflections"))

        # Sort by importance descending, cap
        memories.sort(key=lambda m: m.get("importance", 0.0), reverse=True)
        return memories[: self.cfg.max_memories_per_reflection]

    # ── Duplicate detection ────────────────────────────────────────────────

    def _is_duplicate(self, memories: list) -> bool:
        """
        Returns True if an existing reflection has already processed
        exactly this set of source IDs.
        """
        candidate_ids = frozenset(m["id"] for m in memories)

        for existing in self.store.load_all("reflections"):
            existing_ids = frozenset(existing.get("source_ids", []))
            if existing_ids == candidate_ids:
                return True

        return False

    # ── Analysis (pure logic — no LLM) ────────────────────────────────────

    def _analyse(self, memories: list) -> dict:
        """
        Produce a structured analysis dict from a list of memories.
        This is pure rule-based logic.

        Returns:
          source_ids          list of memory IDs
          source_titles       list of memory titles
          source_types        list of memory types
          tag_counts          {tag: count} across all sources
          high_importance     memories with importance >= 0.7
          detected_patterns   list of pattern strings
          uncertainty_signals list of uncertainty strings
          suggested_tasks     list of task strings
          suggested_core_updates list of suggested update strings
          confidence          float 0.0–1.0
        """
        source_ids = [m["id"] for m in memories]
        source_titles = [m.get("title", "Untitled") for m in memories]
        source_types = [m.get("type", "unknown") for m in memories]

        # Tag frequency
        tag_counts: dict = {}
        for mem in memories:
            for tag in mem.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # High-importance memories
        high_importance = [
            m for m in memories if m.get("importance", 0.0) >= 0.7
        ]

        # Pattern detection (tags appearing >= 3 times)
        detected_patterns = [
            f"Recurring theme: '{tag}' (appears {count}x)"
            for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])
            if count >= 3
        ]

        # Uncertainty signals
        uncertainty_signals = self._detect_uncertainty(memories)

        # Task extraction
        suggested_tasks = self._extract_tasks(memories)

        # Core suggestions (what SHOULD be in core — never written there)
        suggested_core_updates = self._suggest_core_updates(
            high_importance, detected_patterns
        )

        # Confidence score
        confidence = self._score_confidence(
            memories, tag_counts, high_importance, uncertainty_signals
        )

        return {
            "source_ids": source_ids,
            "source_titles": source_titles,
            "source_types": source_types,
            "tag_counts": tag_counts,
            "high_importance": high_importance,
            "detected_patterns": detected_patterns,
            "uncertainty_signals": uncertainty_signals,
            "suggested_tasks": suggested_tasks,
            "suggested_core_updates": suggested_core_updates,
            "confidence": confidence,
        }

    # ── Confidence scoring ─────────────────────────────────────────────────

    def _score_confidence(
        self,
        memories: list,
        tag_counts: dict,
        high_importance: list,
        uncertainty_signals: list,
    ) -> float:
        # Source count score (more sources = more confidence, caps at 20)
        source_score = min(len(memories) / 20, 1.0)

        # Tag diversity score (more unique tags = more diverse)
        diversity_score = min(len(tag_counts) / 15, 1.0)

        # Importance score (ratio of high-importance memories)
        if memories:
            importance_score = len(high_importance) / len(memories)
        else:
            importance_score = 0.0

        # Uncertainty penalty
        uncertainty_penalty = min(len(uncertainty_signals) * 0.05, 0.3)

        raw = (
            source_score * self.cfg.confidence_source_weight +
            diversity_score * self.cfg.confidence_diversity_weight +
            importance_score * self.cfg.confidence_importance_weight
        ) - uncertainty_penalty

        return round(min(max(raw, 0.0), 1.0), 4)

    # ── Uncertainty detection ──────────────────────────────────────────────

    def _detect_uncertainty(self, memories: list) -> list:
        uncertainty_patterns = [
            (r"\b(maybe|perhaps|possibly|might|unclear|unsure|unknown)\b", "Uncertain language"),
            (r"\b(conflict|contradict|inconsistent|opposite)\b", "Conflicting information"),
            (r"\?{2,}", "Multiple questions"),
            (r"\b(todo|fixme|hack|workaround)\b", "Known issues"),
        ]

        signals = []
        for mem in memories:
            text_lower = mem.get("text", "").lower()
            for pattern, label in uncertainty_patterns:
                if re.search(pattern, text_lower):
                    signals.append(f"{label} in: {mem.get('title', mem['id'])}")

        return list(dict.fromkeys(signals))  # deduplicate preserving order

    # ── Task extraction ────────────────────────────────────────────────────

    def _extract_tasks(self, memories: list) -> list:
        tasks = []
        for mem in memories:
            text = mem.get("text", "")
            sentences = re.split(r"[.!?\n]", text)
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                lower = sentence.lower()
                for phrase in self.cfg.task_trigger_phrases:
                    if phrase in lower:
                        tasks.append(sentence[:200])
                        break

        return list(dict.fromkeys(tasks))[:20]  # deduplicate, cap at 20

    # ── Core update suggestions ────────────────────────────────────────────

    def _suggest_core_updates(
        self, high_importance: list, patterns: list
    ) -> list:
        """
        Suggest what COULD go into core memory.
        These are NEVER written to vault/core/ — human decision only.
        """
        suggestions = []

        for mem in high_importance[:5]:
            suggestions.append(
                f"Consider adding to core: '{mem.get('title', mem['id'])}' "
                f"(importance={mem.get('importance', 0.0):.2f})"
            )

        for pattern in patterns[:3]:
            suggestions.append(f"Pattern worth encoding in core: {pattern}")

        return suggestions

    # ── Reflection generation (LLM SWAP POINT) ────────────────────────────

    def _generate_reflection(self, analysis: dict) -> str:
        """
        Convert analysis dict into a Markdown reflection.

        THIS IS THE ONLY LLM SWAP POINT.
        Currently rule-based. Replace this method body with an LLM call
        when ready — signature and return type must remain the same.
        """
        lines = ["# Reflection\n"]

        # What was learned
        lines.append("## What Was Learned\n")
        if analysis["high_importance"]:
            lines.append(
                f"Reviewed {len(analysis['source_ids'])} memories. "
                f"{len(analysis['high_importance'])} were high-importance."
            )
        else:
            lines.append(
                f"Reviewed {len(analysis['source_ids'])} memories. "
                "No high-importance signals detected."
            )

        # Important memories reviewed
        if analysis["high_importance"]:
            lines.append("\n## Important Memories Reviewed\n")
            for mem in analysis["high_importance"][:10]:
                lines.append(
                    f"- [[{mem['type']}/{mem['id']}|{mem.get('title', 'Untitled')}]] "
                    f"(importance={mem.get('importance', 0.0):.2f})"
                )

        # Patterns
        if analysis["detected_patterns"]:
            lines.append("\n## Patterns Detected\n")
            for p in analysis["detected_patterns"]:
                lines.append(f"- {p}")

        # Uncertainty / conflicts
        if analysis["uncertainty_signals"]:
            lines.append("\n## Uncertainty / Conflicts\n")
            for u in analysis["uncertainty_signals"][:10]:
                lines.append(f"- {u}")

        # Suggested tasks
        if analysis["suggested_tasks"]:
            lines.append("\n## Suggested Tasks\n")
            for task in analysis["suggested_tasks"][:10]:
                lines.append(f"- {task}")

        # Core suggestions (HUMAN ONLY)
        if analysis["suggested_core_updates"]:
            lines.append("\n## Suggested Core Memory Updates (Human Review Required)\n")
            lines.append(
                "> ⚠️ These are suggestions only. "
                "No changes to core memory are made automatically.\n"
            )
            for suggestion in analysis["suggested_core_updates"]:
                lines.append(f"- {suggestion}")

        # Confidence
        lines.append(f"\n## Confidence Score\n\n{analysis['confidence']:.2f} / 1.00")

        return "\n".join(lines)

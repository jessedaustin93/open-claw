from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .config import Config
from .memory_store import MemoryStore, _wikilink

# Vault subdirectory for each memory type (used when building source links)
_TYPE_SUBDIR: Dict[str, str] = {
    "episodic": "episodic",
    "semantic":  "semantic",
    "raw":       "raw",
}

_TASK_PHRASES = [
    "need to", "next step", "then test", "should ",
    "build ", "fix ", "install ", "compare ", "research ",
    "try ", "implement ", "create ", "investigate ",
    "check ", "review ", "update ",
]

_UNCERTAINTY_PHRASES = [
    "unclear", "uncertain", "not sure", "maybe", "might",
    "perhaps", "confusing", "confused", "don't know",
    "unsure", "possibly", "doubt", "ambiguous",
]


def reflect(config: Optional[Config] = None) -> Dict:
    """Review episodic and semantic memories and append a new reflection note.

    Safety guarantees:
    - Only episodic and semantic memories are reviewed by default.
      config.allow_reflection_on_reflections controls this.
    - At most config.max_memories_per_reflection sources per pass.
    - vault/core/ is never written to — core suggestions go in the note only.
    - Passes below config.min_reflection_sources are skipped unless
      config.allow_low_value_reflections is True.
    - Passes with the same source IDs as a prior reflection are skipped
      unless config.skip_duplicate_reflections is False.
    """
    if config is None:
        config = Config()

    store = MemoryStore(config)
    episodic = store.list_memories("episodic")
    semantic = store.list_memories("semantic")

    if config.allow_reflection_on_reflections:
        episodic = episodic + store.list_memories("reflections")

    if not episodic and not semantic:
        return {"reflection": None, "message": "No episodic or semantic memories to reflect on."}

    # Apply safety cap: keep the most recent N combined memories.
    combined = episodic + semantic
    limit = config.max_memories_per_reflection
    if len(combined) > limit:
        combined = sorted(combined, key=lambda m: m.get("created", ""))[-limit:]
        episodic = [m for m in combined if m["type"] == "episodic"]
        semantic  = [m for m in combined if m["type"] == "semantic"]

    source_ids = [m["id"] for m in episodic + semantic]

    # Low-value guard: too few sources.
    if len(source_ids) < config.min_reflection_sources and not config.allow_low_value_reflections:
        return {
            "reflection": None,
            "message": (
                f"Too few source memories ({len(source_ids)} < "
                f"{config.min_reflection_sources}). "
                "Set config.allow_low_value_reflections = True to override."
            ),
        }

    # Duplicate guard: same source IDs already reflected on.
    if config.skip_duplicate_reflections and _is_duplicate(source_ids, store):
        return {
            "reflection": None,
            "message": "Duplicate reflection skipped: same source IDs already reflected on.",
        }

    # Build readable source links.
    source_titles: Dict[str, Tuple[str, str]] = {
        m["id"]: (
            _TYPE_SUBDIR.get(m["type"], m["type"]),
            m.get("title", m["id"]),
        )
        for m in episodic + semantic
    }

    all_tags = list({tag for m in episodic + semantic for tag in m.get("tags", [])})

    analysis = _analyse(episodic, semantic)

    content = _generate_reflection(analysis)

    metadata = {
        "source_types":          analysis["source_types"],
        "confidence":            analysis["confidence"],
        "suggested_tasks":       analysis["suggested_tasks"],
        "suggested_core_updates": analysis["suggested_core_updates"],
        "detected_patterns":     analysis["detected_patterns"],
        "uncertainty_notes":     analysis["uncertainty_notes"],
        "generated_at":          analysis["generated_at"],
    }

    reflection = store.store_reflection(
        content=content,
        source_ids=source_ids,
        tags=all_tags,
        source_titles=source_titles,
        metadata=metadata,
    )

    return {"reflection": reflection, "message": "Reflection created."}


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def _is_duplicate(source_ids: List[str], store: MemoryStore) -> bool:
    """Return True if any prior reflection already reviewed the exact same source IDs."""
    source_set = set(source_ids)
    for r in store.list_memories("reflections"):
        if set(r.get("source_ids", [])) == source_set:
            return True
    return False


def _analyse(episodic: List[Dict], semantic: List[Dict]) -> Dict:
    """Build a structured analysis dict from episodic and semantic memories."""
    sources = episodic + semantic

    tag_counts: Dict[str, int] = {}
    for m in sources:
        for tag in m.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    high_importance = [m for m in sources if m.get("importance", 0) >= 0.6]
    detected_patterns = _detect_patterns(sources, tag_counts)
    uncertainty_notes = _detect_uncertainty(sources)
    suggested_tasks = _extract_tasks(sources)
    suggested_core_updates = _extract_core_suggestions(episodic, semantic)
    confidence = _compute_confidence(sources, tag_counts, len(uncertainty_notes))

    return {
        "sources":               sources,
        "source_ids":            [m["id"] for m in sources],
        "source_types":          {"episodic": len(episodic), "semantic": len(semantic)},
        "all_tags":              list(tag_counts.keys()),
        "tag_counts":            tag_counts,
        "high_importance":       high_importance,
        "detected_patterns":     detected_patterns,
        "uncertainty_notes":     uncertainty_notes,
        "suggested_tasks":       suggested_tasks,
        "suggested_core_updates": suggested_core_updates,
        "confidence":            confidence,
        "generated_at":          datetime.utcnow().isoformat(),
    }


def _detect_patterns(sources: List[Dict], tag_counts: Dict[str, int]) -> List[str]:
    patterns = []
    repeated = [tag for tag, count in tag_counts.items() if count > 1]
    if repeated:
        patterns.append(f"Repeated tags across memories: {', '.join(sorted(repeated))}")
    high = [m for m in sources if m.get("importance", 0) >= 0.6]
    if len(high) > 1:
        patterns.append(f"{len(high)} high-importance memories found — recurring themes may exist")
    return patterns


def _detect_uncertainty(sources: List[Dict]) -> List[str]:
    notes = []
    for m in sources:
        text = m.get("text", m.get("summary", m.get("description", ""))).lower()
        found = [p for p in _UNCERTAINTY_PHRASES if p in text]
        if found:
            notes.append(f"Memory {m['id']}: contains uncertainty signal(s): {', '.join(found)}")
    return notes


def _extract_tasks(sources: List[Dict]) -> List[str]:
    tasks = []
    for m in sources:
        text = m.get("text", m.get("summary", ""))
        text_lower = text.lower()
        for phrase in _TASK_PHRASES:
            if phrase in text_lower:
                snippet = text[:80].strip()
                entry = f"From {m['id']}: {snippet}..."
                if entry not in tasks:
                    tasks.append(entry)
                break
    return tasks


def _extract_core_suggestions(episodic: List[Dict], semantic: List[Dict]) -> List[str]:
    suggestions = []
    for m in semantic[:3]:
        concept = m.get("concept", "")
        if concept:
            link = _wikilink("semantic", m["id"], m.get("title"))
            suggestions.append(
                f"Consider adding **{concept}** to `vault/core/concepts.md` (see {link})"
            )
    very_high = [m for m in episodic if m.get("importance", 0) >= 0.8]
    for m in very_high[:3]:
        link = _wikilink("episodic", m["id"], m.get("title"))
        suggestions.append(f"Consider promoting {link} to core memory")
    return suggestions


def _compute_confidence(
    sources: List[Dict],
    tag_counts: Dict[str, int],
    uncertainty_count: int,
) -> float:
    if not sources:
        return 0.0
    source_score = min(len(sources) / 10.0, 0.5)
    tag_diversity = min(len(tag_counts) / 10.0, 0.3)
    uncertainty_penalty = min(uncertainty_count * 0.1, 0.3)
    return round(max(0.0, min(1.0, source_score + tag_diversity - uncertainty_penalty)), 3)


# ---------------------------------------------------------------------------
# _generate_reflection is the designated LLM swap point.
#
# Replace this entire function body with an LLM call when ready:
#
#   import anthropic
#   client = anthropic.Anthropic()
#   response = client.messages.create(
#       model="claude-sonnet-4-6",
#       max_tokens=2048,
#       messages=[{"role": "user", "content": _build_prompt(analysis)}],
#   )
#   return response.content[0].text
#
# The function signature, caller (reflect()), and storage path do not change.
# ---------------------------------------------------------------------------

def _generate_reflection(analysis: Dict) -> str:
    """Rule-based reflection renderer — placeholder for LLM integration.

    Produces a Markdown document with exactly 7 sections so that downstream
    tools and tests can locate each section by header name.
    """
    ep_count = analysis["source_types"].get("episodic", 0)
    sem_count = analysis["source_types"].get("semantic", 0)

    lines = [
        f"## Recursive Reflection — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        "",
        f"Reviewing {ep_count} episodic and {sem_count} semantic memories.",
        "",
    ]

    # Section 1: What Was Learned
    lines.append("### What Was Learned")
    high = analysis["high_importance"]
    if high:
        for m in high:
            subdir = _TYPE_SUBDIR.get(m["type"], m["type"])
            link = _wikilink(subdir, m["id"], m.get("title"))
            if m["type"] == "episodic":
                lines.append(f"- {link} — {m.get('summary', '')[:100]}")
            else:
                lines.append(
                    f"- {link} — {m.get('concept', '')}: {m.get('description', '')[:80]}"
                )
    else:
        lines.append("- No high-importance memories reviewed in this pass.")
    lines.append("")

    # Section 2: Important Memories Reviewed
    lines.append("### Important Memories Reviewed")
    for m in analysis["sources"][:10]:
        subdir = _TYPE_SUBDIR.get(m["type"], m["type"])
        link = _wikilink(subdir, m["id"], m.get("title"))
        lines.append(f"- {link} (importance: {m.get('importance', 0):.2f})")
    lines.append("")

    # Section 3: New Patterns Noticed
    lines.append("### New Patterns Noticed")
    if analysis["detected_patterns"]:
        for p in analysis["detected_patterns"]:
            lines.append(f"- {p}")
    else:
        lines.append("- No repeated patterns detected in this pass.")
    lines.append("")

    # Section 4: Conflicts or Uncertainty
    lines.append("### Conflicts or Uncertainty")
    if analysis["uncertainty_notes"]:
        for note in analysis["uncertainty_notes"]:
            lines.append(f"- {note}")
    else:
        lines.append("- No uncertainty signals detected.")
    lines.append("")

    # Section 5: Suggested Tasks
    lines.append("### Suggested Tasks")
    if analysis["suggested_tasks"]:
        for task in analysis["suggested_tasks"]:
            lines.append(f"- {task}")
    else:
        lines.append(
            "- No explicit task phrases detected. Review memories for implied next steps."
        )
    lines.append("")

    # Section 6: Suggested Core Memory Updates
    lines.append("### Suggested Core Memory Updates")
    lines.append("> **Human review required.** These are suggestions only.")
    lines.append("> Edit `vault/core/` manually after reviewing. Automated processes")
    lines.append("> must never write to `vault/core/` without explicit human approval.")
    lines.append("")
    if analysis["suggested_core_updates"]:
        for s in analysis["suggested_core_updates"]:
            lines.append(f"- {s}")
    else:
        lines.append("- No strong candidates identified in this pass.")
    lines.append("")

    # Section 7: Reflection Quality
    lines.append("### Reflection Quality")
    lines.append(f"**Confidence:** {analysis['confidence']:.2f}")
    lines.append("")
    lines.append(
        "_This reflection was generated by rule-based analysis. "
        "See `reflect.py:_generate_reflection` to swap in LLM-based synthesis._"
    )

    return "\n".join(lines)

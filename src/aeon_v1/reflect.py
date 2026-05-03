from typing import Dict, List, Optional, Tuple

from .config import Config
from .evaluate import EvaluationStore
from .llm import (
    build_reflection_prompt,
    build_reflection_prompt_sparse,
    generate_text,
    generate_with_memory,
    parse_reflection_sections,
)
from .memory_store import MemoryStore, _wikilink
from .tasks import create_tasks_from_reflection
from .time_utils import local_now_string, utc_now_iso

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
    from .write_guard import assert_write_authorized
    assert_write_authorized("reflect")
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

    past_failures = EvaluationStore(config).list_evaluations(feedback="failure")

    analysis = _analyse(episodic, semantic, past_failures)
    analysis["display_tz"] = config.display_timezone

    content = _generate_reflection(analysis, config)
    llm_meta = analysis.pop("_llm_meta", {"llm_used": False, "llm_model": None, "llm_provider": None})

    metadata = {
        "source_types":           analysis["source_types"],
        "confidence":             analysis["confidence"],
        "suggested_tasks":        analysis["suggested_tasks"],
        "suggested_core_updates": analysis["suggested_core_updates"],
        "detected_patterns":      analysis["detected_patterns"],
        "uncertainty_notes":      analysis["uncertainty_notes"],
        "failure_count":          analysis["failure_count"],
        "generated_at":           analysis["generated_at"],
        "llm_used":               llm_meta["llm_used"],
        "llm_model":              llm_meta["llm_model"],
        "llm_provider":           llm_meta["llm_provider"],
    }

    reflection = store.store_reflection(
        content=content,
        source_ids=source_ids,
        tags=all_tags,
        source_titles=source_titles,
        metadata=metadata,
    )

    # Layer 3: convert suggested_tasks from this reflection into stored task objects.
    tasks_created = create_tasks_from_reflection(reflection, config)

    return {
        "reflection": reflection,
        "message": "Reflection created.",
        "tasks_created": tasks_created,
    }


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


def _analyse(
    episodic: List[Dict],
    semantic: List[Dict],
    past_failures: Optional[List[Dict]] = None,
) -> Dict:
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

    failures = past_failures or []
    recent_failures = [
        {
            "task_title":  f.get("task_title",  f.get("task_id", "unknown")),
            "match_score": f.get("match_score", 0.0),
            "divergences": f.get("divergences", []),
            "simulation_id": f.get("simulation_id", ""),
        }
        for f in sorted(failures, key=lambda r: r.get("created_at", ""))[-5:]
    ]

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
        "failure_count":         len(failures),
        "recent_failures":       recent_failures,
        "confidence":            confidence,
        "generated_at":          utc_now_iso(),
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


def _generate_reflection(analysis: Dict, config: Optional[Config] = None) -> str:
    """Generate a 7-section reflection Markdown document.

    When config.llm_enabled is True and the LLM responds, sections 1/3/4/5
    (narrative) are replaced with LLM text. Sections 2/6/7 (memories list,
    core update warning, quality score) are always rule-based for safety.
    Falls back to fully rule-based when LLM is disabled or unavailable.
    """
    ep_count = analysis["source_types"].get("episodic", 0)
    sem_count = analysis["source_types"].get("semantic", 0)
    display_tz = analysis.get("display_tz", "America/New_York")

    # --- LLM attempt for narrative sections ---
    llm_sections: Dict[str, str] = {}
    llm_meta: Dict = {"llm_used": False, "llm_model": None, "llm_provider": None}

    if config is not None:
        if config.llm_tool_calling:
            from .memory_index_agent import MemoryIndexAgent
            agent = MemoryIndexAgent(config)
            llm_text = generate_with_memory(build_reflection_prompt_sparse(analysis), agent, config)
        else:
            llm_text = generate_text(build_reflection_prompt(analysis), config)
        if llm_text:
            llm_sections = parse_reflection_sections(llm_text)
            if llm_sections:
                llm_meta = {
                    "llm_used":     True,
                    "llm_model":    config.llm_deep_model if config.llm_tool_calling else config.llm_model,
                    "llm_provider": config.llm_provider,
                }

    analysis["_llm_meta"] = llm_meta  # picked up by reflect() for JSON metadata

    lines = [
        f"## Recursive Reflection — {local_now_string(display_tz)}",
        "",
        f"Reviewing {ep_count} episodic and {sem_count} semantic memories.",
        "",
    ]

    # Section 1: What Was Learned (LLM-enhanced or rule-based)
    lines.append("### What Was Learned")
    if "What Was Learned" in llm_sections:
        lines.append(llm_sections["What Was Learned"])
    else:
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

    # Section 2: Important Memories Reviewed — always rule-based (no LLM invention of sources)
    lines.append("### Important Memories Reviewed")
    for m in analysis["sources"][:10]:
        subdir = _TYPE_SUBDIR.get(m["type"], m["type"])
        link = _wikilink(subdir, m["id"], m.get("title"))
        lines.append(f"- {link} (importance: {m.get('importance', 0):.2f})")
    lines.append("")

    # Section 3: New Patterns Noticed (LLM-enhanced or rule-based)
    lines.append("### New Patterns Noticed")
    if "New Patterns Noticed" in llm_sections:
        lines.append(llm_sections["New Patterns Noticed"])
    else:
        if analysis["detected_patterns"]:
            for p in analysis["detected_patterns"]:
                lines.append(f"- {p}")
        else:
            lines.append("- No repeated patterns detected in this pass.")
    lines.append("")

    # Section 4: Conflicts or Uncertainty (LLM-enhanced or rule-based)
    lines.append("### Conflicts or Uncertainty")
    if "Conflicts or Uncertainty" in llm_sections:
        lines.append(llm_sections["Conflicts or Uncertainty"])
    else:
        if analysis["uncertainty_notes"]:
            for note in analysis["uncertainty_notes"]:
                lines.append(f"- {note}")
        else:
            lines.append("- No uncertainty signals detected.")
    # Inject past simulation failures regardless of LLM usage — always rule-based.
    recent_failures = analysis.get("recent_failures", [])
    if recent_failures:
        lines.append("")
        lines.append(f"**Past Simulation Failures ({len(recent_failures)} most recent):**")
        for f in recent_failures:
            divs = ", ".join(f["divergences"]) if f["divergences"] else "none"
            lines.append(
                f"- `{f['task_title']}` — match score {f['match_score']:.0%}; "
                f"divergences: {divs}"
            )
    lines.append("")

    # Section 5: Suggested Tasks (LLM-enhanced or rule-based)
    lines.append("### Suggested Tasks")
    if "Suggested Tasks" in llm_sections:
        lines.append(llm_sections["Suggested Tasks"])
    else:
        if analysis["suggested_tasks"]:
            for task in analysis["suggested_tasks"]:
                lines.append(f"- {task}")
        else:
            lines.append(
                "- No explicit task phrases detected. Review memories for implied next steps."
            )
    lines.append("")

    # Section 6: Suggested Core Memory Updates — always rule-based (human-gated safety)
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

    # Section 7: Reflection Quality — always rule-based
    lines.append("### Reflection Quality")
    lines.append(f"**Confidence:** {analysis['confidence']:.2f}")
    lines.append("")
    if llm_meta["llm_used"]:
        lines.append(
            f"_Narrative sections enhanced by {llm_meta['llm_provider']} "
            f"`{llm_meta['llm_model']}`. "
            "Structural sections (memories list, core updates) are rule-based._"
        )
    else:
        lines.append(
            "_This reflection was generated by rule-based analysis. "
            "Enable LLM via AEON_V1_LLM=1 for narrative enhancement._"
        )

    return "\n".join(lines)

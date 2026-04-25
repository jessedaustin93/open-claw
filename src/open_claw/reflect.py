from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .config import Config
from .memory_store import MemoryStore, _wikilink

REFLECTION_QUESTIONS = [
    "What did the system learn from these memories?",
    "What patterns or themes repeat across these memories?",
    "What seems most important, and why?",
    "What should be preserved as long-term core memory?",
    "What tasks or experiments are implied by these memories?",
]

# Vault subdirectory for each memory type (used when building source links)
_TYPE_SUBDIR: Dict[str, str] = {
    "episodic": "episodic",
    "semantic": "semantic",
    "raw":      "raw",
}


def reflect(config: Optional[Config] = None) -> Dict:
    """Review episodic and semantic memories and append a new reflection note.

    Safety guarantees enforced here:
    - Only episodic and semantic memories are reviewed (not prior reflections).
      config.allow_reflection_on_reflections controls this; default is False.
    - At most config.max_memories_per_reflection source memories are included
      per pass (most recent kept when over the limit).
    - Core memory (vault/core/) is never written to. Suggestions are written
      inside the reflection note itself, clearly marked as requiring human review.
    """
    if config is None:
        config = Config()

    store = MemoryStore(config)
    episodic = store.list_memories("episodic")
    semantic = store.list_memories("semantic")

    # Explicitly exclude reflections unless the flag is turned on.
    # This prevents runaway recursive reflection loops.
    if config.allow_reflection_on_reflections:
        prior_reflections = store.list_memories("reflections")
        episodic = episodic + prior_reflections  # treat as additional sources

    if not episodic and not semantic:
        return {"reflection": None, "message": "No episodic or semantic memories to reflect on."}

    # Apply safety cap: take the most recent N combined memories.
    combined = episodic + semantic
    limit = config.max_memories_per_reflection
    if len(combined) > limit:
        combined = sorted(combined, key=lambda m: m.get("created", ""))[-limit:]
        episodic = [m for m in combined if m["type"] == "episodic"]
        semantic  = [m for m in combined if m["type"] == "semantic"]

    source_ids = [m["id"] for m in episodic + semantic]
    all_tags = list({tag for m in episodic + semantic for tag in m.get("tags", [])})

    # Build id -> (vault_subdir, display_title) for readable Obsidian links.
    source_titles: Dict[str, Tuple[str, str]] = {
        m["id"]: (
            _TYPE_SUBDIR.get(m["type"], m["type"]),
            m.get("title", m["id"]),
        )
        for m in episodic + semantic
    }

    content = _generate_reflection(episodic, semantic)
    reflection = store.store_reflection(
        content=content,
        source_ids=source_ids,
        tags=all_tags,
        source_titles=source_titles,
    )

    return {"reflection": reflection, "message": "Reflection created."}


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
#       messages=[{"role": "user", "content": _build_prompt(episodic, semantic)}],
#   )
#   return response.content[0].text
#
# The function signature, caller, and storage path do not need to change.
# ---------------------------------------------------------------------------

def _generate_reflection(episodic: List[Dict], semantic: List[Dict]) -> str:
    """Rule-based reflection generator — placeholder for LLM integration."""
    lines = [
        f"## Recursive Reflection — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        "",
        f"Reviewing {len(episodic)} episodic and {len(semantic)} semantic memories.",
        "",
    ]

    # Tag frequency analysis
    tag_counts: Dict[str, int] = {}
    for m in episodic + semantic:
        for tag in m.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if tag_counts:
        top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:5]
        lines.append("### Dominant Themes")
        for tag, count in top_tags:
            lines.append(f"- **{tag}** (appears {count} time(s))")
        lines.append("")

    # High-importance memories with readable links
    high = [m for m in episodic + semantic if m.get("importance", 0) >= 0.6]
    if high:
        lines.append("### High-Importance Memories")
        for m in high:
            subdir = _TYPE_SUBDIR.get(m["type"], m["type"])
            link = _wikilink(subdir, m["id"], m.get("title"))
            if m["type"] == "episodic":
                lines.append(f"- {link} — {m.get('summary', '')[:100]}")
            else:
                lines.append(f"- {link} — Concept: {m.get('concept', '')}")
        lines.append("")

    # Reusable concepts
    if semantic:
        lines.append("### Reusable Concepts Identified")
        for m in semantic:
            lines.append(f"- **{m.get('concept', 'Unknown')}**: {m.get('description', '')[:80]}")
        lines.append("")

    # Reflection questions for human or future LLM review
    lines.append("### Reflection Questions")
    for q in REFLECTION_QUESTIONS:
        lines.append(f"- {q}")
    lines.append("")

    # Implied tasks
    lines.append("### Implied Tasks")
    task_tags = [t for t in tag_counts if t in ("task", "experiment", "goal", "project")]
    if task_tags:
        for tag in task_tags:
            lines.append(f"- Review memories tagged `{tag}` for actionable follow-up.")
    else:
        lines.append("- No task-specific tags found. Consider reviewing for implied next steps.")
    lines.append("")

    # Core memory suggestions — SUGGESTIONS ONLY, never written automatically.
    lines.append("### Suggested Core Memory Updates")
    lines.append("> **Human review required.** These are suggestions only.")
    lines.append("> Edit `vault/core/` manually after reviewing. Automated processes")
    lines.append("> must never write to `vault/core/` without explicit human approval.")
    lines.append("")
    suggestions_written = False
    if semantic:
        for m in semantic[:3]:
            concept = m.get("concept", "")
            if concept:
                subdir = "semantic"
                link = _wikilink(subdir, m["id"], m.get("title"))
                lines.append(f"- Consider adding **{concept}** to `vault/core/concepts.md` (see {link})")
                suggestions_written = True
    very_high = [m for m in episodic if m.get("importance", 0) >= 0.8]
    for m in very_high[:3]:
        subdir = "episodic"
        link = _wikilink(subdir, m["id"], m.get("title"))
        lines.append(f"- Consider promoting {link} to core memory")
        suggestions_written = True
    if not suggestions_written:
        lines.append("- No strong candidates identified in this pass.")
    lines.append("")

    lines.append("### Note")
    lines.append(
        "This reflection was generated by rule-based analysis. "
        "See `reflect.py:_generate_reflection` to swap in LLM-based synthesis."
    )

    return "\n".join(lines)

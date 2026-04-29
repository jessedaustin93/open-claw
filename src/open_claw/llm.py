"""Optional LLM adapter for Open-Claw Layer 4.

anthropic is NOT a hard dependency. Open-Claw works fully without it.
generate_text() returns None whenever LLM is disabled, the API key is
missing, or any error occurs — callers always fall back to rule-based behavior.

Optional install:
    pip install anthropic

Environment variables:
    OPENCLAW_LLM=1            — enable LLM (also readable via Config.llm_enabled)
    ANTHROPIC_API_KEY=<key>   — required when provider is "anthropic"
"""
import os
import re
from typing import Dict, List, Optional

from .config import Config


def generate_text(prompt: str, config: Optional[Config] = None) -> Optional[str]:
    """Call the configured LLM and return the response text, or None on any failure.

    Args:
        prompt: The full prompt to send.
        config: Open-Claw Config — defaults to Config() if None.

    Returns:
        Response string, or None if LLM is disabled / unavailable / errored.
    """
    if config is None:
        config = Config()
    if not config.llm_enabled:
        return None
    if config.llm_provider == "anthropic":
        return _call_anthropic(prompt, config)
    return None


def _call_anthropic(prompt: str, config: Config) -> Optional[str]:
    """Call Anthropic Messages API. Returns None on any error."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import anthropic  # optional — not in install_requires
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=config.llm_model,
            max_tokens=config.llm_max_tokens,
            temperature=config.llm_temperature,
            messages=[{"role": "user", "content": prompt}],
            timeout=config.llm_timeout_seconds,
        )
        return response.content[0].text
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_reflection_prompt(analysis: Dict) -> str:
    """Build a compact prompt for LLM-enhanced reflection narrative sections.

    The LLM is asked to write ONLY 4 sections using provided data.
    Safety rules are embedded in the prompt.
    """
    ep_count = analysis["source_types"].get("episodic", 0)
    sem_count = analysis["source_types"].get("semantic", 0)

    mem_lines: List[str] = []
    for m in analysis.get("sources", [])[:10]:
        if m["type"] == "episodic":
            text = m.get("summary", "")[:120]
        else:
            concept = m.get("concept", "")
            desc = m.get("description", "")[:100]
            text = f"{concept}: {desc}" if concept else desc
        mem_lines.append(
            f"- [{m['type']}] importance={m.get('importance', 0):.2f}: {text}"
        )

    patterns_text = "\n".join(f"- {p}" for p in analysis.get("detected_patterns", []))
    uncertainty_text = "\n".join(f"- {u}" for u in analysis.get("uncertainty_notes", []))
    tasks_text = "\n".join(f"- {t}" for t in analysis.get("suggested_tasks", []))

    return f"""You are assisting an AI memory system with reflection synthesis.

CONTEXT:
- {ep_count} episodic and {sem_count} semantic memories reviewed.
- Confidence: {analysis.get('confidence', 0):.2f}

MEMORIES (up to 10):
{chr(10).join(mem_lines) or "- None"}

RAW PATTERN SIGNALS:
{patterns_text or "- None detected"}

RAW UNCERTAINTY SIGNALS:
{uncertainty_text or "- None detected"}

RAW TASK SIGNALS:
{tasks_text or "- None detected"}

TASK:
Write exactly 4 reflection sections using ONLY the data above.
Keep each section to 3-6 bullet points. Be specific and concise.

SAFETY RULES (mandatory):
- Use only information provided — do not invent facts, events, or outcomes.
- Do not suggest shell commands, system execution, or deployment actions.
- Do not claim any action was taken or completed.
- Core memory changes are SUGGESTIONS ONLY — humans decide what enters vault/core/.
- Do not alter source IDs, tags, or stored metadata.

OUTPUT FORMAT — use exactly these headers in this order:

### What Was Learned
[bullet points from high-importance memories]

### New Patterns Noticed
[bullet points about recurring themes or trends]

### Conflicts or Uncertainty
[bullet points about unclear or conflicting information]

### Suggested Tasks
[bullet points about implied next steps to investigate]

Write only these 4 sections. Nothing before or after."""


def build_simulation_prompt(task: Dict) -> str:
    """Build a compact prompt for LLM-enhanced simulation planning.

    The LLM proposes an action plan. Safety constraints are embedded.
    """
    return f"""You are assisting an AI memory system with action simulation planning.

TASK:
Title: {task.get('title', '')}
Description: {task.get('description', '')}
Priority: {task.get('priority', 0.5)}
Confidence: {task.get('confidence', 0.5)}

TASK:
Analyze this task and write a simulation plan. Be specific but concise.

SAFETY RULES (mandatory):
- This is SIMULATION ONLY — no real commands will be executed.
- Do not suggest subprocess calls, shell commands, or direct system actions.
- All proposed actions require explicit human approval before any execution.
- Do not claim actions were completed. Describe what WOULD happen.
- Keep the plan grounded in what is described — do not invent requirements.

OUTPUT FORMAT — use exactly these headers in this order:

### Proposed Action
[1-2 sentences: what should happen, concretely]

### Expected Outcome
[1-2 sentences: the realistic result if the action succeeds]

### Risk Assessment
[2-4 bullet points: risks and required approvals]

Write only these 3 sections. Nothing before or after."""


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------

def parse_reflection_sections(text: str) -> Dict[str, str]:
    """Extract the 4 narrative sections from an LLM reflection response.

    Returns a dict of {section_name: content}. Missing sections are omitted.
    """
    section_names = [
        "What Was Learned",
        "New Patterns Noticed",
        "Conflicts or Uncertainty",
        "Suggested Tasks",
    ]
    return _extract_sections(text, section_names)


def parse_simulation_sections(text: str) -> Dict[str, str]:
    """Extract the 3 simulation sections from an LLM simulation response."""
    return _extract_sections(text, ["Proposed Action", "Expected Outcome", "Risk Assessment"])


def _extract_sections(text: str, names: List[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for name in names:
        m = re.search(
            rf"###\s*{re.escape(name)}\s*\n(.*?)(?=###\s|\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            content = m.group(1).strip()
            if content:
                result[name] = content
    return result

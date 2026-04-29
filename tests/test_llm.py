"""Tests for Layer 4 — optional LLM reasoning integration.

Coverage:
- Config defaults and OPENCLAW_LLM env toggle
- generate_text returns None when disabled
- generate_text returns None when API key missing (even if enabled)
- Reflection fallback: full rule-based path works without LLM
- Simulation fallback: full rule-based path works without LLM
- Mocked LLM output is correctly inserted into reflection Markdown
- Mocked LLM output is correctly inserted into simulation record
- llm_used/llm_model/llm_provider metadata is accurate in both cases
- No subprocess or execution primitives in llm.py
- All 7 Markdown sections always present regardless of LLM state
- Prompt builders produce non-empty prompts containing safety language
"""
import ast
import os
from pathlib import Path
from typing import Dict
from unittest.mock import patch

import pytest

from open_claw import Config, generate_text, ingest, reflect, simulate_action
from open_claw.llm import (
    build_reflection_prompt,
    build_simulation_prompt,
    parse_reflection_sections,
    parse_simulation_sections,
)
from open_claw.tasks import TaskStore


SRC_DIR = Path(__file__).parent.parent / "src" / "open_claw"

# ---------------------------------------------------------------------------
# Config — LLM fields and env toggle
# ---------------------------------------------------------------------------

def test_llm_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OPENCLAW_LLM", raising=False)
    cfg = Config()
    assert cfg.llm_enabled is False


def test_llm_enabled_via_env(monkeypatch):
    monkeypatch.setenv("OPENCLAW_LLM", "1")
    cfg = Config()
    assert cfg.llm_enabled is True


def test_llm_env_zero_means_disabled(monkeypatch):
    monkeypatch.setenv("OPENCLAW_LLM", "0")
    cfg = Config()
    assert cfg.llm_enabled is False


def test_llm_config_defaults():
    cfg = Config()
    assert cfg.llm_provider == "anthropic"
    assert cfg.llm_model == "claude-3-5-sonnet-latest"
    assert cfg.llm_temperature == 0.2
    assert cfg.llm_max_tokens == 1200
    assert cfg.llm_timeout_seconds == 60


# ---------------------------------------------------------------------------
# generate_text adapter
# ---------------------------------------------------------------------------

def test_generate_text_returns_none_when_disabled():
    cfg = Config()
    cfg.llm_enabled = False
    assert generate_text("hello", cfg) is None


def test_generate_text_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = Config()
    cfg.llm_enabled = True
    # No API key → None, never raises
    result = generate_text("hello", cfg)
    assert result is None


def test_generate_text_returns_none_on_import_error(monkeypatch):
    """If anthropic is not installed, generate_text returns None gracefully."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    cfg = Config()
    cfg.llm_enabled = True
    # Simulate ImportError when anthropic is imported inside _call_anthropic
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("anthropic not installed")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        result = generate_text("hello", cfg)
    assert result is None


def test_generate_text_returns_none_on_api_error(monkeypatch):
    """API errors are caught and None is returned — system never crashes."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    cfg = Config()
    cfg.llm_enabled = True

    with patch("open_claw.llm._call_anthropic", return_value=None):
        result = generate_text("hello", cfg)
    assert result is None


# ---------------------------------------------------------------------------
# No execution primitives in llm.py
# ---------------------------------------------------------------------------

def test_no_execution_primitives_in_llm():
    tree = ast.parse((SRC_DIR / "llm.py").read_text(encoding="utf-8"))
    forbidden = {"subprocess", "os.system", "os.popen", "shutil", "exec", "eval"}
    imports_found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden:
                    imports_found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden:
                imports_found.add(node.module)
    assert imports_found == set(), f"llm.py imports forbidden modules: {imports_found}"


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def test_reflection_prompt_is_non_empty():
    analysis = {
        "sources": [],
        "source_types": {"episodic": 1, "semantic": 0},
        "detected_patterns": ["Tag X repeated"],
        "uncertainty_notes": [],
        "suggested_tasks": ["Review X"],
        "confidence": 0.5,
    }
    prompt = build_reflection_prompt(analysis)
    assert len(prompt) > 100
    assert "vault/core/" in prompt  # safety instruction present
    assert "### What Was Learned" in prompt
    assert "### Suggested Tasks" in prompt


def test_simulation_prompt_is_non_empty():
    task = {"title": "test-task", "description": "Investigate memory leak", "priority": 0.8, "confidence": 0.7}
    prompt = build_simulation_prompt(task)
    assert len(prompt) > 100
    assert "SIMULATION ONLY" in prompt
    assert "### Proposed Action" in prompt
    assert "### Risk Assessment" in prompt


def test_reflection_prompt_includes_safety_rules():
    analysis = {"sources": [], "source_types": {}, "detected_patterns": [],
                "uncertainty_notes": [], "suggested_tasks": [], "confidence": 0.3}
    prompt = build_reflection_prompt(analysis)
    assert "do not invent" in prompt.lower() or "only the information provided" in prompt.lower()
    assert "core memory" in prompt.lower()


# ---------------------------------------------------------------------------
# parse_reflection_sections / parse_simulation_sections
# ---------------------------------------------------------------------------

def test_parse_reflection_sections_full():
    text = """### What Was Learned
- Learned A
- Learned B

### New Patterns Noticed
- Pattern X appears

### Conflicts or Uncertainty
- No conflicts

### Suggested Tasks
- Do thing Y
"""
    sections = parse_reflection_sections(text)
    assert "What Was Learned" in sections
    assert "Learned A" in sections["What Was Learned"]
    assert "New Patterns Noticed" in sections
    assert "Conflicts or Uncertainty" in sections
    assert "Suggested Tasks" in sections


def test_parse_reflection_sections_partial():
    """Missing sections are omitted — no KeyError."""
    text = "### What Was Learned\n- Only this section\n"
    sections = parse_reflection_sections(text)
    assert "What Was Learned" in sections
    assert "New Patterns Noticed" not in sections


def test_parse_simulation_sections_full():
    text = """### Proposed Action
Review the configuration file and update settings.

### Expected Outcome
Configuration will be updated and system will restart cleanly.

### Risk Assessment
- Human review required before any real action is taken.
- Configuration changes may affect other services.
"""
    sections = parse_simulation_sections(text)
    assert "Proposed Action" in sections
    assert "Expected Outcome" in sections
    assert "Risk Assessment" in sections


def test_parse_simulation_sections_empty_response():
    sections = parse_simulation_sections("")
    assert sections == {}


# ---------------------------------------------------------------------------
# Reflection — fallback path (LLM disabled)
# ---------------------------------------------------------------------------

def test_reflection_works_without_llm(tmp_path):
    config = _tmp_config(tmp_path)
    config.allow_low_value_reflections = True
    config.min_reflection_sources = 1

    ingest(
        'I learned a critical key insight: "Fallback Memory" is an important concept.',
        config=config,
    )
    result = reflect(config=config)
    ref = result["reflection"]
    assert ref is not None
    content = ref["content"]
    _assert_all_7_sections(content)
    assert ref.get("llm_used") is False
    assert ref.get("llm_model") is None
    assert ref.get("llm_provider") is None


def test_reflection_all_7_sections_always_present(tmp_path):
    config = _tmp_config(tmp_path)
    config.allow_low_value_reflections = True
    config.min_reflection_sources = 1
    ingest(
        'I learned a critical key insight: "Section Test" is an important concept.',
        config=config,
    )
    result = reflect(config=config)
    _assert_all_7_sections(result["reflection"]["content"])


# ---------------------------------------------------------------------------
# Reflection — mocked LLM path
# ---------------------------------------------------------------------------

_MOCK_REFLECTION_LLM = """### What Was Learned
- LLM-synthesized insight about memory systems

### New Patterns Noticed
- LLM detected a recurring theme about learning

### Conflicts or Uncertainty
- LLM found no significant conflicts

### Suggested Tasks
- LLM suggests investigating the memory consolidation process
"""


def test_reflection_uses_mocked_llm_output(tmp_path):
    config = _tmp_config(tmp_path)
    config.llm_enabled = True
    config.allow_low_value_reflections = True
    config.min_reflection_sources = 1

    ingest(
        'I learned a critical key insight: "LLM Memory" is an important concept.',
        config=config,
    )

    with patch("open_claw.reflect.generate_text", return_value=_MOCK_REFLECTION_LLM):
        result = reflect(config=config)

    ref = result["reflection"]
    assert ref is not None
    content = ref["content"]
    _assert_all_7_sections(content)
    assert "LLM-synthesized insight" in content
    assert "LLM detected a recurring theme" in content
    assert ref.get("llm_used") is True
    assert ref.get("llm_model") == config.llm_model
    assert ref.get("llm_provider") == config.llm_provider


def test_reflection_llm_sections_2_6_7_always_rule_based(tmp_path):
    """Section 2 (memories list), 6 (core warning), 7 (quality) are never LLM-generated."""
    config = _tmp_config(tmp_path)
    config.llm_enabled = True
    config.allow_low_value_reflections = True
    config.min_reflection_sources = 1

    ingest(
        'I learned a critical key insight: "Rule Based" is an important concept.',
        config=config,
    )

    with patch("open_claw.reflect.generate_text", return_value=_MOCK_REFLECTION_LLM):
        result = reflect(config=config)

    content = result["reflection"]["content"]
    assert "Human review required" in content       # Section 6 core warning intact
    assert "**Confidence:**" in content             # Section 7 quality intact


def test_reflection_fallback_when_llm_returns_empty(tmp_path):
    """If LLM returns empty string, rule-based sections are used."""
    config = _tmp_config(tmp_path)
    config.llm_enabled = True
    config.allow_low_value_reflections = True
    config.min_reflection_sources = 1

    ingest(
        'I learned a critical key insight: "Empty LLM" is an important concept.',
        config=config,
    )

    with patch("open_claw.reflect.generate_text", return_value=""):
        result = reflect(config=config)

    ref = result["reflection"]
    assert ref.get("llm_used") is False
    _assert_all_7_sections(ref["content"])


# ---------------------------------------------------------------------------
# Simulation — fallback path (LLM disabled)
# ---------------------------------------------------------------------------

def test_simulation_works_without_llm(tmp_path):
    config = _tmp_config(tmp_path)
    config.allow_low_value_reflections = True
    config.min_reflection_sources = 1

    ingest(
        'I learned a critical key insight: "Sim Test" is an important concept. '
        'Need to review the simulation pipeline.',
        config=config,
    )
    reflect(config=config)

    tasks = TaskStore(config).list_tasks()
    assert tasks, "No tasks created — cannot test simulation"
    result = simulate_action(tasks[0], config=config)

    sim = result["simulation"]
    assert sim["proposed_action"]
    assert sim["expected_outcome"]
    assert isinstance(sim["risks"], list) and len(sim["risks"]) > 0
    assert sim.get("llm_used") is False
    assert sim.get("llm_model") is None
    assert sim.get("llm_provider") is None


# ---------------------------------------------------------------------------
# Simulation — mocked LLM path
# ---------------------------------------------------------------------------

_MOCK_SIM_LLM = """### Proposed Action
Review the memory consolidation pipeline and identify bottlenecks.

### Expected Outcome
A documented analysis of the pipeline performance with actionable improvements.

### Risk Assessment
- Human review required before any real action is taken.
- Changes to the pipeline may affect other memory layers.
"""


def test_simulation_uses_mocked_llm_output(tmp_path):
    config = _tmp_config(tmp_path)
    config.llm_enabled = True
    config.allow_low_value_reflections = True
    config.min_reflection_sources = 1

    ingest(
        'I learned a critical key insight: "LLM Sim" is an important concept. '
        'Need to build the next phase.',
        config=config,
    )
    reflect(config=config)

    tasks = TaskStore(config).list_tasks()
    assert tasks

    with patch("open_claw.simulate.generate_text", return_value=_MOCK_SIM_LLM):
        result = simulate_action(tasks[0], config=config)

    sim = result["simulation"]
    assert "Review the memory consolidation" in sim["proposed_action"]
    assert "documented analysis" in sim["expected_outcome"]
    assert sim.get("llm_used") is True
    assert sim.get("llm_model") == config.llm_model
    assert sim.get("llm_provider") == config.llm_provider


def test_simulation_always_requires_human_approval(tmp_path):
    """require_human_approval must be True in simulation regardless of LLM."""
    config = _tmp_config(tmp_path)
    config.llm_enabled = True
    config.allow_low_value_reflections = True
    config.min_reflection_sources = 1
    ingest(
        'I learned a critical key insight: "Approval Test" is an important concept. '
        'Need to fix the approval flow.',
        config=config,
    )
    reflect(config=config)
    tasks = TaskStore(config).list_tasks()
    assert tasks
    with patch("open_claw.simulate.generate_text", return_value=_MOCK_SIM_LLM):
        result = simulate_action(tasks[0], config=config)
    assert result["simulation"]["required_human_approval"] is True


def test_simulation_no_real_execution_even_with_llm(tmp_path):
    """simulate.py must not import execution primitives even after LLM integration."""
    tree = ast.parse((SRC_DIR / "simulate.py").read_text(encoding="utf-8"))
    forbidden = {"subprocess", "os.system", "os.popen", "shutil", "exec", "eval"}
    imports_found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden:
                    imports_found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden:
                imports_found.add(node.module)
    assert imports_found == set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_config(tmp_path: Path) -> Config:
    cfg = Config()
    cfg.memory_path = tmp_path / "memory"
    cfg.vault_path = tmp_path / "vault"
    return cfg


def _assert_all_7_sections(content: str) -> None:
    sections = [
        "### What Was Learned",
        "### Important Memories Reviewed",
        "### New Patterns Noticed",
        "### Conflicts or Uncertainty",
        "### Suggested Tasks",
        "### Suggested Core Memory Updates",
        "### Reflection Quality",
    ]
    missing = [s for s in sections if s not in content]
    assert missing == [], f"Missing sections in reflection: {missing}"

"""
Tests proving core Open-Claw guarantees:
- Raw memory is written verbatim
- Markdown vault note is created
- High-importance text is promoted to episodic memory
- Search returns matching results
- Reflection note is created and stored
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from open_claw import Config, ingest, reflect, search


@pytest.fixture
def cfg(tmp_path):
    return Config(base_path=tmp_path)


# ------------------------------------------------------------------ raw memory

def test_raw_memory_written(cfg):
    text = "This is a test memory about a project goal."
    result = ingest(text, config=cfg)
    raw_id = result["raw"]["id"]

    raw_json = cfg.memory_path / "raw" / f"{raw_id}.json"
    assert raw_json.exists(), "Raw JSON file was not created"

    data = json.loads(raw_json.read_text())
    assert data["type"] == "raw"
    assert data["text"] == text, "Raw text must be stored verbatim"
    assert 0 <= data["importance"] <= 1


def test_raw_memory_never_modified(cfg):
    original = "Exact verbatim text — must never be summarized or changed."
    result = ingest(original, config=cfg)
    raw_id = result["raw"]["id"]

    data = json.loads((cfg.memory_path / "raw" / f"{raw_id}.json").read_text())
    assert data["text"] == original


# --------------------------------------------------------------- markdown vault

def test_markdown_note_created(cfg):
    result = ingest("Remember this important concept about learning.", config=cfg)
    raw_id = result["raw"]["id"]

    md_path = cfg.vault_path / "raw" / f"{raw_id}.md"
    assert md_path.exists(), "Markdown vault note was not created"

    content = md_path.read_text()
    assert "---" in content, "Frontmatter delimiter missing"
    assert raw_id in content, "Note should reference its own ID"
    assert "type: raw" in content


def test_markdown_frontmatter_fields(cfg):
    result = ingest("An important project milestone was reached.", config=cfg)
    md_path = cfg.vault_path / "raw" / f"{result['raw']['id']}.md"
    content = md_path.read_text()

    for field in ("id:", "type:", "created:", "source:", "importance:", "tags:", "links:"):
        assert field in content, f"Frontmatter field '{field}' is missing"


# ------------------------------------------------------------ episodic promotion

def test_episodic_promotion_on_high_importance(cfg):
    result = ingest("This is an important project I need to remember.", config=cfg)
    assert result["episodic"] is not None, "High-importance text should be promoted to episodic"

    ep_id = result["episodic"]["id"]
    ep_json = cfg.memory_path / "episodic" / f"{ep_id}.json"
    assert ep_json.exists()

    data = json.loads(ep_json.read_text())
    assert data["raw_ref"] == result["raw"]["id"]


def test_episodic_markdown_note_created(cfg):
    result = ingest("Remember this important project goal.", config=cfg)
    if result["episodic"] is None:
        pytest.skip("Text did not meet importance threshold")

    ep_id = result["episodic"]["id"]
    md_path = cfg.vault_path / "episodic" / f"{ep_id}.md"
    assert md_path.exists()
    assert "Episodic Memory" in md_path.read_text()


def test_no_episodic_for_low_importance(cfg):
    # Plain text with no importance keywords — importance stays at 0.3
    result = ingest("The weather is cloudy today.", config=cfg)
    assert result["episodic"] is None, "Low-importance text should not be promoted"


# --------------------------------------------------------------------- search

def test_search_returns_match(cfg):
    ingest("I learned about recursive memory systems today.", config=cfg)
    results = search("recursive memory", config=cfg)
    assert results, "Search should return at least one result"

    combined = " ".join(
        r["memory"].get("text", "") + r["memory"].get("summary", "") for r in results
    )
    assert "recursive memory" in combined.lower()


def test_search_no_false_positives(cfg):
    ingest("The quick brown fox jumps.", config=cfg)
    results = search("quantum entanglement", config=cfg)
    assert results == [], "Unrelated query should return no results"


def test_search_by_tag(cfg):
    ingest("This is an important project.", config=cfg)
    results = search("project", config=cfg)
    assert results, "Tag-based search should return results"


# ------------------------------------------------------------------ reflection

def test_reflection_created(cfg):
    ingest("This is an important project goal I must remember clearly.", config=cfg)
    result = reflect(config=cfg)

    assert result["reflection"] is not None, "Reflection should be created"
    ref_id = result["reflection"]["id"]

    assert (cfg.memory_path / "reflections" / f"{ref_id}.json").exists()
    assert (cfg.vault_path / "reflections" / f"{ref_id}.md").exists()


def test_reflection_references_source_ids(cfg):
    ingest("An important goal: build a local memory system.", config=cfg)
    result = reflect(config=cfg)

    reflection = result["reflection"]
    assert len(reflection["source_ids"]) > 0, "Reflection should list source memory IDs"


def test_no_reflection_without_memories(cfg):
    # Empty vault — nothing to reflect on
    result = reflect(config=cfg)
    assert result["reflection"] is None
    assert "No episodic or semantic" in result["message"]

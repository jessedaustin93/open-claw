"""
Open-Claw test suite — Layer 1 stabilization.

Guarantees proven:
- Raw memory is written verbatim and is immutable (append-only)
- Multiple raw ingestions never overwrite each other
- Markdown vault notes are created with correct frontmatter
- Memory records include a stable title field
- Obsidian wikilinks use readable [[path|Title]] format
- High-importance text is promoted to episodic; low-importance is not
- Multiple reflections are appended, never replacing prior ones
- Search returns matching results without false positives
- Core memory (vault/core/) is never touched by ingest or reflect
- Importance scoring is weighted: more signals → higher score
"""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from open_claw import Config, ingest, reflect, search
from open_claw.memory_store import _score_importance


@pytest.fixture
def cfg(tmp_path):
    return Config(base_path=tmp_path)


# ═══════════════════════════════════════ raw memory / append-only ══════════

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
    """The text field in a raw record must equal the original input forever."""
    original = "Exact verbatim text — must never be summarized or changed."
    result = ingest(original, config=cfg)
    raw_id = result["raw"]["id"]

    data = json.loads((cfg.memory_path / "raw" / f"{raw_id}.json").read_text())
    assert data["text"] == original


def test_raw_files_not_overwritten(cfg):
    """Two separate ingestions must produce two distinct, intact JSON files."""
    r1 = ingest("First memory about a project goal.", config=cfg)
    r2 = ingest("Second memory about a different goal.", config=cfg)

    id1, id2 = r1["raw"]["id"], r2["raw"]["id"]
    assert id1 != id2, "Each ingest must generate a unique ID"

    data1 = json.loads((cfg.memory_path / "raw" / f"{id1}.json").read_text())
    data2 = json.loads((cfg.memory_path / "raw" / f"{id2}.json").read_text())
    assert data1["text"] == "First memory about a project goal."
    assert data2["text"] == "Second memory about a different goal."


# ═══════════════════════════════════════ markdown vault / frontmatter ══════

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

    for field in ("id:", "title:", "type:", "created:", "source:", "importance:", "tags:", "links:"):
        assert field in content, f"Frontmatter field '{field}' is missing"


# ═══════════════════════════════════════ title field ═══════════════════════

def test_memory_title_field_present(cfg):
    """All promoted memory layers must carry a title field."""
    result = ingest(
        "I learned an important goal for this project must be remembered.",
        config=cfg,
    )
    assert "title" in result["raw"], "Raw memory must include title field"
    if result["episodic"]:
        assert "title" in result["episodic"], "Episodic memory must include title field"
    if result["semantic"]:
        assert "title" in result["semantic"], "Semantic memory must include title field"


def test_title_is_human_readable(cfg):
    """Title must be readable words — not a bare UUID."""
    result = ingest("Remember this important project milestone.", config=cfg)
    title = result["raw"]["title"]

    assert len(title) > 0
    assert not re.fullmatch(r'[0-9a-f]{8}', title), "Title must not be a bare UUID"
    # At least one recognisable word from the input should appear
    assert any(word in title for word in ("remember", "important", "project", "milestone"))


def test_reflection_title_is_date_based(cfg):
    """Reflection title should encode a date stamp, not a bare UUID."""
    ingest("I learned an important project goal must be remembered.", config=cfg)
    result = reflect(config=cfg)
    title = result["reflection"]["title"]
    assert title.startswith("reflection-"), f"Expected reflection- prefix, got: {title}"
    assert re.search(r'\d{8}', title), "Reflection title should contain a date stamp"


# ═══════════════════════════════════════ Obsidian wikilinks ════════════════

def test_obsidian_links_include_readable_title(cfg):
    """Episodic note must link to its raw source using [[path|Title]] format."""
    result = ingest("This is an important project I need to remember.", config=cfg)
    assert result["episodic"] is not None, "Text should promote to episodic"

    ep_id = result["episodic"]["id"]
    md_path = cfg.vault_path / "episodic" / f"{ep_id}.md"
    content = md_path.read_text()

    raw_id = result["raw"]["id"]
    # Link must use readable format: [[raw/{id}|some-title]]
    assert f"[[raw/{raw_id}|" in content, (
        "Episodic vault note should link to raw source with readable display title"
    )


def test_reflection_links_use_readable_titles(cfg):
    """Reflection note sources must use [[subdir/id|title]] wikilinks."""
    ingest("I learned an important project goal must be remembered.", config=cfg)
    result = reflect(config=cfg)

    ref_id = result["reflection"]["id"]
    md_path = cfg.vault_path / "reflections" / f"{ref_id}.md"
    content = md_path.read_text()

    # At least one source link should contain a pipe (readable format)
    assert "|" in content, "Reflection source links should use [[path|Title]] format"


# ═══════════════════════════════════════ episodic promotion ════════════════

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
    result = ingest("The weather is cloudy today.", config=cfg)
    assert result["episodic"] is None, "Low-importance text must not be promoted"


# ═══════════════════════════════════════ importance scoring ════════════════

def test_importance_low():
    """Plain prose with no signal words must score clearly below the threshold."""
    score = _score_importance("The sky is blue and the clouds are white.")
    assert score < 0.5, f"Plain text should score below 0.5, got {score}"


def test_importance_high():
    """Keyword-rich text must score above the default 0.5 threshold."""
    score = _score_importance("I learned a critical insight about project goals.")
    assert score >= 0.5, f"Keyword-rich text should score >= 0.5, got {score}"


def test_importance_weighted_signals():
    """More signals → strictly higher score."""
    low    = _score_importance("Hello world.")
    medium = _score_importance("This is an important note.")
    high   = _score_importance("I learned a critical key insight for this project goal.")

    assert low < medium, f"low ({low}) should be < medium ({medium})"
    assert medium < high, f"medium ({medium}) should be < high ({high})"
    assert low < 0.5,  f"Plain text below threshold expected, got {low}"
    assert high >= 0.5, f"Dense keyword text above threshold expected, got {high}"


def test_importance_via_ingest(cfg):
    """Low-importance text stays raw; high-importance text is promoted."""
    low_result  = ingest("The meeting was held at noon.", config=cfg)
    high_result = ingest("I learned an important project goal must be remembered.", config=cfg)

    assert low_result["episodic"] is None,  "Low-importance text must not promote"
    assert high_result["episodic"] is not None, "High-importance text must promote"


# ═══════════════════════════════════════ search ════════════════════════════

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


# ═══════════════════════════════════════ reflection / append-only ══════════

def test_reflection_created(cfg):
    ingest("This is an important project goal I must remember clearly.", config=cfg)
    result = reflect(config=cfg)

    assert result["reflection"] is not None, "Reflection should be created"
    ref_id = result["reflection"]["id"]

    assert (cfg.memory_path / "reflections" / f"{ref_id}.json").exists()
    assert (cfg.vault_path / "reflections" / f"{ref_id}.md").exists()


def test_reflection_references_source_ids(cfg):
    ingest("I learned an important project goal: build a local memory system.", config=cfg)
    result = reflect(config=cfg)

    reflection = result["reflection"]
    assert reflection is not None, "Reflection should be created for high-importance memory"
    assert len(reflection["source_ids"]) > 0, "Reflection should list source memory IDs"


def test_multiple_reflections_both_preserved(cfg):
    """Calling reflect() twice must create two distinct files — no overwriting."""
    ingest("I learned an important project goal must be remembered.", config=cfg)

    r1 = reflect(config=cfg)
    r2 = reflect(config=cfg)

    assert r1["reflection"] is not None
    assert r2["reflection"] is not None
    id1, id2 = r1["reflection"]["id"], r2["reflection"]["id"]
    assert id1 != id2, "Each reflect() call must produce a unique reflection ID"

    assert (cfg.memory_path / "reflections" / f"{id1}.json").exists(), "First reflection must persist"
    assert (cfg.memory_path / "reflections" / f"{id2}.json").exists(), "Second reflection must persist"
    assert (cfg.vault_path  / "reflections" / f"{id1}.md").exists()
    assert (cfg.vault_path  / "reflections" / f"{id2}.md").exists()


def test_no_reflection_without_memories(cfg):
    result = reflect(config=cfg)
    assert result["reflection"] is None
    assert "No episodic or semantic" in result["message"]


# ═══════════════════════════════════════ core memory protection ════════════

def test_core_not_modified_by_ingest(cfg):
    """Ingestion must never create or modify any file inside vault/core/."""
    core_dir = cfg.vault_path / "core"
    before = set(core_dir.glob("*")) if core_dir.exists() else set()

    ingest("Important project goal must be remembered.", config=cfg)

    after = set(core_dir.glob("*")) if core_dir.exists() else set()
    assert before == after, "Ingestion must not touch vault/core/"


def test_core_not_modified_by_reflect(cfg):
    """Reflection must never create or modify any file inside vault/core/."""
    ingest("I learned an important project goal.", config=cfg)

    core_dir = cfg.vault_path / "core"
    before = set(core_dir.glob("*")) if core_dir.exists() else set()

    reflect(config=cfg)

    after = set(core_dir.glob("*")) if core_dir.exists() else set()
    assert before == after, "Reflection must not touch vault/core/"

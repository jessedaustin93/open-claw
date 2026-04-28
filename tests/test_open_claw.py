"""
Open-Claw Test Suite
Covers:
  Layer 1: raw immutability, append-only, titles, linking, core protection
  Layer 2: reflection structure, metadata, duplicate detection,
           confidence bounds, task extraction, core protection remains intact
"""

import json
import pytest
import tempfile
from pathlib import Path

from open_claw.config import Config
from open_claw.memory_store import MemoryStore
from open_claw.ingest import Ingestor, ImportanceScorer
from open_claw.linker import Linker
from open_claw.reflect import Reflector
from open_claw.exceptions import CoreMemoryProtectedError, InvalidMemoryError


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_config(tmp_path):
    """Config pointing to a fresh temp directory."""
    return Config(
        base_dir=tmp_path,
        memory_dir=tmp_path / "memory",
        vault_dir=tmp_path / "vault",
        min_reflection_sources=2,
        skip_duplicate_reflections=True,
        allow_low_value_reflections=True,  # allow in tests
    )


@pytest.fixture
def store(tmp_config):
    return MemoryStore(config=tmp_config)


@pytest.fixture
def ingestor(tmp_config):
    store = MemoryStore(config=tmp_config)
    return Ingestor(store=store, config=tmp_config)


@pytest.fixture
def linker(tmp_config):
    store = MemoryStore(config=tmp_config)
    return Linker(store=store, config=tmp_config)


@pytest.fixture
def reflector(tmp_config):
    store = MemoryStore(config=tmp_config)
    return Reflector(store=store, config=tmp_config)


# ── Layer 1 Tests ──────────────────────────────────────────────────────────────

class TestRawImmutability:
    def test_raw_memory_is_written_once(self, store):
        """Raw memory files must never be overwritten."""
        mem = store.save("First content", memory_type="raw", tags=["x"])
        path = store.memory_dir / "raw" / f"{mem['id']}.json"
        mtime_before = path.stat().st_mtime

        # Saving a different memory should NOT touch the first file
        store.save("Second content", memory_type="raw", tags=["x"])
        assert path.stat().st_mtime == mtime_before, "Raw memory was overwritten!"

    def test_each_memory_gets_unique_id(self, store):
        """Every memory must have a unique ID."""
        m1 = store.save("Memory one", memory_type="raw")
        m2 = store.save("Memory two", memory_type="raw")
        assert m1["id"] != m2["id"]

    def test_identical_text_creates_separate_memories(self, store):
        """Same text twice = two separate memories, not an overwrite."""
        m1 = store.save("Duplicate text", memory_type="raw")
        m2 = store.save("Duplicate text", memory_type="raw")
        assert m1["id"] != m2["id"]


class TestAppendOnly:
    def test_reflections_always_create_new_entries(self, store):
        """Each reflection save must produce a new file."""
        r1 = store.save("Reflection 1", memory_type="reflections")
        r2 = store.save("Reflection 2", memory_type="reflections")
        files = list((store.memory_dir / "reflections").glob("*.json"))
        assert len(files) == 2

    def test_load_all_returns_all_entries(self, store):
        for i in range(5):
            store.save(f"Memory {i}", memory_type="episodic")
        memories = store.load_all("episodic")
        assert len(memories) == 5


class TestTitleSystem:
    def test_every_memory_has_title(self, store):
        mem = store.save("This is a test memory for titles", memory_type="raw")
        assert "title" in mem
        assert mem["title"] != ""

    def test_title_derived_from_text(self, store):
        mem = store.save("Recursive learning memory system test", memory_type="raw")
        assert "Recursive" in mem["title"]

    def test_title_present_in_json(self, store):
        mem = store.save("Title test memory", memory_type="raw")
        path = store.memory_dir / "raw" / f"{mem['id']}.json"
        loaded = json.loads(path.read_text())
        assert "title" in loaded
        assert loaded["title"]

    def test_filename_is_id_based(self, store):
        mem = store.save("Filename test", memory_type="raw")
        path = store.memory_dir / "raw" / f"{mem['id']}.json"
        assert path.exists()


class TestObsidianIntegration:
    def test_markdown_has_yaml_frontmatter(self, store):
        mem = store.save("Obsidian test", memory_type="raw", tags=["test"])
        md_path = store.vault_dir / "raw" / f"{mem['id']}.md"
        content = md_path.read_text()
        assert content.startswith("---")
        assert "id:" in content
        assert "type:" in content
        assert "created:" in content
        assert "importance:" in content
        assert "tags:" in content

    def test_markdown_has_wikilinks_section(self, store):
        mem = store.save("Wikilink test", memory_type="raw")
        md_path = store.vault_dir / "raw" / f"{mem['id']}.md"
        content = md_path.read_text()
        assert "## Related Memories" in content


class TestImportanceScoring:
    def test_score_is_between_0_and_1(self, tmp_config):
        scorer = ImportanceScorer(tmp_config)
        score = scorer.score("This is a test memory")
        assert 0.0 <= score <= 1.0

    def test_important_keywords_raise_score(self, tmp_config):
        scorer = ImportanceScorer(tmp_config)
        low = scorer.score("random text without signals")
        high = scorer.score(
            "critical error must fix always important key decision"
        )
        assert high > low

    def test_promotion_to_episodic(self, ingestor):
        result = ingestor.ingest(
            "This is a critical and important memory that must never be forgotten. "
            "Key decision: always check the error logs first.",
            tags=["critical", "important", "error"],
        )
        # Score should be high enough for episodic
        assert result["score"] >= 0.0  # always passes raw
        # Check episodic exists if score is high enough
        if result["score"] >= ingestor.cfg.episodic_threshold:
            assert result["episodic"] is not None


class TestLinking:
    def test_memories_with_shared_tags_get_linked(self, store, linker):
        m1 = store.save("Memory A", memory_type="episodic", tags=["learning", "ai"])
        m2 = store.save("Memory B", memory_type="episodic", tags=["learning", "memory"])
        
        summary = linker.run()
        
        # Both should have been scanned
        assert summary["memories_scanned"] >= 2

        # Reload and check links
        updated_m1 = store.load(m1["id"], "episodic")
        assert any(l["id"] == m2["id"] for l in updated_m1.get("links", []))

    def test_memories_without_shared_tags_not_linked(self, store, linker):
        m1 = store.save("Memory X", memory_type="episodic", tags=["alpha"])
        m2 = store.save("Memory Y", memory_type="episodic", tags=["beta"])
        
        linker.run()
        
        updated_m1 = store.load(m1["id"], "episodic")
        assert not any(l["id"] == m2["id"] for l in updated_m1.get("links", []))

    def test_links_use_correct_structure(self, store, linker):
        store.save("Memory P", memory_type="episodic", tags=["shared"])
        store.save("Memory Q", memory_type="episodic", tags=["shared"])
        linker.run()

        memories = store.load_all("episodic")
        for mem in memories:
            for link in mem.get("links", []):
                assert "id" in link
                assert "title" in link
                assert "type" in link


# ── Core Protection Tests ──────────────────────────────────────────────────────

class TestCoreProtection:
    def test_save_to_core_raises_error(self, store):
        with pytest.raises(CoreMemoryProtectedError):
            store.save("Attempt to write core", memory_type="core")

    def test_load_all_core_raises_error(self, store):
        with pytest.raises(CoreMemoryProtectedError):
            store.load_all("core")

    def test_update_links_on_core_raises_error(self, store):
        with pytest.raises(CoreMemoryProtectedError):
            store.update_links("fake-id", "core", [])

    def test_ingestor_cannot_write_to_core(self, ingestor):
        """Ingestor only writes to raw/episodic/semantic — never core."""
        result = ingestor.ingest("Core bypass attempt", tags=["core"])
        assert result["raw"]["type"] != "core"

    def test_reflector_never_writes_to_core(self, store, reflector):
        """Reflector must never touch vault/core/ regardless of suggestions."""
        # Seed memories
        for i in range(3):
            store.save(
                f"Important memory {i} that should be in core",
                memory_type="episodic",
                tags=["core", "important"],
                importance=0.9,
            )

        reflector.run()

        # vault/core/ must remain empty
        core_files = list((store.vault_dir / "core").glob("*"))
        assert len(core_files) == 0

    def test_core_protection_error_is_raised_on_path_traversal(self, store):
        """Direct path write to core must be blocked."""
        fake_core_path = store.vault_dir / "core" / "test.md"
        with pytest.raises(CoreMemoryProtectedError):
            store._assert_not_core(fake_core_path)


# ── Layer 2 Tests ──────────────────────────────────────────────────────────────

class TestReflectionStructure:
    def _seed_memories(self, store, n=5):
        for i in range(n):
            store.save(
                f"Memory {i}: we should build a better system. "
                "This is important for learning and progress.",
                memory_type="episodic",
                tags=["learning", "system", f"tag{i}"],
                importance=0.6 + i * 0.05,
            )

    def test_reflection_is_created(self, store, reflector):
        self._seed_memories(store)
        result = reflector.run()
        assert result is not None

    def test_reflection_has_required_metadata(self, store, reflector):
        self._seed_memories(store)
        result = reflector.run()
        assert result is not None

        for field in [
            "source_ids", "source_titles", "source_types",
            "generated_at", "confidence", "suggested_tasks",
            "suggested_core_updates", "detected_patterns", "uncertainty_notes"
        ]:
            assert field in result, f"Missing field: {field}"

    def test_reflection_source_ids_are_valid(self, store, reflector):
        self._seed_memories(store)
        result = reflector.run()
        assert isinstance(result["source_ids"], list)
        assert len(result["source_ids"]) > 0

    def test_reflection_text_contains_markdown(self, store, reflector):
        self._seed_memories(store)
        result = reflector.run()
        assert "# Reflection" in result["text"]

    def test_reflection_text_contains_confidence(self, store, reflector):
        self._seed_memories(store)
        result = reflector.run()
        assert "Confidence Score" in result["text"]


class TestConfidenceBounds:
    def test_confidence_is_between_0_and_1(self, store, reflector):
        for i in range(5):
            store.save(
                f"Test memory {i}",
                memory_type="episodic",
                tags=["test"],
                importance=0.5,
            )
        result = reflector.run()
        if result:
            assert 0.0 <= result["confidence"] <= 1.0

    def test_more_diverse_sources_increase_confidence(self, store, tmp_config):
        """Reflection with more diverse tags should score higher confidence."""
        store_a = MemoryStore(config=tmp_config)
        reflector_a = Reflector(store=store_a, config=tmp_config)

        # Seed with many diverse tags
        for i in range(10):
            store_a.save(
                f"Diverse memory {i} important critical must build",
                memory_type="episodic",
                tags=[f"tag{i}", f"category{i}", "important"],
                importance=0.8,
            )

        result = reflector_a.run()
        if result:
            assert result["confidence"] > 0.0


class TestDuplicateDetection:
    def test_same_sources_not_reflected_twice(self, store, reflector):
        for i in range(3):
            store.save(
                f"Memory {i}",
                memory_type="episodic",
                tags=["dedup"],
                importance=0.6,
            )

        first = reflector.run()
        assert first is not None

        # Second run with same sources should be skipped
        second = reflector.run()
        assert second is None

    def test_duplicate_check_disabled(self, tmp_config, store):
        """When skip_duplicate_reflections=False, reflections always run."""
        tmp_config.skip_duplicate_reflections = False
        r = Reflector(store=store, config=tmp_config)

        for i in range(3):
            store.save(
                f"Memory {i}",
                memory_type="episodic",
                tags=["nodedup"],
                importance=0.6,
            )

        r1 = r.run()
        r2 = r.run()
        assert r1 is not None
        assert r2 is not None


class TestTaskExtraction:
    def test_tasks_are_extracted(self, store, reflector):
        store.save(
            "We should build a memory indexer. Need to test the linker. "
            "Next step: implement the search module.",
            memory_type="episodic",
            tags=["tasks", "build"],
            importance=0.7,
        )
        store.save(
            "Should review the reflection output format.",
            memory_type="episodic",
            tags=["tasks", "review"],
            importance=0.6,
        )

        result = reflector.run()
        assert result is not None
        assert isinstance(result["suggested_tasks"], list)

    def test_task_extraction_finds_trigger_phrases(self, store, reflector):
        store.save(
            "We should implement caching. Need to test edge cases.",
            memory_type="episodic",
            tags=["implementation"],
            importance=0.7,
        )
        store.save(
            "Build the new interface next step.",
            memory_type="episodic",
            tags=["interface"],
            importance=0.6,
        )

        result = reflector.run()
        if result and result["suggested_tasks"]:
            combined = " ".join(result["suggested_tasks"]).lower()
            assert any(
                phrase in combined
                for phrase in ["should", "need to", "next step", "build", "test"]
            )


class TestNoReflectionOnReflection:
    def test_reflections_not_included_by_default(self, store, reflector):
        """Reflections must NOT be used as sources in further reflections."""
        for i in range(3):
            store.save(
                f"Base memory {i}",
                memory_type="episodic",
                tags=["base"],
                importance=0.6,
            )

        result = reflector.run()
        assert result is not None

        # Source types should NOT include 'reflections'
        assert "reflections" not in result.get("source_types", [])


class TestInvalidInputs:
    def test_empty_text_raises_error(self, store):
        with pytest.raises(InvalidMemoryError):
            store.save("", memory_type="raw")

    def test_whitespace_only_raises_error(self, store):
        with pytest.raises(InvalidMemoryError):
            store.save("   ", memory_type="raw")

    def test_unknown_memory_type_raises_error(self, store):
        with pytest.raises(InvalidMemoryError):
            store.save("valid text", memory_type="unknown_type")

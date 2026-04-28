"""
Open-Claw Memory Store
Handles all read/write operations for JSON and Markdown memory files.
Guarantees:
  - Append-only (no overwriting)
  - Unique IDs for every memory
  - Core memory is NEVER touched
  - Obsidian-compatible Markdown output
"""

import json
import uuid
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import Config, get_config
from .exceptions import CoreMemoryProtectedError, InvalidMemoryError


MEMORY_TYPES = ("raw", "episodic", "semantic", "reflections")
PROTECTED_DIRS = ("core",)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_id() -> str:
    return str(uuid.uuid4())


def _generate_title(text: str, max_words: int = 6) -> str:
    """Generate a human-readable title from the first N words of text."""
    words = re.sub(r"[^\w\s]", "", text).split()
    return " ".join(words[:max_words]) if words else "Untitled Memory"


class MemoryStore:
    """
    Primary interface for reading and writing all memory layers.
    All writes are append-only. No memory file is ever overwritten.
    vault/core/ is hard-protected.
    """

    def __init__(self, config: Optional[Config] = None):
        self.cfg = config or get_config()
        self.memory_dir = Path(self.cfg.memory_dir)
        self.vault_dir = Path(self.cfg.vault_dir)
        self._ensure_dirs()

    # ── Directory setup ────────────────────────────────────────────────────

    def _ensure_dirs(self):
        for t in MEMORY_TYPES:
            (self.memory_dir / t).mkdir(parents=True, exist_ok=True)
            (self.vault_dir / t).mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "schemas").mkdir(parents=True, exist_ok=True)
        for d in ("core", "agents", "tasks"):
            (self.vault_dir / d).mkdir(parents=True, exist_ok=True)

    # ── Core protection ────────────────────────────────────────────────────

    def _assert_not_core(self, path: Path):
        """Raise CoreMemoryProtectedError if path is inside vault/core/."""
        try:
            path.resolve().relative_to((self.vault_dir / "core").resolve())
            raise CoreMemoryProtectedError(
                f"Attempted write to protected core memory path: {path}"
            )
        except ValueError:
            pass  # Not under core/ — safe to proceed

    def _assert_type_not_core(self, memory_type: str):
        if memory_type == "core":
            raise CoreMemoryProtectedError(
                "Direct writes to core memory type are not allowed."
            )

    # ── Write ──────────────────────────────────────────────────────────────

    def save(
        self,
        text: str,
        memory_type: str,
        tags: Optional[list] = None,
        importance: float = 0.0,
        links: Optional[list] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        """
        Create and persist a new memory.
        Returns the full memory dict.
        Raises CoreMemoryProtectedError if memory_type == 'core'.
        Raises InvalidMemoryError if text is empty.
        """
        self._assert_type_not_core(memory_type)

        if not text or not text.strip():
            raise InvalidMemoryError("Memory text cannot be empty.")

        if memory_type not in MEMORY_TYPES:
            raise InvalidMemoryError(
                f"Unknown memory type '{memory_type}'. Must be one of {MEMORY_TYPES}."
            )

        memory_id = _generate_id()
        title = _generate_title(text)
        now = _now_iso()

        memory = {
            "id": memory_id,
            "title": title,
            "type": memory_type,
            "text": text,
            "tags": tags or [],
            "importance": importance,
            "links": links or [],
            "created": now,
        }

        if extra:
            memory.update(extra)

        # Write JSON
        json_path = self.memory_dir / memory_type / f"{memory_id}.json"
        self._assert_not_core(json_path)
        json_path.write_text(json.dumps(memory, indent=2), encoding="utf-8")

        # Write Markdown (Obsidian-compatible)
        md_path = self.vault_dir / memory_type / f"{memory_id}.md"
        self._assert_not_core(md_path)
        md_path.write_text(self._render_markdown(memory), encoding="utf-8")

        return memory

    # ── Read ───────────────────────────────────────────────────────────────

    def load(self, memory_id: str, memory_type: str) -> Optional[dict]:
        """Load a single memory by ID and type. Returns None if not found."""
        path = self.memory_dir / memory_type / f"{memory_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def load_all(self, memory_type: str) -> list:
        """Load all memories of a given type, sorted by creation time."""
        self._assert_type_not_core(memory_type)
        directory = self.memory_dir / memory_type
        memories = []
        for path in sorted(directory.glob("*.json")):
            try:
                memories.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return sorted(memories, key=lambda m: m.get("created", ""))

    def search(self, query: str, memory_types: Optional[list] = None) -> list:
        """Simple text search across memory types."""
        types = memory_types or list(MEMORY_TYPES)
        results = []
        query_lower = query.lower()
        for t in types:
            if t == "core":
                continue
            for mem in self.load_all(t):
                searchable = (
                    mem.get("text", "") + " " +
                    mem.get("title", "") + " " +
                    " ".join(mem.get("tags", []))
                ).lower()
                if query_lower in searchable:
                    results.append(mem)
        return results

    # ── Update (restricted — only Related Memories section in Markdown) ────

    def update_links(self, memory_id: str, memory_type: str, new_links: list):
        """
        Update only the 'links' field of a memory JSON and
        the 'Related Memories' section of its Markdown file.
        This is the ONLY permitted in-place modification.
        """
        self._assert_type_not_core(memory_type)

        json_path = self.memory_dir / memory_type / f"{memory_id}.json"
        self._assert_not_core(json_path)

        if not json_path.exists():
            return

        memory = json.loads(json_path.read_text(encoding="utf-8"))
        memory["links"] = new_links
        json_path.write_text(json.dumps(memory, indent=2), encoding="utf-8")

        # Update Markdown Related Memories section only
        md_path = self.vault_dir / memory_type / f"{memory_id}.md"
        self._assert_not_core(md_path)
        if md_path.exists():
            md_content = md_path.read_text(encoding="utf-8")
            new_section = self._render_related_memories(new_links)
            if "## Related Memories" in md_content:
                md_content = re.sub(
                    r"## Related Memories\n.*",
                    new_section,
                    md_content,
                    flags=re.DOTALL,
                )
            else:
                md_content += f"\n\n{new_section}"
            md_path.write_text(md_content, encoding="utf-8")

    # ── Markdown rendering ─────────────────────────────────────────────────

    def _render_markdown(self, memory: dict) -> str:
        """Render a memory as Obsidian-compatible Markdown with YAML frontmatter."""
        tags_yaml = "\n".join(f"  - {t}" for t in memory.get("tags", []))
        links_yaml = "\n".join(
            f"  - {lnk}" for lnk in memory.get("links", [])
        )
        wikilinks = self._render_related_memories(memory.get("links", []))

        frontmatter = f"""---
id: {memory['id']}
title: "{memory['title']}"
type: {memory['type']}
created: {memory['created']}
importance: {memory['importance']}
tags:
{tags_yaml if tags_yaml else '  []'}
links:
{links_yaml if links_yaml else '  []'}
---"""

        body = f"""# {memory['title']}

{memory['text']}

{wikilinks}"""

        return f"{frontmatter}\n\n{body}"

    def _render_related_memories(self, links: list) -> str:
        if not links:
            return "## Related Memories\n\n_None_"
        items = "\n".join(
            f"- [[{lnk['type']}/{lnk['id']}|{lnk['title']}]]"
            for lnk in links
            if isinstance(lnk, dict)
        )
        return f"## Related Memories\n\n{items}"

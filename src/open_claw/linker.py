import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config

_VAULT_DIR_MAP = {
    "raw": "raw",
    "episodic": "episodic",
    "semantic": "semantic",
    "reflection": "reflections",
}


def link_memories(config: Optional[Config] = None) -> Dict[str, List[str]]:
    """Add Obsidian wikilinks between notes that share at least one tag.

    Returns a map of memory_id -> [related_id, ...] for inspection.
    """
    if config is None:
        config = Config()

    all_memories = _load_all_memories(config)
    link_map: Dict[str, List[str]] = {}

    for mem in all_memories:
        mem_id = mem.get("id")
        mem_tags = set(mem.get("tags", []))
        if not mem_id or not mem_tags:
            continue

        related = [
            other["id"]
            for other in all_memories
            if other.get("id") != mem_id and mem_tags & set(other.get("tags", []))
        ]

        if related:
            link_map[mem_id] = related
            _update_markdown_links(mem, related, config)

    return link_map


def _load_all_memories(config: Config) -> List[Dict]:
    memories = []
    for mem_type in ["raw", "episodic", "semantic", "reflections"]:
        mem_dir = config.memory_path / mem_type
        if not mem_dir.exists():
            continue
        for f in mem_dir.glob("*.json"):
            try:
                memories.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
    return memories


def _update_markdown_links(memory: Dict, related_ids: List[str], config: Config) -> None:
    vault_dir_name = _VAULT_DIR_MAP.get(memory.get("type", "raw"), "raw")
    md_path = config.vault_path / vault_dir_name / f"{memory['id']}.md"
    if not md_path.exists():
        return

    content = md_path.read_text(encoding="utf-8")
    link_section = "\n\n## Related Memories\n" + "\n".join(
        f"- [[{rid}]]" for rid in related_ids
    )

    if "## Related Memories" in content:
        content = re.sub(
            r"\n\n## Related Memories\n.*",
            link_section,
            content,
            flags=re.DOTALL,
        )
    else:
        content += link_section

    md_path.write_text(content, encoding="utf-8")

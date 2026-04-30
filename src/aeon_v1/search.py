import json
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config

# Fields checked during JSON memory search
_SEARCHABLE_FIELDS = ("text", "summary", "concept", "description", "content")


def search(
    query: str,
    memory_types: Optional[List[str]] = None,
    config: Optional[Config] = None,
) -> List[Dict]:
    """Keyword search across JSON memory files and Markdown vault notes.

    Structured so vector/embedding search can replace the inner match logic later
    without changing the function signature or return shape.
    """
    if config is None:
        config = Config()
    if memory_types is None:
        memory_types = ["raw", "episodic", "semantic", "reflections"]

    query_lower = query.lower()
    results: List[Dict] = []
    seen_ids: set = set()

    for mem_type in memory_types:
        # Search structured JSON first (authoritative source)
        mem_dir = config.memory_path / mem_type
        if mem_dir.exists():
            for f in mem_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if _matches(data, query_lower):
                        results.append({"match_type": mem_type, "file": str(f), "memory": data})
                        seen_ids.add(data.get("id", ""))
                except Exception:
                    pass

        # Also search vault Markdown (catches notes without a JSON counterpart)
        vault_dir = config.vault_path / mem_type
        if vault_dir.exists():
            for f in vault_dir.glob("*.md"):
                mem_id = f.stem
                if mem_id in seen_ids:
                    continue
                try:
                    content = f.read_text(encoding="utf-8")
                    if query_lower in content.lower():
                        results.append({
                            "match_type": f"vault/{mem_type}",
                            "file": str(f),
                            "memory": {"id": mem_id, "type": mem_type, "file": str(f)},
                        })
                        seen_ids.add(mem_id)
                except Exception:
                    pass

    return results


def _matches(data: Dict, query_lower: str) -> bool:
    for field in _SEARCHABLE_FIELDS:
        val = data.get(field)
        if isinstance(val, str) and query_lower in val.lower():
            return True
    tags = data.get("tags", [])
    if isinstance(tags, list) and any(query_lower in t.lower() for t in tags):
        return True
    return False

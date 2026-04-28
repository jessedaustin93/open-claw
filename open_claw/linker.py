"""
Open-Claw Linker
Automatically creates links between memories that share tags.
Only modifies the 'Related Memories' section of Markdown files.
Never touches vault/core/.
"""

from typing import Optional

from .config import Config, get_config
from .memory_store import MemoryStore, MEMORY_TYPES
from .exceptions import CoreMemoryProtectedError


class Linker:
    """
    Scans all non-core memory layers and creates bidirectional links
    between memories that share at least min_shared_tags tags.

    Only the 'links' field in JSON and the 'Related Memories' section
    in Markdown are ever modified.
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        config: Optional[Config] = None,
    ):
        self.cfg = config or get_config()
        self.store = store or MemoryStore(self.cfg)

    def run(self) -> dict:
        """
        Run a full linking pass across all memory types.
        Returns a summary of links created.
        """
        all_memories = []
        for t in MEMORY_TYPES:
            if t == "core":
                continue
            for mem in self.store.load_all(t):
                all_memories.append(mem)

        link_map = self._build_link_map(all_memories)
        self._apply_links(link_map)

        total_links = sum(len(v) for v in link_map.values())
        return {
            "memories_scanned": len(all_memories),
            "memories_linked": len(link_map),
            "total_links": total_links,
        }

    def _build_link_map(self, memories: list) -> dict:
        """
        For each memory, find all other memories that share >= min_shared_tags.
        Returns {memory_id: [list of link dicts]}
        """
        link_map = {}

        for i, mem_a in enumerate(memories):
            tags_a = set(mem_a.get("tags", []))
            if not tags_a:
                continue

            links_for_a = []

            for j, mem_b in enumerate(memories):
                if i == j:
                    continue
                tags_b = set(mem_b.get("tags", []))
                shared = tags_a & tags_b

                if len(shared) >= self.cfg.min_shared_tags:
                    links_for_a.append({
                        "id": mem_b["id"],
                        "title": mem_b.get("title", "Untitled"),
                        "type": mem_b["type"],
                        "shared_tags": list(shared),
                    })

            if links_for_a:
                link_map[mem_a["id"]] = {
                    "memory": mem_a,
                    "links": links_for_a,
                }

        return link_map

    def _apply_links(self, link_map: dict):
        """Write link updates back to JSON and Markdown files."""
        for memory_id, data in link_map.items():
            mem = data["memory"]
            links = data["links"]
            self.store.update_links(
                memory_id=memory_id,
                memory_type=mem["type"],
                new_links=links,
            )

    def link_memory(self, memory: dict, candidates: Optional[list] = None) -> list:
        """
        Link a single memory against a list of candidates (or all memories).
        Returns the list of link dicts applied.
        """
        if candidates is None:
            candidates = []
            for t in MEMORY_TYPES:
                if t == "core":
                    continue
                candidates.extend(self.store.load_all(t))

        tags_a = set(memory.get("tags", []))
        links = []

        for candidate in candidates:
            if candidate["id"] == memory["id"]:
                continue
            tags_b = set(candidate.get("tags", []))
            shared = tags_a & tags_b
            if len(shared) >= self.cfg.min_shared_tags:
                links.append({
                    "id": candidate["id"],
                    "title": candidate.get("title", "Untitled"),
                    "type": candidate["type"],
                    "shared_tags": list(shared),
                })

        if links:
            self.store.update_links(
                memory_id=memory["id"],
                memory_type=memory["type"],
                new_links=links,
            )

        return links

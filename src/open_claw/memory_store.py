import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .config import Config

# Keywords that raise importance score during ingestion
IMPORTANCE_KEYWORDS = [
    "i learned", "important", "remember", "project", "goal",
    "discovered", "realized", "key insight", "critical", "must not forget",
]


def _generate_id() -> str:
    return str(uuid.uuid4())[:8]


def _extract_importance(text: str) -> float:
    text_lower = text.lower()
    score = 0.3
    for kw in IMPORTANCE_KEYWORDS:
        if kw in text_lower:
            score += 0.15
    return round(min(score, 1.0), 3)


def _extract_tags(text: str) -> List[str]:
    text_lower = text.lower()
    keyword_tag_map = {
        "project": "project",
        "goal": "goal",
        "learned": "learning",
        "important": "important",
        "remember": "recall",
        "error": "error",
        "bug": "bug",
        "idea": "idea",
        "question": "question",
        "task": "task",
        "experiment": "experiment",
        "concept": "concept",
        "pattern": "pattern",
        "rule": "rule",
    }
    tags = []
    for kw, tag in keyword_tag_map.items():
        if kw in text_lower and tag not in tags:
            tags.append(tag)
    return tags


def _write_markdown(path: Path, frontmatter: Dict, body: str) -> None:
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    path.write_text("\n".join(lines) + "\n\n" + body, encoding="utf-8")


class MemoryStore:
    def __init__(self, config: Config):
        self.config = config
        config.ensure_dirs()

    # ------------------------------------------------------------------ raw --

    def store_raw(self, text: str, source: str = "manual") -> Dict:
        mem_id = _generate_id()
        now = datetime.utcnow().isoformat()
        importance = _extract_importance(text)
        tags = _extract_tags(text)

        memory = {
            "id": mem_id,
            "type": "raw",
            "created": now,
            "source": source,
            "text": text,
            "importance": importance,
            "tags": tags,
            "links": [],
        }

        (self.config.memory_path / "raw" / f"{mem_id}.json").write_text(
            json.dumps(memory, indent=2), encoding="utf-8"
        )

        _write_markdown(
            self.config.vault_path / "raw" / f"{mem_id}.md",
            frontmatter={
                "id": mem_id,
                "type": "raw",
                "created": now,
                "source": source,
                "importance": importance,
                "tags": tags,
                "links": [],
            },
            body=(
                f"# Raw Memory: {mem_id}\n\n"
                f"{text}\n\n"
                "[[Raw Memory]] | [[Episodic Memory]] | [[Core Memory]]"
            ),
        )
        return memory

    # --------------------------------------------------------------- episodic -

    def store_episodic(
        self,
        summary: str,
        raw_id: str,
        tags: List[str],
        importance: float,
        source: str,
    ) -> Dict:
        mem_id = _generate_id()
        now = datetime.utcnow().isoformat()

        memory = {
            "id": mem_id,
            "type": "episodic",
            "created": now,
            "source": source,
            "summary": summary,
            "raw_ref": raw_id,
            "importance": importance,
            "tags": tags,
            "links": [f"[[raw/{raw_id}]]"],
        }

        (self.config.memory_path / "episodic" / f"{mem_id}.json").write_text(
            json.dumps(memory, indent=2), encoding="utf-8"
        )

        _write_markdown(
            self.config.vault_path / "episodic" / f"{mem_id}.md",
            frontmatter={
                "id": mem_id,
                "type": "episodic",
                "created": now,
                "source": source,
                "importance": importance,
                "tags": tags,
                "links": [f"[[raw/{raw_id}]]"],
            },
            body=(
                f"# Episodic Memory: {mem_id}\n\n"
                f"**Summary:** {summary}\n\n"
                f"**Source:** [[raw/{raw_id}]]\n\n"
                "[[Episodic Memory]] | [[Semantic Memory]] | [[Reflections]]"
            ),
        )
        return memory

    # --------------------------------------------------------------- semantic -

    def store_semantic(
        self,
        concept: str,
        description: str,
        tags: List[str],
        importance: float,
        source: str,
    ) -> Dict:
        mem_id = _generate_id()
        now = datetime.utcnow().isoformat()

        memory = {
            "id": mem_id,
            "type": "semantic",
            "created": now,
            "source": source,
            "concept": concept,
            "description": description,
            "importance": importance,
            "tags": tags,
            "links": [],
        }

        (self.config.memory_path / "semantic" / f"{mem_id}.json").write_text(
            json.dumps(memory, indent=2), encoding="utf-8"
        )

        _write_markdown(
            self.config.vault_path / "semantic" / f"{mem_id}.md",
            frontmatter={
                "id": mem_id,
                "type": "semantic",
                "created": now,
                "source": source,
                "importance": importance,
                "tags": tags,
                "links": [],
            },
            body=(
                f"# Semantic Memory: {concept}\n\n"
                f"**Concept:** {concept}\n\n"
                f"**Description:** {description}\n\n"
                "[[Semantic Memory]] | [[Core Memory]] | [[Episodic Memory]]"
            ),
        )
        return memory

    # ------------------------------------------------------------- reflection -

    def store_reflection(
        self,
        content: str,
        source_ids: List[str],
        tags: List[str],
    ) -> Dict:
        mem_id = _generate_id()
        now = datetime.utcnow().isoformat()

        memory = {
            "id": mem_id,
            "type": "reflection",
            "created": now,
            "source": "reflection_engine",
            "content": content,
            "source_ids": source_ids,
            "tags": tags,
            "links": [f"[[{sid}]]" for sid in source_ids],
        }

        (self.config.memory_path / "reflections" / f"{mem_id}.json").write_text(
            json.dumps(memory, indent=2), encoding="utf-8"
        )

        _write_markdown(
            self.config.vault_path / "reflections" / f"{mem_id}.md",
            frontmatter={
                "id": mem_id,
                "type": "reflection",
                "created": now,
                "source": "reflection_engine",
                "tags": tags,
                "links": [f"[[{sid}]]" for sid in source_ids],
            },
            body=(
                f"# Reflection: {mem_id}\n\n"
                f"{content}\n\n"
                "**Sources:** "
                + ", ".join(f"[[{sid}]]" for sid in source_ids)
                + "\n\n[[Reflections]] | [[Episodic Memory]] | [[Semantic Memory]]"
            ),
        )
        return memory

    # ------------------------------------------------------------------ util --

    def list_memories(self, memory_type: str) -> List[Dict]:
        mem_dir = self.config.memory_path / memory_type
        if not mem_dir.exists():
            return []
        memories = []
        for f in mem_dir.glob("*.json"):
            try:
                memories.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return sorted(memories, key=lambda m: m.get("created", ""))

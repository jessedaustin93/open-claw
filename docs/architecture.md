# Aeon-V1 Architecture

## Overview

Aeon-V1 has three physical layers and a processing pipeline that moves data between them.

```
┌─────────────────────────────────────────────────────┐
│  Input (text, files, stdin)                         │
└───────────────────┬─────────────────────────────────┘
                    │ ingest()
                    ▼
┌─────────────────────────────────────────────────────┐
│  memory/   (structured JSON store)                  │
│    raw/          ← immutable verbatim captures      │
│    episodic/     ← promoted event summaries         │
│    semantic/     ← extracted reusable concepts      │
│    reflections/  ← recursive analysis outputs       │
│    schemas/      ← JSON Schema definitions          │
└───────────────────┬─────────────────────────────────┘
                    │ mirror write (every store op)
                    ▼
┌─────────────────────────────────────────────────────┐
│  vault/    (Obsidian-compatible Markdown)            │
│    raw/          ← raw notes with frontmatter       │
│    episodic/     ← episodic notes with wikilinks    │
│    semantic/     ← concept notes                    │
│    reflections/  ← reflection notes                 │
│    core/         ← long-term identity/rules         │
│    agents/       ← agent configs                    │
│    tasks/        ← implied task notes               │
└─────────────────────────────────────────────────────┘
```

Every write to `memory/` always has a corresponding write to `vault/`.  
The JSON store is the machine-readable source of truth.  
The Markdown vault is the human-readable view of the same data.

---

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | Centralized paths and tunable parameters |
| `memory_store.py` | Atomic read/write for all memory types |
| `ingest.py` | Heuristic promotion: raw → episodic → semantic |
| `reflect.py` | Analysis and reflection note generation |
| `search.py` | Keyword search with a vector-ready interface |
| `linker.py` | Wikilink creation based on shared tags |

---

## Data Flow

### Ingestion

```
ingest(text)
  1. Extract importance score (keyword heuristic)
  2. Extract tags (keyword-to-tag map)
  3. store_raw()       → memory/raw/{id}.json + vault/raw/{id}.md
  4. if importance >= threshold:
       store_episodic() → memory/episodic/{id}.json + vault/episodic/{id}.md
  5. if semantic keywords present:
       store_semantic() → memory/semantic/{id}.json + vault/semantic/{id}.md
```

### Reflection

```
reflect()
  1. Load all episodic memories
  2. Load all semantic memories
  3. Compute tag frequencies
  4. Identify high-importance memories
  5. List reusable concepts
  6. Generate reflection note (rule-based or LLM)
  7. store_reflection() → memory/reflections/{id}.json + vault/reflections/{id}.md
```

### Search

```
search(query)
  1. For each memory type directory in memory/:
       Scan *.json, check searchable text fields
  2. For each memory type directory in vault/:
       Scan *.md, check full text
  3. Return deduplicated list of matching records
```

---

## Extensibility Points

| Swap point | File | What to replace |
|---|---|---|
| LLM reflection | `reflect.py:_generate_reflection` | Return LLM-generated Markdown |
| Vector search | `search.py:_matches` | Replace with embedding cosine similarity |
| Promotion rules | `ingest.py` | Replace heuristics with classifier |
| Config source | `config.py:Config` | Load from YAML/env instead of hardcoded |

---

## File Naming

All memory files use an 8-character UUID prefix as their stem (e.g., `a1b2c3d4`).  
This is short enough to cite in notes and unique enough to avoid collisions for this use case.  
Switch to full UUIDs or timestamps in production if the store grows large.

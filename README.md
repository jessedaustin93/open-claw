# Open-Claw

A **local-first recursive AI memory and learning system** built on plain files.

Open-Claw stores knowledge in layered memory — raw captures, episodic summaries, semantic concepts, and recursive reflections — using Markdown and JSON so that humans and agents can both read and extend it.

---

## What Open-Claw Is

Open-Claw is a structured memory framework, not an autonomous AI.  
It gives any agent (or human) a place to:

- Store raw input exactly as received
- Automatically promote high-importance notes to richer memory layers
- Generate recursive reflections that analyze what has been learned
- Search across all memory with plain-text queries
- Link related notes automatically via Obsidian wikilinks

Everything lives in local files. No cloud. No database. No external API required.

---

## Why Raw Memory Is Preserved

Raw memories are **immutable** — they are never overwritten, summarized, or deleted.

This is a core design principle borrowed from append-only logs and MemPalace-style storage:

- Summarization always loses information
- Originals can be re-analyzed with better algorithms later
- Human auditors can trace every piece of knowledge back to its source
- Reversing or correcting errors is possible because the source always exists

Episodic and semantic memories are derived from raws, not replacements for them.

---

## Memory Layers

| Layer | Directory | Purpose |
|---|---|---|
| **Raw** | `vault/raw/`, `memory/raw/` | Exact verbatim captures — never modified |
| **Episodic** | `vault/episodic/`, `memory/episodic/` | Summarized meaningful events |
| **Semantic** | `vault/semantic/`, `memory/semantic/` | Reusable concepts, rules, and patterns |
| **Core** | `vault/core/` | Stable identity, long-term rules, goals |
| **Reflections** | `vault/reflections/`, `memory/reflections/` | Recursive analysis of prior memories |
| **Tasks** | `vault/tasks/` | Implied future actions and experiments |
| **Agents** | `vault/agents/` | Agent-specific configurations and notes |

---

## How Obsidian Is Used

Every stored memory creates a Markdown file inside `vault/`.  
Each file uses YAML frontmatter and Obsidian-style `[[wikilinks]]` to connect related notes.

Example note:

```markdown
---
id: a1b2c3d4
title: i-learned-that-recursive-memory
type: episodic
created: 2024-01-15T10:30:00
source: manual
importance: 0.75
tags:
  - learning
  - project
links:
  - "[[raw/9e8f7a6b|i-learned-that-building]]"
---

# i-learned-that-recursive-memory

**Summary:** I learned that recursive memory systems need layered storage.

**Source:** [[raw/9e8f7a6b|i-learned-that-building]]

[[Episodic Memory]] | [[Semantic Memory]] | [[Reflections]]
```

### ID vs Title

Every record has two identifiers:

| Field | Example | Stable? |
|---|---|---|
| `id` | `a1b2c3d4` | **Yes** — permanent, used in filenames and cross-references |
| `title` | `i-learned-that-recursive-memory` | Derived — for human readability only |

Filenames are always `{id}.md`. Wikilinks use `[[subdir/id|title]]` format so they resolve correctly to the file while displaying readable text in Obsidian.

Open the `vault/` folder as an Obsidian vault to get the graph view, backlinks, and tag explorer — but Obsidian is **not required**.  
All files are plain Markdown readable in any editor.

---

## How MemPalace-Style Storage Works

MemPalace-style storage means every memory has a **specific place** and stays there.

- `raw/` is the permanent record — the source of truth
- `episodic/` is organized by event and time
- `semantic/` is organized by concept
- `reflections/` is organized by analysis session

Nothing is deleted. Nothing is overwritten. New insights create new files.  
The system grows by accumulation, not replacement.

---

## How Recursive Reflection Works

The reflection engine reads all episodic and semantic memories and produces a new reflection note that asks:

1. What did the system learn?
2. What themes repeat?
3. What is most important?
4. What should become long-term core memory?
5. What tasks or experiments are implied?

The current engine is rule-based. The `reflect.py:_generate_reflection(analysis)` function is the single LLM swap point — replace its body with an API call when you are ready for AI-generated analysis. The caller and storage path do not need to change.

**Layer 2 — Reflection Quality** (implemented): Each reflection pass now runs a structured analysis (`_analyse()`) before rendering, producing a 7-section note and persisting rich metadata in the JSON record: `confidence`, `source_types`, `suggested_tasks`, `suggested_core_updates`, `detected_patterns`, `uncertainty_notes`, `generated_at`. Duplicate passes (same source IDs as a prior reflection) are skipped by default (`skip_duplicate_reflections = True`). Passes with too few sources are skipped unless `allow_low_value_reflections = True`.

**Reflection safety limits** (configurable in `Config`):
- Reviews episodic and semantic memories only — never prior reflections (prevents runaway loops)
- Capped at 50 source memories per pass by default (`max_memories_per_reflection`)
- Core memory suggestions are written inside the reflection note itself, clearly marked as requiring human review — never written to `vault/core/` automatically

---

## Safety and Control

Open-Claw is a **local memory framework**, not an autonomous uncontrolled agent.

- All files are local and human-readable at all times
- No action is taken without an explicit script invocation
- Memory is append-only — raw records are never overwritten; reflections always create new files
- Every memory traces back to its raw source via `raw_ref` and `source_ids` fields
- The reflection engine does not execute tasks — it only writes notes
- **`vault/core/` is human-gated and enforced in code.** `_write_markdown` raises `CoreMemoryProtectedError` on any attempt to write there. The linker skips `vault/core/` files. Reflections produce suggestions only, inside `vault/reflections/`. Override with `config.allow_core_modification = True`.
- Humans review, approve, and act on what the system learns

This system supports transparency, reversibility, and full human oversight.  
See `vault/core/PROTECTED.md` for the core memory protection contract.

---

## Quick Start

### Install

```bash
git clone https://github.com/jessedaustin93/open-claw
cd open-claw
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Ingest a Memory

```bash
# From the command line
python scripts/ingest_text.py "I learned that layered memory systems are more robust than flat logs."

# From a file
python scripts/ingest_text.py --file my_notes.txt --source journal

# From stdin
echo "Important project goal: ship Open-Claw v1." | python scripts/ingest_text.py
```

### Run Reflection

```bash
python scripts/run_reflection.py
```

### Search Memory

```bash
python scripts/search_memory.py "recursive learning"
python scripts/search_memory.py "goal" --types episodic semantic
```

### Link Related Notes

```python
from open_claw import Config, link_memories
link_memories(config=Config())
```

---

## Example Flow

```
Input text
  └─> memory/raw/a1b2c3d4.json    (exact verbatim copy)
  └─> vault/raw/a1b2c3d4.md

If importance >= 0.5:
  └─> memory/episodic/e5f6a7b8.json   (summarized event)
  └─> vault/episodic/e5f6a7b8.md

If semantic keywords found:
  └─> memory/semantic/c9d0e1f2.json   (reusable concept)
  └─> vault/semantic/c9d0e1f2.md

After reflection pass:
  └─> memory/reflections/r3a4b5c6.json
  └─> vault/reflections/r3a4b5c6.md
```

---

## Project Structure

```
open-claw/
  src/open_claw/      # Python package
    config.py         # Paths and tunable parameters
    memory_store.py   # Read/write memories (JSON + Markdown)
    ingest.py         # Promotion logic: raw -> episodic -> semantic
    reflect.py        # Reflection engine
    search.py         # Keyword search (vector-ready interface)
    linker.py         # Automatic Obsidian wikilink generation
  scripts/            # CLI entry points
  tests/              # pytest suite
  vault/              # Human-readable Markdown notes (open as Obsidian vault)
  memory/             # Structured JSON memory store + schemas
  docs/               # Architecture and design documentation
```

---

## Next Steps

See `docs/` for:
- `architecture.md` — system design and data flow
- `memory_model.md` — memory layer specification
- `recursive_learning_loop.md` — how ingestion, promotion, and reflection connect

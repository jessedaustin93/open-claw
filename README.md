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
| **Tasks** | `vault/tasks/`, `memory/tasks/` | Structured task objects derived from reflection suggested_tasks |
| **Decisions** | `vault/decisions/`, `memory/decisions/` | Append-only decision records from the selection engine |
| **Simulations** | `vault/simulations/`, `memory/simulations/` | Proposed-action records — never executed automatically |
| **Agents** | `vault/agents/` | Agent-specific configurations and notes |

---

## How Obsidian Is Used

### Quick Start

1. Clone the repository (or `git pull` the latest branch)
2. Open **Obsidian** → **Open folder as vault** → select the `vault/` directory
3. Start from [`vault/index.md`](vault/index.md) — it links all memory layers
4. Use `Ctrl+G` for the graph view, backlinks panel for tracing, and tag search for filtering

Obsidian is **not required**. All files are plain Markdown readable in any editor.

---

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

## Layer 3 — Decision and Action Simulation

**Layer 3 — Decision and Action Simulation** (implemented): Extends the reflection loop into structured propose → decide → simulate, while remaining fully local and human-gated.

### How Tasks Flow from Reflection

Every `reflect()` call automatically converts its `suggested_tasks` list into stored task objects in `memory/tasks/` and `vault/tasks/`. Near-duplicate tasks (Jaccard word-overlap ≥ 0.8) are silently blocked.

### Decision Engine

`select_next_task()` scores all pending tasks by `priority × 0.5 + confidence × 0.3`, selects the highest scorer, marks it `selected`, and writes an append-only decision record to `memory/decisions/`.

### Action Simulation

`simulate_action(task)` produces a structured simulation record describing what *would* happen — proposed action, expected outcome, and risk signals — and stores it in `memory/simulations/` and `vault/simulations/`. **No real commands are executed.** `subprocess`, `os.system`, and every execution primitive are absent from `simulate.py` by design. The `enable_real_actions` config flag is `False` permanently — there is no code path that enables execution.

### CLI

```bash
python scripts/manage_tasks.py tasks     # list pending tasks
python scripts/manage_tasks.py decide    # select best task, write decision record
python scripts/manage_tasks.py simulate  # simulate selected task
python scripts/manage_tasks.py loop      # decide + simulate once
```

### Why Simulation Instead of Execution

Execution requires explicit per-action human approval, sandboxing, and rollback mechanisms. Layer 3 builds the planning substrate — structured task objects, scored decisions, and detailed simulation records — so that when real tool use is added, the reasoning layer already exists and is fully auditable.

---

## Timestamps and Timezones

Open-Claw uses a two-layer timestamp strategy to avoid timezone bugs while keeping notes readable:

| Location | Format | Example |
|---|---|---|
| JSON records (`created`, `created_at`, `generated_at`) | UTC ISO-8601 with `+00:00` offset | `2026-04-28T21:07:13.050967+00:00` |
| Markdown notes and CLI output | Local time (configurable) | `2026-04-28 5:07 PM EDT` |

**Default display timezone:** `America/New_York` — change it in `Config.display_timezone`.

```python
from open_claw import Config
config = Config()
config.display_timezone = "Europe/London"   # or any IANA name
```

All helpers live in `src/open_claw/time_utils.py`:

| Function | Returns |
|---|---|
| `utc_now_iso()` | `'2026-04-28T21:07:13+00:00'` |
| `local_time_string(ts, tz)` | `'5:07 PM EDT'` |
| `local_date_time_string(ts, tz)` | `'2026-04-28 5:07 PM EDT'` |
| `local_now_string(tz)` | current local date + time |

Timezone conversion uses `zoneinfo` (stdlib, Python 3.9+). On systems without the OS timezone database, install `tzdata`:

```bash
pip install tzdata
```

---

## Safety and Control

Open-Claw is a **local memory framework**, not an autonomous uncontrolled agent.

- All files are local and human-readable at all times
- No action is taken without an explicit script invocation
- Memory is append-only — raw records are never overwritten; reflections and decisions always create new files
- Every memory traces back to its raw source via `raw_ref` and `source_ids` fields
- The reflection engine does not execute tasks — it only writes notes and proposed task objects
- The simulation engine writes files only — no subprocess, os.system, or network calls exist in `simulate.py`
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
    reflect.py        # Reflection engine (Layer 2) — triggers task creation
    tasks.py          # Task storage layer (Layer 3)
    decision.py       # Decision engine — select_next_task() (Layer 3)
    simulate.py       # Action simulation — simulate_action() (Layer 3, no execution)
    search.py         # Keyword search (vector-ready interface)
    linker.py         # Automatic Obsidian wikilink generation
    exceptions.py     # CoreMemoryProtectedError
  scripts/            # CLI entry points
    ingest_text.py    # Ingest text from CLI / file / stdin
    run_reflection.py # Trigger a reflection pass
    search_memory.py  # Search across all memory layers
    manage_tasks.py   # Layer 3: tasks | decide | simulate | loop
  tests/              # pytest suite (66 tests across Layers 1–3 + timestamps)
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

# Aeon-V1 Integration Status

This document describes what is implemented, what is planned, and where future
integrations plug in. It is the source of truth for contributors picking up the project.

---

## Layer Status

| Layer | Status | Module(s) | Description |
|---|---|---|---|
| **Raw ingestion** | ✅ Complete | `ingest.py`, `memory_store.py` | Verbatim capture — immutable, append-only |
| **Episodic promotion** | ✅ Complete | `ingest.py`, `memory_store.py` | Promoted when `importance ≥ threshold` |
| **Semantic extraction** | ✅ Complete | `ingest.py`, `memory_store.py` | Promoted when concept + semantic keyword detected |
| **Reflection engine** | ✅ Complete | `reflect.py` | 7-section structured analysis; rule-based renderer |
| **Task creation** | ✅ Complete | `tasks.py` | Suggested tasks → stored task objects; Jaccard dedup |
| **Decision engine** | ✅ Complete | `decision.py` | Scores pending tasks; writes append-only decision records |
| **Action simulation** | ✅ Complete | `simulate.py` | Proposes actions, estimates risk — no execution |
| **Memory linking** | ✅ Complete | `linker.py` | Adds Obsidian wikilinks between related notes |
| **Search** | ✅ Complete | `search.py` | Keyword search across all memory layers |
| **Core protection** | ✅ Complete | `memory_store.py`, `exceptions.py` | `CoreMemoryProtectedError` enforced at write layer |
| **Timezone handling** | ✅ Complete | `time_utils.py` | UTC in JSON, local time in Markdown/CLI |
| **LLM reflection** | ✅ Complete | `llm.py`, `reflect.py` | Optional LLM narrative enhancement; rule-based fallback |
| **LLM simulation** | ✅ Complete | `llm.py`, `simulate.py` | Optional LLM planning; rule-based fallback |
| **Vector search** | 🔲 Planned | `search.py` | Current interface is keyword; swap to embeddings |
| **Real action execution** | 🔲 Out of scope | — | Simulation only by design; tool use added externally |

---

## Data Flow (as implemented)

```
ingest(text)
  │
  ├─▶ store_raw()          → memory/raw/{id}.json   + vault/raw/{id}.md
  ├─▶ store_episodic()     → memory/episodic/{id}.json + vault/episodic/{id}.md
  │       (if importance >= config.importance_threshold)
  └─▶ store_semantic()     → memory/semantic/{id}.json + vault/semantic/{id}.md
          (if concept + semantic keyword detected)

reflect()
  │
  ├─▶ Reads all episodic + semantic memories
  ├─▶ _analyse() — tag counts, patterns, uncertainty, tasks, confidence
  ├─▶ _generate_reflection(analysis, config)
  │     ├─▶ [if llm_enabled] generate_text(build_reflection_prompt(analysis), config)
  │     │     → LLM writes sections 1/3/4/5 (narrative)
  │     └─▶ Rule-based sections 2/6/7 always (memories list, core warning, quality)
  ├─▶ store_reflection()   → memory/reflections/{id}.json + vault/reflections/{id}.md
  │     (includes llm_used, llm_model, llm_provider in JSON)
  └─▶ create_tasks_from_reflection() → memory/tasks/{id}.json + vault/tasks/{id}.md

select_next_task()
  │
  ├─▶ Scores pending tasks: priority×0.5 + confidence×0.3
  ├─▶ Updates winning task status to "selected"
  └─▶ store() decision     → memory/decisions/{id}.json + vault/decisions/{id}.md

simulate_action(task)
  │
  ├─▶ [if llm_enabled] generate_text(build_simulation_prompt(task), config)
  │     → LLM writes proposed_action, expected_outcome, risk_assessment
  ├─▶ Rule-based fallback for any LLM-missing field
  ├─▶ store() simulation   → memory/simulations/{id}.json + vault/simulations/{id}.md
  │     (includes llm_used, llm_model, llm_provider in JSON)
  └─▶ Updates task status to "simulated"
```

---

## Layer 4 — LLM Integration

### Architecture

LLM support is handled by `src/aeon_v1/llm.py`. It is an **optional adapter** —
the system works fully without it and without the `anthropic` package installed.

```
llm.py
  generate_text(prompt, config) → str | None
    │
    ├─▶ Returns None if config.llm_enabled is False
    ├─▶ Returns None if ANTHROPIC_API_KEY is missing
    ├─▶ Returns None on any API / import error
    └─▶ Calls _call_anthropic(prompt, config) if all checks pass
```

### Enabling LLM

```bash
# Linux / macOS
export AEON_V1_LLM=1
export ANTHROPIC_API_KEY=your_key_here

# PowerShell
$env:AEON_V1_LLM="1"
$env:ANTHROPIC_API_KEY="your_key_here"
```

Optional dependency:
```bash
pip install anthropic
```

### What the LLM does

| Component | LLM writes | Always rule-based |
|---|---|---|
| Reflection | Sections 1, 3, 4, 5 (narrative) | Sections 2, 6, 7 (memories list, core warning, quality) |
| Simulation | `proposed_action`, `expected_outcome`, risk bullets | Fallback when any field missing; human approval flag |

### What the LLM never does

- Write to `vault/core/` (enforced at code level)
- Remove the core memory warning block (section 6 is always rule-based)
- Execute commands or trigger real actions
- Override `source_ids` or stored metadata
- Become the memory authority (all records are written from Aeon-V1's own code)

### Metadata added to JSON records

Both reflection and simulation JSON records now include:

```json
{
  "llm_used": true,
  "llm_model": "claude-3-5-sonnet-latest",
  "llm_provider": "anthropic"
}
```

These are `false` / `null` when LLM is disabled or unavailable.

---

## File Layout

```
Aeon-V1/
  src/aeon_v1/          Python package
    config.py             Paths, tunable parameters, LLM config
    memory_store.py       Read/write all memory layers (JSON + Markdown)
    ingest.py             Raw → episodic → semantic promotion logic
    reflect.py            Reflection engine — Layers 2 + 4
    tasks.py              Task storage — Layer 3
    decision.py           Decision engine — Layer 3
    simulate.py           Action simulation — Layers 3 + 4 (no execution)
    llm.py                Optional LLM adapter — Layer 4
    linker.py             Automatic wikilink generation
    search.py             Keyword search (vector-ready interface)
    time_utils.py         UTC storage / local display helpers
    exceptions.py         CoreMemoryProtectedError
  scripts/                CLI entry points
  tests/                  pytest suite (105 tests)
  vault/                  Obsidian-compatible Markdown vault
  memory/                 Structured JSON store
  docs/                   This directory
```

---

## What Is Intentionally Absent

| Feature | Reason |
|---|---|
| External database | Local files only — no cloud, no DB |
| Web UI | Out of scope; Obsidian covers visualization |
| Real action execution | Simulation layer exists; execution requires explicit human tooling |
| Vendor / external repos | No vendored code; no bundled external libraries |
| Hard anthropic dependency | `pip install anthropic` is optional; system runs without it |
| Autonomous operation | Every significant action requires script invocation or human approval |

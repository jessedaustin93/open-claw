# Open-Claw Integration Status

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
| **LLM reflection** | 🔲 Planned | `reflect.py:_generate_reflection` | Replace rule-based renderer with LLM call |
| **LLM simulation** | 🔲 Planned | `simulate.py:_propose_action`, `_expected_outcome` | Replace heuristics with LLM reasoning |
| **Vector search** | 🔲 Planned | `search.py` | Current interface is keyword; swap to embeddings |
| **Real action execution** | 🔲 Out of scope | — | Simulation only by design; tool use added externally |

---

## Data Flow (as implemented)

```
ingest(text)
  │
  ├─▶ store_raw()          → memory/raw/{id}.json   + vault/raw/{id}.md
  │
  ├─▶ store_episodic()     → memory/episodic/{id}.json + vault/episodic/{id}.md
  │       (if importance >= config.importance_threshold)
  │
  └─▶ store_semantic()     → memory/semantic/{id}.json + vault/semantic/{id}.md
          (if concept + semantic keyword detected)

reflect()
  │
  ├─▶ Reads all episodic + semantic memories
  ├─▶ _analyse() — tag counts, patterns, uncertainty, tasks, confidence
  ├─▶ _generate_reflection(analysis) — rule-based (LLM swap point)
  ├─▶ store_reflection()   → memory/reflections/{id}.json + vault/reflections/{id}.md
  └─▶ create_tasks_from_reflection() → memory/tasks/{id}.json + vault/tasks/{id}.md

select_next_task()
  │
  ├─▶ Scores pending tasks: priority×0.5 + confidence×0.3
  ├─▶ Updates winning task status to "selected"
  └─▶ store() decision     → memory/decisions/{id}.json + vault/decisions/{id}.md

simulate_action(task)
  │
  ├─▶ _propose_action()     — rule-based (LLM swap point)
  ├─▶ _expected_outcome()   — rule-based (LLM swap point)
  ├─▶ _estimate_risks()     — heuristic signals
  ├─▶ store() simulation    → memory/simulations/{id}.json + vault/simulations/{id}.md
  └─▶ Updates task status to "simulated"
```

---

## LLM Swap Points

Three functions are designated as clean LLM replacement targets.  
Their signatures, callers, and storage paths do not change — only the function body is replaced.

### 1. `reflect.py:_generate_reflection(analysis: Dict) → str`

Replace the function body with an LLM call:

```python
import anthropic
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    messages=[{"role": "user", "content": _build_prompt(analysis)}],
)
return response.content[0].text
```

### 2. `simulate.py:_propose_action(description: str) → str`

Replace the heuristic with an LLM call that reasons about what action to take.

### 3. `simulate.py:_expected_outcome(title: str, description: str) → str`

Replace the template string with an LLM call that predicts realistic outcomes.

---

## File Layout

```
Open-Claw/
  src/open_claw/          Python package
    config.py             Paths and tunable parameters
    memory_store.py       Read/write all memory layers (JSON + Markdown)
    ingest.py             Raw → episodic → semantic promotion logic
    reflect.py            Reflection engine — Layer 2
    tasks.py              Task storage — Layer 3
    decision.py           Decision engine — Layer 3
    simulate.py           Action simulation — Layer 3 (no execution)
    linker.py             Automatic wikilink generation
    search.py             Keyword search (vector-ready interface)
    time_utils.py         UTC storage / local display helpers
    exceptions.py         CoreMemoryProtectedError
  scripts/                CLI entry points
  tests/                  pytest suite
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
| Autonomous operation | Every significant action requires script invocation or human approval |

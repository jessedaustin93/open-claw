# Recursive Learning Loop

## Concept

Open-Claw implements a three-phase loop that mirrors how biological memory consolidation works:

```
 ┌──────────────────────────────────────────────────┐
 │                                                  │
 │   INPUT ──► RAW ──► EPISODIC ──► SEMANTIC        │
 │                                        │         │
 │                    REFLECTION ◄────────┘         │
 │                        │                         │
 │                        └──► TASKS / CORE         │
 │                                  │               │
 │                                  └──► (next INPUT)
 └──────────────────────────────────────────────────┘
```

Each cycle through the loop increases the depth and quality of stored knowledge without losing the originals.

---

## Phase 1: Ingestion

**Trigger:** A call to `ingest(text)` or the `scripts/ingest_text.py` script.

**What happens:**

1. Text is received and stored verbatim as a **raw memory**.
2. An importance score is computed from keyword heuristics.
3. Tags are extracted from the content.
4. If importance >= threshold (default 0.5):
   - An **episodic memory** is created with a one-line summary.
   - If semantic keywords are detected:
     - A **semantic memory** is created with a named concept and description.
5. All memories are written to both `memory/` (JSON) and `vault/` (Markdown) simultaneously.

**Design note:** Raw storage is unconditional. Even low-importance inputs are preserved because their significance may not be apparent until a future reflection pass.

---

## Phase 2: Reflection

**Trigger:** A call to `reflect()` or the `scripts/run_reflection.py` script.

**What happens:**

1. All episodic and semantic memories are loaded (reflections excluded by default).
2. Safety limits are applied: source cap, duplicate guard, low-value guard.
3. Structured analysis is computed via `_analyse()`:
   - Tag frequencies reveal dominant themes and repeated patterns.
   - Uncertainty signals are detected across source text.
   - Task phrases are extracted and listed as suggested actions.
   - Core memory candidates are identified (suggestions only — never written automatically).
   - A confidence score [0.0–1.0] is computed from source count, tag diversity, and uncertainty.
4. A reflection note is generated with 7 required sections:
   - **What Was Learned** — high-importance memories with readable wikilinks
   - **Important Memories Reviewed** — all source memories with importance scores
   - **New Patterns Noticed** — repeated tags and recurring themes
   - **Conflicts or Uncertainty** — uncertainty signals found in source text
   - **Suggested Tasks** — task phrases extracted from memories
   - **Suggested Core Memory Updates** — human-review-required suggestions only
   - **Reflection Quality** — confidence score and analysis notes
5. The reflection note and its metadata are stored in `memory/reflections/` and `vault/reflections/`.

**Duplicate guard:** If `config.skip_duplicate_reflections = True` (default), a pass whose source IDs exactly match a prior reflection is skipped — no redundant notes accumulate.

**Low-value guard:** If the source count falls below `config.min_reflection_sources` (default: 1), the pass is skipped unless `config.allow_low_value_reflections = True`.

**Reflection JSON metadata fields** (Layer 2, stored alongside core fields):

| Field | Type | Description |
|---|---|---|
| `confidence` | float [0, 1] | Computed from source count, tag diversity, uncertainty |
| `source_types` | dict | `{"episodic": N, "semantic": M}` |
| `suggested_tasks` | list[str] | Extracted task phrases from source memories |
| `suggested_core_updates` | list[str] | Core memory candidates (suggestions only) |
| `detected_patterns` | list[str] | Repeated tags and high-importance clusters |
| `uncertainty_notes` | list[str] | Memories containing uncertainty-signal words |
| `generated_at` | ISO timestamp | When the analysis was computed |

**LLM swap point:** `reflect.py:_generate_reflection(analysis: Dict) -> str` receives the full structured analysis dict and returns Markdown.  
Replace the function body with an LLM call — the caller, the storage path, and the analysis structure do not change.

---

## Phase 3: Integration

**Trigger:** Human review of reflection notes, or an agent reading `vault/reflections/`.

**What happens:**

1. A human (or agent) reads the reflection note.
2. Key insights are manually promoted to `vault/core/` as long-term core memory.
3. Implied tasks are added to `vault/tasks/`.
4. These core memories and tasks become context for the next round of ingestion.

This is the recursive element: reflections feed back into future inputs, creating a continuously improving memory store.

---

## Reflection Interval

The `Config.reflection_interval` field (default: 10) is a placeholder for future automation.  
A future version could automatically trigger a reflection pass every N ingestions, or on a schedule.  
For now, reflections are triggered manually.

---

## Future Phases

The loop is designed to support additional phases:

| Future Phase | Description |
|---|---|
| **Forgetting** | Archive low-importance memories that haven't been linked in N days |
| **Consolidation** | Merge duplicate semantic memories into a single stronger concept |
| **Dreaming** | Offline reflection pass that cross-links memories without new input |
| **Agent Memory** | Per-agent episodic stores that feed into a shared semantic layer |
| **Distillation** | Generate a compressed "worldview" summary for LLM system prompt injection |

---

## Example Cycle

```
Day 1:
  ingest("I learned that recursive functions need a base case. This is a key concept.")
  → raw/a1b2c3d4.json   (verbatim)
  → episodic/e5f6a7b8.json  (summary: "I learned that recursive functions need a base case")
  → semantic/c9d0e1f2.json  (concept: "Recursive Function", description: "needs a base case")

Day 2:
  ingest("Important project milestone: all unit tests passing.")
  → raw/b2c3d4e5.json
  → episodic/f6a7b8c9.json

After Day 2:
  reflect()
  → reflections/r7b8c9d0.json
  Reflection identifies: "learning" and "project" are top tags.
  Implies task: "Review test coverage and document passing criteria."

Human reads reflection:
  → Adds note to vault/core/project_rules.md
  → Adds note to vault/tasks/review_test_coverage.md
```

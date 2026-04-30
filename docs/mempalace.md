# MemPalace-Style Memory in Aeon-V1

Aeon-V1's memory architecture is inspired by the **Memory Palace** (Method of Loci)
mnemonic technique and append-only log design patterns.

> **MemPalace is not a software dependency.** Aeon-V1 does not import, vendor,
> or require any library called "MemPalace". The term describes a design philosophy
> implemented entirely within Aeon-V1's own code.

---

## The Core Principle

In a classical memory palace, each piece of knowledge has a **specific, fixed location**.
You never erase a location — you add new rooms or update your mental map of what is there.

Aeon-V1 applies this to structured file storage:

| MemPalace idea | Aeon-V1 implementation |
|---|---|
| Each memory has a fixed place | Each record has a permanent `id` used as the filename |
| You never erase a memory location | Raw records are **immutable** — never overwritten or deleted |
| Derived associations build on originals | Episodic and semantic records **link back** to the raw via `raw_ref` |
| New insights add new rooms, not new walls | New reflections, tasks, and decisions are **new files**, never edits |
| The palace grows by accumulation | The `memory/` and `vault/` directories grow monotonically |

---

## Append-Only Guarantee

### Raw memories

Every `ingest()` call writes exactly one raw memory and never modifies it afterward.

```python
raw = store.store_raw(text, source=source)
# raw is now immutable — no function in Aeon-V1 overwrites it
```

The `_guard_core_path()` function in `memory_store.py` enforces the same protection
for `vault/core/`, raising `CoreMemoryProtectedError` on any write attempt.

### Derived memories

Episodic and semantic records are derived from raws, not replacements for them.
Each derived record carries a `raw_ref` field pointing to the original:

```json
{
  "id": "b8330e88",
  "type": "episodic",
  "raw_ref": "aa97bff7",
  "summary": "...",
  "importance": 0.80
}
```

### Decision and simulation records

Decision records are explicitly append-only: `select_next_task()` always writes a new
`{id}.json` file and never modifies a prior decision. Simulation records follow the
same pattern.

---

## Traceability

Every piece of derived knowledge traces back to its raw source:

```
vault/simulations/sim123.md
  └─▶ [[tasks/task456|...]]
        └─▶ [[reflections/ref789|...]]
              └─▶ source_ids: [ep001, ep002, sem003]
                    └─▶ raw_ref: [raw_aaa, raw_bbb, raw_ccc]
```

From any simulation, you can walk the wikilinks back to the exact text that caused it.

---

## Why This Matters for LLM Integration

When an LLM replaces the rule-based renderers (see `reflect.py:_generate_reflection`
and `simulate.py:_propose_action`), the MemPalace structure means:

1. The LLM's reasoning is stored in a new file — it doesn't overwrite anything
2. The raw inputs the LLM reasoned over are still accessible via `source_ids`
3. If the LLM output is wrong or biased, a human can trace exactly what it was given
4. Re-running reflection with a better LLM or prompt creates an additional record,
   not a replacement — both versions are preserved

This makes the system auditable and correctable by design.

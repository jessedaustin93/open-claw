---
title: Open-Claw Memory Vault
type: index
created: 2026-04-29T00:00:00+00:00
---

# Open-Claw Memory Vault

Welcome to the Open-Claw knowledge graph.

**To explore the graph view, backlinks, and tag search: open this `vault/` folder in Obsidian.**  
Obsidian is optional — all files are plain Markdown readable in any editor.

---

## Memory Layers

| Layer | Link | Purpose |
|---|---|---|
| Raw | [[Raw Memory]] | Verbatim captures — never modified after ingestion |
| Episodic | [[Episodic Memory]] | Summarized meaningful events derived from raw |
| Semantic | [[Semantic Memory]] | Reusable concepts, rules, and patterns |
| Reflections | [[Reflections]] | Recursive analysis of episodic and semantic memory |
| Tasks | [[Tasks]] | Structured task objects derived from reflection |
| Decisions | [[Decisions]] | Append-only decision records from the selection engine |
| Simulations | [[Simulations]] | Proposed-action records — never executed automatically |
| Core | [[Core Memory]] | Stable identity, goals, and rules — human-gated |

---

## How to Navigate

- **Graph view** (`Ctrl+G` in Obsidian) — see how all notes connect
- **Tag search** — filter memories by topic tag
- **Backlinks** — trace any insight back to its raw source
- **Wikilinks** — every derived memory links to the raw it came from

---

## Memory Flow

```
Raw (verbatim, immutable)
  └─▶ Episodic (summarized event, if importance ≥ threshold)
        └─▶ Semantic (reusable concept, if semantic keyword detected)

Episodic + Semantic
  └─▶ Reflection (recursive analysis, structured 7-section note)
        └─▶ Tasks (suggested actions converted to task objects)
              └─▶ Decision (best task selected by scoring engine)
                    └─▶ Simulation (proposed-action record, human review required)

Core Memory (human-gated — never written automatically)
```

---

## Example Notes

- [[example_raw]] — an example raw memory input
- [[example_episodic]] — the episodic note derived from the example raw
- [[example_semantic]] — the semantic concept extracted from the example
- [[example_reflection]] — the reflection note produced after analysis

---

[[Core Memory]] | [[Reflections]] | [[Tasks]] | [[Decisions]] | [[Simulations]]

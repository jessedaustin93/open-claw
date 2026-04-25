# Open-Claw Memory Model

## Design Principles

1. **Raw memory is sacred.** Once written, a raw record is never modified, summarized over, or deleted.
2. **Promotion is additive.** Creating an episodic or semantic note never removes its source.
3. **Every layer is human-readable.** All memory exists as plain Markdown alongside the JSON.
4. **Links are explicit.** Related notes are connected with wikilinks so the knowledge graph is inspectable.

---

## Memory Types

### Raw Memory

The exact, verbatim capture of an input.

- **Created by:** `ingest()`
- **Stored at:** `memory/raw/{id}.json`, `vault/raw/{id}.md`
- **Schema:** `memory/schemas/raw_memory.schema.json`
- **Key field:** `text` — this field is immutable after creation
- **Importance scoring:** Heuristic — based on presence of keywords like "important", "project", "goal"

Raw memories are analogous to sensory memory in cognitive models: everything is stored before anything is evaluated.

### Episodic Memory

A summarized, meaningful event derived from one or more raw memories.

- **Created by:** `ingest()` when importance >= threshold
- **Stored at:** `memory/episodic/{id}.json`, `vault/episodic/{id}.md`
- **Schema:** `memory/schemas/episodic_memory.schema.json`
- **Key fields:** `summary`, `raw_ref` (link back to source raw memory)

Episodic memories answer the question: *"What happened?"*  
They are compact but always traceable to their raw source.

### Semantic Memory

A reusable concept, rule, pattern, or lesson that transcends a single event.

- **Created by:** `ingest()` when episodic promotion occurs AND semantic keywords are detected
- **Stored at:** `memory/semantic/{id}.json`, `vault/semantic/{id}.md`
- **Schema:** `memory/schemas/semantic_memory.schema.json`
- **Key fields:** `concept`, `description`

Semantic memories answer the question: *"What does this mean in general?"*  
Examples: "Recursive functions need a base case", "The project deadline is Q2".

### Core Memory

Long-term stable identity, rules, and goals. Manually curated.

- **Stored at:** `vault/core/` (Markdown only — no JSON schema)
- **Written by:** Humans, or by an agent acting on reflection outputs
- **Example files:** `identity.md`, `rules.md`, `goals.md`, `preferences.md`

Core memory is not automatically generated. It represents durable, trusted knowledge.

### Reflections

Recursive analysis of what has been stored.

- **Created by:** `reflect()`
- **Stored at:** `memory/reflections/{id}.json`, `vault/reflections/{id}.md`
- **Schema:** `memory/schemas/reflection.schema.json`
- **Key fields:** `content` (Markdown analysis), `source_ids` (which memories were analyzed)

Reflections answer: *"What patterns emerged? What should be remembered long-term? What is implied?"*

### Tasks

Implied future actions derived from reflections or direct input.

- **Stored at:** `vault/tasks/` (Markdown notes)
- **Created by:** Humans, or by an agent acting on reflection outputs

### Agents

Per-agent configuration and observation notes.

- **Stored at:** `vault/agents/` (Markdown notes)

---

## Frontmatter Schema

Every vault note includes YAML frontmatter with these standard fields:

```yaml
---
id: a1b2c3d4          # 8-char unique identifier
type: raw             # raw | episodic | semantic | reflection
created: 2024-01-15T10:30:00  # ISO 8601 UTC
source: manual        # origin label
importance: 0.75      # float [0, 1]
tags:
  - learning
  - project
links:
  - "[[raw/9e8f7a6b]]"
---
```

---

## Importance Scoring

The current heuristic adds +0.15 for each of these keywords found in the text:

```
"i learned", "important", "remember", "project", "goal",
"discovered", "realized", "key insight", "critical", "must not forget"
```

Base score is 0.3. Maximum is 1.0.  
The default promotion threshold is **0.5** (configurable in `Config`).

Replace with a trained classifier or LLM confidence score when ready.

---

## Tag Extraction

Tags are extracted by keyword-to-tag mapping:

| Keyword in text | Tag applied |
|---|---|
| project | project |
| goal | goal |
| learned | learning |
| important | important |
| remember | recall |
| error | error |
| bug | bug |
| idea | idea |
| question | question |
| task | task |
| experiment | experiment |
| concept | concept |
| pattern | pattern |
| rule | rule |

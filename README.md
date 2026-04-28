# Open-Claw

Local-first AI memory and learning framework. Simulates persistent cognition using structured memory layers, reflection, and a future decision/action loop.

**This is NOT a chatbot.** It is a memory + cognition backbone for an evolving agent.

---

## Memory Architecture

```
raw → episodic → semantic → reflection → (future: core, tasks, decisions)
```

Storage:
- `memory/` — JSON files (agent-readable, append-only)
- `vault/` — Markdown files (human-readable, Obsidian-compatible)

---

## Install

```bash
git clone https://github.com/jessedaustin93/Open-claw.git
cd Open-claw
pip install -e .
pip install -r requirements.txt
```

---

## Usage

### Ingest a memory
```bash
python -m open_claw.cli ingest "We should build a caching layer for episodic memory" --tags learning architecture
```

### Run reflection
```bash
python -m open_claw.cli reflect
```

### Run linking pass
```bash
python -m open_claw.cli link
```

### Search memories
```bash
python -m open_claw.cli search "caching"
```

---

## Run Tests

```bash
pytest -v
```

---

## Layer Status

| Layer | Status | Description |
|-------|--------|-------------|
| Layer 1 | ✅ Complete | Raw memory, append-only storage, importance scoring, linking, core protection |
| Layer 2 | ✅ Complete | Structured reflection, metadata, duplicate detection, confidence, task extraction |
| Layer 3 | 🔲 Planned | Decision loop, task execution, agent actions |

---

## Core Memory Protection

`vault/core/` is **hard-protected**. No ingestion, reflection, or linking operation
can write to it. Violations raise `CoreMemoryProtectedError`. This is enforced in
code — not just documentation.

Core memory updates are **human-only**. The reflection engine may suggest updates
but never writes them.

---

## LLM Integration

`Reflector._generate_reflection()` is the **only LLM swap point**.
Currently rule-based. Replace the method body with an LLM call when ready.
Signature and return type must remain the same.

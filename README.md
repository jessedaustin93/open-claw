# Aeon-V1

Aeon-V1 is a **local-first recursive AI memory and learning system** built on plain JSON and Markdown files.

It stores raw inputs, promotes important memories into episodic and semantic layers, reflects on what it has learned, turns reflections into tasks, simulates possible actions, and gates agent-initiated writes through a human approval pipeline. The system is designed to stay inspectable: every durable record lives in `memory/` for machines and, where useful, in `vault/` for humans and Obsidian.

Aeon-V1 is not an autonomous executor. It is a governed memory and reasoning substrate.

---

## Current Capabilities

| Area | Status | Main modules |
|---|---|---|
| Raw memory ingestion | Implemented | `ingest.py`, `memory_store.py` |
| Episodic and semantic promotion | Implemented | `ingest.py`, `memory_store.py` |
| Recursive reflection | Implemented | `reflect.py` |
| Task creation from reflections | Implemented | `tasks.py` |
| Decision selection | Implemented | `decision.py` |
| Action simulation | Implemented, simulation-only | `simulate.py` |
| Tool definitions and tool-call records | Implemented | `tools.py`, `builtin_tools.py`, `tool_calls.py` |
| Simulation evaluation | Implemented | `evaluate.py` |
| Agent nodes and orchestrator | Implemented | `agent.py`, `orchestrator.py` |
| Layer 7 write governance | Implemented and locked | `schemas.py`, `security.py`, `approval_agent.py`, `write_agent.py` |
| Manifest drift monitoring | Implemented | `manifest_agent.py` |
| Optional LLM reasoning | Implemented | `llm.py`, `memory_index_agent.py` |
| ESP32-S3 hardware approval token | Added on hardware auth branch | `hardware_auth_provider.py`, `firmware/esp32s3-auth-device/` |
| Vector embeddings | Planned | `search.py` is vector-ready |
| Real command execution | Out of scope | No execution path exists |

---

## Quick Start

### Install

```bash
git clone https://github.com/jessedaustin93/aeon-v1
cd aeon-v1
pip install -e ".[dev]"
```

Optional extras:

```bash
pip install anthropic       # Optional Claude/Anthropic LLM support
pip install -e ".[hardware]" # Optional ESP32-S3 USB approval provider
```

### Run Tests

```bash
pytest
```

### Ingest Memory

```bash
python scripts/ingest_text.py "I learned that layered memory systems are more robust than flat logs."
python scripts/ingest_text.py --file my_notes.txt --source journal
echo "Important project goal: ship Aeon-V1 v1." | python scripts/ingest_text.py
```

### Reflect, Decide, Simulate

```bash
python scripts/run_reflection.py
python scripts/manage_tasks.py tasks
python scripts/manage_tasks.py decide
python scripts/manage_tasks.py simulate
python scripts/manage_tasks.py loop
```

### Search And Link

```bash
python scripts/search_memory.py "recursive learning"
python scripts/search_memory.py "goal" --types episodic semantic
```

```python
from aeon_v1 import Config, link_memories

link_memories(config=Config())
```

---

## Core Design

Aeon-V1 keeps two synchronized views of memory:

| Store | Purpose |
|---|---|
| `memory/` | Machine-readable JSON records, schemas, logs, staging, approvals |
| `vault/` | Human-readable Markdown notes for Obsidian or any text editor |

Raw memory is preserved because summaries lose information. Episodic and semantic memories are derived views, not replacements. Reflections and decisions are append-only records, so the system can be audited later.

Everything is local by default. No database is required. No cloud service is required. LLM calls are optional.

---

## Memory Layers

| Layer | Directories | Purpose |
|---|---|---|
| Raw | `memory/raw/`, `vault/raw/` | Exact verbatim captures |
| Episodic | `memory/episodic/`, `vault/episodic/` | Event-like summaries of important inputs |
| Semantic | `memory/semantic/`, `vault/semantic/` | Concepts, reusable rules, and patterns |
| Core | `vault/core/` | Stable identity, long-term rules, goals; human-gated |
| Reflections | `memory/reflections/`, `vault/reflections/` | Recursive analysis of episodic and semantic memory |
| Tasks | `memory/tasks/`, `vault/tasks/` | Suggested actions derived from reflections |
| Decisions | `memory/decisions/`, `vault/decisions/` | Append-only task selection records |
| Simulations | `memory/simulations/`, `vault/simulations/` | Proposed actions and risk analysis; no execution |
| Tool calls | `memory/tool_calls/`, `vault/tool_calls/` | Structured pending tool-call records from simulations |
| Agents | `memory/agents/`, `vault/agents/` | Agent node lifecycle records and tool definitions |
| Governance | `memory/staging/`, `memory/approved/`, `memory/logs/` | Layer 7 proposal, approval, commit, and audit trail |
| Tool additions | `memory/tool_additions/` | Approved tool additions proposed through Layer 7 |
| Orchestrator | `memory/orchestrator/` | Live agent-pool manifest |

---

## Recursive Loop

```text
Input text
  -> raw memory
  -> episodic memory, if importance >= threshold
  -> semantic memory, if concept signals are present
  -> reflection over episodic + semantic memory
  -> suggested tasks
  -> decision record
  -> simulation record
  -> human review / governed write
  -> new input
```

`reflect()` produces a seven-section reflection note:

1. What Was Learned
2. Important Memories Reviewed
3. New Patterns Noticed
4. Conflicts or Uncertainty
5. Suggested Tasks
6. Suggested Core Memory Updates
7. Reflection Quality

Reflections do not write to `vault/core/`. Core updates are suggestions only.

---

## Layer 3: Tasks, Decisions, Simulations

Every reflection can create task objects from `suggested_tasks`. Near-duplicates are blocked with Jaccard word-overlap, and pending task count is capped by config.

`select_next_task()` scores pending tasks by:

```text
priority * 0.5 + confidence * 0.3
```

`simulate_action(task)` creates a local simulation record with:

- Proposed action
- Expected outcome
- Risk signals
- Required human approval flag
- Optional matched tool call
- LLM metadata if LLM enhancement was used

Simulation remains file-only. `simulate.py` does not import or call subprocess, shell, network, `exec`, or `eval` primitives.

---

## Layer 4: Optional LLM Reasoning

Aeon-V1 runs without an LLM. If enabled, LLM output enhances reflection and simulation narrative while the file-based system remains the source of truth.

Enable Anthropic/Claude mode:

```bash
export AEON_V1_LLM=1
export ANTHROPIC_API_KEY=your_key_here
```

PowerShell:

```powershell
$env:AEON_V1_LLM="1"
$env:ANTHROPIC_API_KEY="your_key_here"
```

Useful environment variables:

| Variable | Purpose |
|---|---|
| `AEON_V1_LLM` | Set to `1` to enable LLM calls |
| `AEON_V1_LLM_PROVIDER` | Provider name; defaults to `anthropic` |
| `AEON_V1_LLM_MODEL` | Model name; defaults from `Config` |
| `AEON_V1_LLM_MAX_TOKENS` | Max response tokens |
| `AEON_V1_LLM_TIMEOUT` | Request timeout seconds |
| `AEON_V1_LLM_BASE_URL` | Local/OpenAI-compatible server URL |
| `AEON_V1_LLM_TOOL_CALLING` | Set to `1` to let the LLM query memory through `MemoryIndexAgent` |

When tool-calling is enabled, `MemoryIndexAgent` services `query_memory` tool calls by searching local memory and returning bounded, formatted results. This keeps prompts sparse while still letting the model inspect relevant memory.

LLM fallback is fail-safe: missing package, missing key, API failure, or disabled config all return to rule-based behavior.

---

## Layer 5: Tools And Tool Calls

Aeon-V1 has a definition-only tool registry:

- `ToolDefinition` describes a tool name, description, JSON-schema-like parameters, tags, layer, enabled flag, and approval requirement.
- `ToolRegistry` persists tool definitions to `memory/schemas/tools/` and `vault/agents/`.
- `builtin_tools.py` defines `file_read`, `file_write`, and `command_preview` as built-in tool slots.

No registered tool is executed by the registry.

During simulation, `_match_tool_call()` can map a task description to a registered tool and create a `pending_review` tool-call record through `ToolCallStore`. These records are auditable proposals, not executions.

---

## Layer 6: Agent Nodes And Orchestrator

`AgentNode` is a single-purpose lifecycle-managed unit:

```text
spawn() -> run() -> dissolve()
```

Supported roles:

| Role | Purpose |
|---|---|
| `thinker` | Runs reflection |
| `executor` | Selects or receives a task, then simulates it |
| `monitor` | Watches memory growth and can trigger reflection |
| `evaluator` | Evaluates simulations against observed results |
| `custom` | Caller-defined role with a required description |

`Orchestrator.tick()` coordinates one synchronous work cycle:

1. Ensures and runs a monitor agent.
2. Fills the thinker pool up to `Config.max_thinking_agents`.
3. Runs thinkers.
4. Spawns an executor for one pending task.
5. Spawns an evaluator for one unreviewed simulation.
6. Dissolves task-specific agents and persists the pool manifest.

Layer 6 still does not execute system commands. It coordinates memory, reflection, simulation, and evaluation only.

---

## Layer 7: Governed Writes

Layer 7 enforces a proposal-to-commit pipeline for agent-initiated memory writes:

```text
create_proposal()
  -> memory/staging/{trace_id}.json
  -> ValidationAgent.validate_proposal()
  -> ApprovalAgent.approve_proposal()
  -> WriteAgent.commit_proposal()
  -> memory/approved/{trace_id}.json + memory/logs/audit.jsonl
```

Key modules:

| Module | Responsibility |
|---|---|
| `schemas.py` | Pure schema factories and validators |
| `security.py` | `PathGuard`, `AuditLog`, `ValidationAgent` |
| `approval_agent.py` | `AuthProvider`, `CLIAuthProvider`, `ApprovalAgent` |
| `write_agent.py` | `create_proposal()`, `WriteAgent`, approved commit handling |

Safety rules:

- No auto-approval path exists.
- `WriteAgent` commits only proposals with status `approved_for_commit`.
- All Layer 7 actions append to `memory/logs/audit.jsonl`.
- Path traversal is blocked by `PathGuard`.
- Suspicious content is flagged for human review, not silently accepted.
- `vault/core/` is not written by Layer 7.
- Layer 7 stable modules are marked: `LAYER 7 STABLE - DO NOT MODIFY WITHOUT EXPLICIT INSTRUCTION`.

`AuthProvider` is the plug-in point for approval mechanisms. The default is CLI yes/no approval; the ESP32-S3 provider is available on the hardware auth branch.

---

## ESP32-S3 Hardware Approval Device

This branch adds a dedicated one-button USB approval token for Layer 7.

Files:

| Path | Purpose |
|---|---|
| `src/aeon_v1/hardware_auth_provider.py` | PC-side `ESP32S3AuthProvider(AuthProvider)` |
| `firmware/esp32s3-auth-device/` | PlatformIO firmware for ESP32-S3 native USB CDC |
| `docs/auth_device.md` | Integration guide and protocol notes |

Install the optional serial dependency:

```bash
pip install -e ".[hardware]"
```

Use it with `ApprovalAgent`:

```python
from aeon_v1 import ApprovalAgent, Config, ESP32S3AuthProvider

agent = ApprovalAgent(
    Config(),
    auth_provider=ESP32S3AuthProvider(port="COM5"),  # omit port for auto-discovery
)
agent.process_queue()
```

Flash the firmware:

```bash
cd firmware/esp32s3-auth-device
pio run -t upload
pio device monitor
```

Hardware defaults:

- `GPIO0` button to `GND`, using internal pull-up; many boards use the built-in BOOT button.
- `GPIO48` optional status LED.
- Native USB CDC serial at `115200`.

Protocol shape:

```json
{"type":"approval_request","id":"proposal-trace-id","summary":"semantic memory write","expires_ms":30000}
```

```json
{"type":"approval","id":"proposal-trace-id","approved":true,"method":"button_hold","held_ms":1007}
```

The firmware ignores button presses unless a request is armed, binds approval to the exact proposal id, requires a one-second hold, and expires requests automatically.

---

## Manifest Agent

`ManifestAgent` keeps `docs/tools_manifest.md` honest.

It can:

- Parse manifest tool headings.
- Scan Python imports and dependency declarations.
- Report drift between documented tools and code dependencies.
- Propose tool additions through the full Layer 7 pipeline.
- Store approved tool additions in `memory/tool_additions/`.

The agent can propose changes, but cannot commit them directly. Governed additions still require validation, approval, and `WriteAgent` commit.

---

## Obsidian Vault

Open `vault/` as an Obsidian vault for graph view, backlinks, and human-readable memory inspection.

Every Markdown note uses frontmatter and stable wikilinks. IDs are stable; titles are human-readable. Filenames use IDs, and links use `[[subdir/id|title]]` so notes remain readable and resolvable.

Obsidian is optional. The vault is plain Markdown.

---

## Project Structure

```text
aeon-v1/
  src/aeon_v1/
    agent.py                  Layer 6 agent node lifecycle
    approval_agent.py         Layer 7 human approval gate
    builtin_tools.py          Built-in tool definitions
    config.py                 Paths, limits, LLM/env configuration
    decision.py               Task selection engine
    evaluate.py               Simulation evaluation
    hardware_auth_provider.py ESP32-S3 AuthProvider implementation
    ingest.py                 Raw -> episodic -> semantic promotion
    linker.py                 Obsidian wikilink generation
    llm.py                    Optional LLM adapter and tool-calling loop
    manifest_agent.py         Tools manifest drift and governed additions
    memory_index_agent.py     query_memory handler for LLM tool calls
    memory_store.py           JSON + Markdown memory storage
    orchestrator.py           Agent pool coordination
    reflect.py                Reflection engine
    schemas.py                Layer 7 schemas and validators
    search.py                 Keyword search, vector-ready interface
    security.py               PathGuard, AuditLog, ValidationAgent
    simulate.py               Action simulation and tool-call matching
    tasks.py                  Task storage and deduplication
    time_utils.py             UTC storage and local display helpers
    tool_calls.py             Tool-call record storage
    tools.py                  Tool registry
    write_agent.py            Governed write commit stage
  scripts/
    ingest_text.py
    manage_tasks.py
    run_reflection.py
    search_memory.py
  firmware/
    esp32s3-auth-device/
  docs/
  memory/
  vault/
  tests/
```

---

## Safety Guarantees

Aeon-V1 is intentionally conservative:

- Raw memories are append-only.
- Reflections do not write core memory.
- Simulations do not execute actions.
- Tool definitions do not call tools.
- Tool-call records are pending review records.
- Agent nodes do not call shell, subprocess, network, `exec`, or `eval` primitives.
- Layer 7 requires validation and human approval before agent-initiated writes commit.
- The hardware auth device is only a physical approval signal; it cannot commit memory by itself.

Humans remain in the loop at the points where state changes matter.

---

## More Documentation

- `docs/architecture.md` - system layout and data flow
- `docs/memory_model.md` - memory layer specification
- `docs/recursive_learning_loop.md` - ingestion, reflection, task, and simulation cycle
- `docs/INTEGRATION_STATUS.md` - implementation status and planned integrations
- `docs/tools_manifest.md` - tools, dependencies, hardware, and planned additions
- `docs/auth_device.md` - ESP32-S3 approval-token details

# Aeon-V1 — Tools & Requirements Reference

**Purpose:** Human reference only. This file is never imported or executed by the system.
**Rule:** Do not delete entries. Future updates append or modify; note the reason inline.

---

## How to Read This Document

Each entry lists:
- **Purpose** — what it does *inside this system specifically*
- **Importance** — `Required` · `Optional` · `Experimental` · `Planned`
- **Link** — official download or best source
- **Notes** — why this choice matters for Aeon-V1

---

## 1. Core System Tools

### Python 3.10+
- **Purpose:** Runtime for all Aeon-V1 modules (ingest, reflect, simulate, orchestrator, Layer 7 security)
- **Importance:** Required
- **Link:** https://www.python.org/downloads/
- **Notes:** 3.10 minimum for `match` statements and `zoneinfo` stdlib. 3.11+ preferred for faster startup and better error messages. Must NOT be 2.x.

---

### pip / pip-tools
- **Purpose:** Installing Python dependencies and managing requirements.txt
- **Importance:** Required
- **Link:** https://pip.pypa.io/en/stable/
- **Notes:** Ships with Python. Use `pip install -e .[dev]` from repo root to install in editable mode with test dependencies.

---

### Git 2.x
- **Purpose:** Version control for all source code, docs, and vault structure
- **Importance:** Required
- **Link:** https://git-scm.com/downloads
- **Notes:** Required to track memory architecture changes. The append-only memory philosophy is mirrored in commit history — do not force-push main.

---

### zoneinfo (stdlib) + tzdata
- **Purpose:** Local timezone display for Markdown notes and CLI output (UTC stored in JSON, local displayed to human)
- **Importance:** Required
- **Link:** https://pypi.org/project/tzdata/
- **Notes:** `zoneinfo` is stdlib from Python 3.9+. `tzdata` (PyPI) is required on Windows where the OS timezone database may be absent. Listed in requirements.txt.

---

### pytest 7.4+
- **Purpose:** Running the full test suite
- **Importance:** Required (development)
- **Link:** https://docs.pytest.org/
- **Notes:** Only needed for development/CI — not a runtime dependency. Run `pytest tests/` from repo root.

---

## 2. LLM / AI Tools

### Anthropic Python SDK (`anthropic`)
- **Purpose:** Optional LLM enhancement for reflection narrative (sections 1/3/4/5) and simulation planning. All sections fall back to rule-based output if unavailable.
- **Importance:** Optional
- **Link:** https://pypi.org/project/anthropic/
- **Notes:** Soft dependency — the system runs fully without it. Install with `pip install anthropic`. Enable via `AEON_V1_LLM=1` environment variable + `ANTHROPIC_API_KEY`.

---

### Anthropic API Key
- **Purpose:** Authentication for Claude API calls when LLM mode is enabled
- **Importance:** Optional (required only if LLM mode is on)
- **Link:** https://console.anthropic.com/
- **Notes:** Set as `ANTHROPIC_API_KEY` environment variable. Never commit to source control. The system fails safe and falls back to rule-based mode if the key is missing or the API is unreachable.

---

### Claude Models (claude-3-5-sonnet-latest default)
- **Purpose:** Generates narrative reflection sections and simulation planning text when LLM mode is enabled
- **Importance:** Optional
- **Link:** https://docs.anthropic.com/en/docs/models-overview
- **Notes:** Model is configurable via `config.llm_model`. Default is `claude-3-5-sonnet-latest`. Upgrade to Opus-class models for higher reasoning quality at higher cost. Rule-based fallback always active.

---

### LM Studio
- **Purpose:** Local OpenAI-compatible LLM server for chat, reflection, simulation, and tool-calling memory queries
- **Importance:** Optional
- **Link:** https://lmstudio.ai/
- **Notes:** Implemented through the `lmstudio` provider in `llm.py`. Configure with `AEON_V1_LLM_PROVIDER=lmstudio` and model-role variables (`AEON_V1_LLM_CHAT_MODEL`, `AEON_V1_LLM_MODEL`, `AEON_V1_LLM_DEEP_MODEL`). Start from `.env.lmstudio.template`. Aeon caps outbound LM Studio concurrency at 10 in-flight requests and falls back safely when the local server or model is unavailable.

---

### Future Local LLM Providers (Ollama / llama.cpp)
- **Purpose:** Additional local inference options without an API key or internet connection
- **Importance:** Planned
- **Link:** https://ollama.com/
- **Notes:** LM Studio is the current implemented local provider. Additional providers should follow the same fail-safe pattern as `generate_text()` and return `None` on provider errors so rule-based fallback remains active.

---

## 3. Development Tools

### Visual Studio Code
- **Purpose:** Primary IDE for development; works with the Obsidian vault via the filesystem
- **Importance:** Optional
- **Link:** https://code.visualstudio.com/
- **Notes:** Recommended extensions: Python (Microsoft), Pylance, GitLens. Not required — any editor works.

---

### Obsidian
- **Purpose:** Human-readable view of the entire memory vault (`vault/`). All `.md` files are Obsidian-compatible with YAML frontmatter and `[[wikilinks]]`.
- **Importance:** Optional (strongly recommended for operators)
- **Link:** https://obsidian.md/
- **Notes:** Install locally and open only the `vault/` directory as an Obsidian vault. No plugins required. Graph view shows memory connections after generated notes and `link_memories()` populate wikilinks. `vault/.obsidian/` is local app/workspace state and is ignored by Git. Core vault (`vault/core/`) is human-gated; edit manually here, never by the system.

---

### GitHub / GitHub Actions
- **Purpose:** Remote repository hosting and future CI/CD (automated test runs on push)
- **Importance:** Required (for team use) / Optional (solo local)
- **Link:** https://github.com/jessedaustin93/aeon-v1
- **Notes:** CI is not yet configured. Recommended: add a GitHub Actions workflow that runs `pytest tests/ -q` on every push to main. Badge in README is a good next step.

---

### pre-commit
- **Purpose:** Enforce code quality (formatting, linting) before commits land
- **Importance:** Optional
- **Link:** https://pre-commit.com/
- **Notes:** Not yet configured for this repo. When added, recommended hooks: `black`, `ruff`, `check-yaml`, `end-of-file-fixer`.

---

## 4. Hardware Components

### Development Machine (any)
- **Purpose:** Run Aeon-V1 locally — ingestion, reflection, simulation, orchestrator ticks
- **Importance:** Required
- **Link:** N/A
- **Notes:** No GPU required for rule-based mode. If local LLM inference is added (see Ollama above), a machine with 8–16 GB RAM minimum is recommended for 7B-parameter models. ARM (Apple Silicon, Raspberry Pi 5) and x86 both supported.

---

### Dedicated Always-On Device (Raspberry Pi 5 or similar)
- **Purpose:** Run the Orchestrator continuously (`Orchestrator.tick()` on a timer) without keeping a laptop awake
- **Importance:** Planned
- **Link:** https://www.raspberrypi.com/products/raspberry-pi-5/
- **Notes:** Pi 5 (4–8 GB RAM) is ideal for the rule-based stack. Not suitable for local LLM inference — use a mini PC with more RAM for that role. Pairs well with an external SSD for the memory/vault storage.

---

### Dedicated Auth Device (hardware token)
- **Purpose:** Layer 7 human approval gate — physical confirmation required before any agent-proposed memory write is committed
- **Importance:** Planned
- **Link:** https://www.yubico.com/products/ (YubiKey series)
- **Notes:** The `AuthProvider` abstract class in `approval_agent.py` is the plug-in point. Implement `HardwareTokenAuthProvider(AuthProvider)` and pass it to `ApprovalAgent(config, auth_provider=...)`. CLI approval (`CLIAuthProvider`) is the active default. A YubiKey or similar FIDO2 device is the intended production replacement.

---

## 5. Sensors & Experimental Equipment

### USB Microphone / Audio Input
- **Purpose:** Future voice ingestion — spoken observations transcribed and passed to `ingest()`
- **Importance:** Experimental
- **Link:** https://www.amazon.com/s?k=usb+microphone
- **Notes:** Would require adding Whisper (OpenAI) or a local STT model as a pre-processing step before `ingest()`. The memory system itself needs no changes — the interface is always plain text.

---

### Camera / Webcam
- **Purpose:** Future visual ingestion — scene descriptions or OCR output fed to `ingest()`
- **Importance:** Experimental
- **Link:** N/A (any USB webcam)
- **Notes:** Would pair with a vision model (e.g., Claude's vision API or a local CLIP/LLaVA model) to generate a text description before ingestion. No core changes needed.

---

### Environmental Sensors (temperature, light, etc.)
- **Purpose:** Contextual data for episodic memory — timestamped environment snapshots ingested alongside events
- **Importance:** Experimental
- **Link:** https://www.adafruit.com/category/35
- **Notes:** Adafruit sensors (BME280, SGP30, etc.) via I2C on a Pi are a natural fit. A simple polling script that calls `ingest(f"Temp: {t}°C, Humidity: {h}%", source="sensor")` is all that is needed.

---

## 6. Networking / Infrastructure

### Local File System (primary storage)
- **Purpose:** All memory JSON and Markdown vault files are stored on local disk — no network required for core operation
- **Importance:** Required
- **Link:** N/A
- **Notes:** The local-first design is intentional. No database, no cloud service, no internet connection needed for ingestion, reflection, or simulation. LLM calls are the only network-dependent feature, and they are optional.

---

### Network Share / NAS (optional sync)
- **Purpose:** Sync the `memory/` and `vault/` directories across machines or create backups
- **Importance:** Optional
- **Link:** https://www.synology.com/ (or any NAS/rsync target)
- **Notes:** Since all writes are append-only JSON files, rsync or any file-sync tool works cleanly. Avoid syncing `memory/staging/` across machines while the orchestrator is running to prevent race conditions.

---

### Anthropic API (remote)
- **Purpose:** LLM inference when `AEON_V1_LLM=1` is set
- **Importance:** Optional
- **Link:** https://api.anthropic.com/
- **Notes:** The only external network dependency in the current system. The system degrades gracefully (rule-based fallback) if this is unreachable. Monitor usage at https://console.anthropic.com/.

---

### Future: Inter-Agent Message Bus
- **Purpose:** Allow agent nodes to communicate asynchronously across processes or machines (currently they share state via the local filesystem)
- **Importance:** Planned
- **Link:** https://redis.io/ (Redis Streams) or https://www.rabbitmq.com/
- **Notes:** Current orchestrator uses in-process synchronous ticks. For a true multi-process swarm, a lightweight message bus (Redis Streams or ZeroMQ) would replace direct filesystem polling. The shared `memory/` directory acts as the bus for now.

---

## 7. Planned / Future Additions

### Vector Embedding Store (e.g., ChromaDB, FAISS)
- **Purpose:** Replace keyword search in `search.py` with semantic similarity search over memory embeddings
- **Importance:** Planned
- **Link:** https://www.trychroma.com/ · https://faiss.ai/
- **Notes:** The `search()` function already has a vector-ready interface. Adding embeddings requires generating vectors at ingest time and querying by cosine similarity. ChromaDB is the simplest drop-in for local use; FAISS scales better for large stores.

---

### TOTP / Authenticator App Integration
- **Purpose:** Layer 7 approval gate — time-based one-time password as an alternative to CLI yes/no
- **Importance:** Planned
- **Link:** https://pypi.org/project/pyotp/
- **Notes:** Implement `TOTPAuthProvider(AuthProvider)` using `pyotp`. The operator scans a QR code once; each approval requires a 6-digit code from their authenticator app. Significantly stronger than CLI approval with minimal hardware cost.

---

### Systemd Service / LaunchAgent (process supervision)
- **Purpose:** Keep the Orchestrator running continuously and restart it automatically on crash or reboot
- **Importance:** Planned
- **Link:** https://www.freedesktop.org/wiki/Software/systemd/
- **Notes:** A simple `aeon-v1-orchestrator.service` unit file wrapping a Python script that calls `Orchestrator(config).tick()` in a loop with a configurable sleep interval. On macOS, a `launchd` plist achieves the same.

---

### Docker / Container Image
- **Purpose:** Reproducible deployment of the full stack on any machine without manual environment setup
- **Importance:** Planned
- **Link:** https://docs.docker.com/
- **Notes:** The current stack has no native dependencies beyond Python and optional `anthropic`. A minimal `python:3.11-slim` base image would suffice. Volume-mount `memory/` and `vault/` for persistence.

---

### Web Dashboard (read-only)
- **Purpose:** Browser-based view of memory stats, pending proposals, orchestrator status, and audit log — without replacing Obsidian
- **Importance:** Planned
- **Link:** https://fastapi.tiangolo.com/ (or Flask)
- **Notes:** Read-only API over the existing JSON store. No writes through the dashboard — all writes must still go through the Layer 7 pipeline. FastAPI + a simple HTML/JS frontend is the most pragmatic path.

---

*Document created: 2026-04-30 — Initial version reflecting Layers 1–7.*
*Updated: 2026-05-03 — Documented implemented LM Studio provider and local Obsidian workflow.*
*Update policy: append or modify entries only; never delete without explicit instruction; note reason for each change.*

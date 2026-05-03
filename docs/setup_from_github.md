# Setup From GitHub

This checklist describes what is ready immediately after cloning Aeon-V1 and
what still needs local setup.

Aeon-V1 is local-first. The repository includes the source code, docs, tests,
seed memory structure, Obsidian-compatible vault structure, LM Studio template,
and ESP32-S3 firmware source. Local secrets, model selections, installed Python
packages, running LM Studio servers, and flashed hardware are intentionally not
stored in GitHub.

## 1. Clone The Repository

```bash
git clone https://github.com/jessedaustin93/aeon-v1
cd aeon-v1
```

## 2. Install Aeon-V1

For normal local use:

```bash
pip install -e .
```

For development and tests:

```bash
pip install -e ".[dev]"
```

Optional extras:

```bash
pip install anthropic        # Anthropic provider support
pip install -e ".[hardware]" # ESP32-S3 USB approval provider support
```

## 3. Run The Test Suite

```bash
pytest
```

Expected result for the current suite:

```text
577 passed, 1 skipped
```

## 4. Run Aeon Without An LLM

Aeon works without a model. In this mode, ingestion, search, reflection,
task creation, decision selection, simulation, and the chat shell use local
rule-based behavior.

Launch the chat interface:

```bash
python scripts/aeon_chat.py
```

Or, after editable install:

```bash
aeon-chat
```

Windows users can also launch:

```text
Aeon Chat.bat
```

## 5. Enable LM Studio

Start from the generic template:

```bash
cp .env.lmstudio.template .env
```

PowerShell:

```powershell
Copy-Item .env.lmstudio.template .env
```

Then edit `.env` and replace these placeholders with exact model IDs from
LM Studio:

```env
AEON_V1_LLM_CHAT_MODEL=your-fast-chat-model-id
AEON_V1_LLM_MODEL=your-general-model-id
AEON_V1_LLM_DEEP_MODEL=your-deep-reasoning-model-id
```

You may use one model for all three roles, or split them by purpose:

| Variable | Purpose |
|---|---|
| `AEON_V1_LLM_CHAT_MODEL` | Fast interactive chat responses |
| `AEON_V1_LLM_MODEL` | General reflection/simulation reasoning |
| `AEON_V1_LLM_DEEP_MODEL` | Deeper tool-calling reflection/simulation paths |

In LM Studio, start the OpenAI-compatible local server. The default Aeon URL is:

```text
http://localhost:1234/v1
```

If LM Studio uses another URL, update:

```env
AEON_V1_LLM_BASE_URL=http://localhost:1234/v1
```

## 6. Optional Tool Calling

Tool calling lets reflection and simulation ask Aeon's `MemoryIndexAgent` for
bounded local memory context instead of receiving all memories inlined in the
prompt.

Enable it in `.env`:

```env
AEON_V1_LLM_TOOL_CALLING=1
```

Not every LM Studio model supports OpenAI-style tool calling well. If a
tool-calling request fails or returns no final content, Aeon retries the deep
model without tools and then falls back to rule-based behavior if needed.

## 7. Optional Anthropic Provider

Install the optional package:

```bash
pip install anthropic
```

Set environment variables:

```bash
export AEON_V1_LLM=1
export AEON_V1_LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=your_key_here
```

PowerShell:

```powershell
$env:AEON_V1_LLM="1"
$env:AEON_V1_LLM_PROVIDER="anthropic"
$env:ANTHROPIC_API_KEY="your_key_here"
```

## 8. Optional Obsidian Vault

Install Obsidian locally from the official download page:

```text
https://obsidian.md/download
```

Windows users may also be able to install with:

```powershell
winget install Obsidian.Obsidian
```

Then open the repository's `vault/` directory as an Obsidian vault:

```text
aeon-v1/vault/
```

Start from `index.md`. Aeon-generated notes use YAML frontmatter and `[[wikilinks]]`, and `link_memories()` can refresh related-memory links.

See `docs/obsidian.md` for the full local workflow.

## 9. Optional ESP32-S3 Approval Device

The repository includes firmware source for the hardware approval token:

```text
firmware/esp32s3-auth-device/
```

Install the hardware extra:

```bash
pip install -e ".[hardware]"
```

Flash the firmware with PlatformIO:

```bash
cd firmware/esp32s3-auth-device
pio run -t upload
pio device monitor
```

See `docs/auth_device.md` for protocol details.

## 10. What Is Ready Immediately

- Python package source under `src/aeon_v1/`
- CLI scripts under `scripts/`
- Windows launcher `Aeon Chat.bat`
- local JSON memory directories
- Obsidian-compatible Markdown vault directories
- test suite
- LM Studio template `.env.lmstudio.template`
- ESP32-S3 firmware source

## 11. What Must Stay Local

- `.env`
- API keys
- exact local model selections
- LM Studio server state
- Obsidian app/workspace state in `vault/.obsidian/`
- generated runtime memories and transcripts
- flashed hardware state

These are intentionally not committed to GitHub.

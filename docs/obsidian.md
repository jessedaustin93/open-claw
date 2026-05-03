# Obsidian Integration

Aeon-V1 mirrors memory records into `vault/` as plain Markdown so humans can inspect the system through Obsidian.

Obsidian is optional. Aeon runs without it. The vault remains readable in any text editor because the source of truth is local JSON in `memory/` plus Markdown in `vault/`.

## Install Obsidian

Install Obsidian locally from the official download page:

```text
https://obsidian.md/download
```

On Windows, `winget` may also be available:

```powershell
winget install Obsidian.Obsidian
```

## Open The Aeon Vault

1. Start Obsidian.
2. Choose **Open folder as vault**.
3. Select the repository's `vault/` directory.
4. Open `index.md` first.
5. Use graph view, backlinks, search, and tags to inspect memory relationships.

Do not open the repository root as the vault. Open only:

```text
aeon-v1/vault/
```

## How Aeon Writes Obsidian Notes

Aeon creates Markdown notes alongside JSON records:

| Aeon layer | Markdown folder |
|---|---|
| Raw memories | `vault/raw/` |
| Episodic memories | `vault/episodic/` |
| Semantic memories | `vault/semantic/` |
| Reflections | `vault/reflections/` |
| Tasks | `vault/tasks/` |
| Decisions | `vault/decisions/` |
| Simulations | `vault/simulations/` |
| Core memory | `vault/core/` |

Each generated note uses YAML frontmatter and Obsidian wikilinks where possible.

## Build Or Refresh Links

Aeon can add related-memory links between notes that share tags:

```python
from aeon_v1 import Config, link_memories

link_memories(config=Config())
```

This updates generated vault notes with `## Related Memories` sections.

## Core Memory Rule

`vault/core/` is human-gated.

Automated Aeon processes should not write core memory. Reflections may suggest core updates, but a human decides what belongs in `vault/core/`.

## What Not To Commit

Obsidian creates local app state under:

```text
vault/.obsidian/
```

That folder is ignored by Git. It can contain machine-specific workspace state, appearance settings, plugin state, and cache files.

Generated runtime memories are also ignored by default except for example seed files. This keeps personal memories out of GitHub.

## Recommended Local Workflow

1. Run Aeon normally from the CLI or chat interface.
2. Let Aeon write JSON and Markdown memory records.
3. Open `vault/` in Obsidian.
4. Browse from `index.md`.
5. Use backlinks and graph view to inspect relationships.
6. Manually curate `vault/core/` after reviewing reflections.

## Troubleshooting

If Obsidian shows unresolved links, run `link_memories()` and reopen graph view.

If Obsidian does not show new files, use **Reload app without saving** from the command palette or restart Obsidian.

If URI deep links do not work on a local machine, open Obsidian normally and navigate through the file explorer. Aeon's integration does not require `obsidian://` links.

"""Live end-to-end test: ingest varied questions, reflect, inspect memory files."""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aeon_v1 import ingest, reflect
from aeon_v1.config import Config
from aeon_v1.tasks import TaskStore

QUESTIONS = [
    "I learned a critical key insight: the best way to retain knowledge is to teach it back. Need to find a method to test this.",
    "I noticed an important pattern: sleep quality directly affects how well I recall information the next day. This needs more investigation.",
    "I discovered something surprising: spaced repetition outperforms massed practice by a factor of 2 to 1 in long-term retention.",
    "I'm uncertain about something: whether emotional context during learning improves or hinders factual recall under stress.",
    "I learned a critical key insight: writing by hand encodes memory more deeply than typing. Need to evaluate if this applies to code.",
]

cfg = Config()
cfg.allow_low_value_reflections = True
cfg.min_reflection_sources = 1
cfg.skip_duplicate_reflections = False

print("=" * 60)
print("PHASE 1 — INGESTING MEMORIES")
print("=" * 60)
for i, q in enumerate(QUESTIONS, 1):
    result = ingest(q, config=cfg)
    raw = result.get("raw") or {}
    ep  = result.get("episodic")
    sem = result.get("semantic")
    promoted = "episodic" if ep else ("semantic" if sem else "raw only")
    imp = raw.get("importance", 0)
    imp_str = f"{imp:.2f}" if isinstance(imp, float) else str(imp)
    print(f"[{i}] imp={imp_str}  promoted={promoted:<12}  {raw.get('title', q[:50])[:60]}")

print()
print("=" * 60)
print("PHASE 2 — REFLECT x3 (Gemma called each pass)")
print("=" * 60)
for i in range(1, 4):
    print(f"\n--- Pass {i} ---")
    result = reflect(config=cfg)
    ref = result.get("reflection")
    if ref is None:
        print("Skipped:", result.get("message"))
        continue
    print(f"llm_used={ref.get('llm_used')}  model={ref.get('llm_model')}  confidence={ref.get('confidence', 0):.2f}")
    print(f"tasks_suggested={len(ref.get('suggested_tasks', []))}")
    print()
    print(ref["content"][:1200])

print()
print("=" * 60)
print("PHASE 3 — MEMORY FILE INSPECTION")
print("=" * 60)

def show_json_dir(label, path):
    p = Path(path)
    if not p.exists():
        print(f"\n{label}: (missing)")
        return
    files = sorted(p.glob("*.json"))
    print(f"\n{label} ({len(files)} files):")
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            imp = d.get("importance", d.get("confidence", ""))
            imp_str = f"{imp:.2f}" if isinstance(imp, float) else str(imp)
            title = d.get("title") or d.get("concept") or d.get("id", "?")
            print(f"  {f.stem[:20]:<22} type={d.get('type','?'):<12} imp={imp_str:<6} {str(title)[:50]}")
        except Exception as e:
            print(f"  {f.name}: read error ({e})")

def show_md_dir(label, path):
    p = Path(path)
    if not p.exists():
        print(f"\n{label}: (missing)")
        return
    files = sorted(p.glob("*.md"))
    print(f"\n{label} ({len(files)} .md files):")
    for f in files:
        print(f"  {f.stem}")

show_json_dir("memory/episodic",    cfg.memory_path / "episodic")
show_json_dir("memory/semantic",    cfg.memory_path / "semantic")
show_json_dir("memory/reflections", cfg.memory_path / "reflections")
show_md_dir("vault/episodic",       cfg.vault_path / "episodic")
show_md_dir("vault/semantic",       cfg.vault_path / "semantic")
show_md_dir("vault/raw",            cfg.vault_path / "raw")
show_md_dir("vault/reflections",    cfg.vault_path / "reflections")
show_md_dir("vault/tasks",          cfg.vault_path / "tasks")

print()
print("=" * 60)
print("PHASE 4 — TASK QUEUE")
print("=" * 60)
tasks = TaskStore(cfg).list_tasks()
print(f"{len(tasks)} tasks:")
for t in tasks:
    print(f"  [{t.get('status','?'):<10}] {t.get('title','')[:70]}")

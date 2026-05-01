"""Live test: Gemma queries the MemoryIndexAgent via tool calling."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aeon_v1.config import Config
from aeon_v1.llm import generate_with_memory, build_reflection_prompt_sparse
from aeon_v1.memory_index_agent import MemoryIndexAgent
from aeon_v1.memory_store import MemoryStore
from aeon_v1.reflect import _analyse
from aeon_v1.evaluate import EvaluationStore

cfg = Config()
print(f"tool_calling : {cfg.llm_tool_calling}")
print(f"model        : {cfg.llm_model}")
print(f"timeout      : {cfg.llm_timeout_seconds}s")
print(f"max_tokens   : {cfg.llm_max_tokens}")

store = MemoryStore(cfg)
ep  = store.list_memories("episodic")
sem = store.list_memories("semantic")
pf  = EvaluationStore(cfg).list_evaluations(feedback="failure")
analysis = _analyse(ep, sem, pf)
analysis["display_tz"] = cfg.display_timezone

prompt = build_reflection_prompt_sparse(analysis)
print(f"sparse prompt: {len(prompt)} chars")
print()

agent = MemoryIndexAgent(cfg)

orig_handle = agent.handle_tool_call
def logged_handle(name, args):
    a = json.loads(args)
    print(f"  [index agent] << {a.get('query','')} | types={a.get('memory_types')}")
    result = orig_handle(name, args)
    count = len(json.loads(result))
    print(f"  [index agent] >> {count} memories returned")
    return result
agent.handle_tool_call = logged_handle

print("Calling Gemma with query_memory tool access...")
print()
result = generate_with_memory(prompt, agent, cfg)
print()
print("=" * 60)
print("LLM RESPONSE:")
print("=" * 60)
print(result[:1200] if result else "None")

"""Agent node for Aeon-V1 Layer 6.

Each AgentNode is a single-purpose unit with a defined lifecycle:

    spawn() → run() → dissolve()

Agents are stateless between runs; all state is persisted to
memory/agents/<id>.json and vault/agents/<id>.md.

SAFETY GUARANTEE
================
No subprocess, os.system, os.popen, exec, eval, or any network/execution
primitive is imported or invoked here. vault/core/ is never written.
"""
import json
from typing import Any, Dict, List, Optional

from .config import Config
from .decision import DecisionStore, select_next_task
from .evaluate import EvaluationStore, evaluate_simulation
from .memory_store import _generate_id, _wikilink
from .simulate import SimulationStore, simulate_action
from .tasks import TaskStore
from .time_utils import local_date_time_string, utc_now_iso

# Allowed agent roles — enforced at spawn time.
AGENT_ROLES = {
    "thinker",    # persistent reasoning / reflection agent
    "executor",   # task-specific: select → simulate → evaluate one task
    "monitor",    # watches memory growth, triggers reflect() when due
    "evaluator",  # re-scores past simulations against observed results
    "custom",     # caller-defined role; role_description is required
}

# Lifecycle states — only forward transitions are valid.
_VALID_TRANSITIONS = {
    "idle":       {"running", "dissolved"},
    "running":    {"idle", "dissolved"},
    "dissolved":  set(),           # terminal
}


class AgentNode:
    """A single-purpose agent node with a managed lifecycle.

    Args:
        role:             One of AGENT_ROLES.
        config:           Optional Config. Defaults to Config().
        agent_id:         Optional stable ID (generated if omitted).
        role_description: Required when role == "custom".
        tags:             Optional metadata tags.
    """

    def __init__(
        self,
        role: str,
        config: Optional[Config] = None,
        agent_id: Optional[str] = None,
        role_description: str = "",
        tags: Optional[List[str]] = None,
    ) -> None:
        if role not in AGENT_ROLES:
            raise ValueError(f"Unknown agent role {role!r}. Choose from {sorted(AGENT_ROLES)}.")
        if role == "custom" and not role_description:
            raise ValueError("role_description is required for role='custom'.")

        self.config = config or Config()
        self.id = agent_id or _generate_id()
        self.role = role
        self.role_description = role_description or role
        self.tags = tags or []
        self.status = "idle"
        self.created_at = utc_now_iso()
        self.last_run_at: Optional[str] = None
        self.run_count = 0
        self.results: List[Dict] = []

        self._ensure_dirs()
        self._persist()

    # ---------------------------------------------------------------- lifecycle

    def run(self, **kwargs: Any) -> Dict:
        """Execute one work cycle and return a result dict.

        Dispatches to the role-specific handler. The result is appended to
        self.results and persisted.

        Keyword args are forwarded to the role handler (e.g. task= for executor).
        """
        self._transition("running")
        self.last_run_at = utc_now_iso()
        self.run_count += 1

        try:
            result = self._dispatch(**kwargs)
        except Exception as exc:
            result = {"error": str(exc), "role": self.role}

        self.results.append(result)
        self._transition("idle")
        self._persist()
        return result

    def dissolve(self) -> None:
        """Mark the agent as dissolved (terminal state)."""
        self._transition("dissolved")
        self._persist()

    # ---------------------------------------------------------------- internal

    def _transition(self, new_status: str) -> None:
        allowed = _VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise RuntimeError(
                f"Agent {self.id}: invalid transition {self.status!r} → {new_status!r}."
            )
        self.status = new_status

    def _dispatch(self, **kwargs: Any) -> Dict:
        if self.role == "executor":
            return self._run_executor(**kwargs)
        if self.role == "thinker":
            return self._run_thinker(**kwargs)
        if self.role == "monitor":
            return self._run_monitor(**kwargs)
        if self.role == "evaluator":
            return self._run_evaluator(**kwargs)
        # custom
        return {"role": self.role, "description": self.role_description, "kwargs": kwargs}

    # ---------------------------------------------------------------- role handlers

    def _run_executor(self, task: Optional[Dict] = None, **_: Any) -> Dict:
        """Select the best pending task (or use the provided one), simulate, and return."""
        task_store = TaskStore(self.config)
        dec_store = DecisionStore(self.config)

        if task is None:
            decision_result = select_next_task(self.config)
            if decision_result.get("task") is None:
                return {"role": "executor", "outcome": "no_pending_tasks"}
            task = decision_result["task"]

        sim_result = simulate_action(task, self.config)
        return {
            "role":       "executor",
            "task_id":    task["id"],
            "task_title": task.get("title", ""),
            "simulation": sim_result.get("simulation", {}),
        }

    def _run_thinker(self, **_: Any) -> Dict:
        """Run a reflection pass and return a summary."""
        from .reflect import reflect  # local import avoids circular dep at module load
        result = reflect(self.config)
        ref = result.get("reflection")
        return {
            "role":          "thinker",
            "reflection_id": ref["id"] if ref else None,
            "tasks_created": len(result.get("tasks_created", [])),
            "message":       result.get("message", ""),
        }

    def _run_monitor(self, **_: Any) -> Dict:
        """Check memory counts; trigger reflection if interval is due."""
        from .memory_store import MemoryStore
        store = MemoryStore(self.config)
        ep_count  = len(store.list_memories("episodic"))
        sem_count = len(store.list_memories("semantic"))
        total = ep_count + sem_count

        triggered = False
        if total > 0 and total % self.config.reflection_interval == 0:
            from .reflect import reflect
            reflect(self.config)
            triggered = True

        return {
            "role":               "monitor",
            "episodic_count":     ep_count,
            "semantic_count":     sem_count,
            "reflection_trigger": triggered,
        }

    def _run_evaluator(self, simulation_id: Optional[str] = None, result_text: str = "", **_: Any) -> Dict:
        """Evaluate a simulation against an observed result string."""
        sim_store = SimulationStore(self.config)
        sims = sim_store.list_simulations()

        if simulation_id:
            target = next((s for s in sims if s["id"] == simulation_id), None)
        else:
            # Evaluate the most recent unevaluated simulation.
            target = next(
                (s for s in reversed(sims) if s.get("feedback") == "unknown"),
                None,
            )

        if target is None:
            return {"role": "evaluator", "outcome": "no_simulation_found"}

        if not result_text:
            result_text = target.get("expected_outcome", "")

        evaluation = evaluate_simulation(target, result_text, self.config)
        return {
            "role":          "evaluator",
            "simulation_id": target["id"],
            "evaluation":    evaluation,
        }

    # ---------------------------------------------------------------- persistence

    def _ensure_dirs(self) -> None:
        (self.config.memory_path / "agents").mkdir(parents=True, exist_ok=True)
        (self.config.vault_path  / "agents").mkdir(parents=True, exist_ok=True)

    def _persist(self) -> None:
        record = {
            "id":               self.id,
            "role":             self.role,
            "role_description": self.role_description,
            "tags":             self.tags,
            "status":           self.status,
            "created_at":       self.created_at,
            "last_run_at":      self.last_run_at,
            "run_count":        self.run_count,
        }
        (self.config.memory_path / "agents" / f"{self.id}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        self._write_markdown(record)

    def _write_markdown(self, record: Dict) -> None:
        md_path = self.config.vault_path / "agents" / f"{self.id}.md"
        fm_lines = ["---"]
        for key, val in [
            ("id",               record["id"]),
            ("role",             record["role"]),
            ("status",           record["status"]),
            ("created_at",       record["created_at"]),
            ("last_run_at",      record.get("last_run_at") or ""),
            ("run_count",        record["run_count"]),
        ]:
            fm_lines.append(f"{key}: {val}")
        fm_lines.append("tags:")
        for t in record.get("tags", []):
            fm_lines.append(f"  - {t}")
        fm_lines.append("---")

        display_tz = self.config.display_timezone
        local_ts = local_date_time_string(record["created_at"], display_tz)
        body = (
            f"# Agent — {record['role']} / {record['id']}\n\n"
            f"**Created:** {local_ts}\n\n"
            f"**Role:** `{record['role']}` — {record['role_description']}\n\n"
            f"**Status:** `{record['status']}`\n\n"
            f"**Run count:** {record['run_count']}\n\n"
            "[[Agents]] | [[Tasks]] | [[Reflections]] | [[Simulations]]"
        )
        md_path.write_text("\n".join(fm_lines) + "\n\n" + body, encoding="utf-8")

    # ---------------------------------------------------------------- class helpers

    @classmethod
    def load(cls, agent_id: str, config: Optional[Config] = None) -> Optional["AgentNode"]:
        """Load an agent from persisted JSON. Returns None if not found."""
        cfg = config or Config()
        path = cfg.memory_path / "agents" / f"{agent_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        node = cls.__new__(cls)
        node.config           = cfg
        node.id               = data["id"]
        node.role             = data["role"]
        node.role_description = data.get("role_description", data["role"])
        node.tags             = data.get("tags", [])
        node.status           = data["status"]
        node.created_at       = data["created_at"]
        node.last_run_at      = data.get("last_run_at")
        node.run_count        = data.get("run_count", 0)
        node.results          = []
        node._ensure_dirs()
        return node

    def to_dict(self) -> Dict:
        return {
            "id":               self.id,
            "role":             self.role,
            "role_description": self.role_description,
            "tags":             self.tags,
            "status":           self.status,
            "created_at":       self.created_at,
            "last_run_at":      self.last_run_at,
            "run_count":        self.run_count,
        }

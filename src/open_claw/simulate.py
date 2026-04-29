"""Action simulation engine for Open-Claw Layer 3.

simulate_action() produces a structured simulation record describing what
*would* happen if the task were acted upon — and stores it as JSON + Markdown.

SAFETY GUARANTEE
================
This module NEVER imports or calls:
  subprocess, os.system, os.popen, shutil, exec, eval,
  PowerShell, bash, shell, or any network/execution primitive.

All output is written to local files only. enable_real_actions is checked
on every call and raises RuntimeError if True (the value is always False
in the shipped Config — changing it does nothing because no execution path
exists to enable).
"""
import json
from typing import Dict, List, Optional

from .config import Config
from .llm import build_simulation_prompt, generate_text, parse_simulation_sections
from .memory_store import _generate_id, _wikilink
from .tasks import TaskStore
from .time_utils import local_date_time_string, utc_now_iso

_DESTRUCTIVE_SIGNALS = ("delete", "remove", "drop", "clear", "wipe", "purge")
_EXTERNAL_SIGNALS    = ("deploy", "push", "publish", "release", "ship")
_NETWORK_SIGNALS     = ("api", "request", "call", "fetch", "send", "http", "url")


class SimulationStore:
    """Read/write simulation records from memory/simulations/ and vault/simulations/."""

    def __init__(self, config: Config):
        self.config = config
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        (self.config.memory_path / "simulations").mkdir(parents=True, exist_ok=True)
        (self.config.vault_path / "simulations").mkdir(parents=True, exist_ok=True)

    def store(self, simulation: Dict) -> Dict:
        sim_id = simulation["id"]
        (self.config.memory_path / "simulations" / f"{sim_id}.json").write_text(
            json.dumps(simulation, indent=2), encoding="utf-8"
        )
        self._write_markdown(simulation)
        return simulation

    def list_simulations(self) -> List[Dict]:
        sim_dir = self.config.memory_path / "simulations"
        if not sim_dir.exists():
            return []
        sims = []
        for f in sim_dir.glob("*.json"):
            try:
                sims.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return sorted(sims, key=lambda s: s.get("created_at", ""))

    def _write_markdown(self, sim: Dict) -> None:
        md_path = self.config.vault_path / "simulations" / f"{sim['id']}.md"
        fm_lines = ["---"]
        for key, val in [
            ("id",                      sim["id"]),
            ("type",                    "simulation"),
            ("task_id",                 sim["task_id"]),
            ("task_title",              sim["task_title"]),
            ("created_at",              sim["created_at"]),
            ("required_human_approval", sim["required_human_approval"]),
        ]:
            fm_lines.append(f"{key}: {val}")
        fm_lines.append("source_links:")
        for lnk in sim.get("source_links", []):
            fm_lines.append(f"  - {lnk}")
        fm_lines.append("---")

        risks_md = (
            "\n".join(f"- {r}" for r in sim.get("risks", []))
            or "- None identified"
        )
        display_tz = self.config.display_timezone
        local_ts = local_date_time_string(sim["created_at"], display_tz)
        task_link = _wikilink("tasks", sim["task_id"], sim["task_title"])
        body = (
            f"# Simulation — {sim['task_title']}\n\n"
            f"**Created:** {local_ts}\n\n"
            f"**Task:** {task_link}\n\n"
            f"**Proposed Action:** {sim['proposed_action']}\n\n"
            f"**Expected Outcome:** {sim['expected_outcome']}\n\n"
            f"**Risks:**\n{risks_md}\n\n"
            f"**Required Human Approval:** `{sim['required_human_approval']}`\n\n"
            "> **SIMULATION ONLY** — no system commands were executed.\n"
            "> All actions above are proposed and require human review.\n\n"
            "[[Simulations]] | [[Decisions]] | [[Tasks]]"
        )
        md_path.write_text("\n".join(fm_lines) + "\n\n" + body, encoding="utf-8")


def simulate_action(task: Dict, config: Optional[Config] = None) -> Dict:
    """Produce and store a simulation record for a task.

    The function writes files only. It never calls any execution primitive.

    Args:
        task:   A task dict as returned by TaskStore.
        config: Optional Config — defaults to Config().

    Returns:
        {"simulation": simulation_record}
    """
    if config is None:
        config = Config()

    # Safety check — belt-and-suspenders even though no execution path exists.
    if config.enable_real_actions:
        raise RuntimeError(
            "enable_real_actions is True, but no real execution path is implemented. "
            "Open-Claw is a simulation-only system. Do not set enable_real_actions = True."
        )

    sim_store = SimulationStore(config)
    task_store = TaskStore(config)

    sim_id   = _generate_id()
    now      = utc_now_iso()
    desc     = task.get("description", "")
    title    = task.get("title", task.get("id", "unknown"))
    task_link = _wikilink("tasks", task["id"], title)

    # --- LLM attempt for planning fields (falls back to rule-based on any failure) ---
    llm_meta: Dict = {"llm_used": False, "llm_model": None, "llm_provider": None}
    llm_sections: Dict = {}

    if config.llm_enabled:
        llm_text = generate_text(build_simulation_prompt(task), config)
        if llm_text:
            llm_sections = parse_simulation_sections(llm_text)
            if llm_sections:
                llm_meta = {
                    "llm_used":     True,
                    "llm_model":    config.llm_model,
                    "llm_provider": config.llm_provider,
                }

    proposed_action  = llm_sections.get("Proposed Action") or _propose_action(desc)
    expected_outcome = llm_sections.get("Expected Outcome") or _expected_outcome(title, desc)
    risks            = _risks_from_llm(llm_sections.get("Risk Assessment"), desc, config)

    simulation: Dict = {
        "id":                      sim_id,
        "task_id":                 task["id"],
        "task_title":              title,
        "proposed_action":         proposed_action,
        "expected_outcome":        expected_outcome,
        "risks":                   risks,
        "required_human_approval": config.require_human_approval_for_simulation,
        "created_at":              now,
        "source_links":            [task_link],
        "llm_used":                llm_meta["llm_used"],
        "llm_model":               llm_meta["llm_model"],
        "llm_provider":            llm_meta["llm_provider"],
    }

    sim_store.store(simulation)
    task_store.update_status(task["id"], "simulated")

    return {"simulation": simulation}


# ---------------------------------------------------------------------------
# Rule-based fallbacks — used when LLM is disabled or unavailable.
# LLM integration is in simulate_action() via llm.generate_text().
# ---------------------------------------------------------------------------

def _propose_action(description: str) -> str:
    desc_lower = description.lower()
    if any(s in desc_lower for s in _DESTRUCTIVE_SIGNALS):
        return f"[DESTRUCTIVE — human approval required] {description[:120]}"
    if any(s in desc_lower for s in _EXTERNAL_SIGNALS):
        return f"[EXTERNAL-FACING — human approval required] {description[:120]}"
    return f"Review and act on: {description[:120]}"


def _expected_outcome(title: str, description: str) -> str:
    return (
        f"Task '{title}' is addressed according to its description. "
        "Relevant memory layers are updated as needed by subsequent ingestion."
    )


def _risks_from_llm(llm_text: Optional[str], description: str, config: Config) -> List[str]:
    """Parse LLM Risk Assessment text into a risk list, or fall back to rule-based."""
    if llm_text:
        risks = [
            line.lstrip("-•* ").strip()
            for line in llm_text.splitlines()
            if line.strip()
        ]
        risks = [r for r in risks if r]
        if risks:
            if config.require_human_approval_for_simulation:
                approval = "Human review required before any real action is taken."
                if not any("human review" in r.lower() for r in risks):
                    risks = [approval] + risks
            return risks
    return _estimate_risks(description, config)


def _estimate_risks(description: str, config: Config) -> List[str]:
    risks = []
    if config.require_human_approval_for_simulation:
        risks.append("Human review required before any real action is taken.")
    desc_lower = description.lower()
    if any(s in desc_lower for s in _DESTRUCTIVE_SIGNALS):
        risks.append("Destructive operation — verify exact scope before proceeding.")
    if any(s in desc_lower for s in _EXTERNAL_SIGNALS):
        risks.append("External-facing action — confirm environment and recipients.")
    if any(s in desc_lower for s in _NETWORK_SIGNALS):
        risks.append("Network operation — ensure authorization and rate limits are respected.")
    if not risks:
        risks.append("No specific risk signals detected. Standard human review recommended.")
    return risks

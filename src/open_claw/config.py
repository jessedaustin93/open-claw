from pathlib import Path
import os


class Config:
    def __init__(self, base_path: Path = Path(".")):
        self.base_path = Path(base_path)
        self.vault_path = self.base_path / "vault"
        self.memory_path = self.base_path / "memory"
        self.importance_threshold = 0.5
        # Placeholder: reflect after this many ingestions (not enforced automatically yet)
        self.reflection_interval = 10
        self.model_provider = "local"
        # Reflection safety: cap how many source memories one reflection pass reviews
        self.max_memories_per_reflection: int = 50
        # Reflection safety: reflections never reflect on prior reflections by default
        self.allow_reflection_on_reflections: bool = False
        # Core memory protection: ingestion/reflection never write to vault/core/.
        # Setting this True requires an explicit human decision.
        self.allow_core_modification: bool = False
        # Layer 2 — reflection quality controls
        self.min_reflection_sources: int = 1
        self.skip_duplicate_reflections: bool = True
        self.allow_low_value_reflections: bool = False
        # Layer 3 — decision and action simulation
        self.enable_real_actions: bool = False
        self.max_pending_tasks: int = 100
        self.duplicate_task_similarity_threshold: float = 0.8
        self.require_human_approval_for_simulation: bool = True
        # Timestamps — UTC is stored in JSON; this timezone is used for Markdown/CLI display.
        self.display_timezone: str = "America/New_York"
        # Layer 5 — tool registry
        self.allow_tool_override: bool = False
        # Layer 6 — orchestrator / agent pool
        self.max_thinking_agents: int = 10
        # Layer 4 — optional LLM reasoning
        # Toggle via OPENCLAW_LLM=1 environment variable or set directly.
        self.llm_enabled: bool = os.environ.get("OPENCLAW_LLM", "0").strip() == "1"
        self.llm_provider: str = "anthropic"
        self.llm_model: str = "claude-3-5-sonnet-latest"
        self.llm_temperature: float = 0.2
        self.llm_max_tokens: int = 1200
        self.llm_timeout_seconds: int = 60

    def ensure_dirs(self):
        for subdir in ["core", "raw", "episodic", "semantic", "reflections", "agents", "tasks"]:
            (self.vault_path / subdir).mkdir(parents=True, exist_ok=True)
        for subdir in ["raw", "episodic", "semantic", "reflections"]:
            (self.memory_path / subdir).mkdir(parents=True, exist_ok=True)
        (self.memory_path / "schemas").mkdir(parents=True, exist_ok=True)
        # Layer 7 — governance directories
        for subdir in ["staging", "approved", "logs"]:
            (self.memory_path / subdir).mkdir(parents=True, exist_ok=True)


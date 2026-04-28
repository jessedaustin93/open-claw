from pathlib import Path


class Config:
    def __init__(self, base_path: Path = Path(".")):
        self.base_path = Path(base_path)
        self.vault_path = self.base_path / "vault"
        self.memory_path = self.base_path / "memory"
        self.importance_threshold = 0.5
        # Placeholder: reflect after this many ingestions (not enforced automatically yet)
        self.reflection_interval = 10
        # Placeholder: swap in "openai", "anthropic", etc. when LLM integration is added
        self.model_provider = "local"
        # Reflection safety: cap how many source memories one reflection pass reviews
        self.max_memories_per_reflection: int = 50
        # Reflection safety: reflections never reflect on prior reflections by default
        self.allow_reflection_on_reflections: bool = False
        # Core memory protection: ingestion/reflection never write to vault/core/.
        # Setting this True requires an explicit human decision.
        self.allow_core_modification: bool = False
        # Layer 2 — reflection quality controls
        # Minimum number of source memories required to produce a reflection.
        self.min_reflection_sources: int = 1
        # When True, skip a reflect() pass whose source IDs exactly match a prior reflection.
        self.skip_duplicate_reflections: bool = True
        # When False (default), skip reflect() passes that fall below min_reflection_sources.
        self.allow_low_value_reflections: bool = False
        # Layer 3 — decision and action simulation
        # Safety lock: real execution is permanently disabled. Never set to True.
        self.enable_real_actions: bool = False
        # Maximum number of pending tasks before new task creation is blocked.
        self.max_pending_tasks: int = 100
        # Jaccard similarity threshold above which a new task is considered a duplicate.
        self.duplicate_task_similarity_threshold: float = 0.8
        # When True (default), every simulation record is flagged for human approval.
        self.require_human_approval_for_simulation: bool = True
        # Timestamps — UTC is stored in JSON; this timezone is used for Markdown/CLI display.
        self.display_timezone: str = "America/New_York"

    def ensure_dirs(self):
        for subdir in ["core", "raw", "episodic", "semantic", "reflections", "agents", "tasks"]:
            (self.vault_path / subdir).mkdir(parents=True, exist_ok=True)
        for subdir in ["raw", "episodic", "semantic", "reflections"]:
            (self.memory_path / subdir).mkdir(parents=True, exist_ok=True)
        (self.memory_path / "schemas").mkdir(parents=True, exist_ok=True)

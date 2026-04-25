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

    def ensure_dirs(self):
        for subdir in ["core", "raw", "episodic", "semantic", "reflections", "agents", "tasks"]:
            (self.vault_path / subdir).mkdir(parents=True, exist_ok=True)
        for subdir in ["raw", "episodic", "semantic", "reflections"]:
            (self.memory_path / subdir).mkdir(parents=True, exist_ok=True)
        (self.memory_path / "schemas").mkdir(parents=True, exist_ok=True)

"""
Open-Claw Configuration
All tunable parameters for memory ingestion, linking, and reflection.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # ── Paths ──────────────────────────────────────────────────────────────
    base_dir: Path = Path(".")
    memory_dir: Path = Path("memory")
    vault_dir: Path = Path("vault")

    # ── Importance scoring ─────────────────────────────────────────────────
    importance_threshold: float = 0.3        # Minimum score to keep a memory
    episodic_threshold: float = 0.5          # Score needed for episodic promotion
    semantic_threshold: float = 0.6          # Score needed for semantic promotion

    importance_keywords: list = field(default_factory=lambda: [
        "important", "critical", "remember", "always", "never",
        "key", "core", "fundamental", "essential", "must",
        "goal", "objective", "problem", "error", "fail",
        "success", "learn", "pattern", "insight", "decision",
    ])

    keyword_weight: float = 0.4
    length_weight: float = 0.2
    signal_weight: float = 0.4

    # ── Linking ────────────────────────────────────────────────────────────
    min_shared_tags: int = 1                 # Minimum shared tags to create a link

    # ── Reflection (Layer 2) ───────────────────────────────────────────────
    min_reflection_sources: int = 2          # Minimum memories needed to reflect
    max_memories_per_reflection: int = 50    # Cap on memories per reflection run
    skip_duplicate_reflections: bool = True  # Skip if same source set reflected before
    allow_low_value_reflections: bool = False
    allow_reflection_on_reflections: bool = False  # Reflections are NOT re-reflected

    # Task extraction trigger phrases
    task_trigger_phrases: list = field(default_factory=lambda: [
        "should", "need to", "next step", "test", "build",
        "implement", "create", "fix", "update", "check",
        "investigate", "explore", "consider", "review", "add",
    ])

    # Confidence scoring weights
    confidence_source_weight: float = 0.4
    confidence_diversity_weight: float = 0.3
    confidence_importance_weight: float = 0.3

    # ── Core protection ────────────────────────────────────────────────────
    core_protected: bool = True              # NEVER disable this


# Singleton default config
_default_config: Config = None


def get_config() -> Config:
    global _default_config
    if _default_config is None:
        _default_config = Config()
    return _default_config


def set_config(cfg: Config):
    global _default_config
    _default_config = cfg

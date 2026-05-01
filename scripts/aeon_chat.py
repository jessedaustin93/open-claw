#!/usr/bin/env python3
"""Launch the Aeon-V1 terminal chat interface."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aeon_v1.chat_cli import main


if __name__ == "__main__":
    main()

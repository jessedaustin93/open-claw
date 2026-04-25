#!/usr/bin/env python3
"""Run a reflection pass over all existing episodic and semantic memories."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from open_claw import Config, reflect


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Open-Claw reflection engine.",
        epilog="Example:\n  python scripts/run_reflection.py --base-path .",
    )
    parser.add_argument(
        "--base-path", default=".", help="Root directory containing vault/ and memory/ (default: .)"
    )
    args = parser.parse_args()

    config = Config(base_path=args.base_path)
    result = reflect(config=config)

    print(result["message"])
    if result["reflection"]:
        r = result["reflection"]
        print(f"[reflection] {r['id']}  tags={r['tags']}")
        print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    main()

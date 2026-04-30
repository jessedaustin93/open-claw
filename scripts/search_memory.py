#!/usr/bin/env python3
"""Search Aeon-V1 memory for a keyword or phrase."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aeon_v1 import Config, search


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Aeon-V1 memory by keyword.",
        epilog='Example:\n  python scripts/search_memory.py "recursive learning"',
    )
    parser.add_argument("query", help="Search query (keyword or phrase)")
    parser.add_argument(
        "--types",
        nargs="+",
        choices=["raw", "episodic", "semantic", "reflections"],
        help="Limit search to specific memory types",
    )
    parser.add_argument(
        "--base-path", default=".", help="Root directory containing vault/ and memory/ (default: .)"
    )
    args = parser.parse_args()

    config = Config(base_path=args.base_path)
    results = search(args.query, memory_types=args.types, config=config)

    if not results:
        print(f"No results for: {args.query!r}")
        return

    print(f"Found {len(results)} result(s) for {args.query!r}:\n")
    for r in results:
        mem = r["memory"]
        print(f"  [{r['match_type']}]  id={mem.get('id', '?')}")
        for field in ("summary", "concept", "text", "content"):
            val = mem.get(field, "")
            if val:
                snippet = val[:120].replace("\n", " ")
                print(f"    {field}: {snippet}")
        print()


if __name__ == "__main__":
    main()

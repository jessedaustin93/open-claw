#!/usr/bin/env python3
"""Ingest a text memory from a positional argument, --file, or stdin."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from open_claw import Config, ingest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest text into the Open-Claw memory system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/ingest_text.py "I learned that recursion needs a base case."
  python scripts/ingest_text.py --file notes.txt --source journal
  echo "Important project goal: ship v1." | python scripts/ingest_text.py
""",
    )
    parser.add_argument("text", nargs="?", help="Text to ingest")
    parser.add_argument("--file", "-f", help="Read text from a file instead")
    parser.add_argument("--source", "-s", default="manual", help="Source label (default: manual)")
    parser.add_argument(
        "--base-path", default=".", help="Root directory containing vault/ and memory/ (default: .)"
    )
    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8").strip()
    elif args.text:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.buffer.read().decode("utf-8").strip()
    else:
        parser.error("Provide text as an argument, --file, or via stdin.")

    config = Config(base_path=args.base_path)
    result = ingest(text, source=args.source, config=config)

    print(f"[raw]      {result['raw']['id']}  importance={result['raw']['importance']}")
    if result["episodic"]:
        print(f"[episodic] {result['episodic']['id']}")
    if result["semantic"]:
        print(f"[semantic] {result['semantic']['id']}  concept={result['semantic'].get('concept')}")

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

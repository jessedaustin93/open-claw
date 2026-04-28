"""
Open-Claw CLI
Usage:
  python -m open_claw.cli ingest "Your memory text here" --tags tag1 tag2
  python -m open_claw.cli reflect
  python -m open_claw.cli link
  python -m open_claw.cli search "query"
"""

import argparse
import json
import sys


def cmd_ingest(args):
    from open_claw import Ingestor
    ingestor = Ingestor()
    result = ingestor.ingest(
        text=args.text,
        tags=args.tags or [],
    )
    print(f"✓ Ingested raw memory: {result['raw']['id']}")
    print(f"  Title:     {result['raw']['title']}")
    print(f"  Score:     {result['score']:.4f}")
    if result["episodic"]:
        print(f"  → Promoted to episodic: {result['episodic']['id']}")
    if result["semantic"]:
        print(f"  → Promoted to semantic: {result['semantic']['id']}")


def cmd_reflect(args):
    from open_claw import Reflector
    reflector = Reflector()
    result = reflector.run()
    if result is None:
        print("⚠ No reflection generated (not enough sources or duplicate).")
    else:
        print(f"✓ Reflection created: {result['id']}")
        print(f"  Confidence: {result.get('confidence', 0.0):.4f}")
        tasks = result.get("suggested_tasks", [])
        if tasks:
            print(f"  Suggested tasks ({len(tasks)}):")
            for t in tasks[:5]:
                print(f"    - {t}")


def cmd_link(args):
    from open_claw import Linker
    linker = Linker()
    summary = linker.run()
    print(f"✓ Linking complete")
    print(f"  Memories scanned: {summary['memories_scanned']}")
    print(f"  Memories linked:  {summary['memories_linked']}")
    print(f"  Total links:      {summary['total_links']}")


def cmd_search(args):
    from open_claw import MemoryStore
    store = MemoryStore()
    results = store.search(args.query)
    if not results:
        print(f"No results for: {args.query}")
        return
    print(f"Found {len(results)} result(s) for '{args.query}':\n")
    for r in results[:20]:
        print(f"  [{r['type']}] {r['title']}")
        print(f"    id:         {r['id']}")
        print(f"    importance: {r['importance']:.4f}")
        print(f"    tags:       {', '.join(r.get('tags', []))}")
        print()


def main():
    parser = argparse.ArgumentParser(
        prog="open-claw",
        description="Open-Claw: Local-first AI memory framework",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingest a new memory")
    p_ingest.add_argument("text", help="Memory text to ingest")
    p_ingest.add_argument("--tags", nargs="*", default=[], help="Tags for this memory")
    p_ingest.set_defaults(func=cmd_ingest)

    # reflect
    p_reflect = subparsers.add_parser("reflect", help="Run a reflection pass")
    p_reflect.set_defaults(func=cmd_reflect)

    # link
    p_link = subparsers.add_parser("link", help="Run a linking pass")
    p_link.set_defaults(func=cmd_link)

    # search
    p_search = subparsers.add_parser("search", help="Search memories")
    p_search.add_argument("query", help="Search query")
    p_search.set_defaults(func=cmd_search)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

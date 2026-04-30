#!/usr/bin/env python3
"""Layer 3 CLI — decision and action simulation.

Commands:
  tasks     List all pending tasks
  decide    Select the best pending task and write a decision record
  simulate  Simulate the most recently selected (or pending) task
  loop      Run decide then simulate once

Usage:
  python scripts/manage_tasks.py tasks
  python scripts/manage_tasks.py decide
  python scripts/manage_tasks.py simulate
  python scripts/manage_tasks.py loop
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aeon_v1 import Config
from aeon_v1.decision import select_next_task
from aeon_v1.simulate import simulate_action
from aeon_v1.tasks import TaskStore


def cmd_tasks(config: Config) -> None:
    store = TaskStore(config)
    tasks = store.list_tasks(status="pending")
    if not tasks:
        print("No pending tasks.")
        return
    print(f"{len(tasks)} pending task(s):\n")
    for t in tasks:
        print(f"  [{t['id']}] {t['title']}")
        print(f"    priority={t.get('priority', 0.5):.2f}  confidence={t.get('confidence', 0.5):.2f}")
        print(f"    {t.get('description', '')[:80]}")
        print()


def cmd_decide(config: Config) -> None:
    result = select_next_task(config=config)
    if result["task"] is None:
        print(result.get("message", "No task selected."))
        return
    task     = result["task"]
    decision = result["decision"]
    print(f"Selected task : [{task['id']}] {task['title']}")
    print(f"Reason        : {decision['reason']}")
    print(f"Decision ID   : {decision['id']}")
    if decision["alternatives_considered"]:
        print(f"Alternatives  : {', '.join(decision['alternatives_considered'])}")


def cmd_simulate(config: Config) -> None:
    store = TaskStore(config)
    tasks = store.list_tasks(status="selected") or store.list_tasks(status="pending")
    if not tasks:
        print("No selected or pending tasks to simulate.")
        return
    task   = tasks[-1]  # most recently created eligible task
    result = simulate_action(task, config=config)
    sim    = result["simulation"]
    print(f"Simulation ID     : {sim['id']}")
    print(f"Task              : {sim['task_title']}")
    print(f"Proposed action   : {sim['proposed_action']}")
    print(f"Expected outcome  : {sim['expected_outcome']}")
    print("Risks:")
    for r in sim["risks"]:
        print(f"  - {r}")
    print(f"Human approval    : {sim['required_human_approval']}")


def cmd_loop(config: Config) -> None:
    print("=== DECIDE ===")
    result = select_next_task(config=config)
    if result["task"] is None:
        print(result.get("message", "No task to decide on."))
        return
    task = result["task"]
    print(f"Selected: [{task['id']}] {task['title']}")
    print()

    print("=== SIMULATE ===")
    sim_result = simulate_action(task, config=config)
    sim = sim_result["simulation"]
    print(f"Simulation : {sim['id']}")
    print(f"Action     : {sim['proposed_action']}")
    print(f"Outcome    : {sim['expected_outcome']}")


_COMMANDS = {
    "tasks":    cmd_tasks,
    "decide":   cmd_decide,
    "simulate": cmd_simulate,
    "loop":     cmd_loop,
}

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "tasks"
    if command not in _COMMANDS:
        print(f"Unknown command: {command!r}")
        print(f"Available: {', '.join(_COMMANDS)}")
        sys.exit(1)
    _COMMANDS[command](Config())

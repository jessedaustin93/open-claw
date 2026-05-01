"""Interactive terminal chat interface for Aeon-V1.

This module is the human-facing front door: a simple chat loop that feels like a
normal AI app while quietly using Aeon's local memory, search, optional LLM, and
maintenance hooks in the background.

It does not bypass Layer 7. It writes ordinary conversational memories through
trusted local ingestion, and it does not execute commands or commit governed
agent proposals.
"""
from __future__ import annotations

import argparse
import cmd
import json
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import Config
from .ingest import ingest
from .linker import link_memories
from .llm import generate_text, generate_with_memory
from .memory_index_agent import MemoryIndexAgent
from .orchestrator import Orchestrator
from .reflect import reflect
from .search import search
from .time_utils import local_now_string


WELCOME = """
Aeon-V1 Terminal
Local memory online. Type naturally, or use /help for commands.
""".strip()

SYSTEM_PROMPT = """You are Aeon-V1 speaking through a local terminal interface.

Voice and behavior:
- Be warm, direct, and useful.
- Answer like a normal chat AI, but ground yourself in the user's local Aeon memory when relevant.
- Be honest when memory is thin or uncertain.
- Do not claim actions were executed. Aeon simulations and Layer 7 proposals are governed separately.
- If the user asks for something that changes important state, describe the safe next step and keep human approval in the loop.
"""


@dataclass
class ChatOptions:
    base_path: Path = Path(".")
    source: str = "aeon-chat"
    no_ingest: bool = False
    auto_link: bool = True
    auto_tick: bool = False
    reflect_every: int = 0
    memory_limit: int = 5
    transcript_path: Optional[Path] = None


@dataclass
class ChatTurn:
    user: str
    assistant: str
    memory_ids: List[str] = field(default_factory=list)
    llm_used: bool = False


class TerminalChatApp(cmd.Cmd):
    """Small cmd-based chat shell for Aeon."""

    intro = WELCOME
    prompt = "aeon> "

    def __init__(self, config: Config, options: ChatOptions):
        super().__init__()
        self.config = config
        self.options = options
        self.index_agent = MemoryIndexAgent(config)
        self.turns: List[ChatTurn] = []
        self.turn_count = 0
        self.config.ensure_dirs()

    # ------------------------------------------------------------------ input

    def default(self, line: str) -> None:
        text = line.strip()
        if not text:
            return
        turn = self.handle_chat(text)
        print_wrapped(turn.assistant)

    def emptyline(self) -> None:
        return

    # ---------------------------------------------------------------- commands

    def do_help(self, arg: str) -> None:  # noqa: D401 - cmd module convention
        """Show available commands."""
        print(
            textwrap.dedent(
                """
                Commands:
                  /help              show this help
                  /status            show memory + LLM status
                  /memory <query>     search local memory
                  /reflect           run one reflection pass now
                  /tick              run one orchestrator tick now
                  /transcript        show where this session is being logged
                  /exit              leave the chat

                You can also just type normally. Aeon will ingest the turn,
                search memory, answer with the configured LLM when available,
                and fall back to a local memory summary when no LLM is enabled.
                """
            ).strip()
        )

    def do_status(self, arg: str) -> None:
        """Show current interface status."""
        status = {
            "base_path": str(self.config.base_path),
            "llm_enabled": self.config.llm_enabled,
            "llm_provider": self.config.llm_provider,
            "llm_model": self.config.llm_model,
            "llm_tool_calling": self.config.llm_tool_calling,
            "auto_link": self.options.auto_link,
            "auto_tick": self.options.auto_tick,
            "reflect_every": self.options.reflect_every,
            "turns": self.turn_count,
        }
        print(json.dumps(status, indent=2))

    def do_memory(self, arg: str) -> None:
        """Search local memory. Usage: /memory recursive learning"""
        query = arg.strip()
        if not query:
            print("Usage: /memory <query>")
            return
        results = search(query, config=self.config)[: self.options.memory_limit]
        if not results:
            print("No matching memory found.")
            return
        for result in results:
            mem = result.get("memory", {})
            print(f"- [{result.get('match_type')}] {mem.get('id', 'unknown')}: {memory_preview(mem)}")

    def do_reflect(self, arg: str) -> None:
        """Run one reflection pass."""
        result = reflect(self.config)
        reflection = result.get("reflection")
        if reflection:
            print(f"Reflection written: {reflection['id']}")
            created = result.get("tasks_created", [])
            if created:
                print(f"Tasks created: {len(created)}")
        else:
            print(result.get("message", "No reflection written."))

    def do_tick(self, arg: str) -> None:
        """Run one orchestrator tick."""
        summary = Orchestrator(self.config).tick()
        print(json.dumps(summary, indent=2, default=str))

    def do_transcript(self, arg: str) -> None:
        """Show transcript location, if enabled."""
        if self.options.transcript_path:
            print(str(self.options.transcript_path))
        else:
            print("Transcript logging is off for this session.")

    def do_exit(self, arg: str) -> bool:
        """Exit Aeon chat."""
        print("Aeon chat closed.")
        return True

    def do_quit(self, arg: str) -> bool:
        """Exit Aeon chat."""
        return self.do_exit(arg)

    def do_EOF(self, arg: str) -> bool:  # Ctrl+Z/Ctrl+D
        print()
        return self.do_exit(arg)

    # cmd dispatch treats slash commands as unknown syntax; normalize them.
    def onecmd(self, line: str):
        if line.startswith("/"):
            line = line[1:]
        return super().onecmd(line)

    # ------------------------------------------------------------------ chat

    def handle_chat(self, user_text: str) -> ChatTurn:
        self.turn_count += 1
        user_memory_id = None
        if not self.options.no_ingest:
            user_memory_id = self._ingest_safely(f"User: {user_text}")

        memories = retrieve_context(user_text, self.config, self.options.memory_limit)
        response = build_response(
            user_text=user_text,
            memories=memories,
            history=self.turns[-4:],
            config=self.config,
            index_agent=self.index_agent,
        )

        assistant_memory_id = None
        if not self.options.no_ingest:
            assistant_memory_id = self._ingest_safely(f"Aeon: {response}")

        if self.options.auto_link:
            self._link_safely()

        if self.options.auto_tick:
            self._tick_safely()
        elif self.options.reflect_every and self.turn_count % self.options.reflect_every == 0:
            self._reflect_safely()

        turn = ChatTurn(
            user=user_text,
            assistant=response,
            memory_ids=[mid for mid in (user_memory_id, assistant_memory_id) if mid],
            llm_used=not response.startswith(local_fallback_prefix()),
        )
        self.turns.append(turn)
        self._append_transcript(turn)
        return turn

    def _ingest_safely(self, text: str) -> Optional[str]:
        try:
            result = ingest(text, source=self.options.source, config=self.config)
            return (
                (result.get("semantic") or {}).get("id")
                or (result.get("episodic") or {}).get("id")
                or (result.get("raw") or {}).get("id")
            )
        except Exception:
            return None

    def _link_safely(self) -> None:
        try:
            link_memories(config=self.config)
        except Exception:
            pass

    def _tick_safely(self) -> None:
        try:
            Orchestrator(self.config).tick()
        except Exception:
            pass

    def _reflect_safely(self) -> None:
        try:
            reflect(self.config)
        except Exception:
            pass

    def _append_transcript(self, turn: ChatTurn) -> None:
        path = self.options.transcript_path
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "at": local_now_string(self.config.display_timezone),
                    "user": turn.user,
                    "assistant": turn.assistant,
                    "memory_ids": turn.memory_ids,
                    "llm_used": turn.llm_used,
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass


def build_response(
    user_text: str,
    memories: List[Dict],
    history: Iterable[ChatTurn],
    config: Config,
    index_agent: MemoryIndexAgent,
) -> str:
    prompt = build_chat_prompt(user_text, memories, history)
    if config.llm_tool_calling:
        llm_text = generate_with_memory(prompt, index_agent=index_agent, config=config)
    else:
        llm_text = generate_text(prompt, config=config)
    if llm_text:
        return llm_text.strip()
    return fallback_response(user_text, memories)


def build_chat_prompt(user_text: str, memories: List[Dict], history: Iterable[ChatTurn]) -> str:
    memory_block = format_memories(memories)
    history_block = format_history(history)
    return f"""{SYSTEM_PROMPT}

Recent conversation:
{history_block or '- No prior turns in this session.'}

Relevant local memory:
{memory_block or '- No matching local memory found.'}

User message:
{user_text}

Reply as Aeon. Keep the answer useful and conversational. If you use memory, make it feel natural rather than dumping records."""


def retrieve_context(query: str, config: Config, limit: int) -> List[Dict]:
    results = search(query, memory_types=["episodic", "semantic", "reflections"], config=config)
    return results[:limit]


def format_memories(results: List[Dict]) -> str:
    lines: List[str] = []
    for result in results:
        mem = result.get("memory", {})
        lines.append(f"- {mem.get('id', 'unknown')} [{result.get('match_type', 'memory')}]: {memory_preview(mem)}")
    return "\n".join(lines)


def format_history(history: Iterable[ChatTurn]) -> str:
    lines: List[str] = []
    for turn in history:
        lines.append(f"User: {turn.user}")
        lines.append(f"Aeon: {turn.assistant}")
    return "\n".join(lines)


def memory_preview(memory: Dict) -> str:
    for field_name in ("summary", "description", "concept", "content", "text", "title"):
        value = memory.get(field_name)
        if value:
            return compact(str(value), 160)
    return compact(str(memory), 160)


def compact(text: str, limit: int) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= limit:
        return one_line
    cutoff = max(0, limit - 3)
    shortened = one_line[:cutoff].rstrip()
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0]
    return shortened + "..."


def fallback_response(user_text: str, memories: List[Dict]) -> str:
    if memories:
        memory_lines = "\n".join(
            f"- {memory_preview(result.get('memory', {}))}" for result in memories[:3]
        )
        return (
            f"{local_fallback_prefix()} I stored that and found a few nearby memories:\n"
            f"{memory_lines}\n\n"
            "LLM mode is off or unavailable, so I am giving you the local-memory view instead of a generated answer."
        )
    return (
        f"{local_fallback_prefix()} I stored that. I do not have a close memory match yet, "
        "and LLM mode is off or unavailable, so there is no generated answer this turn."
    )


def local_fallback_prefix() -> str:
    return "[local]"


def print_wrapped(text: str) -> None:
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            print()
        else:
            print(textwrap.fill(paragraph, width=88, replace_whitespace=False))


def parse_args(argv: Optional[List[str]] = None) -> ChatOptions:
    parser = argparse.ArgumentParser(description="Open the Aeon-V1 terminal chat interface.")
    parser.add_argument("--base-path", default=".", help="Repo root containing memory/ and vault/.")
    parser.add_argument("--source", default="aeon-chat", help="Source label for ingested chat turns.")
    parser.add_argument("--no-ingest", action="store_true", help="Do not store chat turns in memory.")
    parser.add_argument("--no-link", action="store_true", help="Do not run link_memories after turns.")
    parser.add_argument("--auto-tick", action="store_true", help="Run one Orchestrator.tick() after each turn.")
    parser.add_argument(
        "--reflect-every",
        type=int,
        default=0,
        help="Run reflect() every N chat turns. Default 0 disables automatic reflection.",
    )
    parser.add_argument("--memory-limit", type=int, default=5, help="Relevant memories to include per turn.")
    parser.add_argument(
        "--transcript",
        default="memory/chat/transcript.jsonl",
        help="JSONL transcript path relative to base path. Use 'off' to disable.",
    )
    args = parser.parse_args(argv)

    base_path = Path(args.base_path).resolve()
    transcript = None
    if args.transcript.lower() != "off":
        transcript_path = Path(args.transcript)
        transcript = transcript_path if transcript_path.is_absolute() else base_path / transcript_path

    return ChatOptions(
        base_path=base_path,
        source=args.source,
        no_ingest=args.no_ingest,
        auto_link=not args.no_link,
        auto_tick=args.auto_tick,
        reflect_every=max(0, args.reflect_every),
        memory_limit=max(1, args.memory_limit),
        transcript_path=transcript,
    )


def main(argv: Optional[List[str]] = None) -> None:
    options = parse_args(argv)
    config = Config(base_path=options.base_path)
    TerminalChatApp(config, options).cmdloop()


if __name__ == "__main__":
    main()

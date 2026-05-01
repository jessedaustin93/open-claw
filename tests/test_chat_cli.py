"""Tests for the Aeon terminal chat interface."""
from pathlib import Path

from aeon_v1.chat_cli import (
    ChatTurn,
    build_chat_prompt,
    compact,
    fallback_response,
    format_history,
    format_memories,
    memory_preview,
    parse_args,
)


def test_compact_keeps_short_text():
    assert compact("hello world", 20) == "hello world"


def test_compact_truncates_long_text():
    assert compact("one two three four", 10) == "one two..."


def test_memory_preview_prefers_summary():
    preview = memory_preview({"summary": "short summary", "content": "long content"})

    assert preview == "short summary"


def test_format_memories_includes_id_type_and_preview():
    text = format_memories([
        {
            "match_type": "semantic",
            "memory": {"id": "abc123", "description": "A useful concept"},
        }
    ])

    assert "abc123" in text
    assert "semantic" in text
    assert "A useful concept" in text


def test_format_history_includes_recent_turns():
    text = format_history([ChatTurn(user="hi", assistant="hello")])

    assert "User: hi" in text
    assert "Aeon: hello" in text


def test_build_chat_prompt_contains_user_memory_and_safety_contract():
    prompt = build_chat_prompt(
        user_text="What matters?",
        memories=[{"match_type": "episodic", "memory": {"id": "m1", "summary": "Important goal"}}],
        history=[ChatTurn(user="Earlier", assistant="Earlier reply")],
    )

    assert "What matters?" in prompt
    assert "Important goal" in prompt
    assert "Earlier reply" in prompt
    assert "Do not claim actions were executed" in prompt


def test_fallback_response_mentions_memory_when_available():
    response = fallback_response(
        "hello",
        [{"memory": {"summary": "stored memory"}}],
    )

    assert response.startswith("[local]")
    assert "stored memory" in response


def test_fallback_response_handles_no_memory():
    response = fallback_response("hello", [])

    assert response.startswith("[local]")
    assert "I stored that" in response


def test_parse_args_resolves_base_path_and_transcript(tmp_path):
    options = parse_args(["--base-path", str(tmp_path), "--reflect-every", "3"])

    assert options.base_path == tmp_path.resolve()
    assert options.reflect_every == 3
    assert options.transcript_path == tmp_path.resolve() / "memory/chat/transcript.jsonl"


def test_parse_args_can_disable_transcript(tmp_path):
    options = parse_args(["--base-path", str(tmp_path), "--transcript", "off"])

    assert options.transcript_path is None

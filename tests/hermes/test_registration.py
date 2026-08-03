"""test_registration.py - unit tests for plugin registration against a
fake Hermes host context. No Hermes installation required.

These tests enforce the documented Hermes plugin API contract:
  - register_tool(*, name, toolset, schema, handler, description)
  - register_skill(name, path)
  - register_hook(event, handler)
  - register_command(name, *, handler, description)
  - tool handlers are def handler(args: dict, **kwargs) -> str
"""

from __future__ import annotations

import inspect
from pathlib import Path

import adjacent  # noqa: E402


def _plugin_dir() -> Path:
    return Path(adjacent.__file__).resolve().parent


def test_register_full(fake_ctx):
    adjacent.register(fake_ctx)
    assert set(fake_ctx.tools) == set(adjacent.tools.TOOL_HANDLERS)
    assert len(fake_ctx.skills) == 11
    assert fake_ctx.hooks[0][0] == "pre_tool_call"
    assert "adjacent" in fake_ctx.commands


def test_register_tool_uses_documented_kwargs(fake_ctx):
    adjacent.register(fake_ctx)
    for name, entry in fake_ctx.tools.items():
        assert entry["toolset"] == "adjacent", f"{name} missing toolset=adjacent"
        assert entry["description"], f"{name} missing description="
        schema = entry["schema"]
        # Documented schema shape: name + description + parameters.
        assert schema["name"] == name
        assert isinstance(schema["description"], str) and schema["description"]
        params = schema["parameters"]
        assert params.get("type") == "object"
        assert isinstance(params.get("properties"), dict)


def test_registered_tool_handlers_match_documented_signature(fake_ctx):
    adjacent.register(fake_ctx)
    for name, entry in fake_ctx.tools.items():
        handler = entry["handler"]
        assert callable(handler)
        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        # First positional param is `args` (the LLM parameter dict).
        assert params[0].name == "args"
        # Accepts **kwargs for forward compatibility.
        assert any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
        # Handler returns a JSON string even on empty input.
        out = handler({})
        assert isinstance(out, str)
        import json

        json.loads(out)


def test_registered_skill_paths_exist(fake_ctx):
    adjacent.register(fake_ctx)
    # register_skill(name, path): the recorded value is the path string.
    for name, path in fake_ctx.skills.items():
        assert isinstance(path, str)
        p = Path(path)
        assert p.exists(), f"skill {name} SKILL.md missing at {p}"
        assert p.name == "SKILL.md"


def test_command_handler_is_callable_raw_args_string(fake_ctx):
    adjacent.register(fake_ctx)
    entry = fake_ctx.commands["adjacent"]
    handler = entry["handler"]
    assert callable(handler)
    assert isinstance(entry["description"], str) and entry["description"]
    # The handler receives a raw argument string and returns a string.
    out = handler("")
    assert isinstance(out, str)
    out = handler("--explain")
    assert isinstance(out, str)
    assert "workflow" in out


def test_command_handler_does_not_shell_interpolate(fake_ctx):
    # Malicious raw input must never reach a shell. The handler parses a
    # pure-Python flag grammar and dispatches to a tool handler with a
    # dict; an unknown workflow returns help text, not a shell command.
    adjacent.register(fake_ctx)
    handler = fake_ctx.commands["adjacent"]["handler"]
    nasty = "workflow portfolio_snapshot --index $(rm -rf /); echo pwned"
    out = handler(nasty)
    assert isinstance(out, str)
    # The index slug pattern rejects the shell metacharacters, so the
    # tool returns an invalid-argument error, never executing a shell.
    import json

    payload = json.loads(out)
    assert payload["ok"] is False
    assert "invalid arguments" in payload["error"]


def test_hook_handler_is_callable(fake_ctx):
    adjacent.register(fake_ctx)
    _event, handler = fake_ctx.hooks[0]
    assert callable(handler)
    decision = handler({"tool_name": "Write", "tool_input": {"content": "ok"}})
    assert decision["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_register_is_idempotent(fake_ctx):
    adjacent.register(fake_ctx)
    first_tools = set(fake_ctx.tools)
    first_skills = set(fake_ctx.skills)
    adjacent.register(fake_ctx)
    assert set(fake_ctx.tools) == first_tools
    assert set(fake_ctx.skills) == first_skills


def test_bundled_skills_dir_matches_registry():
    skills_dir = _plugin_dir() / "skills"
    for name, rel in adjacent.BUNDLED_SKILLS.items():
        assert (skills_dir / rel).exists(), f"{name}: {rel} missing"

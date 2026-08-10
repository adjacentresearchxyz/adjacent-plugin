"""test_hooks.py - unit tests for the Adjacent pre_tool_call hook.

Exercises allow/deny decisions and the false-positive guards (the hook
must NOT block arbitrary tool input, only write-capable content).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import adjacent  # noqa: E402
from adjacent import hooks as H

EM = chr(0x2014)  # em-dash
BULLET = chr(0x2022)  # unicode bullet


def _payload(tool, **fields):
    return {"tool_name": tool, "tool_input": fields}


# --- allow cases ---------------------------------------------------------


def test_allow_clean_write():
    d = H.pre_tool_call(_payload("Write", content="hello world - 4% move"))
    assert d["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_allow_non_write_tool_ignores_forbidden_codepoints():
    # Bash command carrying an em-dash must NOT be blocked: the hook
    # only scans write-capable content, not arbitrary tool input.
    d = H.pre_tool_call(_payload("Bash", command=f"echo 'a{EM}b'"))
    assert d["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_allow_write_with_no_content():
    d = H.pre_tool_call(_payload("Write", path="x.txt"))
    assert d["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_pp_not_false_positive_on_words():
    # "approach" / "happen" contain "pp" but are not numeric tokens.
    d = H.pre_tool_call(_payload("Write", content="the approach happened at 12:00"))
    assert d["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_ascii_range_with_percent_allowed():
    d = H.pre_tool_call(_payload("Write", content="range 4-7% drift -0.42%"))
    assert d["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_secret_redactor_blocks_raw_secret_in_write():
    d = H.pre_tool_call(
        _payload("Write", content="key = 'sk_live_12345678901234567890'")
    )
    assert d["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "raw secret" in d["hookSpecificOutput"]["permissionDecisionReason"]


def test_secret_redactor_allows_env_template():
    d = H.pre_tool_call(
        _payload("Write", content="key = process.env.ADJACENT_API_KEY")
    )
    assert d["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_chart_style_denies_generic_palette():
    d = H.pre_tool_call(_payload("Write", content="sns.set_palette('viridis')"))
    assert d["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "chart-style" in d["hookSpecificOutput"]["permissionDecisionReason"]


def test_chart_style_allows_adjacent_aware():
    d = H.pre_tool_call(
        _payload("Write", content="import adjacent_chart_style as adj")
    )
    assert d["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_pre_tool_call_combines_all_checks():
    secret = H.pre_tool_call(
        _payload("Write", content="sk_live_12345678901234567890")
    )
    clean = H.pre_tool_call(_payload("Write", content="clean content"))
    assert secret["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert clean["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_post_tool_call_logs_mover(tmp_path, monkeypatch):
    monkeypatch.setattr(H, "LOG_PATH", str(tmp_path / "movers.log"))
    result = H.post_tool_call(
        {
            "tool_name": "mcp__adjacent-markets-dev__price",
            "tool_response": {"slug": "demo", "moves": {"1d": 0.02}},
        }
    )
    assert result is not None
    assert "additionalContext" in result["hookSpecificOutput"]
    assert "demo 1d" in Path(H.LOG_PATH).read_text(encoding="utf-8")


# --- deny cases ----------------------------------------------------------


def test_deny_em_dash():
    d = H.pre_tool_call(_payload("Write", content=f"price{EM}drop"))
    assert d["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "em-dash" in d["hookSpecificOutput"]["permissionDecisionReason"]


def test_deny_unicode_bullet():
    d = H.pre_tool_call(_payload("Write", content=f"{BULLET} item one"))
    assert d["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "unicode bullet" in d["hookSpecificOutput"]["permissionDecisionReason"]


def test_deny_pp_numeric():
    d = H.pre_tool_call(_payload("Write", content="tracking -0.42pp vs index"))
    assert d["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "pp" in d["hookSpecificOutput"]["permissionDecisionReason"]


def test_deny_pp_with_space():
    d = H.pre_tool_call(_payload("Write", content="move of 1.5 pp today"))
    assert d["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_deny_emoji():
    d = H.pre_tool_call(_payload("Write", content="bullish \U0001F680"))
    assert d["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "emoji" in d["hookSpecificOutput"]["permissionDecisionReason"]


def test_deny_multiedit_edits_field():
    d = H.pre_tool_call(
        _payload("MultiEdit", edits=[{"new_string": f"a{EM}b"}, {"new_string": "ok"}])
    )
    assert d["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_deny_lists_all_findings():
    d = H.pre_tool_call(_payload("Write", content=f"{BULLET} {EM} 1pp"))
    reason = d["hookSpecificOutput"]["permissionDecisionReason"]
    assert "unicode bullet" in reason
    assert "em-dash" in reason
    assert "pp" in reason


# --- CLI main entry ------------------------------------------------------


def test_main_allow(tmp_path, monkeypatch):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_payload("Write", content="ok"))))
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    rc = H.main()
    assert rc == 0
    out = json.loads(buf.getvalue())
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_main_unreadable_payload(tmp_path, monkeypatch):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    rc = H.main()
    assert rc == 0
    out = json.loads(buf.getvalue())
    # Fail-open on unreadable payload.
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


# --- self-cleanliness ----------------------------------------------------


def test_hook_source_is_byte_clean():
    # The hook must not contain the codepoints it forbids, so it does
    # not self-block.
    src = Path(H.__file__).read_text(encoding="utf-8")
    assert EM not in src
    assert BULLET not in src

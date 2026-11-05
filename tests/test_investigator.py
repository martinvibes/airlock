"""The headless investigator runner, with a fake `claude`. No model, no server."""

from __future__ import annotations

from pathlib import Path

import pytest

from airlock import investigator as inv_mod
from airlock.investigator import Investigator, claude_command, scrub, split_reply

STATE = {
    "switch_url": "http://127.0.0.1:9",
    "companies": {
        "kudimart": {
            "party": "merchant",
            "workspace": "/nonexistent/kudimart",
            "private_room": "!k",
            "user": {"name": "KudiMart Engineer"},
            "agents": {
                "customs": {"id": "c1", "name": "kudimart-customs-t9", "api_key": "x"},
                "investigator": {"id": "i1", "name": "kudimart-investigator-t9", "api_key": "x"},
            },
            "participants": {"engineer": ["@eng"], "customs": ["@cus"], "investigator": ["@inv"]},
        },
        "paylane": {"party": "provider", "agents": {}, "participants": {}},
    },
}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(inv_mod, "STATE", tmp_path)
    posted: list[str] = []
    calls: list[list[str]] = []
    replies: list[dict] = []

    def runner(cmd: list[str], cwd: Path) -> dict:
        calls.append(cmd)
        out = replies.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    i = Investigator("kudimart", STATE, runner=runner, post=posted.append)
    i.session_file = tmp_path / "session.txt"
    return i, posted, calls, replies


def msg(sender: str, body: str, **kw) -> dict:
    return {"sender": sender, "body": body, "sender_name": sender, **kw}


def test_command_is_read_only_and_isolated():
    cmd = claude_command("hi", "s-1", "sonnet")
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    denied = cmd[cmd.index("--disallowedTools") + 1:cmd.index("--resume")]
    for tool in ("Bash", "Edit", "Write", "WebFetch", "WebSearch", "Task"):
        assert tool in denied
    assert "--allowedTools" not in cmd  # a blanket Read allow would reach outside the folder
    assert "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--setting-sources") + 1] == "project,local"
    assert cmd[cmd.index("--resume") + 1] == "s-1"


def test_split_reply_posts_each_proposal_to_the_real_customs_name():
    text = (
        "Only pod-canary-1 rejects webhooks.\n"
        '@kudimart-customs propose {"kind":"finding","code":"merchant_verifier_reads_primary_header_only"}\n'
        '`@kudimart-customs propose {"kind":"timeline_event","event":"verifier_deployed","at":"2026-11-03T09:12:00Z","version":"v2.14.0"}`'
    )
    prose, proposals = split_reply(text, "kudimart-customs-t9")
    assert prose == "Only pod-canary-1 rejects webhooks."
    assert proposals == [
        '@kudimart-customs-t9 propose {"kind":"finding","code":"merchant_verifier_reads_primary_header_only"}',
        '@kudimart-customs-t9 propose {"kind":"timeline_event","event":"verifier_deployed","at":"2026-11-03T09:12:00Z","version":"v2.14.0"}',
    ]


def test_scrub_removes_references_and_phones():
    out = scrub("order KDM-498150-0001 for +2348002156670 and 2348002156670")
    assert "KDM-" not in out and "800215" not in out


def test_wakes_only_when_asked(world):
    i, *_ = world
    assert i.wants(msg("@eng", "@kudimart-investigator-t9 why the 401s?"))
    assert i.wants(msg("@cus", "@kudimart-investigator-t9 From paylane, validated by Customs."))
    assert not i.wants(msg("@inv", "@kudimart-investigator-t9 talking to myself"))
    assert not i.wants(msg("@eng", "release 1", addressed=True))  # a Customs command
    assert not i.wants(msg("@cus", "Claim 1 queued, not sent", addressed=True))
    assert not i.wants(msg("@eng", "@kudimart-investigator-t9 hi", switch_notice=True))
    assert i.wants(msg("@eng", "what changed at 09:12?", addressed=True))
    assert i.wants(msg("@bridge", "what changed?", addressed=True, sender_kind="platform", on_behalf_of="@eng"))


def test_answer_posts_prose_then_one_message_per_proposal_and_keeps_session(world):
    i, posted, calls, replies = world
    replies.append({"result": "Canary pod, v2.14.0.\n@kudimart-customs propose {\"kind\":\"finding\","
                              "\"code\":\"merchant_verifier_reads_primary_header_only\"}",
                    "session_id": "s-1"})
    i.answer([msg("@eng", "@kudimart-investigator-t9 look")])
    assert posted == ["Canary pod, v2.14.0.",
                      '@kudimart-customs-t9 propose {"kind":"finding","code":"merchant_verifier_reads_primary_header_only"}']
    assert "--resume" not in calls[0]
    assert "[KudiMart engineer]" in calls[0][2] and "@kudimart-investigator-t9" not in calls[0][2]

    replies.append({"result": "Nothing new.", "session_id": "s-1"})
    i.answer([msg("@cus", "@kudimart-investigator-t9 From paylane, validated by Customs.")])
    assert calls[1][calls[1].index("--resume") + 1] == "s-1"
    assert "forwarding a validated claim from Paylane" in calls[1][2]


def test_a_lost_session_starts_fresh(world):
    i, posted, calls, replies = world
    i.session_file.write_text("gone")
    replies.extend([RuntimeError("no such session"), {"result": "ok", "session_id": "s-2"}])
    i.answer([msg("@eng", "@kudimart-investigator-t9 look")])
    assert "--resume" in calls[0] and "--resume" not in calls[1]
    assert i.session_file.read_text() == "s-2" and posted == ["ok"]

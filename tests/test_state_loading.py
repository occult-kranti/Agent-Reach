import json

import pytest

from agent_reach.runtime import state
from agent_reach.runtime.result import ReachError


@pytest.mark.parametrize("raw_json", ["null", "[]", '["unexpected"]', "42", "true", '"unexpected"'])
def test_non_object_ledger_recovers_without_rewriting_it(raw_json):
    path = state.state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw_json, encoding="utf-8")
    saved = state.load()
    assert saved["version"] == state.STATE_VERSION
    assert saved["channels"] == {}
    assert saved["skill"]["links"] == []
    assert path.read_text(encoding="utf-8") == raw_json


def test_valid_ledger_keeps_channel_and_extension_data():
    data = {"channels": {"reddit": {"added_at": "2026-11-01T00:00:00Z"}}, "custom": [1, 2]}
    path = state.state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    saved = state.load()
    assert saved["channels"] == data["channels"]
    assert saved["custom"] == data["custom"]


def test_missing_ledger_still_loads_defaults():
    assert state.load()["channels"] == {}


def test_invalid_json_still_loads_defaults():
    path = state.state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", encoding="utf-8")
    assert state.load()["channels"] == {}


@pytest.mark.parametrize("key", ["channels", "tools", "checks", "skill", "owned_paths"])
@pytest.mark.parametrize("value", [None, [], "private-value", 0, False])
def test_malformed_ledger_container_fails_closed_without_rewriting(key, value):
    path = state.state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({key: value, "custom": {"keep": "unchanged"}})
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(ReachError) as caught:
        state.load()

    assert caught.value.code == "BAD_INPUT"
    assert key in caught.value.message
    assert "private-value" not in caught.value.message
    assert path.read_text(encoding="utf-8") == raw


@pytest.mark.parametrize("key", ["links", "unlinked"])
@pytest.mark.parametrize("value", [None, {}, "private-value", 0, False])
def test_malformed_skill_list_fails_closed_without_discarding_preferences(key, value):
    path = state.state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({"skill": {key: value}})
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(ReachError) as caught:
        state.load()

    assert caught.value.code == "BAD_INPUT"
    assert f"skill.{key}" in caught.value.message
    assert path.read_text(encoding="utf-8") == raw


def test_malformed_ownership_ledger_prevents_mutation():
    path = state.state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = '{"owned_paths": ["config.yaml"]}'
    path.write_text(raw, encoding="utf-8")
    changes = []

    with pytest.raises(ReachError, match="owned_paths"):
        state.mutate(lambda data: changes.append(data))

    assert changes == []
    assert path.read_text(encoding="utf-8") == raw


@pytest.mark.parametrize("key,value", [
    ("skill", None),
    ("checks", "private-value"),
    ("owned_paths", ["config.yaml"]),
])
def test_doctor_text_reports_bad_state_on_stderr_without_rewriting(key, value, capsys):
    from agent_reach.runtime import cli

    path = state.state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({key: value})
    path.write_text(raw, encoding="utf-8")

    assert cli.main(["doctor", "--text"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"BAD_INPUT: Invalid state.json: {key} must be an object\n")
    assert "Restore" in captured.err
    assert "private-value" not in captured.err
    assert "Traceback" not in captured.err
    assert path.read_text(encoding="utf-8") == raw


def test_doctor_text_success_output_is_unchanged(monkeypatch, capsys):
    from agent_reach import __version__
    from agent_reach.runtime import cli, manage

    monkeypatch.setattr(manage, "_channels", lambda: [])
    assert cli.main(["doctor", "--text"]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"Agent Reach {__version__}\n\n"
    assert captured.err == ""
    assert not state.state_path().exists()

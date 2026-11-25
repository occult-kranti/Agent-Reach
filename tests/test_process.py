from agent_reach.utils import process
from agent_reach.utils.process import utf8_subprocess_env, windows_hidden_kwargs


def test_utf8_subprocess_env_forces_python_utf8():
    env = utf8_subprocess_env({"PYTHONUTF8": "0", "OTHER": "value"})

    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["OTHER"] == "value"


def test_explicit_empty_environment_does_not_inherit_parent(monkeypatch):
    monkeypatch.setenv("REACH_TEST_PARENT_ONLY", "not-for-child")

    assert utf8_subprocess_env({}) == {
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }


def test_default_environment_inherits_parent_without_mutating_it(monkeypatch):
    monkeypatch.setenv("REACH_TEST_PARENT_ONLY", "for-child")
    monkeypatch.setenv("PYTHONUTF8", "0")

    env = utf8_subprocess_env()

    assert env["REACH_TEST_PARENT_ONLY"] == "for-child"
    assert env["PYTHONUTF8"] == "1"
    assert process.os.environ["PYTHONUTF8"] == "0"


def test_explicit_environment_is_copied_without_parent_keys(monkeypatch):
    monkeypatch.setenv("REACH_TEST_PARENT_ONLY", "not-for-child")
    base = {"PYTHONUTF8": "0", "OTHER": "value"}

    env = utf8_subprocess_env(base)

    assert "REACH_TEST_PARENT_ONLY" not in env
    assert base == {"PYTHONUTF8": "0", "OTHER": "value"}
    env["OTHER"] = "changed"
    assert base["OTHER"] == "value"


def test_windows_hidden_kwargs_is_empty_on_non_windows(monkeypatch):
    monkeypatch.setattr(process.sys, "platform", "linux")

    assert windows_hidden_kwargs() == {}


def test_windows_hidden_kwargs_hides_windows_console_without_detaching(monkeypatch):
    monkeypatch.setattr(process.sys, "platform", "win32")
    monkeypatch.setattr(process.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(process.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200, raising=False)
    monkeypatch.setattr(process.subprocess, "DETACHED_PROCESS", 0x00000008, raising=False)

    flags = windows_hidden_kwargs()["creationflags"]

    assert flags & process.subprocess.CREATE_NO_WINDOW
    assert flags & process.subprocess.CREATE_NEW_PROCESS_GROUP
    assert flags & process.subprocess.DETACHED_PROCESS == 0

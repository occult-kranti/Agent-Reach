#!/usr/bin/env python3
"""Focused offline regression checks using the standard-library unittest runner.

Run from any directory with: python3 /path/to/Agent-Reach/scripts/validate_hardening.py
The project itself still needs its existing import dependencies (notably PyYAML).
This script installs nothing and is not a replacement for the repository pytest,
lint, type-check, packaging, or live-platform suites.
"""

from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPOSITORY = Path(__file__).resolve().parents[1]
PROJECT = SimpleNamespace()


def _forbid_external_io(stack: ExitStack, attempts: list[str]) -> None:
    """Block HTTP, DNS, loopback/Unix sockets, listeners, and child processes."""
    def forbid(label):
        def blocked(*args, **kwargs):
            attempts.append(label)
            # Do not print arguments: a failing call could contain credentials.
            raise AssertionError(f"Offline validation forbids {label}")
        return blocked

    targets = [
        (urllib.request, "urlopen"),
        (urllib.request.OpenerDirector, "open"),
        (socket, "create_connection"),
        (socket, "getaddrinfo"),
        (socket, "gethostbyname"),
        (socket, "gethostbyname_ex"),
        (socket, "socketpair"),
        (socket.socket, "connect"),
        (socket.socket, "connect_ex"),
        (socket.socket, "bind"),
        (socket.socket, "listen"),
        (socket.socket, "sendto"),
        (subprocess, "Popen"),
        (subprocess, "run"),
        (subprocess, "call"),
        (subprocess, "check_call"),
        (subprocess, "check_output"),
        (os, "system"),
        (os, "popen"),
    ]
    for name in ("fork", "forkpty", "posix_spawn", "posix_spawnp", "spawnl", "spawnle",
                 "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
                 "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe"):
        if hasattr(os, name):
            targets.append((os, name))
    if hasattr(socket.socket, "sendmsg"):
        targets.append((socket.socket, "sendmsg"))
    for owner, name in targets:
        label = f"{getattr(owner, '__name__', type(owner).__name__)}.{name}"
        stack.enter_context(patch.object(owner, name, side_effect=forbid(label)))


class ContainedCase(unittest.TestCase):
    """Keep application state in a fresh directory; never replace HOME."""

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temporary = self.stack.enter_context(tempfile.TemporaryDirectory(
            prefix="case-", dir=PROJECT.containment))
        self.root = Path(temporary) / ".agent-reach"
        self.root.mkdir(mode=0o700)
        self.stack.enter_context(patch.object(PROJECT.state, "root", return_value=self.root))
        self.stack.enter_context(patch.object(PROJECT.Config, "CONFIG_DIR", self.root))
        self.stack.enter_context(patch.object(PROJECT.Config, "CONFIG_FILE", self.root / "config.yaml"))

    def write_ledger(self, value) -> str:
        raw = json.dumps(value, ensure_ascii=False)
        PROJECT.state.state_path().write_text(raw, encoding="utf-8")
        return raw

    def run_raw_cli(self, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        # The real CLI may extend PATH or set proxy bypasses. Restore those
        # changes afterwards without assigning a replacement HOME.
        with patch.dict(os.environ), redirect_stdout(stdout), redirect_stderr(stderr):
            code = PROJECT.cli.main(list(arguments))
        return code, stdout.getvalue(), stderr.getvalue()

    def run_cli(self, *arguments):
        code, stdout, stderr = self.run_raw_cli(*arguments)
        lines = stdout.splitlines()
        self.assertEqual(len(lines), 1, "CLI must emit exactly one JSON object")
        self.assertEqual(stderr, "")
        return code, json.loads(lines[0]), stdout


class EnvironmentChecks(ContainedCase):
    def test_explicit_empty_environment_excludes_parent(self):
        with patch.object(os, "environ", {"REACH_TEST_PARENT_ONLY": "synthetic-secret"}):
            actual = PROJECT.process.utf8_subprocess_env({})
        self.assertEqual(actual, {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})

    def test_default_environment_is_an_independent_copy(self):
        parent = {"REACH_TEST_PARENT_ONLY": "synthetic-value", "PYTHONUTF8": "0"}
        with patch.object(os, "environ", parent):
            actual = PROJECT.process.utf8_subprocess_env()
        self.assertEqual(actual["REACH_TEST_PARENT_ONLY"], "synthetic-value")
        self.assertEqual(actual["PYTHONUTF8"], "1")
        self.assertEqual(parent["PYTHONUTF8"], "0")
        actual["REACH_TEST_PARENT_ONLY"] = "changed"
        self.assertEqual(parent["REACH_TEST_PARENT_ONLY"], "synthetic-value")

    def test_explicit_environment_is_copied_without_parent_keys(self):
        supplied = {"OTHER": "kept", "PYTHONUTF8": "0"}
        with patch.object(os, "environ", {"REACH_TEST_PARENT_ONLY": "synthetic-secret"}):
            actual = PROJECT.process.utf8_subprocess_env(supplied)
        self.assertEqual(actual, {"OTHER": "kept", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
        actual["OTHER"] = "changed"
        self.assertEqual(supplied, {"OTHER": "kept", "PYTHONUTF8": "0"})


class StateChecks(ContainedCase):
    def test_malformed_containers_fail_closed_without_rewriting_or_leaking(self):
        for key in ("channels", "tools", "checks", "skill", "owned_paths"):
            for value in (None, [], "synthetic-private-value", 0, False):
                with self.subTest(field=key, value_type=type(value).__name__):
                    raw = self.write_ledger({key: value, "custom": {"keep": True}})
                    with self.assertRaises(PROJECT.ReachError) as caught:
                        PROJECT.state.load()
                    self.assertEqual(caught.exception.code, "BAD_INPUT")
                    self.assertIn(key, caught.exception.message)
                    self.assertNotIn("synthetic-private-value", caught.exception.message)
                    self.assertEqual(PROJECT.state.state_path().read_text(encoding="utf-8"), raw)

    def test_malformed_skill_lists_preserve_preferences(self):
        for key in ("links", "unlinked"):
            for value in (None, {}, "synthetic-private-value", 0, False):
                with self.subTest(field=key, value_type=type(value).__name__):
                    raw = self.write_ledger({"skill": {key: value}})
                    with self.assertRaises(PROJECT.ReachError) as caught:
                        PROJECT.state.load()
                    self.assertEqual(caught.exception.code, "BAD_INPUT")
                    self.assertIn("skill." + key, caught.exception.message)
                    self.assertNotIn("synthetic-private-value", caught.exception.message)
                    self.assertEqual(PROJECT.state.state_path().read_text(encoding="utf-8"), raw)

    def test_bad_ownership_prevents_the_mutation_callback(self):
        raw = self.write_ledger({"owned_paths": ["config.yaml"]})
        changes = []
        with self.assertRaises(PROJECT.ReachError) as caught:
            PROJECT.state.mutate(lambda data: changes.append(data))
        self.assertEqual(caught.exception.code, "BAD_INPUT")
        self.assertEqual(changes, [])
        self.assertEqual(PROJECT.state.state_path().read_text(encoding="utf-8"), raw)

    def test_valid_extension_data_and_missing_defaults_are_preserved(self):
        initial = {
            "channels": {"reddit": {"added_at": "2026-11-01T00:00:00Z"}},
            "skill": {"unlinked": ["/synthetic/opted-out"]},
            "custom": {"nested": [1, 2]},
        }
        raw = self.write_ledger(initial)
        actual = PROJECT.state.load()
        self.assertEqual(actual["channels"], initial["channels"])
        self.assertEqual(actual["custom"], initial["custom"])
        self.assertEqual(actual["skill"]["unlinked"], initial["skill"]["unlinked"])
        self.assertEqual(actual["skill"]["links"], [])
        self.assertEqual(actual["tools"], {})
        self.assertEqual(actual["checks"], {})
        self.assertEqual(PROJECT.state.state_path().read_text(encoding="utf-8"), raw)


class CliChecks(ContainedCase):
    def test_real_doctor_dispatch_emits_one_structured_error(self):
        for key, value in (("skill", None), ("checks", "synthetic-private-value"),
                           ("owned_paths", ["config.yaml"])):
            with self.subTest(field=key):
                raw = self.write_ledger({key: value})
                code, payload, rendered = self.run_cli("doctor")
                self.assertEqual(code, 1)
                self.assertEqual(payload["schema_version"], 1)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["action"], "doctor")
                self.assertIsNone(payload["result"])
                self.assertEqual(payload["error"]["code"], "BAD_INPUT")
                self.assertIn(key, payload["error"]["message"])
                self.assertNotIn("synthetic-private-value", rendered)
                self.assertEqual(PROJECT.state.state_path().read_text(encoding="utf-8"), raw)

    def test_text_doctor_reports_bad_ledger_without_traceback(self):
        for key, value in (("skill", None), ("checks", "synthetic-private-value"),
                           ("owned_paths", ["config.yaml"])):
            with self.subTest(field=key):
                raw = self.write_ledger({key: value})
                code, stdout, stderr = self.run_raw_cli("doctor", "--text")
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertTrue(stderr.startswith(f"BAD_INPUT: Invalid state.json: {key} must be an object\n"))
                self.assertIn("Restore", stderr)
                self.assertNotIn("synthetic-private-value", stderr)
                self.assertNotIn("Traceback", stderr)
                self.assertEqual(PROJECT.state.state_path().read_text(encoding="utf-8"), raw)

    def test_text_doctor_preserves_successful_output(self):
        with patch.object(PROJECT.manage, "_channels", return_value=[]):
            code, stdout, stderr = self.run_raw_cli("doctor", "--text")
        self.assertEqual(code, 0)
        self.assertEqual(stdout, f"Agent Reach {PROJECT.manage.__version__}\n\n")
        self.assertEqual(stderr, "")
        self.assertFalse(PROJECT.state.state_path().exists())

    def test_read_only_registry_and_version_commands_do_not_create_state(self):
        before = list(self.root.iterdir())
        code, version, _ = self.run_cli("version")
        self.assertEqual(code, 0)
        self.assertTrue(version["ok"])
        code, registry, _ = self.run_cli("channels")
        self.assertEqual(code, 0)
        self.assertTrue(registry["ok"])
        names = [row["name"] for row in registry["channels"]]
        self.assertTrue(names)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(list(self.root.iterdir()), before)


class DoctorChecks(ContainedCase):
    def prepare_channels(self, count=1, *, passed=False):
        class OfflineChannel(PROJECT.Channel):
            level = "default"
            actions = (PROJECT.Action("search", "offline fixture", (), (("fixture", "_unused"),)),)

            def can_handle(self, url):
                return False

        channels = [OfflineChannel() for _ in range(count)]
        for index, channel in enumerate(channels):
            channel.name = f"offline_{index}"
        self.stack.enter_context(patch.object(PROJECT.manage, "_channels", return_value=channels))
        data = {"checks": {}}
        for channel in channels:
            data["checks"][channel.name] = {
                "at": PROJECT.state.now(), "actions": {"search": passed},
                "previous": {"search": True},
                "evidence": {"search": {"at": PROJECT.state.now(),
                                         "fingerprint": PROJECT.manage.fingerprint(channel.name)}},
            }
        PROJECT.state.save(data)
        return channels

    def test_expiry_and_regression_agree_and_next_report_reevaluates(self):
        self.prepare_channels()
        expired = PROJECT.manage.CHECK_FRESH_SECONDS + 1
        for ages in ((0, expired), (expired, 0)):
            with self.subTest(ages=ages), patch.object(PROJECT.state, "age_seconds", side_effect=ages):
                outputs = [PROJECT.manage.doctor()["channels"][0] for _ in range(2)]
                for age, output in zip(ages, outputs):
                    self.assertEqual(output["status"], "broken" if age == 0 else "unverified")
                    self.assertEqual(output["regressed"], age == 0)

    def test_each_checked_channel_computes_one_fingerprint_per_report(self):
        channels = self.prepare_channels(count=14, passed=True)
        with patch.object(PROJECT.manage, "fingerprint", wraps=PROJECT.manage.fingerprint) as compute:
            output = PROJECT.manage.doctor()
        self.assertEqual(len(output["channels"]), len(channels))
        self.assertTrue(all(row["status"] == "ready" for row in output["channels"]))
        self.assertEqual(compute.call_count, len(channels))


def main() -> int:
    sys.path.insert(0, str(REPOSITORY))
    attempts: list[str] = []
    with ExitStack() as stack:
        PROJECT.containment = Path(stack.enter_context(tempfile.TemporaryDirectory(
            prefix="agent-reach-hardening-")))
        _forbid_external_io(stack, attempts)

        # Install path guards before importing browser/channel modules: browser
        # configuration is evaluated at module import, not just in main().
        from agent_reach.utils import paths

        bootstrap = PROJECT.containment / "bootstrap"
        stack.enter_context(patch.object(paths, "home_dir", return_value=bootstrap))
        read_small = paths.read_small_text_no_follow

        def contained_read(path, *args, **kwargs):
            if not Path(path).absolute().is_relative_to(PROJECT.containment):
                attempts.append("application state read outside temporary directory")
                raise AssertionError("Application state reads must stay in the temporary directory")
            return read_small(path, *args, **kwargs)

        stack.enter_context(patch.object(paths, "read_small_text_no_follow", side_effect=contained_read))
        from agent_reach.config import Config

        PROJECT.Config = Config
        stack.enter_context(patch.object(Config, "CONFIG_DIR", bootstrap / ".agent-reach"))
        stack.enter_context(patch.object(Config, "CONFIG_FILE", bootstrap / ".agent-reach" / "config.yaml"))

        from agent_reach.channels.base import Action, Channel
        from agent_reach.runtime import cli, manage, state
        from agent_reach.runtime.result import ReachError
        from agent_reach.utils import process

        PROJECT.Action, PROJECT.Channel = Action, Channel
        PROJECT.cli, PROJECT.manage, PROJECT.state = cli, manage, state
        PROJECT.ReachError, PROJECT.process = ReachError, process
        stack.enter_context(patch.object(state, "root", return_value=bootstrap / ".agent-reach"))
        suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        if attempts:
            # Surface even guarded calls swallowed by production error handlers.
            print("Forbidden I/O attempted: " + ", ".join(sorted(set(attempts))), file=sys.stderr)
            return 1
        print("Offline guards: zero network, socket, subprocess, or external state-read attempts.")
        print("Scope: focused unittest checks only; full pytest/lint/type/live suites were not run.")
        return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

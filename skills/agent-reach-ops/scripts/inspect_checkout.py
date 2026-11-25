#!/usr/bin/env python3
"""Inspect an Agent Reach checkout without importing or running its code.

Uses only the Python standard library and a read-only ``git rev-parse``.
It never reads the user's Agent Reach configuration or browser sessions.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from pathlib import Path

MAX_SOURCE_BYTES = 2 * 1024 * 1024


def read_source(root: Path, relative: str) -> str:
    path = root / relative
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError(f"Source escapes the checkout: {relative}")
    if not resolved.is_file() or resolved.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError(f"Expected a small source file: {relative}")
    return resolved.read_text(encoding="utf-8")


def literal(node: ast.AST | None, default=None):
    try:
        return ast.literal_eval(node) if node is not None else default
    except (ValueError, TypeError, SyntaxError):
        return default


def assignments(body: list[ast.stmt]) -> dict[str, ast.AST]:
    found = {}
    for node in body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                found[node.target.id] = node.value
    return found


def inspect(root: Path) -> dict:
    project = read_source(root, "pyproject.toml")
    section = re.search(r"(?ms)^\[project\]\s*\n(.*?)(?=^\[|\Z)", project)
    if section is None:
        raise ValueError("Missing [project] metadata")
    metadata = {}
    for key in ("name", "version", "requires-python"):
        match = re.search(rf'(?m)^{re.escape(key)}\s*=\s*"([^"\n]+)"\s*$', section[1])
        metadata[key] = match[1] if match else None

    registry = ast.parse(read_source(root, "agent_reach/channels/__init__.py"))
    entries = assignments(registry.body).get("ALL_CHANNELS")
    if not isinstance(entries, (ast.List, ast.Tuple)):
        raise ValueError("Channel registry is dynamic or unrecognized; inspect it manually")
    registered = [item.func.id for item in entries.elts
                  if isinstance(item, ast.Call) and isinstance(item.func, ast.Name)]
    if len(registered) != len(entries.elts):
        raise ValueError("Channel registry contains dynamic entries; inspect it manually")

    classes = {}
    for source_path in sorted((root / "agent_reach/channels").glob("*.py")):
        tree = ast.parse(read_source(root, source_path.relative_to(root).as_posix()))
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef) or cls.name not in registered:
                continue
            fields = assignments(cls.body)
            actions_node = fields.get("actions")
            actions = []
            if isinstance(actions_node, (ast.Tuple, ast.List)):
                for action in actions_node.elts:
                    if not (isinstance(action, ast.Call) and isinstance(action.func, ast.Name)
                            and action.func.id == "Action" and len(action.args) >= 4):
                        raise ValueError(f"Dynamic action in {cls.name}; inspect it manually")
                    backends = literal(action.args[3], [])
                    public = next((literal(kw.value, []) for kw in action.keywords
                                   if kw.arg == "public_web"), [])
                    actions.append({"name": literal(action.args[0]),
                                    "backends": [row[0] for row in backends],
                                    "public_web": list(public)})
            classes[cls.name] = {"name": literal(fields.get("name")),
                                 "level": literal(fields.get("level"), "unknown/inherited"),
                                 "actions": actions,
                                 "source": source_path.relative_to(root).as_posix()}
    missing = sorted(set(registered) - classes.keys())
    if missing:
        raise ValueError(f"Registered classes not found: {', '.join(missing)}")
    channels = [classes[name] for name in registered]
    levels = {}
    for channel in channels:
        levels[channel["level"]] = levels.get(channel["level"], 0) + 1

    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
                            capture_output=True, text=True, timeout=5, check=False)
    commit = result.stdout.strip() if result.returncode == 0 else None
    if commit is not None and re.fullmatch(r"[0-9a-f]{40,64}", commit) is None:
        raise ValueError("Unexpected Git revision output")
    return {"schema_version": 1, "ok": True, "inspection": "static; target code not executed",
            "commit": commit, "package": metadata, "channel_count": len(channels),
            "levels": levels, "channels": channels,
            "review": {"source_is_trusted": "not established by this inventory",
                       "session_reuse_review_required": (root / "agent_reach/runtime/session_reuse.py").exists(),
                       "install_from": "reviewed GitHub source; never the same-named PyPI project",
                       "live_platform_status": "not tested"}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--require-commit", help="Expected full immutable Git SHA")
    args = parser.parse_args()
    if args.require_commit and not re.fullmatch(r"[0-9a-fA-F]{40,64}", args.require_commit):
        parser.error("--require-commit requires a full 40- or 64-character hexadecimal SHA")
    try:
        root = args.checkout.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Checkout must be a directory")
        result = inspect(root)
        if args.require_commit:
            result["revision_matches"] = result["commit"] == args.require_commit.lower()
            result["ok"] = result["revision_matches"]
            if not result["ok"]:
                result["error"] = "Checkout revision differs from the required baseline"
    except (OSError, ValueError, SyntaxError, subprocess.TimeoutExpired) as exc:
        result = {"schema_version": 1, "ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify and benchmark URL validation offline using only the standard library.

This measures the normalization helper, not the CLI, HTTP, DNS, or platform
backends. The baseline is fixed to the reviewed upstream commit and additionally
verified by SHA-256 before its module is evaluated. No user-supplied Git ref or
source file is accepted. The complete upstream commit must exist in local Git.

Run from any directory:
    python3 scripts/benchmark_url_validation.py --iterations 3000 --repeats 5
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import timeit
import types
from pathlib import Path

BASELINE_COMMIT = "8d9ecc1f5521fe7d223cde782aaa4005695e2671"
MODULE_PATH = "agent_reach/utils/url.py"
BASELINE_SHA256 = "a5ad76ecc4ca641d497b01cc7e90f573c137d2e7acac4c45ade519b6a461e0e8"
UNICODE_CODE_POINTS = 0x110000
SAMPLES = (
    ("short_article", "https://example.com/article"),
    (
        "repository_issue",
        "https://github.com/Panniantong/Agent-Reach/issues/123?sort=updated&state=open",
    ),
    ("video_query", "https://www.youtube.com/watch?v=abc123&list=example&index=2"),
    ("long_encoded_query", "https://example.com/read?q=" + "a%20b-" * 250),
)


def _positive_int(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def _load_modules(repository: Path) -> tuple[types.ModuleType, types.ModuleType]:
    """Load only the checked-out helper and the exact reviewed Git blob."""
    result = subprocess.run(
        ["git", "-C", str(repository), "show", f"{BASELINE_COMMIT}:{MODULE_PATH}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=10,
    )
    if result.returncode:
        raise RuntimeError(
            "The reviewed baseline commit is missing from local Git; "
            "use a checkout containing the upstream history. No network fetch was attempted."
        )
    if hashlib.sha256(result.stdout).hexdigest() != BASELINE_SHA256:
        raise RuntimeError("Baseline source hash mismatch; refusing to evaluate it")
    baseline = types.ModuleType("_agent_reach_reviewed_url_baseline")
    exec(compile(result.stdout, "<reviewed URL baseline>", "exec"), baseline.__dict__)

    spec = importlib.util.spec_from_file_location(
        "_agent_reach_current_url", repository / MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the checked-out URL helper")
    current = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(current)
    return baseline, current


def _verify_unicode_scanner(current: types.ModuleType) -> dict:
    """Compare every Unicode code point with the original rejection predicate."""
    rejected = 0
    scanner = current._UNSAFE_URL_CHARACTERS
    for codepoint in range(UNICODE_CODE_POINTS):
        character = chr(codepoint)
        original = (
            character == "\\"
            or character.isspace()
            or codepoint < 0x20
            or codepoint == 0x7F
        )
        if bool(scanner.search(character)) != original:
            raise AssertionError(f"Unsafe-character predicate differs at U+{codepoint:04X}")
        rejected += original
    return {
        "code_points_checked": UNICODE_CODE_POINTS,
        "rejected_code_points": rejected,
        "mismatches": 0,
        "includes_surrogates": True,
    }


def _outcome(normalize, value: str) -> tuple[str, str | None]:
    try:
        return "allowed", normalize(value)
    except ValueError:
        return "rejected", None


def _verify_normalization(baseline: types.ModuleType, current: types.ModuleType) -> dict:
    allowed = [
        "https://example.com/article",
        "example.com/article",
        " https://example.com/article ",
        "https://EXAMPLE.COM./article?part=1#heading",
        "https://example.com:443/article",
        "http://example.com:80/article",
        "https://8.8.8.8/dns-query",
        "https://[2606:4700:4700::1111]/dns-query",
        "https://example.com/search?q=hello%20world",
        "https://example.com/post/a%0Ab",
        "https://example.com/%E4%B8%AD%E6%96%87",
        "https://example.com/中文?q=café",
    ]
    rejected = [
        "",
        "ftp://example.com/article",
        "https://user:password@example.com/article",
        "https://localhost/article",
        "https://metadata.google.internal/",
        "http://127.0.0.1/",
        "http://127.1/",
        "http://2130706433/",
        "http://10.0.0.1/",
        "http://169.254.169.254/",
        "http://[::1]/",
        "https://example.com:65536/",
        "https://example.com:not-a-port/",
        "https://example%2ecom/",
        "\x00https://example.com/",
    ]
    for character in ("\t", "\n", "\r", "\x00", "\x1f", "\x7f", " ", "\u00a0", "\\"):
        rejected.extend(
            (
                f"https://exa{character}mple.com/path",
                f"https://example.com/a{character}b",
                f"https://example.com/path?q=a{character}b",
            )
        )
    for expected, values in (("allowed", allowed), ("rejected", rejected)):
        for index, value in enumerate(values):
            original = _outcome(baseline.normalize_public_http_url, value)
            changed = _outcome(current.normalize_public_http_url, value)
            if original != changed or changed[0] != expected:
                raise AssertionError(f"Normalization mismatch in {expected} case {index}")

    routing_rejections = [
        "\x00https://example.com/path",
        " https://example.com/path",
        "https://example.com/path\n",
        "https://example.com/a\tb",
        "https://example.com/a\\b",
        "https://example.com/path?q=a b",
        "https://example.com.evil.test/path",
        "https://example.com@evil.test/path",
    ]
    for index, value in enumerate(routing_rejections):
        if current.host_matches(value, "example.com"):
            raise AssertionError(f"Malformed URL accepted in routing case {index}")
    for index, value in enumerate(allowed[8:]):
        if not current.host_matches(value, "example.com"):
            raise AssertionError(f"Valid encoded/Unicode URL rejected in routing case {index}")
    return {
        "allowed_cases": len(allowed),
        "rejected_cases": len(rejected),
        "normalization_matches_baseline": True,
        "routing_rejections": len(routing_rejections),
        "routing_encoded_or_unicode_acceptances": len(allowed[8:]),
    }


def _benchmark(baseline, current, *, iterations: int, repeats: int) -> list[dict]:
    results = []
    for label, url in SAMPLES:
        before = lambda: baseline.normalize_public_http_url(url)  # noqa: E731
        after = lambda: current.normalize_public_http_url(url)  # noqa: E731
        for _ in range(250):
            before()
            after()
        before_samples = timeit.Timer(before).repeat(repeat=repeats, number=iterations)
        after_samples = timeit.Timer(after).repeat(repeat=repeats, number=iterations)
        before_median = statistics.median(before_samples)
        after_median = statistics.median(after_samples)
        results.append(
            {
                "sample": label,
                "url_characters": len(url),
                "baseline_median_ns_per_call": round(before_median * 1e9 / iterations, 1),
                "current_median_ns_per_call": round(after_median * 1e9 / iterations, 1),
                "speedup_ratio": round(before_median / after_median, 3),
                "baseline_samples_seconds": [round(value, 9) for value in before_samples],
                "current_samples_seconds": [round(value, 9) for value in after_samples],
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=_positive_int, default=3000)
    parser.add_argument("--repeats", type=_positive_int, default=5)
    args = parser.parse_args()
    try:
        baseline, current = _load_modules(Path(__file__).resolve().parent.parent)
        unicode_checks = _verify_unicode_scanner(current)
        behavior_checks = _verify_normalization(baseline, current)
        measurements = _benchmark(
            baseline, current, iterations=args.iterations, repeats=args.repeats
        )
    except (AssertionError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "scope": "URL-normalization helper only; no network, DNS, CLI, or platform benchmark",
                "baseline_commit": BASELINE_COMMIT,
                "baseline_source_sha256": BASELINE_SHA256,
                "machine": {
                    "python": platform.python_version(),
                    "implementation": platform.python_implementation(),
                    "operating_system": platform.system(),
                    "architecture": platform.machine(),
                    "logical_cpus": os.cpu_count(),
                    "timer_resolution_seconds": time.get_clock_info("perf_counter").resolution,
                },
                "method": {
                    "iterations_per_repeat": args.iterations,
                    "repeats": args.repeats,
                    "warmup_calls_per_function_per_sample": 250,
                    "statistic": "median",
                    "garbage_collection": "disabled during timeit measurements",
                    "limitations": "Process-local timing; scheduler and interpreter noise affect results",
                },
                "unicode_scanner_equivalence": unicode_checks,
                "behavior_checks": behavior_checks,
                "measurements": measurements,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

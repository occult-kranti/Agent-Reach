# Validation record: Agent Reach improvements

Date: 25 November 2026. Upstream base: `8d9ecc1f5521fe7d223cde782aaa4005695e2671`.

## Executed checks

| Check | Result | Evidence and scope |
| --- | --- | --- |
| Focused offline unittest harness | Passed: 13 methods, including 43 explicit subcases | [Raw output](offline-validation.txt); real in-process JSON/text CLI dispatch, temporary state, denied network/process calls |
| Unicode rejection predicate comparison | Passed: 1,114,112 code points; 54 unsafe; zero mismatches | [Benchmark JSON](url-validation-benchmark.json); includes surrogates |
| URL behavior comparison | Passed: 12 allowed + 42 rejected normalization examples | Same benchmark JSON; fixed baseline source verified by SHA-256 |
| URL routing examples | Passed: 8 malformed cases rejected, 4 encoded/Unicode cases accepted | Same benchmark JSON |
| Diagnostic duplicate-work check | Passed: 14 checked fixture channels, 14 fingerprint evaluations | Offline harness; per-report computation, no persistent cache |
| Static checkout inventory | Passed: 14 channels, 40 actions, 5 default/6 optional/3 experimental | [Inventory JSON](reviewed-capabilities.json); source parsed without target execution |
| Static inspector boundaries | Passed | Synthetic non-execution case; dynamic registry rejection; escaping-symlink rejection; revision mismatch returns exit 1 |
| Skill structural validation | Passed | Canonical personal skill validated before save |
| Skill scenario evaluation | Passed | Independent worker selected existing web connector, stopped on PLATFORM_BLOCKED, rejected credential caching and unsupported global speedup claims |
| Patch whitespace validation | Passed | `git diff --check` |
| Independent patch review | No blocking issue found; text-mode diagnostic finding resolved and re-reviewed | Final CLI fix adds controlled stderr output with return code 1; successful text mode stays unchanged |
| Syntax inventory | Passed: 92 Python files parsed | Application, tests, scripts, and repository skill code; this is not type checking |
| Installed skill readback | Passed: six reconciled files match repository copy | SKILL.md, metadata, generated icon, two references, and static inspector |

## Commands used

```bash
python3 scripts/validate_hardening.py
python3 scripts/benchmark_url_validation.py --iterations 3000 --repeats 5
python3 skills/agent-reach-ops/scripts/inspect_checkout.py .
git diff --check
```

The unittest runner uses the standard library. Application imports also use the already-available PyYAML dependency. It installs nothing and blocks HTTP, DNS, sockets, child processes, and application-state reads outside a temporary directory. No real platform credentials or accounts were used.

These containment checks are targeted Python mocks and temporary application paths, not an operating-system sandbox. Their passing output describes the exercised paths, not every possible I/O mechanism in the application or its dependencies.

The benchmark compares the fixed reviewed Git blob with the changed helper. It establishes helper-only timing, not network/CLI speed. It requires the reviewed commit to be present in local Git history and will not fetch it automatically.

## Gates not executed

| Gate | Status | Reason |
| --- | --- | --- |
| Complete upstream pytest suite | Not run | pytest is absent; automatic approval review rejected downloading development dependencies from PyPI |
| Ruff | Not run | Tool absent; no new package installation authorized after the rejection |
| Mypy | Not run | Tool absent; same dependency limitation |
| Wheel build and clean package installation | Not run | Build/install dependencies were not installed |
| Python 3.10/3.11/3.13 compatibility matrix | Not run | Focused executed harness uses the existing CPython 3.12.14 runtime |
| Live 14-channel checks | Not run | No platform session import, login, provider quota, or live platform requests used for this audit |
| Upstream release acceptance | Not claimed | Existing upstream acceptance record does not validate changed source |
| Fork creation / remote publication | Blocked pending target-account decision | Browser and GitHub connector identify different accounts; automatic approval review rejected the ambiguous fork/account switch |

## Follow-up validation when authorized

Use the reviewed local checkout as the package source, and distinguish installing its legitimate development dependencies from resolving the unrelated bare PyPI name. Use the repository constraints after confirming package-source permission. Then run:

```bash
python -m pytest -q
ruff check agent_reach tests
mypy agent_reach
```

Record exact versions, complete output, and any failures. Do not amend this record to say “passed” based on an unexecuted command, a mock, or an earlier upstream release. Preserve any required upstream live acceptance gate before proposing a release.

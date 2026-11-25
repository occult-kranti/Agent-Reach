# Validation record: Agent Reach improvements

Date: 25 November 2026. Upstream base: `8d9ecc1f5521fe7d223cde782aaa4005695e2671`.

Full-suite validation ran against implementation commit `bd33e035f441bf632f092135bace7919d3f63b45` on Linux with CPython 3.12.14. The user explicitly approved the constrained development dependency installation before these checks ran.

## Executed checks

| Check | Result | Evidence and scope |
| --- | --- | --- |
| Complete repository pytest suite | Passed: 701 tests in 17.05 seconds; exit 0 | [Complete output](full-validation.txt); `.venv/bin/pytest -q`, pytest 8.0.0 |
| Ruff | Passed; exit 0 | Same complete output; `.venv/bin/ruff check agent_reach tests`, Ruff 0.15.1 |
| Mypy | Passed: no issues in 50 source files; exit 0 | Same complete output; `.venv/bin/mypy agent_reach`, mypy 1.19.1 |
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

After the user's explicit approval, the local reviewed checkout and its development dependencies were installed into `.venv` with the repository constraints. The successful command was:

```bash
uv pip install --python .venv/bin/python -e '.[dev]' -c constraints.txt
```

The full checks then ran with that environment's executables:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check agent_reach tests
.venv/bin/mypy agent_reach
```

The recorded tool versions and complete check outputs are in [full-validation.txt](full-validation.txt). All three commands exited 0. HEAD remained at the validated implementation commit and the worktree was clean after the run.

The earlier focused offline stage used these commands:

```bash
python3 scripts/validate_hardening.py
python3 scripts/benchmark_url_validation.py --iterations 3000 --repeats 5
python3 skills/agent-reach-ops/scripts/inspect_checkout.py .
git diff --check
```

The focused unittest runner uses the standard library. Application imports also use the already-available PyYAML dependency. The harness installs nothing and blocks HTTP, DNS, sockets, child processes, and application-state reads outside a temporary directory. No real platform credentials or accounts were used by that harness.

An initial dependency-install attempt was rejected by automatic approval review. The later explicit user authorization enabled the constrained installation recorded above; dependency availability no longer blocks pytest, Ruff, or mypy. The source remained the reviewed local checkout, rather than resolving the unrelated bare PyPI project name.

These containment checks are targeted Python mocks and temporary application paths, not an operating-system sandbox. Their passing output describes the exercised paths, not every possible I/O mechanism in the application or its dependencies.

The benchmark compares the fixed reviewed Git blob with the changed helper. It establishes helper-only timing, not network/CLI speed. It requires the reviewed commit to be present in local Git history and will not fetch it automatically.

## Gates not executed

| Gate | Status | Reason |
| --- | --- | --- |
| Wheel build and clean package installation | Not run | The approved editable development install succeeded; a standalone wheel build and clean non-editable installation were not performed |
| Python 3.10/3.11/3.13 compatibility matrix | Not run | Executed validation used CPython 3.12.14 |
| Windows compatibility | Not run | Executed validation used Linux; no Windows run was performed |
| Live 14-channel checks | Not run | No platform session import, login, provider quota, or live platform requests used for this audit |
| Upstream release acceptance | Not claimed | Existing upstream acceptance record does not validate changed source |
| Fork creation / remote publication | Not completed | Fresh GitHub browser sign-in is required; no remote publication is claimed |

## Remaining validation

The passing full suite resolves the earlier pytest, lint, and type-check gates. Packaging, other Python versions, Windows, and live platform acceptance remain separate checks. Record their actual versions and complete output if they are executed; do not infer those results from the passing Linux development suite or an earlier upstream release. Preserve the required upstream live acceptance gate before proposing a release.

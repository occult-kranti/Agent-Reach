# Agent Reach: source review, focused improvements, and adoption plan

Review date: 25 November 2026. Reviewed upstream: `Panniantong/Agent-Reach` at **`8d9ecc1f5521fe7d223cde782aaa4005695e2671`**. Package metadata: **1.6.1**, MIT, Python **3.10 or newer**. This is a review of that source snapshot, not a certification of every upstream dependency or live platform integration.

## Contents

1. [Assessment and status](#assessment-and-status)
2. [Installation provenance](#installation-provenance)
3. [What the current code provides](#what-the-current-code-provides)
4. [Architecture and execution flow](#architecture-and-execution-flow)
5. [Implemented changes](#implemented-changes)
6. [Performance evidence](#performance-evidence)
7. [Validation and release limits](#validation-and-release-limits)
8. [Authentication, data, and installation boundaries](#authentication-data-and-installation-boundaries)
9. [Skill and research-system integration](#skill-and-research-system-integration)
10. [Prioritized next work](#prioritized-next-work)
11. [Source index](#source-index)

## Assessment and status

Agent Reach is useful as an agent-facing adapter and lifecycle manager. Its strongest design choices are explicit channel/action contracts, ordered backends, a common JSON response, public-content routes, local state, and structured failure codes. Its responsibilities extend beyond merely recommending a scraper: it can install tools, manage browser processes, reuse authenticated sessions, persist state, and route requests. Those side effects matter when deciding whether an ordinary research task authorizes a command. [S1, S3–S8]

This review produced a small production patch addressing five connected concerns: duplicated diagnostic work, inconsistent diagnostic snapshots, malformed ledger containers, empty subprocess environments, and URL validation/routing. A separate reusable skill, `agent-reach-ops`, adds version-aware discovery, source pinning, session-consent boundaries, evidence receipts, and bounded review rounds. The upstream bundled `agent-reach` skill is retained; the new skill is an optional operating and review layer.

**Delivery status:** source changes, regression cases, offline validation tools, and documentation are prepared locally. A personal skill can be installed independently of GitHub publication. No upstream push or fork publication is claimed by this document. The publishing account must be resolved before creating the fork. Full pytest, lint, type-check, packaging, and live-platform acceptance remain separate gates; see the accompanying validation record.

The review used parallel workstreams for upstream research, runtime reliability, process/URL correctness, and integration. Findings were checked against the checked-out source rather than assumed from older descriptions. This is a focused engineering review with an explicit remaining-work list, not a line-by-line security assessment of all third-party software.

## Installation provenance

The official installation guide explicitly warns that the PyPI distribution named `agent-reach` is a different project. The official project uses GitHub release/source URLs. The separate PyPI listing identifies Jean Galea and `jgalea/agent-reach`; the upstream maintainer also describes it as an unrelated legitimate project in issue #547. Calling it confirmed malware would overstate the evidence. The practical instruction is to avoid resolving this project by its bare package name. [S1, S2]

The published release inspected was **v1.6.1**, dated **1 November 2026**, at commit `7a38047acf26a729cbb27851e3cb81639da86b29`. The reviewed main-branch commit is later. Both report package version 1.6.1, demonstrating why a version string alone is insufficient to identify the code used for an audit. Record the full commit and, for downloaded artifacts, a content checksum. The short fragments in the original shared description were not treated as verified revision identifiers. [S9]

The moving `releases/latest` and `main` URLs are convenient operational defaults but are not immutable evidence. For reproducible work, resolve an official release or commit, inspect its package metadata and installation hooks, then use that exact source. A virtual environment provides dependency separation; it does not sandbox filesystem or network access. Source pinning also does not prove that a dependency is safe.

The repository declares four direct runtime dependencies: `requests`, `loguru`, `pyyaml`, and `yt-dlp[default]`, with yt-dlp pinned to `2026.8.19`. Its `constraints.txt` pins a tested development set. Constraints improve reproducibility when used, but this file is not a complete hash-verified lock of every transitive dependency. Tools installed by channel management are a separate dependency surface. [S3, S10]

During this session, automatic approval review rejected installing development dependencies from PyPI because of the user's installation warning. No substitute package source was used to bypass that rejection. The validation tools in this patch use the existing Python runtime; the offline harness uses the application's already-available PyYAML dependency where configuration imports require it.

## What the current code provides

The reviewed registry contains **14 channels: five default, six optional, and three experimental**. These are code registrations, not a claim that all 14 were reachable or authenticated in this environment. No platform-account acceptance tests were performed. The static inventory is saved alongside this report. [S4]

| Channel | Level | Declared actions | Current declared backends | Interpretation |
| --- | --- | --- | --- | --- |
| GitHub | Default | Search, read | `gh`, GitHub REST | Public REST fallback; issue/PR comment completeness still needs attention. |
| YouTube | Default | Read, search, subtitle, transcribe | `yt-dlp`, Whisper path | Metadata/subtitles differ from speech transcription; transcription may use a paid provider. |
| Bilibili | Default | Search, read, hot, subtitle | `bili-cli`, Bilibili API | Public API fallback for read/hot; subtitles have login/session requirements. |
| V2EX | Default | Hot, node, read, user | V2EX API | Structured public forum content. |
| Web | Default | Search, read | Exa; Jina then Exa for reading | Fallback when existing provider search/fetch is insufficient. |
| Reddit | Optional | Search, read, subreddit | OpenCLI | Some actions also declare public-web routes; not a feedparser integration. |
| Xiaohongshu | Optional | Search, read, comments | OpenCLI | Browser/session dependent site actions. |
| LinkedIn | Optional | Jobs, read | OpenCLI | Job search and job details; not a general people/company extraction promise. |
| BOSS | Optional | Search, read | OpenCLI, `boss-agent-cli` | Backend order differs by action. |
| Xueqiu | Optional | Quote, search, hot posts, hot stocks | Tencent, Xueqiu API | Market data and authenticated community content have different requirements. |
| Xiaoyuzhou | Optional | Transcribe | Groq Whisper | Provider key/quota applies. |
| Twitter/X | Experimental | Search, profile, tweets, thread | OpenCLI | The older twitter-cli mapping is no longer current. |
| Facebook | Experimental | Search, profile | OpenCLI | Platform-dependent browser access. |
| Instagram | Experimental | Search, profile, posts | OpenCLI | Platform-dependent browser access. |

The source explicitly removed the older Bilibili yt-dlp fallback and Twitter twitter-cli path. There is no independent RSS channel in this registry. Therefore the original “15+ platforms, twitter-cli, feedparser, linkedin-scraper-mcp” summary should be treated as historical context, not copied into an operational skill. [S4, S11]

## Architecture and execution flow

### 1. CLI and declarative contracts

`agent_reach/cli.py` is the console wrapper. `runtime/cli.py` handles command parsing, management commands, channel action discovery, URL routing, and JSON output. `channels/base.py` defines `Channel`, `Action`, and `Param`. An action supplies its parameters, ordered backend labels and methods, optional public-web scopes, live-test inputs, and timeout. The registry connects these declarations to commands. [S4, S5]

This separation is valuable: a channel can change its implementation without forcing agents to parse a different output format. It also makes `agent-reach channels` the appropriate source of capability truth for an installed revision. Hard-coded examples from an old blog post are weaker evidence than the current action declarations.

The action result envelope contains `schema_version`, `ok`, `channel`, `action`, `backend`, `items`, `meta`, and `error`. Management responses use an analogous shape with `result`. Consumers must distinguish these shapes and inspect `ok`/`error.code`; an exit status or a nonempty stdout string is not enough. Missing article text, a subtitle-track list, and a real transcript are different outputs. [S6]

### 2. Dispatcher and fallback semantics

`runtime/dispatch.py` validates arguments before setup work, checks channel cooldowns, selects allowed backends, applies browser scheduling, records backend health, and returns the envelope. Public-web routes are declared by individual actions. A caller can select `--backend public-web` only where that route exists; this is not a universal switch accepted by every action. [S5, S7]

`runtime/public_web.py` reuses the Web channel and scopes results to declared hosts/paths. It rejects empty page shells and obvious login/challenge pages. Successful public results explicitly mark completeness as unverified. This is good evidence hygiene: publicly indexed text may be useful without proving current site ranking, complete comment coverage, or authenticated access.

The dispatcher treats `NOT_FOUND`, `BAD_INPUT`, `PLATFORM_BLOCKED`, `RATE_LIMITED`, `NEED_LOGIN`, and `BUSY` as terminal outcomes. Other errors can permit an ordered fallback. These codes therefore encode policy, not just presentation. Reclassifying a failure can change which requests happen next; error changes deserve tests at the dispatcher boundary. [S6, S7]

### 3. Deadlines, concurrency, and process execution

Actions have a budget tracked by `runtime/clock.py`. Setup waits can pause that budget. The dispatcher runs in-process backend calls in daemon threads because it cannot forcibly interrupt arbitrary Python HTTP work. Subprocess backends receive timeouts through `runtime/run.py`. Browser bindings impose locks, queueing, per-site limits, and search pacing. This patch does not increase any request limits or disable pacing. [S7, S8]

The distinction between “the caller stopped waiting” and “all work stopped” is significant. A timed-out daemon thread may continue until its underlying operation returns. Future changes should test late writes and cleanup rather than assuming timeout equals cancellation. Likewise, `Popen.communicate()` buffers process output; a deadline alone is not a byte limit.

### 4. State, diagnostics, and ownership

`runtime/state.py` records added channels, tool ownership, live-check evidence, skill links, and paths the application owns. `runtime/manage.py` performs setup, add/remove, diagnostics, skill placement, update, and uninstall. Ownership metadata has deletion implications, so malformed state must not silently create permission to remove files. Private-file helpers reject symlink paths and use atomic writes for important state/configuration operations. [S8, S12]

`doctor` reads local configuration and recorded evidence; `check` performs live requests. Freshness depends on evidence timestamps and a fingerprint incorporating relevant code/configuration/tool information. A locally installed executable is not sufficient evidence of a working authenticated channel. Conversely, a missing credential should not be reported as a broken parser.

In the modified checkout, the application contains about 9,400 Python source lines across 50 modules. The largest responsibilities are concentrated in `manage.py`, `browser.py`, `tools.py`, and `runtime/cli.py`. This supports a cautious extraction roadmap, not an immediate rewrite: these modules contain many coupled ownership, lifecycle, and compatibility rules.

## Implemented changes

### A. Reuse one diagnostic freshness result within a report

**Files:** `agent_reach/runtime/manage.py`, `tests/test_manage.py`.

Previously `doctor()` called `fresh_actions()` to determine regression and then `channel_status()` called it again. For checked, fully configured channels, that recalculated fingerprints and their state/config reads twice. More subtly, evidence could cross its expiry threshold between calls, making one report show an expired/unverified status and a simultaneously fresh regression flag.

`channel_status()` now accepts an optional `current_actions` argument. `doctor()` passes the result it already computed. An empty dictionary is reused correctly; `None` is the explicit “compute it here” sentinel. Other callers retain the previous behavior, and a later doctor invocation recomputes the evidence. No long-lived cache is introduced.

This reduces the duplicated fingerprint evaluations from **two to one per relevant channel/report** and makes status/regression internally consistent. It is not a claim that the entire CLI became twice as fast. Tests exercise both directions of a controlled expiry transition and ensure the following report reevaluates evidence.

### B. Reject malformed present ledger containers

**Files:** `agent_reach/runtime/state.py`, `tests/test_state_loading.py`.

Valid JSON such as `{"skill": null}` previously raised `AttributeError`. Other wrong-shaped containers could reach ownership or management code. `load()` now validates present `channels`, `tools`, `checks`, and `skill` as objects; `skill.links` and `skill.unlinked` as lists; and `owned_paths` as an object.

Wrong types produce `ReachError(BAD_INPUT, ...)` naming the field without echoing its value. The source ledger is not rewritten. A malformed ownership ledger prevents the mutation callback from running. Missing fields still receive defaults, preserving ordinary upgrade behavior.

Independent review caught an additional caller gap: `doctor --text` invoked the management function without catching that error. The final patch also updates `runtime/cli.py` to print its code/message and recovery hint to stderr and return 1. Successful text output remains unchanged; normal JSON mode continues to emit its structured management error. The offline harness exercises both modes.

The change intentionally has a narrow scope. It does not validate every nested record. Existing fallback for invalid JSON or a non-object root is retained; the `removed_defaults` normalization also remains unchanged. These are documented follow-up design questions, not silently presented as solved.

### C. Respect an explicitly empty subprocess environment

**Files:** `agent_reach/utils/process.py`, `tests/test_process.py`.

`utf8_subprocess_env()` used `dict(base or os.environ)`. An explicitly supplied empty dictionary was falsy and therefore inherited the entire parent environment. The new expression distinguishes `base is None` from an empty mapping. It still enforces Python UTF-8 settings and returns a copy without mutating the caller.

Tests cover default inheritance, empty mappings, nonempty mappings, caller/parent immutability, and absence of unexpected inherited keys. Current production callers generally use the default environment; this is an API contract correction, not evidence that real credentials were exposed.

### D. Validate malformed routing input before URL parsing

**Files:** `agent_reach/utils/url.py`, `tests/test_url_security.py`.

`host_matches()` parsed URLs before rejecting raw controls or whitespace. `urllib.parse.urlsplit()` can strip some controls, changing malformed input before the routing decision. The helper now rejects non-text input and unsafe raw characters before parsing. Host, subdomain, scheme, userinfo, and port checks remain in place.

Percent-encoded path/query values and legitimate Unicode paths remain supported. The normalization helper still has its explicit surrounding-whitespace normalization behavior, while routing rejects raw surrounding whitespace. This distinction is deliberate and documented by the tests. The work establishes routing consistency and defensive input handling; it does not establish a separate exploitable vulnerability.

### E. Replace the Python character loop with a compiled expression

The normalization helper previously checked each character in a Python generator. A shared compiled expression detects Unicode whitespace, backslashes, ASCII controls, and DEL. The rejection set is equivalent to the previous predicate. The benchmark script checks every Unicode code point, including surrogates, and compares accepted/rejected URL cases before timing.

This is a local CPU optimization with no added network requests, concurrency, persistent state, or credential caching. Keeping the algorithm's meaning fixed makes the performance result easier to evaluate and keeps the patch small.

## Performance evidence

Run `python3 scripts/benchmark_url_validation.py --iterations 3000 --repeats 5` from the repository. It reads a fixed baseline helper from local Git, verifies its SHA-256, performs correctness checks, warms both implementations, and emits raw samples plus medians and machine metadata as JSON. It accepts no arbitrary baseline ref or source path.

The recorded run is in `url-validation-benchmark.json`. It used CPython 3.12.14 on Linux x86_64, five repeats of 3,000 calls, and 250 warmup calls per function and sample. Later machines may differ.

| Sample | URL characters | Baseline median | Modified median | Ratio |
| --- | ---: | ---: | ---: | ---: |
| Short article | 27 | 6,335.9 ns/call | 4,415.7 ns/call | 1.435× |
| Repository issue | 77 | 9,663.6 ns/call | 4,891.6 ns/call | 1.976× |
| Video query | 59 | 8,549.3 ns/call | 4,748.6 ns/call | 1.800× |
| Long encoded query | 1,527 | 106,740.9 ns/call | 12,839.9 ns/call | 8.313× |

The exhaustive scan covers **1,114,112 Unicode code points**, finds **54 unsafe code points**, and reports **zero predicate mismatches**. Additional cases cover allowed normalization, rejected normalization, malformed routing, and accepted encoded/Unicode routing. The input set is explicit; it is not a proof about every possible URL parser interaction.

These are helper-level measurements. Network latency, browser startup, backend execution, provider limits, and remote availability often dominate user-visible latency. No end-to-end speedup is asserted. The diagnostic improvement is separately measured as avoided fingerprint evaluations, not inferred from this benchmark.

## Validation and release limits

The patch includes normal pytest regression cases in the existing suite and a separate `scripts/validate_hardening.py` offline unittest harness. The latter uses temporary state/configuration paths, blocks network/process creation, and exercises actual management dispatch and JSON emission in process. It does not impersonate pytest or claim to run the entire upstream suite.

The static skill inspector parses source with `ast` and reads Git identity. It does not import or execute the target repository, install tools, inspect personal configuration, or read cookies. It was checked against the real 14-channel registry, a synthetic source file that would raise if executed, a dynamic registry that must be rejected, an escaping symlink, and a mismatched revision.

The validation record distinguishes executed offline checks from pending gates. Full `pytest`, `ruff`, `mypy`, wheel installation, and live channel checks must not be described as passed unless their actual outputs are recorded. Package installation was blocked in this session; a successful import or AST parse is not a substitute for those gates.

Before proposing an upstream release, use the project's contribution/release process, including any live acceptance record required for changed channel behavior. Do not reuse the upstream release-acceptance record after code changes; its code fingerprint no longer identifies this build. This patch does not bump the upstream version, create a release tag, or claim fresh platform acceptance. [S10]

## Authentication, data, and installation boundaries

### Conflicting session guidance needs an explicit decision

`CONTRIBUTING.md` and `llms.txt` describe explicitly authorized, one-time, site-scoped imports. Other documentation and `runtime/session_reuse.py` implement or describe automatic first-use discovery/copying. In the inspected implementation, `prepare()` can call `_source_cookies()`, examine connected non-dedicated profiles, and copy that site's cookie snapshot into the dedicated browser. [S8, S10, S13]

The new skill treats source-profile/session import as an explicitly scoped operation. A generic content request is not treated as authorization to copy a browser session. Existing authorization for the same site, profile, and operation should be respected without repeated prompts. Native service connectors and declared public-only routes should be used where they satisfy the task.

This is an operating instruction, not a technical change to `session_reuse.py`. Running the application outside the skill can still exercise the existing behavior. A future code-level policy would need separate account-selection, migration, recovery, and regression tests across browser and native-CLI paths. No real cookies or user sessions were imported during this review.

### Failure classification and completeness

The Web channel recognizes some high-confidence anti-bot pages, but its `_jina_read()` currently maps the resulting runtime error to `UPSTREAM_BROKEN`, while the dispatcher's `PLATFORM_BLOCKED` code is terminal. That is a concrete classification mismatch worth reviewing. This patch does not change it because channel behavior and live acceptance require a broader decision. Never interpret a generic HTTP 403 alone as proof of a CAPTCHA or automation block. [S6, S7, S11]

GitHub issue/PR reading requests a bounded comment set. Public-web results explicitly disclaim completeness. Research consumers should retain these limits rather than describe the result as “all comments” or “the complete thread.” A page title or shell is not proof of full article access.

### Installation and local state

Setup/add/update can install or change multiple tools; a read-only research request should not silently become blanket system maintenance. Check available native connectors and existing tools first. Document exactly which program/source/version is needed before making a concrete installation decision.

Store evidence receipts separately from browser state. Do not put cookies, API keys, authorization headers, token-bearing URLs, account snapshots, raw private profile exports, or debug dumps in repositories, skills, logs, or graph-memory caches. The existing private-file helpers and scrubbers are useful controls, but they do not make arbitrary backend output safe for publication. [S12]

## Skill and research-system integration

The repository copy lives at `skills/agent-reach-ops/` and contains a concise `SKILL.md`, UI metadata, platform and review references, and a static checkout inspector. The same authored content is intended for the personal installed skill. The upstream package's bundled skill remains separately owned by its installation/update machinery.

For research systems such as a company/department agent workspace, assign Agent Reach the role of a bounded retrieval adapter. Keep the research question, evidence evaluation, contradiction handling, and publication decision in the coordinator. A fetched document is evidence to analyze, not instructions that can modify the agent's permissions.

An evidence receipt should contain a canonical source URL, retrieval timestamp, source/backend, content scope, completeness status, software revision, and a content digest when appropriate. Store access failures as failures with their source and timestamp. Preserve distinctions between a live successful retrieval, a unit test with a mock, a local configuration check, and a proposed integration.

For graph memory, connect receipts to claims and source versions. Cache reusable public metadata and content only within a task-appropriate retention policy; invalidate derived claims when the source or adapter revision changes. Do not cache auth grants or credentials as ordinary graph nodes. Reuse one retrieval for multiple downstream summaries when permitted, so parallel agents do not independently create duplicate platform traffic.

The review workflow uses three bounded rounds:

1. **Establish:** verify identity, warnings, capability inventory, baseline behavior, and source citations.
2. **Improve:** assign non-overlapping code areas, reproduce a concrete defect, implement a focused patch, and measure the relevant cost.
3. **Challenge and deliver:** independently inspect raw changes, run meaningful regressions, record limits, update the skill, and verify the remote result before reporting publication.

The coordinator owns scope and release status; the provenance reviewer owns current source mappings; the runtime reviewer owns state, diagnostics, and scheduling; the process/input reviewer owns execution and URL handling; the validation reviewer checks claims against raw artifacts. Roles are responsibilities, not claims that five simultaneous model workers were used. Reuse workers across rounds when practical.

## Prioritized next work

| Priority | Work item | Why it matters | Required acceptance evidence |
| --- | --- | --- | --- |
| 0 | Resolve the fork-owning account and publish the prepared branch | The task is not complete until the correct remote contains the changes | Verified repository owner, branch SHA, file hashes/contents |
| 0 | Run the full constrained development suite when dependency installation is authorized | Focused offline checks do not cover the complete application | Actual pytest, lint, type-check, packaging outputs |
| 1 | Reconcile session-import documentation and implementation | Different documents promise different consent behavior | Explicit site/profile scope, no silent import, migration/recovery tests |
| 1 | Align confirmed challenge classification with terminal dispatch rules | Error classification can trigger another backend | Mocked dispatcher tests plus authorized live acceptance |
| 1 | Add content completeness/pagination metadata | Avoid overstating bounded comments or public page content | Truncation, pagination, and partial-response fixtures |
| 2 | Bound subprocess output while draining both pipes | Timeouts do not cap buffered memory | Large-output child tests, stderr drain, termination cleanup |
| 2 | Define full ledger schema and corruption recovery | Current container validation deliberately stops short of nested validation | Versioned migrations, preserved ownership and unlink preferences |
| 2 | Test timeout cancellation and late worker effects | Returning TIMEOUT does not terminate arbitrary Python work | Controlled slow backends, no unsafe late mutations |
| 3 | Extract cohesive lifecycle modules from large management/browser files | Improve maintainability after behavior is covered | Equivalent externally visible behavior and focused ownership tests |

Do not prioritize more retries, more account switching, broader browser concurrency, or broad persistent caches as performance work. They can increase traffic or stale-state risk without addressing the measured costs. The changes in this review remove redundant local work while preserving the existing pacing and failure controls.

## Source index

Unless a release or external source is named, repository links below refer to the reviewed immutable commit. Local code and its tests were the authority for implementation findings.

- **S1 — Official install guide:** [docs/install.md](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/docs/install.md).
- **S2 — Name collision:** [upstream issue #547](https://github.com/Panniantong/Agent-Reach/issues/547) and [the separate PyPI project](https://pypi.org/project/agent-reach/).
- **S3 — Package/dependencies:** [pyproject.toml](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/pyproject.toml), [constraints.txt](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/constraints.txt).
- **S4 — Registry/contracts:** [channels/__init__.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/channels/__init__.py), [channels/base.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/channels/base.py).
- **S5 — CLI:** [runtime/cli.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/runtime/cli.py).
- **S6 — Envelopes/errors:** [runtime/result.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/runtime/result.py).
- **S7 — Dispatch/public routes:** [runtime/dispatch.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/runtime/dispatch.py), [runtime/public_web.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/runtime/public_web.py).
- **S8 — Runtime/session lifecycle:** [runtime/session_reuse.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/runtime/session_reuse.py), [runtime/browser_binding.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/runtime/browser_binding.py), [runtime/clock.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/runtime/clock.py).
- **S9 — Published release:** [v1.6.1](https://github.com/Panniantong/Agent-Reach/releases/tag/v1.6.1).
- **S10 — Contribution/release rules:** [CONTRIBUTING.md](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/CONTRIBUTING.md), [SECURITY.md](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/SECURITY.md).
- **S11 — Channel implementations/history:** [channels directory](https://github.com/Panniantong/Agent-Reach/tree/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/channels), [CHANGELOG.md](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/CHANGELOG.md).
- **S12 — State/private files:** [runtime/state.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/runtime/state.py), [config.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/config.py), [utils/paths.py](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/utils/paths.py).
- **S13 — Conflicting operating guidance:** [llms.txt](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/llms.txt), [bundled session guide](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/skill/references/sessions.md), [English README](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/docs/README_en.md).

# Publication record

Date: 25 November 2026.

The reviewed changes are published to the user-owned fork [occult-kranti/Agent-Reach](https://github.com/occult-kranti/Agent-Reach), on branch [`audit/agent-reach-ops-20261125`](https://github.com/occult-kranti/Agent-Reach/tree/audit/agent-reach-ops-20261125). The user will decide when to merge. No upstream pull request or merge was performed.

## Verified source and destination

| Field | Value |
| --- | --- |
| Upstream repository | `Panniantong/Agent-Reach` |
| Reviewed upstream base | `8d9ecc1f5521fe7d223cde782aaa4005695e2671` |
| Implementation commit tested by the full suite | `bd33e035f441bf632f092135bace7919d3f63b45` |
| First published snapshot, including full validation records | `d0c87af1e0ca06c357075562fea1311d311cd65d` |
| Complete tree of that snapshot | `cdc61c28942e00853e14aeb9849cdf89f47e2beb` |
| Verified publishing account | `occult-kranti` |
| Fork parent | `Panniantong/Agent-Reach` |
| Verified fork write permission | `true` |
| Publication method | Authenticated Git push, new review branch, no force |

GitHub's branch-ref API returned the exact published snapshot above. Its Git-commit API returned the tree SHA above, which equals `git rev-parse HEAD^{tree}` from the local published checkout. The complete content-addressed tree comparison covers every tracked file, including the skill and regression tests. Later commits containing this publication record or other documentation can advance the branch; this receipt deliberately identifies the snapshot actually verified, rather than trying to embed its own future commit hash.

## Validation and installed skill

The [complete local validation output](full-validation.txt) records **701 passing tests**, a passing Ruff check, and mypy reporting no issues in **50 source files**, on Linux with CPython 3.12.14. The [validation record](validation-record.md) separately identifies the offline harness, exhaustive Unicode comparison, static inspector checks, and remaining live/platform/packaging gates.

The personal **Agent Reach Operations** skill was persisted and read back. Its `SKILL.md`, UI metadata, icon, two references, and static inspector match the repository's `skills/agent-reach-ops/` directory. The skill's presence is separate from installing or authenticating any platform backend.

Credentials are excluded from the repository, test output, reports, skill, and patch. This record contains source identities and verification results only.

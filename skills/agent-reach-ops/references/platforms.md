# Platform contracts at the reviewed snapshot

Contents: [Channel matrix](#channel-matrix) · [Examples](#examples-after-executablesource-verification) ·
[Completeness](#interpret-completeness-precisely) · [History](#separate-historical-descriptions-from-current-behavior) ·
[Sessions](#verify-the-session-boundary) · [Sources](#sources).

Use the installed `agent-reach channels` output as the action/parameter authority after
verifying provenance. Reinspect source when the runtime version differs from this table.

Reviewed upstream commit: `8d9ecc1f5521fe7d223cde782aaa4005695e2671` (2026-11-25).
Package version: `1.6.1`. Count: 14 registered channels, 40 declared actions.
Use [the immutable source tree](https://github.com/Panniantong/Agent-Reach/tree/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/channels)
for exact parameters, action-specific backends, validators, and limits.

## Channel matrix

Read “public-web actions” as an explicit action declaration, not proof of completeness
or a permission to bypass a final error returned by another backend.

| Channel | Level | Declared actions | Backend family | Public-web actions |
|---|---|---|---|---|
| `github` | default | `search`, `read` | `gh`, GitHub REST | none |
| `youtube` | default | `read`, `search`, `subtitle`, `transcribe` | yt-dlp; Groq/OpenAI Whisper for transcription | none |
| `web` | default | `search`, `read` | Exa search; Jina then Exa reading | native web channel, not a `public-web` override |
| `v2ex` | default | `hot`, `node`, `read`, `user` | V2EX JSON API | none |
| `bilibili` | default | `search`, `read`, `hot`, `subtitle` | bili-cli; public API fallback for read/hot | none |
| `reddit` | optional | `search`, `read`, `subreddit` | OpenCLI | `search`, `read` |
| `linkedin` | optional | `jobs`, `read` | OpenCLI jobs/job-detail | `jobs`, `read` |
| `xiaohongshu` | optional | `search`, `read`, `comments` | OpenCLI | `search`, `read` |
| `xueqiu` | optional | `quote`, `search`, `hot_posts`, `hot_stocks` | Tencent public quotes/search; Xueqiu API | none |
| `boss` | optional | `search`, `read` | OpenCLI and boss-agent-cli, action-specific order | `search`, `read` |
| `xiaoyuzhou` | optional | `transcribe` | Groq Whisper script | none |
| `twitter` | experimental | `search`, `profile`, `tweets`, `thread` | OpenCLI | `search` |
| `facebook` | experimental | `search`, `profile` | OpenCLI | `search` |
| `instagram` | experimental | `search`, `profile`, `posts` | OpenCLI | none |

Treat default/optional/experimental as packaging and maintenance classifications.
Do not interpret them as evidence that every action works on the current host/network.
Check action-level requirements: YouTube transcription uses quota; Bilibili subtitles can
need a session; Xueqiu community actions differ from public quotes/search.

## Examples after executable/source verification

Discover before choosing parameters:

```bash
agent-reach version
agent-reach channels
agent-reach doctor --text
```

Use public content where it meets the request, and keep the result's declared scope:

```bash
agent-reach github read Panniantong/Agent-Reach
agent-reach youtube subtitle 'https://www.youtube.com/watch?v=jNQXAC9IVRw' --lang en
agent-reach reddit search 'retrieval evaluation' --limit 3 --backend public-web
agent-reach linkedin jobs 'research engineer' --limit 3 --backend public-web
```

These commands are examples, not mandatory live checks. Public-web search can return
indexed pages with partial text; do not claim complete site search or account access.
Do not add `--backend public-web` to Instagram, YouTube subtitles, or arbitrary actions.
Do not run browser/session-backed examples until their account scope is authorized.

## Interpret completeness precisely

- GitHub `read` handles repositories and issue/PR URLs; do not imply code-tree analysis.
  At this snapshot it reads at most 50 issue/PR comments without pagination.
- YouTube `read` returns metadata/description; use `subtitle` for caption text.
  Transcription is a separate audio processing operation with provider requirements.
- Bilibili `subtitle` describes the first video part; unavailable output alone does not
  establish that the source has no subtitles.
- Reddit `read` makes one OpenCLI request with `--limit 20`; the upstream limit semantics
  are not established here, so do not describe that as exactly 20 comments. This adapter
  has no comment-pagination or reply-expansion loop; do not claim it returns all comments.
  Reddit `subreddit` exposes no sort parameter and does not explicitly request `new`;
  do not label its output the latest posts without independently verifying order and coverage.
- LinkedIn declares job search and job-detail actions; do not promise full people or company scraping.
- Xiaohongshu `read` supplies text; do not claim the images or video were understood.
  `comments` returns loaded comments/replies, not an exhaustive export.
- Instagram `search` searches users, not posts; `posts` is scoped to one username.
- Preserve encoded/unknown BOSS salary fields; obtain readable detail before reporting a number.

## Separate historical descriptions from current behavior

Keep old mappings only as history. Earlier descriptions used 15 channels, `twitter-cli`,
`rdt-cli`, `feedparser` RSS, and `linkedin-scraper-mcp`. The reviewed registry exposes
14 channels; Twitter/Reddit/LinkedIn now use OpenCLI paths, and RSS has no standalone channel.
Bilibili no longer uses yt-dlp; YouTube still does. Do not install a removed backend to
satisfy an obsolete example. Use the changelog to explain migrations, then verify the code.

## Verify the session boundary

Inspect `runtime/session_reuse.py`, `runtime/onboarding.py`, `backends/opencli.py`, and
native channel login helpers before executing an unfamiliar session path. Automatic
site-cookie reuse exists in this snapshot, including Bilibili subtitle preparation.
A no-password design can still copy sensitive session credentials. Require only the
missing explicit site/source authorization; reuse it once the user has supplied it.

## Sources

- [Registry](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/channels/__init__.py)
- [Action contract](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/channels/base.py)
- [Dispatch and public route selection](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/runtime/dispatch.py)
- [Final error codes](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/runtime/result.py)
- [Session reuse implementation](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/agent_reach/runtime/session_reuse.py)
- [Installation and name-collision warning](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/docs/install.md)
- [Historical changes](https://github.com/Panniantong/Agent-Reach/blob/8d9ecc1f5521fe7d223cde782aaa4005695e2671/CHANGELOG.md)

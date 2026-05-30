# input-to-park

Personal source ingestion pipeline for Park-IO.

## Architecture

```text
~/park-io/sources.md
    -> fetch.py
    -> ~/park-io/inbox/unprocessed/<YY-MM-DD-profile>.md
    -> open-batch.py
    -> ~/park-io/inbox/processed/<YY-MM-DD>/<YY-MM-DD-profile>.md
    -> score.py
    -> build-digest.py
    -> check-quality.py
    -> archive-items.py
    -> send-artifacts.py
    -> push-telegram.py
```

`sources.md` is the single source of truth for tracked sources, user context,
and source-persona scoring guidance.

## Schedule

`fetch-all.sh` runs every 4 hours through launchd. It pins the fetch runtime to
a Python 3.11+ interpreter (`PARKIO_PYTHON`, `/usr/local/bin/python3`,
`/opt/homebrew/bin/python3`, then the content-toolkit venv) before calling
`fetch.py`; do not let launchd fall back to `/usr/bin/python3`, because the
Douyin client uses modern Python typing/Pydantic. The digest is built and pushed
once per day at 08:30 local time. If a fetch is still running, `push-digest.sh`
waits for the fetch lock before processing the batch.

## Manual Usage

```bash
cd /Users/wendy/work/input-to-park
./fetch-all.sh
python3 fetch.py
PARKIO_BATCH_ID=20260521 python3 open-batch.py
PARKIO_BATCH_ID=20260521 python3 score.py
PARKIO_BATCH_ID=20260521 python3 build-digest.py
PARKIO_BATCH_ID=20260521 python3 check-quality.py
PARKIO_BATCH_ID=20260521 python3 archive-items.py
PARKIO_BATCH_ID=20260521 PARKIO_FORCE_PUSH=1 python3 send-artifacts.py

# Build a recent-history baseline for a new or important profile.
python3 onboard-baseline.py huang-xiaomu --per-source 12
```

## Key Files

- `lib.py` — shared paths, source parsing, raw markdown rendering.
- `state.json` — last-seen state for incremental fetches.
- `scores.json` — LLM score cache keyed by item URL.
- `media-summaries.json` — video/podcast transcript summary cache.
- `media-queue.json` — video/podcast processing status by URL (`pending`, `processing`, `summarized`, `failed`, `skipped_too_long`).
- `logs/*.log` — component logs.
- `/Users/wendy/park-io/inbox/inbox-workflow.html` — human-readable inbox workflow map.
- `/Users/wendy/park-io/inbox/inbox-workflow.json` — machine-readable inbox workflow map.
- `/Users/wendy/park-io/inbox/inbox-workflow.yaml` — source of truth for the inbox workflow diagram.
- `/Users/wendy/park-io/inbox/validate-workflow.py` — closed-system validator for workflow YAML.

## Output Policy

- An `item` is one fetched content unit: one X post, one blog/news article, one GitHub release, one YouTube/podcast video, one Douyin video, or one WeChat article.
- `profile_id` is the stable attribution key. `anthropic` includes Anthropic, Claude, Claude Code, and Anthropic/Claude people. `openai` includes OpenAI, ChatGPT, Codex, and OpenAI people.
- Item filenames use `YY-MM-DD-profile-channel-slug.md` in the long-term library.
- `inbox/unprocessed/YY-MM-DD-profile.md` is the pending queue file for a profile. It is flat: no profile subfolder under `unprocessed`.
- `inbox/processed/<YY-MM-DD>/YY-MM-DD-profile.md` is the processed batch evidence file.
- `inbox/sent/` keeps only the final Markdown artifact as `YY-MM-DD.md`. HTML and PNG are transient Telegram attachments and are removed after a successful send.
- `library/profiles/<profile_id>/items/` is the long-term item archive. Every processed item is archived there, whether or not it enters the digest.
- A profile directory has exactly two primary surfaces: `profile.md` for the source/profile background and `items/` for individual content.
- `items/` must contain individual items directly. Do not create channel or migration wrapper folders such as `legacy-douyin/`, `legacy-wechat/`, `legacy-blog/`, `post/`, `x/`, `youtube/`, or `wechat/` under `items/`.
- Channel belongs in item metadata and the item filename, not in another folder layer.
- `library/独立链接/` stores manually saved links or media that do not map to a tracked profile.
- `library/` should only contain two user-facing folders: `profiles/` and `独立链接/`. Operational import/export files belong under `outbox/`.
- `inbox/processed/` is retained for 72 hours as a debug window; long-term memory lives in `library/profiles`.
- Official/company channels (`code`, `official`, and key company people) bypass score filtering. A scoring outage must not hide OpenAI, Anthropic, Claude, Codex, or official-person account updates from the official section after they have been fetched.
- Podcast / YouTube / Douyin, manually supplied WeChat articles, and saved X posts are user-curated inputs. They bypass score filtering.
- Saved X posts and manually supplied WeChat articles are also independent items by default. Do not force them into canonical event buckets such as `Claude Code 工具链与 Fast Mode 更新` or `ChatGPT / Codex 移动端代理预览` unless they are the same URL or an explicitly verified duplicate.
- X/Twitter items use an X-specific presentation. For single X items, prefer `author + content` over a generated headline plus a second summary paragraph; short posts and X Articles should not repeat the same idea in both the heading and the body.
- The public newsletter is reader-facing. It must not show pipeline metadata such as fetch counts, filter counts, source health tables, generated timestamps, `WeChat ID`, raw `t.co` links, `文章标题`, `引用内容`, score/tags/line-fit labels, or internal file names. Those belong in `inbox/status.html`.
- Markdown and HTML must use the same reader-cleaning layer before rendering. Raw item files may keep source metadata for archival/debugging, but rendered product surfaces must show only title, useful paragraph, and source link.
- Video/audio files are not stored in `unprocessed` or `processed`. Fetch writes title/link/metadata first; transcript jobs may temporarily download audio/video, transcribe with MLX Whisper, write transcript text back into Markdown, organize the transcript summary, and then delete the media file.
- AI quality check is non-blocking by default. Rule-based quality checks still block pushes; set `PARKIO_STRICT_AI_QUALITY=1` when testing if AI QC should become a hard gate again.
- Deterministic quality gates block pushes only for product red lines: missing artifacts, producer/agent voice, internal metadata leaks, duplicate event headings, duplicate push URLs, or local file URLs. Non-fatal presentation issues such as repeated visible links, no push URL, or more than 10 candidate URLs are warnings and must not stop the daily push. AI QC is a second opinion; deterministic red lines are the product contract.
- Telegram delivery is daily. If a finished digest has no high-value push URL, it still sends the daily summary and attachments.
- Daily digest selection and event dedupe are scoped to the current batch only. Do not look back at prior newsletters, Telegram push state, or library history to decide whether today's item should appear.
- Cross-run state has narrow responsibilities only: `state.json` prevents fetchers from importing the same raw item repeatedly, and `tg-push-state.json` is a delivery/idempotency log for Telegram. Neither file may provide reader-facing summaries or remove an item from today's digest.
- Reader-facing summaries must be generated from the current item's actual content. Do not hardcode author-specific fallback summaries such as a Roland.W paragraph for a whole topic bucket.
- X/Twitter items should contain actual content. For quoted, retweeted, or X Article posts, fetchers should prefer the referenced long content when the user's source only adds a short comment.

## Workflow Diagram Contract

The inbox workflow diagram is generated from:

```text
/Users/wendy/park-io/inbox/inbox-workflow.yaml
```

The YAML is the source of truth; HTML/PNG/JSON are rendered artifacts. The
workflow must be modeled as a closed system:

- Only `role: entry` nodes may have no incoming edge.
- All non-entry nodes must be reachable from an entry node.
- Final newsletter sections are not independent nodes or entry points.
- Section 1/2/3/4 must be `artifact_component` entries under the final brief
  assembly artifact.
- `artifact_component` must not appear as a top-level node.
- `sent_artifact` must be generated from an upstream process, decision, or
  artifact node.

Before rendering the workflow diagram, run:

```bash
python3 /Users/wendy/park-io/inbox/validate-workflow.py /Users/wendy/park-io/inbox/inbox-workflow.yaml
```

`render-workflow-diagram.py` runs this validator automatically before writing
HTML/PNG/JSON. If validation fails, the diagram must not be rendered or treated
as updated.

## Source Onboarding Baseline

Daily fetch is delta-only. When adding a new source or when a profile lacks
historical context, run:

```bash
python3 onboard-baseline.py <profile_id-or-source-name> --per-source 12
```

The baseline writes to:

```text
/Users/wendy/park-io/library/profiles/<profile_id>/profile.md
```

It looks back across supported channels for that profile, summarizes the recent
history into `Baseline Summary`, `Source Persona`, `Scoring Calibration`, and
`How To Use In Daily Summary`, then records unsupported collectors as baseline
gaps. RSS/YouTube feeds and X/Twitter profiles are supported. Scraped official
blog indexes, WeChat account timelines, and Douyin historical timelines depend
on external collectors and may appear as blockers.

For newly added Douyin sources, onboarding must also process the latest 5
videos immediately: archive the item, temporarily download the video, transcribe
with MLX Whisper, write `Baseline Summary` and `Transcript` back to the
library item, then delete temporary media. This is separate from daily fetch:
the historical 5 items are baseline context, not today's digest items unless
they were published today.

## WeChat Article Discovery

For one-off articles, use the manual collection inbox:

```text
/Users/wendy/park-io/inbox/manual-links.md
```

Paste one URL per line under `Pending`. `fetch-manual-links.py` runs during the
normal 4-hour fetch cycle, imports supported links into the next digest batch,
then moves successful links to `Imported`. Failed links are listed under
`Failed` with the error. Imported URLs are also recorded in `state.json` so the
same link is not imported again. Manual links are user-curated and bypass score
filtering. If the article belongs to a tracked WeChat profile, it is archived
under that profile; otherwise it is archived under `library/独立链接/`.

Manual seed URLs are fetched by `fetch-wechat.py`. If the account maps to a
tracked profile, the article is saved under
`/Users/wendy/park-io/library/profiles/<profile_id>/items/`.

For automatic public-account discovery, the preferred inbox path is a local
WeChat RSS/JSON bridge such as `cooderl/wewe-rss` or `rachelos/we-mp-rss`.
Add a source row with `platform=wechat-rss` and the bridge feed URL in `url`, or
keep `platform=wechat` and add `rss_url <feed-url>` to the source notes.
`fetch-wechat-rss.py` imports new feed entries every fetch run, writes today's
new articles into `inbox/unprocessed`, and archives full text under
`library/profiles/<profile_id>/items/`.

Local WeWe RSS deployment:

```bash
colima start
docker run -d --name wewe-rss -p 4000:4000 \
  -e DATABASE_TYPE=sqlite \
  -e AUTH_CODE=parkio \
  -e SERVER_ORIGIN_URL='http://localhost:4000' \
  -e FEED_MODE=fulltext \
  -e CRON_EXPRESSION='15 */4 * * *' \
  -e TZ='Asia/Shanghai' \
  -v /Users/wendy/work/input-to-park/.runtime/wewe-rss/data:/app/data \
  cooderl/wewe-rss-sqlite:latest
docker update --restart unless-stopped wewe-rss
```

Dashboard: `http://localhost:4000/dash`; auth code: `parkio`.
WeWe RSS uses the WeRead account `Zinan`. Configured public-account feeds:
`数字生命卡兹克`, `AGI Hunt`, `Ray在思考`, `卡尔的AI沃茨`, `海外独角兽`,
`嘉妍Kea`, `峥嵘岁月AI`, and `深思SenseAI`. Each corresponding `sources.md`
row stores its `rss_url` so Park-IO can import it during the normal fetch run.

`深思SenseAI` maps to `profile_id=shensi-senseai`. Its seed article and future
manual links from the same account are archived under that profile; automatic
updates come from `http://localhost:4000/feeds/MP_WXS_3016155866.json`.

Exporter-based discovery is the fallback / backfill path. Use a WeChat exporter
such as `wechat-article-exporter` to export account article data as
JSON/HTML/Markdown into:

```text
/Users/wendy/park-io/outbox/wechat-exporter/
```

`fetch-wechat-exporter.py` imports that directory every fetch run. It records
its own status as `WeChat Exporter Bridge` in source health so missing setup is
visible instead of silent.

The local WeWe RSS bridge is the primary automatic path. The exporter directory
is still a fallback / backfill path and may remain unconfigured.

## Douyin Status

`fetch-douyin.py` monitors configured Douyin profiles and writes new videos into
the daily raw queue. As of 2026-05-29, five Douyin sources are configured:
慢学AI, 小天fotos, dontbesilent聊赚钱, MyElc, and 柱子哥TzFilm. The fetch stage explicitly
adds `~/content-toolkit/capabilities/download` to `PYTHONPATH` and `fetch-all.sh`
uses Python 3.11+ so launchd and manual runs use the same Douyin client.

The current Douyin path internalizes the useful parts of
`jiji262/douyin-downloader` through the local `content-toolkit` downloader:
profile post pagination, XBogus/ABogus signing, cookies, retry/backoff,
standardized metadata, and Playwright browser fallback for item detail/download.
`NanmiCoder/MediaCrawler` is treated as the heavier fallback pattern: if the
API/signing path breaks, use a browser/CDP session with an existing Douyin login
state rather than adding more fragile API-only logic. Keep this as fallback
because it is larger and stateful; the default fetch path should remain the
lightweight API client.

If the dashboard shows `DouyinAPIClient unavailable`, first check the runtime:

```bash
cd /Users/wendy/work/input-to-park
python3 -V
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "content-toolkit/capabilities/download"))
from content_downloader.adapters.douyin.api_client import DouyinAPIClient
print(sys.executable, sys.version.split()[0], DouyinAPIClient)
PY
```

`/usr/bin/python3` on macOS is too old for this client and should not be used by
launchd. `fetch-all.sh` logs the chosen Python path at the start of every run.

First-run behavior: existing historical videos are archived into
`/Users/wendy/park-io/library/profiles/<profile>/items/`, but only videos
published today enter `inbox/unprocessed`. When a new Douyin video enters the
raw queue, `fetch-media-transcripts.py` automatically treats it like YouTube:
it temporarily downloads the video through `content-downloader`, transcribes it
with MLX Whisper, writes the transcript and consumer-facing summary back to the
raw Markdown/cache, and deletes the downloaded media file.

For YouTube, the transcript worker first tries subtitles, then audio ASR only
when subtitles are unavailable or too short. It uses
`/Users/wendy/park-io/secrets/youtube-cookies.txt` when present, then falls back
to browser cookie sources from `PARKIO_YTDLP_COOKIE_SOURCES`
(`chrome,chrome:Default` by default). Subtitle fetches use
`--ignore-no-formats-error` because YouTube can expose subtitle tracks while
blocking downloadable video formats. Do not store YouTube cookies in source
files, logs, README examples, or rendered newsletters.

Media processing statuses are recorded in `media-queue.json`:
`summarized`, `failed`, `skipped_too_long`, and `no_transcript`. These statuses
are owner-facing only and must not leak into the final newsletter body.

## Status / Owner Panel

`generate-status.py` writes `/Users/wendy/park-io/inbox/status.html`. It should
answer operational questions before the daily push:

- Which sources had new items today.
- Which sources fetched successfully but had no new items.
- Which sources failed or were filtered out.
- Whether X auth, WeWe RSS, Douyin downloader/cookies, and MLX Whisper are
  currently available.
- Current media transcript queue counts by status.

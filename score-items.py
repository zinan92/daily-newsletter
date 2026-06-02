#!/usr/bin/env python3
"""
score-items.py — Score every unscored item in today's inbox via LLM.

For each item, the LLM produces:
  - relevance_score (1-5)
  - narrative_tags (1-3 short kebab-case tags)
  - reason (short explanation for keeping or filtering)

Results are stored in scores.json (keyed by item URL). Already-scored items
are skipped on subsequent runs (incremental).

Designed to run between fetch-* and summarize.py in fetch-all.sh.
Borrows the prompt structure from zinan92/intel's tagging/llm.py, adapted
for this user's interests (AI tooling + 自媒体 + practical builder content).
"""
import json
import os
import re
import time
from pathlib import Path

from lib import (
    PARKIO,
    PROFILE_LIBRARY_DIR,
    ROOT,
    processed_batch_dir,
    llm_call,
    log,
    today,
    now_utc,
    parse_frontmatter,
    parse_md_items,
)
from digest_config import media_source_names

SCORES_PATH = ROOT / "scores.json"
SOURCES_PATH = PARKIO / "sources.md"
BATCH_SIZE = 10
MIN_INTERVAL_SEC = 1.0
RESCORE_CONTEXT = os.environ.get("PARKIO_RESCORE_CONTEXT") == "1"
ALWAYS_INCLUDE_CATEGORIES = {"video-podcast"}
ALWAYS_INCLUDE_SOURCES = {"我的 X 收藏"}
ALWAYS_INCLUDE_PLATFORMS = {"wechat", "douyin"}


SCORING_PROMPT = """You are the first owner of Park-IO's daily intelligence product.

Judge each item from the user's own baseline, not generic AI-news importance.

For each item, produce:

1. **score** (integer 1-5):
   - 5: Must-read today — changes what we should build, trade/research, or publish this week; concrete release/capability/access change; major official launch with practical implications.
   - 4: Useful — actionable detail, credible source interpretation, release note with workflow impact, strong content angle, or source that clarifies official/company movement. Long-form interviews/podcasts are 4 only when the guest/topic clearly maps to our development/content/trading lines.
   - 3: Keep if space — relevant but incremental; useful context but not urgent.
   - 2: Low — meta-commentary, retweet wrappers without commentary, vague "AI is changing things" posts, GitHub repos with empty descriptions
   - 1: Noise — pure self-promotion, replies without context, content unrelated to AI/content/building

Personal saved X items:
   - Treat "我的 X 收藏" as a direct user-interest signal, not a normal source feed.
   - Still score by usefulness: a bookmarked item can be 5/4 if it gives concrete workflow, product, content, or trading value; it can be 2/1 if it is clickbait, weak listicle, or only loosely related.
   - If the author looks repeatedly useful, mention that in the Chinese reason as a possible source-candidate signal.

2. **line_fit**:
   A list using only these values: "development", "trading", "content".
   Include a line only if the item gives concrete utility to that line.

3. **tags** (1-3 short kebab-case phrases, 2-4 words each):
   Capture the item's specific topic. Examples:
   - "claude-opus-4-7-launch"
   - "codex-goal-workflow"
   - "agent-cost-economics"
   - "douyin-content-strategy"
   - "wittgenstein-philosophy"
   - "github-trending-tool"
   Use the SAME tag across items covering the same topic so they cluster.

Respond with a JSON array. Each element MUST have:
- "url": the item's URL (string, copy exactly as given)
- "score": integer 1-5
- "line_fit": list of 0-3 strings from ["development", "trading", "content"]
- "tags": list of 1-3 lowercase kebab-case strings
- "reason": one concise Chinese sentence explaining what this helps us do, or why it is filtered

Respond ONLY with the JSON array, no surrounding text."""


def read_context_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")[:8000]


def read_sources_section(title: str, limit: int = 8000) -> str:
    text = read_context_file(SOURCES_PATH)
    if not text:
        return ""
    pattern = re.compile(rf"^## {re.escape(title)}\s*$", re.M)
    match = pattern.search(text)
    if not match:
        return ""
    next_match = re.search(r"^## .+$", text[match.end():], re.M)
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.end():end].strip()[:limit]


def owner_context() -> str:
    user_context = read_sources_section("User Context")
    personas = read_sources_section("Source Personas")
    profiles = []
    if PROFILE_LIBRARY_DIR.exists():
        for path in sorted(PROFILE_LIBRARY_DIR.glob("*/profile.md")):
            profiles.append(path.read_text(encoding="utf-8")[:5000])
    chunks = []
    if user_context:
        chunks.append("## User baseline\n\n" + user_context)
    if personas:
        chunks.append("## Source personas\n\n" + personas)
    if profiles:
        chunks.append("## Source onboarding profiles\n\n" + "\n\n---\n\n".join(profiles)[:12000])
    return "\n\n".join(chunks)


def extract_json_array(text: str) -> list:
    """Robust JSON array extraction — model may wrap in code block or prose."""
    text = text.strip()
    try:
        out = json.loads(text)
        if isinstance(out, list):
            return out
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            out = json.loads(m.group(1).strip())
            if isinstance(out, list):
                return out
        except json.JSONDecodeError:
            pass
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            out = json.loads(m.group(0))
            if isinstance(out, list):
                return out
        except json.JSONDecodeError:
            pass
    return []


def score_batch(batch: list) -> list:
    """batch: [{url, title, content, source}]. Returns valid score dicts."""
    parts = []
    for it in batch:
        parts.append(
            f"URL: {it['url']}\n"
            f"Source: {it['source']}\n"
            f"Category: {it.get('category', '')}\n"
            f"Title: {it.get('title', '')}\n"
            f"Content: {(it.get('content') or '')[:800]}"
        )
    context = owner_context()
    prompt = SCORING_PROMPT
    if context:
        prompt += "\n\n" + context
    prompt += "\n\n## Items to score\n\n" + "\n---\n".join(parts)

    text = llm_call(prompt, max_tokens=3000)
    raw = extract_json_array(text)

    valid = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        url = r.get("url")
        try:
            score = int(r.get("score"))
        except (TypeError, ValueError):
            continue
        if not url or not (1 <= score <= 5):
            continue
        tags = r.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        line_fit = r.get("line_fit", [])
        if not isinstance(line_fit, list):
            line_fit = []
        allowed_lines = {"development", "trading", "content"}
        reason = str(r.get("reason", "")).strip()
        valid.append(
            {
                "url": url,
                "score": score,
                "line_fit": [str(v).strip() for v in line_fit if str(v).strip() in allowed_lines],
                "tags": [str(t).strip().lower() for t in tags[:3] if str(t).strip()],
                "reason": reason,
            }
        )
    return valid


SCORING_HEALTH_PATH = ROOT / "scoring-health.json"


def write_scoring_health(total_batches: int, failed_batches: int, queued: int, scored: int) -> None:
    """Persist a scoring-outage signal so the status dashboard can surface it.

    gotcha #21: a scoring outage must degrade visibly, not silently. When the
    LLM was unreachable for some/all batches, this records it; ordinary content
    that went unscored will be missing from the newsletter and the owner needs
    to know it was an outage, not an empty feed.
    """
    outage = total_batches > 0 and failed_batches > 0
    status = "ok"
    if outage:
        status = "outage" if failed_batches == total_batches else "degraded"
    payload = {
        "date": today(),
        "checked_at": now_utc(),
        "status": status,
        "total_batches": total_batches,
        "failed_batches": failed_batches,
        "queued_items": queued,
        "scored_items": scored,
    }
    SCORING_HEALTH_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if outage:
        log(
            "score",
            f"  !!! SCORING {status.upper()}: {failed_batches}/{total_batches} batches failed "
            f"({scored}/{queued} items scored). Ordinary feed may be missing — this is an "
            f"outage, not an empty feed. See scoring-health.json.",
        )


def main() -> None:
    scores: dict = {}
    if SCORES_PATH.exists():
        try:
            scores = json.loads(SCORES_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            scores = {}

    inbox = processed_batch_dir() if os.environ.get("PARKIO_BATCH_ID") or os.environ.get("PARKIO_BATCH_DIR") else PARKIO / "inbox" / "unprocessed"
    if not inbox.exists():
        log("score", f"no input dir, nothing to score: {inbox}")
        return

    md_files = sorted(p for p in inbox.rglob("*.md") if not p.name.startswith("000-"))
    log("score", f"START — {len(md_files)} source files, {len(scores)} already scored")

    queue: list = []
    for mf in md_files:
        try:
            text = mf.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(text)
            items = parse_md_items(body)
            category = fm.get("category", "")
            platform = fm.get("platform", "")
            for it in items:
                if not it.get("url"):
                    continue
                source_name = it.get("source") or fm.get("source_name", mf.stem)
                item_category = it.get("category") or category
                if (
                    platform in ALWAYS_INCLUDE_PLATFORMS
                    or item_category in ALWAYS_INCLUDE_CATEGORIES
                    or item_category.startswith("video-")
                    or item_category.startswith("wechat-")
                    or source_name in ALWAYS_INCLUDE_SOURCES
                    or source_name in media_source_names()
                ):
                    continue
                existing = scores.get(it["url"])
                if existing and not RESCORE_CONTEXT and existing.get("line_fit") is not None:
                    continue
                queue.append({**it, "source": source_name, "category": item_category})
        except Exception as ex:
            log("score", f"  {mf.name}: parse error {type(ex).__name__}: {ex}")

    log("score", f"  {len(queue)} new items to score")

    last_call = 0.0
    total_batches = 0
    failed_batches = 0
    scored_count = 0
    for i in range(0, len(queue), BATCH_SIZE):
        batch = queue[i : i + BATCH_SIZE]
        total_batches += 1
        # Rate limit
        elapsed = time.time() - last_call
        if elapsed < MIN_INTERVAL_SEC:
            time.sleep(MIN_INTERVAL_SEC - elapsed)
        last_call = time.time()

        try:
            results = score_batch(batch)
            now = now_utc()
            for r in results:
                scores[r["url"]] = {
                    "score": r["score"],
                    "tags": r["tags"],
                    "line_fit": r.get("line_fit", []),
                    "reason": r.get("reason", ""),
                    "scored_at": now,
                }
            scored_count += len(results)
            log(
                "score",
                f"  batch {i // BATCH_SIZE + 1}: {len(results)}/{len(batch)} scored",
            )
        except Exception as ex:
            failed_batches += 1
            log(
                "score",
                f"  batch {i // BATCH_SIZE + 1}: ERROR {type(ex).__name__}: {ex}",
            )

    SCORES_PATH.write_text(
        json.dumps(scores, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_scoring_health(total_batches, failed_batches, len(queue), scored_count)
    from lib import get_usage
    u = get_usage()
    log("score", f"DONE — total scored: {len(scores)} · LLM tokens: {u['total']} "
                 f"(prompt {u['prompt']} / completion {u['completion']} / reasoning {u['reasoning']}) over {u['calls']} calls")


if __name__ == "__main__":
    main()

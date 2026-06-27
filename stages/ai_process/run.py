#!/usr/bin/env python3
"""AI-first Daily Inbox processing pipeline.

Stage 4 owns all editorial judgment: item understanding, event merge,
selection, and final writing. It intentionally does not use scores.json,
deterministic newsletter fallback, or quality-check.py.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import is_youtube_short, llm_call, log, parse_frontmatter, parse_md_items, processed_batch_dir, today


PROMPT_DIR = REPO_ROOT / "prompts" / "ai-process"
ITEM_UNDERSTANDING_MAX_ITEMS = 4
ITEM_UNDERSTANDING_MAX_CONTENT_CHARS = 12000
EVENT_MERGE_MAX_TOKENS = 30000
SELECTION_MAX_TOKENS = 18000


class AIProcessError(RuntimeError):
    pass


@dataclass
class AIProcessResult:
    markdown: str
    deep_markdown: str
    processed_urls: list[str]
    push_urls: list[str]
    deep_urls: list[str]


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def json_payload(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def escape_probable_inner_quotes(value: str) -> str:
    """Best-effort repair for common LLM JSON mistakes.

    The most frequent failure is a JSON string containing natural-language
    quotes, e.g. `"新功能名为"调度任务""`. A double quote inside a string is only a
    legal closing quote when the next non-space character is a JSON structural
    delimiter. Otherwise, escape it and preserve the text.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    length = len(value)
    for idx, char in enumerate(value):
        if escaped:
            out.append(char)
            escaped = False
            continue
        if char == "\\":
            out.append(char)
            if in_string:
                escaped = True
            continue
        if char == '"':
            if not in_string:
                in_string = True
                out.append(char)
                continue
            next_idx = idx + 1
            while next_idx < length and value[next_idx].isspace():
                next_idx += 1
            next_char = value[next_idx] if next_idx < length else ""
            if next_char in {":", ",", "]", "}"} or not next_char:
                in_string = False
                out.append(char)
            else:
                out.append('\\"')
            continue
        out.append(char)
    return "".join(out)


def loads_json_lenient(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return json.loads(escape_probable_inner_quotes(value))


def extract_json(text: str) -> Any:
    raw = (text or "").strip()
    if not raw:
        raise AIProcessError("empty AI response")
    try:
        return loads_json_lenient(raw)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fenced:
        try:
            return loads_json_lenient(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass
    bracket = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
    if bracket:
        try:
            return loads_json_lenient(bracket.group(1))
        except json.JSONDecodeError:
            pass
    raise AIProcessError("AI response did not contain valid JSON")


def first_heading_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
        if line.startswith("## "):
            return line.removeprefix("## ").strip()
    return fallback


def item_from_single_markdown(path: Path, fm: dict, body: str) -> dict:
    title = str(fm.get("title") or first_heading_title(body, path.stem)).strip()
    return {
        "id": str(fm.get("id") or fm.get("url") or path.stem),
        "source": str(fm.get("source") or fm.get("source_name") or fm.get("profile_name") or ""),
        "author": str(fm.get("author") or fm.get("profile_name") or ""),
        "title": title,
        "url": str(fm.get("url") or ""),
        "published_at": str(fm.get("published_at") or fm.get("published") or ""),
        "platform": str(fm.get("platform") or ""),
        "category": str(fm.get("category") or ""),
        "channel": str(fm.get("channel") or ""),
        "profile_name": str(fm.get("profile_name") or ""),
        "duration": str(fm.get("duration") or ""),
        "content_type": str(fm.get("content_type") or fm.get("platform") or fm.get("category") or "markdown"),
        "file": str(path),
        "content": body.strip(),
    }


def collect_processed_items(batch_dir: Path | None = None) -> list[dict]:
    root = batch_dir or processed_batch_dir()
    rows: list[dict] = []
    for path in sorted(root.rglob("*.md")):
        rel_parts = path.relative_to(root).parts
        if path.name.startswith("000-") or path.name.startswith("deep-") or (bool(rel_parts) and (rel_parts[0] == "ai" or rel_parts[0].startswith("ai."))):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = parse_frontmatter(text)
        parsed = parse_md_items(body)
        if parsed:
            for idx, item in enumerate(parsed, 1):
                rows.append(
                    {
                        "id": item.get("url") or f"{path.stem}#{idx}",
                        "source": item.get("source") or fm.get("source_name") or fm.get("profile_name") or "",
                        "author": item.get("author") or fm.get("profile_name") or "",
                        "title": item.get("title") or path.stem,
                        "url": item.get("url") or "",
                        "published_at": item.get("published") or fm.get("published_at") or "",
                        "platform": str(fm.get("platform") or ""),
                        "category": str(fm.get("category") or ""),
                        "channel": str(fm.get("channel") or ""),
                        "profile_name": str(fm.get("profile_name") or ""),
                        "duration": str(fm.get("duration") or ""),
                        "content_type": fm.get("content_type") or fm.get("platform") or fm.get("category") or "markdown",
                        "file": str(path),
                        "content": item.get("content") or "",
                    }
                )
        else:
            rows.append(item_from_single_markdown(path, fm, body))
    return rows


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_payload(data) + "\n", encoding="utf-8")


def write_error(ai_dir: Path, stage: str, raw: str = "", error: str = "") -> None:
    ai_dir.mkdir(parents=True, exist_ok=True)
    if raw:
        (ai_dir / "raw-response.md").write_text(raw, encoding="utf-8")
    write_json(ai_dir / "error.json", {"stage": stage, "error": error})


def clear_stale_error(ai_dir: Path) -> None:
    for name in ("error.json", "raw-response.md"):
        path = ai_dir / name
        if path.exists():
            path.unlink()


def fail_schema(ai_dir: Path, stage: str, message: str) -> None:
    write_error(ai_dir, stage, "", message)
    raise AIProcessError(message)


def repair_json_response(raw: str, max_tokens: int = 8000) -> Any:
    prompt = (
        "The following AI response was intended to be JSON but failed JSON parsing.\n"
        "Return ONLY valid JSON. Preserve the exact data and meaning. Do not add markdown fences, commentary, or new fields.\n\n"
        "BROKEN JSON-LIKE RESPONSE:\n"
        f"{raw}"
    )
    repaired = llm_call(prompt, max_tokens=max_tokens, timeout=120)
    return extract_json(repaired)


def call_json_stage(ai_dir: Path, stage_name: str, prompt_file: str, payload: Any, max_tokens: int = 8000) -> Any:
    prompt = load_prompt(prompt_file) + "\n\nINPUT JSON:\n" + json_payload(payload)
    raw = ""
    try:
        raw = llm_call(prompt, max_tokens=max_tokens, timeout=240)
        try:
            data = extract_json(raw)
        except AIProcessError:
            log("ai-process", f"{stage_name}: invalid JSON; retrying JSON repair")
            data = repair_json_response(raw, max_tokens=max_tokens)
    except Exception as exc:
        write_error(ai_dir, stage_name, raw, f"{type(exc).__name__}: {exc}")
        raise
    return data


def repair_brief_markdown(raw: str, final_payload: dict, expected_item_count: int) -> str:
    date = str(final_payload.get("date") or "DATE")
    prompt = (
        "The following Daily Inbox brief markdown failed structural validation.\n"
        f"It must contain exactly {expected_item_count} bullet item(s), one bullet per selected event in selection.brief_universe.\n"
        "Rewrite the entire Markdown from INPUT JSON as the source of truth. The FAILED DRAFT is only diagnostic.\n"
        "Do not omit selected events. Do not split one event into multiple bullets. Do not add events not in selection.brief_universe.\n"
        "Output only Markdown. No code block. No explanations.\n\n"
        "Required structure, exactly:\n"
        f"# Daily Inbox 快讯 — {date}\n\n"
        "## 快讯\n\n"
        "### 底层工具\n\n"
        "### 工作流\n\n"
        "### 内容\n\n"
        "Each selected event must appear exactly once under its selection.subsection.\n"
        "If a subsection has no items, write: *(今日无内容)*.\n\n"
        "INPUT JSON:\n"
        f"{json_payload(final_payload)}\n\n"
        "FAILED DRAFT:\n"
        f"{raw}"
    )
    return llm_call(prompt, max_tokens=12000, timeout=240)


def validate_brief_markdown_with_repair(
    raw: str,
    final_payload: dict,
    expected_item_count: int,
    max_attempts: int = 3,
) -> str:
    current = raw
    last_exc: AIProcessError | None = None
    for attempt in range(0, max_attempts + 1):
        try:
            return validate_brief_markdown(current, expected_item_count)
        except AIProcessError as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break
            log("ai-process", f"brief_writing: {exc}; retrying structural repair {attempt + 1}/{max_attempts}")
            current = repair_brief_markdown(current, final_payload, expected_item_count)
    assert last_exc is not None
    raise last_exc


def missing_event_cards(cards: list[dict], events: list[dict]) -> list[dict]:
    assigned = {
        str(item_id or "").strip()
        for event in events
        for item_id in (event.get("item_ids") or [])
        if isinstance(event, dict)
    }
    return [card for card in cards if str(card.get("id") or "").strip() not in assigned]


def repair_event_merge(cards: list[dict], events: list[dict]) -> list[dict]:
    missing_cards = missing_event_cards(cards, events)
    prompt = (
        "The following event_merge output failed coverage validation.\n"
        "Return ONLY a valid JSON array of events.\n"
        "Every item card id must appear in exactly one event.item_ids array.\n"
        "Preserve the existing event grouping where it is reasonable, but add or adjust events so the missing item cards are covered.\n"
        "Do not invent item ids. Do not omit low-quality items; low-quality content can be represented as its own event and later discarded by selection.\n\n"
        "ALL ITEM CARDS:\n"
        f"{json_payload(cards)}\n\n"
        "CURRENT EVENTS:\n"
        f"{json_payload(events)}\n\n"
        "MISSING ITEM CARDS:\n"
        f"{json_payload(missing_cards)}"
    )
    raw = llm_call(prompt, max_tokens=EVENT_MERGE_MAX_TOKENS, timeout=240)
    try:
        repaired = extract_json(raw)
    except AIProcessError:
        repaired = repair_json_response(raw, max_tokens=EVENT_MERGE_MAX_TOKENS)
    if not isinstance(repaired, list):
        raise AIProcessError("event_merge repair must return a JSON array")
    return repaired


def force_cover_missing_event_cards(cards: list[dict], events: list[dict]) -> list[dict]:
    card_by_id = {str(card.get("id") or ""): card for card in cards}
    used: set[str] = set()
    cleaned: list[dict] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        valid_ids: list[str] = []
        for raw_item_id in event.get("item_ids") or []:
            item_id = str(raw_item_id or "").strip()
            if item_id not in card_by_id or item_id in used:
                continue
            valid_ids.append(item_id)
            used.add(item_id)
        if not valid_ids:
            continue
        copy = dict(event)
        copy["item_ids"] = valid_ids
        cleaned.append(copy)

    missing = [card for card in cards if str(card.get("id") or "") not in used]
    for idx, card in enumerate(missing, 1):
        card_id = str(card.get("id") or f"missing-{idx}")
        title = str(card.get("title") or card.get("main_claim") or card_id)
        cleaned.append(
            {
                "event_id": f"unmerged_{idx}_{card_id}"[:80],
                "event_title": title,
                "sources": [
                    {
                        "source": card.get("source") or "",
                        "author": card.get("author") or "",
                        "title": card.get("title") or title,
                        "url": card.get("url") or "",
                    }
                ],
                "item_ids": [card_id],
                "merged_summary": card.get("main_claim") or card.get("novelty") or title,
                "evidence": "AI event_merge did not cover this item; preserved as a single-item event for selection.",
                "discussion_level": "single",
            }
        )
    return cleaned


def validate_event_coverage_with_repair(
    ai_dir: Path,
    cards: list[dict],
    events: list[dict],
    max_attempts: int = 3,
) -> list[dict]:
    try:
        validate_event_coverage(ai_dir, cards, events)
        return events
    except AIProcessError as exc:
        if "event_merge omitted" not in str(exc):
            raise
        last_exc = exc

    current = events
    for attempt in range(1, max_attempts + 1):
        log("ai-process", f"event_merge: {last_exc}; retrying coverage repair {attempt}/{max_attempts}")
        current = repair_event_merge(cards, current)
        clear_stale_error(ai_dir)
        try:
            validate_event_coverage(ai_dir, cards, current)
            return current
        except AIProcessError as exc:
            if "event_merge omitted" not in str(exc):
                if "references unknown item_id" in str(exc):
                    log("ai-process", f"event_merge: {exc}; forcing single-item coverage for missing cards")
                    current = force_cover_missing_event_cards(cards, current)
                    clear_stale_error(ai_dir)
                    validate_event_coverage(ai_dir, cards, current)
                    return current
                raise
            last_exc = exc
    log("ai-process", f"event_merge: {last_exc}; forcing single-item coverage for missing cards")
    current = force_cover_missing_event_cards(cards, current)
    clear_stale_error(ai_dir)
    validate_event_coverage(ai_dir, cards, current)
    return current


def item_content_size(item: dict) -> int:
    return len(str(item.get("content") or "")) + len(str(item.get("title") or ""))


def chunk_items_for_understanding(items: list[dict]) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0
    for item in items:
        size = item_content_size(item)
        if current and (
            len(current) >= ITEM_UNDERSTANDING_MAX_ITEMS
            or current_chars + size > ITEM_UNDERSTANDING_MAX_CONTENT_CHARS
        ):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += size
    if current:
        chunks.append(current)
    return chunks


def item_understanding(ai_dir: Path, items: list[dict]) -> list[dict]:
    chunks = chunk_items_for_understanding(items)
    cards: list[dict] = []
    for idx, chunk in enumerate(chunks, 1):
        log("ai-process", f"item_understanding chunk {idx}/{len(chunks)} — {len(chunk)} items")
        data = call_json_stage(
            ai_dir,
            f"item_understanding_{idx:02d}",
            "01-item-understanding.md",
            chunk,
            max_tokens=12000,
        )
        if not isinstance(data, list):
            fail_schema(ai_dir, f"item_understanding_{idx:02d}", "item_understanding chunk must return a JSON array")
        cards.extend(data)
    return cards


def validate_selection(selection: Any) -> dict:
    if not isinstance(selection, dict):
        raise AIProcessError("selection must be a JSON object")
    for key in ("brief_universe", "deep_candidates", "discard"):
        if not isinstance(selection.get(key), list):
            raise AIProcessError(f"selection missing list: {key}")
    return selection


def validate_event_coverage(ai_dir: Path, cards: list[dict], events: list[dict]) -> None:
    card_ids: list[str] = []
    for idx, card in enumerate(cards, 1):
        if not isinstance(card, dict):
            fail_schema(ai_dir, "item_understanding", f"item card {idx} must be an object")
        card_id = str(card.get("id") or "").strip()
        if not card_id:
            fail_schema(ai_dir, "item_understanding", f"item card {idx} missing id")
        card_ids.append(card_id)

    duplicate_card_ids = sorted({card_id for card_id in card_ids if card_ids.count(card_id) > 1})
    if duplicate_card_ids:
        fail_schema(ai_dir, "item_understanding", f"duplicate item card id(s): {', '.join(duplicate_card_ids[:10])}")

    expected = set(card_ids)
    seen: dict[str, str] = {}
    unknown: list[str] = []
    duplicate_event_refs: list[str] = []

    for idx, event in enumerate(events, 1):
        if not isinstance(event, dict):
            fail_schema(ai_dir, "event_merge", f"event {idx} must be an object")
        event_id = str(event.get("event_id") or f"event[{idx}]")
        item_ids = event.get("item_ids")
        if not isinstance(item_ids, list) or not item_ids:
            fail_schema(ai_dir, "event_merge", f"{event_id} missing non-empty item_ids")
        deduped_item_ids: list[str] = []
        local_seen: set[str] = set()
        for raw_item_id in item_ids:
            item_id = str(raw_item_id or "").strip()
            if not item_id:
                fail_schema(ai_dir, "event_merge", f"{event_id} contains empty item_id")
            if item_id in local_seen:
                continue
            local_seen.add(item_id)
            if item_id not in expected:
                unknown.append(item_id)
                continue
            if item_id in seen:
                duplicate_event_refs.append(item_id)
                continue
            deduped_item_ids.append(item_id)
            seen[item_id] = event_id
        event["item_ids"] = deduped_item_ids

    if unknown:
        fail_schema(ai_dir, "event_merge", f"event_merge references unknown item_id(s): {', '.join(sorted(set(unknown))[:10])}")
    if duplicate_event_refs:
        log("ai-process", f"event_merge normalized duplicate item_id reference(s): {', '.join(sorted(set(duplicate_event_refs))[:10])}")
        events[:] = [event for event in events if event.get("item_ids")]

    missing = sorted(expected - set(seen))
    if missing:
        fail_schema(
            ai_dir,
            "event_merge",
            f"event_merge omitted {len(missing)} item card(s): {', '.join(missing[:10])}",
        )


def clean_markdown(markdown: str) -> str:
    text = re.sub(r"^```(?:markdown|md)?\s*", "", (markdown or "").strip())
    text = re.sub(r"\s*```$", "", text)
    return text


def brief_item_count(markdown: str) -> int:
    return len(re.findall(r"^- \*\*", markdown, flags=re.M))


def validate_brief_markdown(markdown: str, expected_item_count: int | None = None) -> str:
    text = clean_markdown(markdown)
    required = ("## 快讯", "### 底层工具", "### 工作流", "### 内容")
    for heading in required:
        pattern = r"^" + re.escape(heading).replace(r"\ ", r"\s+") + r"\s*$"
        if not re.search(pattern, text, flags=re.M):
            raise AIProcessError(f"final markdown missing {heading}")
    if re.search(r"^##\s+深读\s*$", text, flags=re.M):
        raise AIProcessError("brief markdown must not include 深读 section")
    if expected_item_count is not None:
        actual_item_count = brief_item_count(text)
        if actual_item_count != expected_item_count:
            raise AIProcessError(
                f"brief markdown rendered {actual_item_count} bullet item(s) for {expected_item_count} selected event(s)"
            )
    return text


def markdown_link_text(text: str) -> str:
    return text.replace("[", "\\[").replace("]", "\\]").strip()


def markdown_heading_link_urls(markdown: str) -> list[str]:
    urls: list[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^###\s+\[[^\]]+\]\(([^)]+)\)\s*$", line.strip())
        if match:
            urls.append(match.group(1).strip())
    return urls


def primary_event_url(event: dict) -> str:
    for source in event.get("sources") or []:
        if isinstance(source, dict):
            url = str(source.get("url") or "").strip()
            if url:
                return url
    return ""


def deep_primary_urls(events: list[dict], selection: dict) -> list[str]:
    lookup = event_lookup(events)
    urls: list[str] = []
    for row in selection.get("deep_candidates", []):
        event = lookup.get(row_event_id(row))
        url = primary_event_url(event or {})
        if url:
            urls.append(url)
    return urls


def ensure_deep_heading_links(markdown: str, urls: list[str]) -> str:
    text = clean_markdown(markdown)
    if not urls:
        return text

    linked: list[str] = []
    heading_idx = 0
    for line in text.splitlines():
        if line.startswith("### ") and heading_idx < len(urls):
            url = urls[heading_idx]
            title = line.removeprefix("### ").strip()
            existing = re.match(r"^\[([^\]]+)\]\(([^)]+)\)\s*$", title)
            if existing:
                title = existing.group(1).strip()
            if url:
                line = f"### [{markdown_link_text(title)}]({url})"
            heading_idx += 1
        linked.append(line)
    return "\n".join(linked).strip()


def validate_deep_markdown(markdown: str, required_heading_urls: list[str] | None = None) -> str:
    text = clean_markdown(markdown)
    required = ("## 深读",)
    for heading in required:
        pattern = r"^" + re.escape(heading).replace(r"\ ", r"\s+") + r"\s*$"
        if not re.search(pattern, text, flags=re.M):
            raise AIProcessError(f"deep markdown missing {heading}")
    if re.search(r"^##\s+快讯\s*$", text, flags=re.M):
        raise AIProcessError("deep markdown must not include 快讯 section")
    if required_heading_urls:
        linked_urls = set(markdown_heading_link_urls(text))
        missing = [url for url in required_heading_urls if url not in linked_urls]
        if missing:
            raise AIProcessError(f"deep markdown missing heading link(s): {', '.join(missing[:3])}")
    return text


def event_lookup(events: list[dict]) -> dict[str, dict]:
    return {str(event.get("event_id") or ""): event for event in events if isinstance(event, dict)}


def row_event_id(row: dict) -> str:
    return str(row.get("event_id") or row.get("parent_brief_event_id") or "")


def normalize_selection_subsection(value: Any) -> str:
    subsection = str(value or "").strip()
    aliases = {
        "工具": "底层工具",
        "底层": "底层工具",
        "基础工具": "底层工具",
        "workflow": "工作流",
        "Workflow": "工作流",
        "工作流程": "工作流",
        "内容创作": "内容",
        "内容分发": "内容",
    }
    return aliases.get(subsection, subsection)


def validate_selection_references(events: list[dict], selection: dict) -> dict:
    lookup = event_lookup(events)
    if not selection.get("brief_universe"):
        raise AIProcessError("selection brief_universe must not be empty")

    brief_ids: set[str] = set()
    for idx, row in enumerate(selection.get("brief_universe", []), 1):
        event_id = row_event_id(row)
        if not event_id:
            raise AIProcessError(f"brief_universe[{idx}] missing event_id")
        if event_id not in lookup:
            raise AIProcessError(f"brief_universe references unknown event_id: {event_id}")
        brief_ids.add(event_id)
        subsection = normalize_selection_subsection(row.get("subsection"))
        row["subsection"] = subsection
        if subsection not in {"底层工具", "工作流", "内容"}:
            raise AIProcessError(f"brief_universe[{idx}] invalid subsection: {subsection}")

    discard_ids: set[str] = set()
    for idx, row in enumerate(selection.get("discard", []), 1):
        event_id = row_event_id(row)
        if not event_id:
            raise AIProcessError(f"discard[{idx}] missing event_id")
        if event_id not in lookup:
            raise AIProcessError(f"discard references unknown event_id: {event_id}")
        if event_id in brief_ids:
            raise AIProcessError(f"event cannot be both brief_universe and discard: {event_id}")
        discard_ids.add(event_id)

    missing_ids = sorted(set(lookup) - brief_ids - discard_ids)
    if missing_ids:
        raise AIProcessError(f"selection missing event_id(s): {', '.join(missing_ids[:10])}")

    for idx, row in enumerate(selection.get("deep_candidates", []), 1):
        parent = str(row.get("parent_brief_event_id") or "")
        if not parent:
            raise AIProcessError(f"deep_candidates[{idx}] missing parent_brief_event_id")
        if parent not in brief_ids:
            raise AIProcessError(f"deep_candidates[{idx}] parent not in brief_universe: {parent}")
        event_id = str(row.get("event_id") or parent)
        if event_id not in lookup:
            raise AIProcessError(f"deep_candidates[{idx}] references unknown event_id: {event_id}")
        row["event_id"] = event_id
    return selection


def selection_from_override(ai_dir: Path, events: list[dict], original: dict) -> dict:
    path = ai_dir / "selection-override.json"
    if not path.exists():
        return original
    try:
        override = validate_selection(json.loads(path.read_text(encoding="utf-8")))
        override = validate_selection_references(events, override)
    except Exception as exc:
        write_json(
            ai_dir / "selection-override-error.json",
            {"error": f"{type(exc).__name__}: {exc}", "action": "ignored_override_used_ai_selection"},
        )
        return original
    write_json(ai_dir / "03-selection.original.json", original)
    write_json(ai_dir / "03-selection.override-applied.json", override)
    return override


def selected_urls(events: list[dict], selection: dict, keys: tuple[str, ...]) -> list[str]:
    lookup = event_lookup(events)
    urls: list[str] = []
    for key in keys:
        for row in selection.get(key, []):
            event = lookup.get(row_event_id(row))
            if not event:
                continue
            for source in event.get("sources", []):
                url = str(source.get("url") or "")
                if url and url not in urls:
                    urls.append(url)
    return urls


def duration_seconds(value: Any, content: str = "") -> int | None:
    raw = str(value or "").strip()
    if not raw:
        match = re.search(r"(?:Duration|时长)[:：]\s*([0-9.]+)\s*(?:seconds?|秒)", content, flags=re.I)
        raw = match.group(1) if match else ""
    try:
        secs = float(raw)
    except (TypeError, ValueError):
        return None
    if secs <= 0:
        return None
    return int(round(secs))


def format_duration(seconds: int | None) -> str:
    if not seconds:
        return "未知"
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def is_youtube_item(item: dict) -> bool:
    haystack = " ".join(
        str(item.get(key) or "")
        for key in ("url", "source", "profile_name", "platform", "category", "content_type")
    ).lower()
    return "youtube.com" in haystack or "youtu.be" in haystack or "youtube" in haystack


def is_douyin_item(item: dict) -> bool:
    haystack = " ".join(
        str(item.get(key) or "")
        for key in ("url", "source", "profile_name", "platform", "category", "content_type")
    ).lower()
    return "douyin.com" in haystack or "douyin" in haystack or str(item.get("platform") or "").lower() == "douyin"


def video_description(item: dict, max_chars: int = 260) -> str:
    content = re.sub(r"<[^>]+>", " ", str(item.get("content") or ""))
    title = str(item.get("title") or "").strip()
    if content.strip().lower().startswith("transcript"):
        return title
    lines: list[str] = []
    for raw in content.splitlines():
        line = raw.strip().strip("# ").strip()
        if not line or line == title:
            continue
        if re.match(r"^(作者|时长|点赞|评论|收藏|分享)[:：]", line):
            continue
        if line.startswith("Duration:"):
            continue
        lines.append(line)
    text = re.sub(r"\s+", " ", " ".join(lines)).strip()
    if text.lower().startswith("transcript"):
        text = title
    if not text:
        text = title
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


def video_display_name(item: dict) -> str:
    return str(
        item.get("author")
        or item.get("profile_name")
        or item.get("source")
        or item.get("channel")
        or "Unknown"
    ).strip()


def video_updates(items: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for item in items:
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        kind = "youtube" if is_youtube_item(item) else "douyin" if is_douyin_item(item) else ""
        if not kind:
            continue
        secs = duration_seconds(item.get("duration"), str(item.get("content") or ""))
        if kind == "youtube" and is_youtube_short(url, secs):
            continue
        seen.add(url)
        rows.append(
            {
                "kind": kind,
                "name": video_display_name(item),
                "title": str(item.get("title") or "Untitled").strip(),
                "url": url,
                "description": video_description(item),
                "duration": format_duration(secs),
            }
        )
    return rows


def render_video_updates_section(items: list[dict]) -> tuple[str, list[str]]:
    rows = video_updates(items)
    if not rows:
        return "", []
    labels = (("youtube", "YouTube"), ("douyin", "抖音"))
    lines = ["## 视频更新", ""]
    urls: list[str] = []
    for kind, heading in labels:
        group = [row for row in rows if row["kind"] == kind]
        if not group:
            continue
        lines.extend([f"### {heading}", ""])
        for row in group:
            title = markdown_link_text(row["title"])
            lines.append(f"- **{row['name']}** | [{title}]({row['url']})")
            lines.append(f"  {row['description']}")
            lines.append(f"  时长：{row['duration']}")
            lines.append("")
            urls.append(row["url"])
    return "\n".join(lines).strip(), urls


def append_video_updates_to_deep(markdown: str, items: list[dict], date: str) -> tuple[str, list[str]]:
    block, urls = render_video_updates_section(items)
    if not block:
        return markdown, []
    text = clean_markdown(markdown)
    if not text:
        text = f"# Daily Inbox 深读 — {date}\n\n## 深读\n\n*(今日没有 AI 选择出的深读文章。)*"
    if "## 深读" not in text:
        text = text.rstrip() + "\n\n## 深读\n\n*(今日没有 AI 选择出的深读文章。)*"
    return f"{text.rstrip()}\n\n{block}", urls


def event_display_source(event: dict) -> tuple[str, str, str, str]:
    sources = event.get("sources") or []
    first = sources[0] if sources and isinstance(sources[0], dict) else {}
    return (
        str(first.get("source") or ""),
        str(first.get("author") or ""),
        str(first.get("title") or event.get("event_title") or ""),
        str(first.get("url") or ""),
    )


def write_calibration_page(root: Path, date: str, events: list[dict], selection: dict) -> None:
    label = root.name
    brief_by_id = {row_event_id(row): row for row in selection.get("brief_universe", [])}
    deep_by_parent = {str(row.get("parent_brief_event_id") or row_event_id(row)): row for row in selection.get("deep_candidates", [])}
    discard_by_id = {row_event_id(row): row for row in selection.get("discard", [])}
    rows: list[dict] = []
    for event in events:
        event_id = str(event.get("event_id") or "")
        source, author, title, url = event_display_source(event)
        brief = event_id in brief_by_id
        deep = event_id in deep_by_parent
        decision = brief_by_id.get(event_id) or deep_by_parent.get(event_id) or discard_by_id.get(event_id) or {}
        rows.append(
            {
                "event_id": event_id,
                "title": event.get("event_title") or title or event_id,
                "url": url,
                "source": source,
                "author": author,
                "subsection": decision.get("subsection") or "",
                "summary": decision.get("summary") or event.get("merged_summary") or "",
                "reason": decision.get("decision_reason") or "",
                "brief": brief,
                "deep": deep,
                "discarded": event_id in discard_by_id,
                "sources": event.get("sources") or [],
            }
        )
    html = render_calibration_html(date, label, rows)
    (root / f"review-{label}-selection.html").write_text(html, encoding="utf-8")


def render_calibration_html(date: str, label: str, rows: list[dict]) -> str:
    payload = json.dumps(rows, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Daily Inbox {date} 双产品校准</title>
<style>
:root {{ --bg:#f6f7f8; --panel:#fff; --text:#17202a; --muted:#667085; --line:#d9dee7; --brief:#1769aa; --deep:#8a4b10; --both:#426b1f; --discard:#98a2b3; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--text); }}
header {{ position:sticky; top:0; z-index:5; background:rgba(246,247,248,.96); border-bottom:1px solid var(--line); backdrop-filter:blur(10px); }}
.inner {{ max-width:1180px; margin:0 auto; padding:16px 20px; }}
h1 {{ font-size:20px; margin:0 0 10px; letter-spacing:0; }}
.toolbar {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; }}
input, select, button {{ height:34px; border:1px solid var(--line); border-radius:7px; background:#fff; color:var(--text); padding:0 10px; font-size:14px; }}
input {{ min-width:320px; flex:1; }}
button {{ cursor:pointer; }}
main {{ max-width:1180px; margin:0 auto; padding:16px 20px 40px; }}
.item {{ background:var(--panel); border:1px solid var(--line); border-left:5px solid transparent; border-radius:8px; padding:14px; margin:10px 0; display:grid; grid-template-columns:1fr auto; gap:12px; }}
.item.brief {{ border-left-color:var(--brief); }}
.item.deep {{ border-left-color:var(--deep); }}
.item.both {{ border-left-color:var(--both); }}
.item.discard {{ border-left-color:var(--discard); }}
.meta {{ color:var(--muted); font-size:12px; display:flex; gap:8px; flex-wrap:wrap; margin-bottom:6px; }}
.title {{ font-size:16px; font-weight:650; margin:0 0 8px; line-height:1.35; }}
.title a {{ color:var(--text); text-decoration:none; }}
.summary, .reason {{ font-size:13px; line-height:1.55; color:#344054; }}
.reason {{ margin-top:8px; color:#667085; }}
.actions {{ display:flex; gap:8px; align-items:flex-start; }}
button.active.brief {{ background:var(--brief); border-color:var(--brief); color:#fff; }}
button.active.deep {{ background:var(--deep); border-color:var(--deep); color:#fff; }}
textarea {{ width:100%; min-height:180px; border:1px solid var(--line); border-radius:8px; padding:10px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }}
@media (max-width:760px) {{ .item {{ grid-template-columns:1fr; }} input {{ min-width:0; }} }}
</style>
</head>
<body>
<header><div class="inner"><h1>Daily Inbox {date} 双产品校准</h1><div class="toolbar"><input id="q" type="search" placeholder="搜索标题、摘要、来源、理由" /><select id="filter"><option value="all">全部 signals</option><option value="brief">快讯</option><option value="deep">深读</option><option value="both">both</option><option value="none">未选中</option><option value="discard">舍弃</option></select><button id="exportBtn">导出 selection-override.json</button><button id="resetBtn">恢复默认</button></div></div></header>
<main><div id="stats"></div><div id="list"></div><textarea id="exportBox" placeholder="导出后，把 JSON 保存到 processed/{label}/ai/selection-override.json，再重新生成即可。"></textarea></main>
<script>
const ITEMS = {payload};
const STORAGE_KEY = 'daily-inbox-dual-product-selection-{label}';
const defaultState = Object.fromEntries(ITEMS.map(item => [item.event_id, {{brief:!!item.brief, deep:!!item.deep}}]));
let state = loadState();
function esc(s) {{ return String(s ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c])); }}
function loadState() {{ try {{ const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); if (saved && typeof saved === 'object') return {{...defaultState, ...saved}}; }} catch (e) {{}} return structuredClone(defaultState); }}
function saveState() {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }}
function itemState(item) {{ return state[item.event_id] || {{brief:false, deep:false}}; }}
function cls(st, item) {{ if (st.brief && st.deep) return 'both'; if (st.deep) return 'deep'; if (st.brief) return 'brief'; if (item.discarded) return 'discard'; return ''; }}
function passes(item) {{ const st = itemState(item); const f = document.getElementById('filter').value; if (f === 'brief' && !st.brief) return false; if (f === 'deep' && !st.deep) return false; if (f === 'both' && !(st.brief && st.deep)) return false; if (f === 'none' && (st.brief || st.deep)) return false; if (f === 'discard' && (st.brief || st.deep || !item.discarded)) return false; const q = document.getElementById('q').value.trim().toLowerCase(); return !q || [item.title,item.source,item.author,item.summary,item.reason,item.subsection].join('\\n').toLowerCase().includes(q); }}
function render() {{ const rows = ITEMS.filter(passes); document.getElementById('stats').textContent = `显示 ${{rows.length}} / 总计 ${{ITEMS.length}} · 快讯 ${{ITEMS.filter(i => itemState(i).brief).length}} · 深读 ${{ITEMS.filter(i => itemState(i).deep).length}}`; document.getElementById('list').innerHTML = rows.map(item => {{ const st = itemState(item); const href = item.url ? `href="${{esc(item.url)}}" target="_blank" rel="noreferrer"` : ''; return `<article class="item ${{cls(st, item)}}"><div><div class="meta"><span>${{esc(item.event_id)}}</span><span>${{esc(item.source || 'unknown')}}</span><span>${{esc(item.author)}}</span><span>${{esc(item.subsection)}}</span></div><h2 class="title"><a ${{href}}>${{esc(item.title)}}</a></h2><div class="summary">${{esc(item.summary || '(no summary)')}}</div>${{item.reason ? `<div class="reason">reason: ${{esc(item.reason)}}</div>` : ''}}</div><div class="actions"><button class="brief ${{st.brief ? 'active' : ''}}" data-kind="brief" data-id="${{esc(item.event_id)}}">快讯</button><button class="deep ${{st.deep ? 'active' : ''}}" data-kind="deep" data-id="${{esc(item.event_id)}}">深读</button></div></article>`; }}).join(''); }}
document.addEventListener('click', e => {{ const btn = e.target.closest('button[data-kind]'); if (!btn) return; const id = btn.dataset.id; const kind = btn.dataset.kind; state[id] = state[id] || {{brief:false, deep:false}}; state[id][kind] = !state[id][kind]; if (kind === 'deep' && state[id][kind]) state[id].brief = true; saveState(); render(); }});
document.getElementById('q').addEventListener('input', render); document.getElementById('filter').addEventListener('change', render);
document.getElementById('resetBtn').addEventListener('click', () => {{ state = structuredClone(defaultState); saveState(); render(); }});
document.getElementById('exportBtn').addEventListener('click', () => {{ const brief_universe = ITEMS.filter(i => itemState(i).brief).map(i => ({{event_id:i.event_id, subsection:i.subsection || '工作流', decision_reason:i.reason || 'manual override', summary:i.summary || ''}})); const deep_candidates = ITEMS.filter(i => itemState(i).deep).map(i => ({{event_id:i.event_id, parent_brief_event_id:i.event_id, decision_reason:i.reason || 'manual override', reading_angle:i.summary || ''}})); const chosen = new Set(brief_universe.map(i => i.event_id)); const discard = ITEMS.filter(i => !chosen.has(i.event_id)).map(i => ({{event_id:i.event_id, decision_reason:'manual override discard'}})); document.getElementById('exportBox').value = JSON.stringify({{date:'{date}', version:'dual-product-v1', brief_universe, deep_candidates, discard}}, null, 2); }});
render();
</script>
</body>
</html>
"""


def run_ai_process(date: str | None = None, batch_dir: Path | None = None) -> AIProcessResult:
    date = date or today()
    root = batch_dir or processed_batch_dir()
    ai_dir = root / "ai"
    clear_stale_error(ai_dir)
    items = collect_processed_items(root)
    if not items:
        raise AIProcessError(f"no processed markdown items found in {root}")
    write_json(ai_dir / "00-input-items.json", items)

    log("ai-process", f"item_understanding START — {len(items)} items")
    cards = item_understanding(ai_dir, items)
    if len(cards) < len(items):
        fail_schema(ai_dir, "item_understanding", f"item_understanding returned {len(cards)} cards for {len(items)} items")
    write_json(ai_dir / "01-item-cards.json", cards)

    log("ai-process", f"event_merge START — {len(cards)} cards")
    events = call_json_stage(ai_dir, "event_merge", "02-event-merge.md", cards, max_tokens=EVENT_MERGE_MAX_TOKENS)
    if not isinstance(events, list):
        fail_schema(ai_dir, "event_merge", "event_merge must return a JSON array")
    write_json(ai_dir / "02-events.json", events)
    events = validate_event_coverage_with_repair(ai_dir, cards, events)
    write_json(ai_dir / "02-events.json", events)

    log("ai-process", f"selection START — {len(events)} events")
    try:
        selection = validate_selection(call_json_stage(ai_dir, "selection", "03-selection.md", events, max_tokens=SELECTION_MAX_TOKENS))
        selection = validate_selection_references(events, selection)
    except AIProcessError as exc:
        fail_schema(ai_dir, "selection", str(exc))
    selection = selection_from_override(ai_dir, events, selection)
    write_json(ai_dir / "03-selection.json", selection)
    write_json(ai_dir / "discard-log.json", selection.get("discard", []))
    write_calibration_page(root, date, events, selection)

    final_payload = {
        "date": date,
        "events": events,
        "selection": selection,
    }
    final_prompt = load_prompt("04-brief-writing.md").replace("{date}", date)
    raw = ""
    expected_brief_count = len(selection.get("brief_universe", []))
    try:
        raw = llm_call(final_prompt + "\n\nINPUT JSON:\n" + json_payload(final_payload), max_tokens=9000, timeout=240)
        markdown = validate_brief_markdown_with_repair(raw, final_payload, expected_brief_count)
    except Exception as exc:
        write_error(ai_dir, "brief_writing", raw, f"{type(exc).__name__}: {exc}")
        raise
    (ai_dir / "04-brief.md").write_text(markdown + "\n", encoding="utf-8")

    deep_markdown = ""
    if selection.get("deep_candidates"):
        deep_prompt = load_prompt("05-deep-writing.md").replace("{date}", date)
        required_deep_urls = deep_primary_urls(events, selection)
        raw = ""
        try:
            raw = llm_call(deep_prompt + "\n\nINPUT JSON:\n" + json_payload(final_payload), max_tokens=9000, timeout=240)
            deep_markdown = ensure_deep_heading_links(raw, required_deep_urls)
            deep_markdown = validate_deep_markdown(deep_markdown, required_deep_urls)
        except Exception as exc:
            write_error(ai_dir, "deep_writing", raw, f"{type(exc).__name__}: {exc}")
            raise
    video_markdown_urls: list[str] = []
    deep_markdown, video_markdown_urls = append_video_updates_to_deep(deep_markdown, items, date)
    if deep_markdown:
        deep_markdown = validate_deep_markdown(deep_markdown)
        (ai_dir / "05-deep.md").write_text(deep_markdown + "\n", encoding="utf-8")
    else:
        write_json(ai_dir / "05-deep-empty.json", {"date": date, "reason": "no deep_candidates_or_video_updates"})

    processed = [str(item.get("url") or item.get("id") or "") for item in items if str(item.get("url") or item.get("id") or "")]
    push = selected_urls(events, selection, ("brief_universe",))[:10]
    deep_urls = selected_urls(events, selection, ("deep_candidates",))
    for url in video_markdown_urls:
        if url not in deep_urls:
            deep_urls.append(url)
    return AIProcessResult(
        markdown=markdown,
        deep_markdown=deep_markdown,
        processed_urls=processed,
        push_urls=push,
        deep_urls=deep_urls,
    )

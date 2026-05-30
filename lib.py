"""Shared utilities for the input-to-park pipeline."""
import json
import os
import re
import sys
import time
import hashlib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parent
PARKIO = Path.home() / "park-io"
SOURCES_PATH = PARKIO / "sources.md"
TRACKING_LIST = SOURCES_PATH
STATE_PATH = ROOT / "state.json"
LOGS = ROOT / "logs"
PROMPTS = ROOT / "prompts"
INBOX = PARKIO / "inbox"
UNPROCESSED_DIR = INBOX / "unprocessed"
PROCESSED_DIR = INBOX / "processed"
SENT_DIR = INBOX / "sent"
LIBRARY_DIR = PARKIO / "library"
PROFILE_LIBRARY_DIR = LIBRARY_DIR / "profiles"
INDEPENDENT_LINKS_DIR = LIBRARY_DIR / "独立链接"

# -----------------------------------------------------------------------------
# Shared LLM client (CLIProxyAPI). Single definition — every script imports this
# instead of copy-pasting its own llm_call. Adds retry/backoff so a transient
# 502 no longer cascades into "no scores + English summaries" (gotcha #21), and
# raises LLMUnavailable so callers can surface the outage instead of silently
# degrading.
# -----------------------------------------------------------------------------
CLIPROXY_ENDPOINT = os.environ.get("PARKIO_CLIPROXY_ENDPOINT", "http://localhost:8317/v1/messages")
CLIPROXY_KEY = os.environ.get("PARKIO_CLIPROXY_KEY", "REDACTED-see-secrets-file")
CLIPROXY_MODEL = os.environ.get("PARKIO_CLIPROXY_MODEL", "claude-sonnet-4-5-20250929")
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMUnavailable(RuntimeError):
    """Raised when the LLM endpoint cannot be reached after retries."""


def llm_call(prompt: str, max_tokens: int = 2000, *, retries: int = 3, timeout: int = 120) -> str:
    """POST a single user message to CLIProxyAPI and return the text response.

    Retries transient failures (connection errors and retryable HTTP statuses)
    with exponential backoff. Raises LLMUnavailable if all attempts fail; a
    non-retryable HTTP error (e.g. 400/401) fails fast.
    """
    body = json.dumps(
        {
            "model": CLIPROXY_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(
            CLIPROXY_ENDPOINT,
            data=body,
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key": CLIPROXY_KEY,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = json.loads(r.read())
            return "".join(
                c.get("text", "") for c in resp.get("content", []) if c.get("type") == "text"
            ).strip()
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in _RETRYABLE_STATUS:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_exc = exc
        if attempt < retries:
            time.sleep(min(2 ** attempt, 8))
    raise LLMUnavailable(f"CLIProxyAPI unavailable after {retries} attempts: {last_exc}") from last_exc

PROFILE_ID_BY_SOURCE_NAME = {
    "Anthropic News": "anthropic",
    "Anthropic Engineering": "anthropic",
    "Claude Blog": "anthropic",
    "Anthropic X": "anthropic",
    "Claude X": "anthropic",
    "Claude Devs X": "anthropic",
    "Anthropic YouTube": "anthropic",
    "claude-code-releases": "anthropic",
    "Dario Amodei": "anthropic",
    "Daniela Amodei": "anthropic",
    "Mike Krieger": "anthropic",
    "OpenAI Blog": "openai",
    "OpenAI X": "openai",
    "ChatGPT X": "openai",
    "OpenAI YouTube": "openai",
    "ChatGPT YouTube": "openai",
    "openai-codex-releases": "openai",
    "Sam Altman": "openai",
    "Greg Brockman": "openai",
    "Kevin Weil": "openai",
    "Mark Chen": "openai",
    "慢学AI": "manxue-ai",
    "dontbesilent": "dontbesilent",
    "op7418": "guizang",
    "longdechen12": "longdechen",
    "vista8": "vista8",
    "wadezone": "wadezone",
    "lijigang": "lijigang",
    "ai_xiaomu": "huang-xiaomu",
    "rwayne": "roland-w",
    "Dwarkesh Podcast": "dwarkesh",
    "Latent Space": "latent-space",
    "No Priors Podcast": "no-priors",
    "Y Combinator YouTube": "y-combinator",
    "a16z YouTube": "a16z",
    "小君小宇宙 Podcast": "zhang-xiaojun",
    "Lex Fridman Podcast": "lex-fridman",
    "Joe Rogan / PowerfulJRE": "joe-rogan",
    "Why Not TV": "why-not-tv",
    "数字生命卡兹克": "shuzi-shengming-kazike",
    "AGI Hunt": "agi-hunt",
    "Ray在思考": "ray-thinking",
    "卡尔的AI沃茨": "karls-ai-watts",
    "海外独角兽": "haiwai-dujiaoshou",
    "嘉妍Kea": "kea",
    "峥嵘岁月AI": "zhengrong-suiyue-ai",
    "深思SenseAI": "shensi-senseai",
    "我的 X 收藏": "x-saved",
}


# -----------------------------------------------------------------------------
# Time helpers
# -----------------------------------------------------------------------------

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    override = os.environ.get("PARKIO_DATE", "").strip()
    if override:
        return override
    return datetime.now().strftime("%Y-%m-%d")


def digest_slot(dt: datetime | None = None) -> datetime:
    """Return the current daily digest slot."""
    dt = dt or datetime.now()
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def batch_id(dt: datetime | None = None) -> str:
    override = os.environ.get("PARKIO_BATCH_ID", "").strip()
    if override:
        return override
    return digest_slot(dt).strftime("%Y%m%d")


def batch_label(batch: str | None = None) -> str:
    batch = batch or batch_id()
    if re.fullmatch(r"\d{8}", batch):
        return f"{batch[2:4]}-{batch[4:6]}-{batch[6:8]}"
    if not re.fullmatch(r"\d{12}", batch):
        return batch
    time_part = batch[8:12]
    if time_part == "0800":
        suffix = "早"
    elif time_part == "2000":
        suffix = "晚"
    elif time_part < "2000":
        suffix = f"早-{time_part}"
    else:
        suffix = f"晚-{time_part}"
    return f"{batch[2:4]}-{batch[4:6]}-{batch[6:8]}-{suffix}"


def processed_batch_dir(batch: str | None = None) -> Path:
    override = os.environ.get("PARKIO_BATCH_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return PROCESSED_DIR / batch_label(batch or batch_id())


def batch_artifact_paths(batch: str | None = None, prefix: bool = True) -> tuple[Path, Path, Path]:
    batch = batch or batch_id()
    label = batch_label(batch)
    stem = f"000-{label}" if prefix else label
    base = processed_batch_dir(batch) if prefix else SENT_DIR
    return base / f"{stem}.md", base / f"{stem}.html", base / f"{stem}.png"


# -----------------------------------------------------------------------------
# Source list (CSV) and state (JSON)
# -----------------------------------------------------------------------------

def load_sources() -> list:
    """Read sources.md, parse the first markdown table, return active rows.

    sources.md is the single source of truth. The first markdown table is the
    tracking list, followed by owner context and source persona guidance.
    """
    if not SOURCES_PATH.exists():
        return []
    text = SOURCES_PATH.read_text(encoding="utf-8")
    return _parse_first_md_table(text)


_TABLE_SEPARATOR = re.compile(r"^\|[\s\-:|]+\|\s*$")


def _parse_first_md_table(text: str) -> list:
    """Parse the first markdown table in `text` and return active rows as dicts.
    A table is detected by a header row `| col | col | …` immediately followed by
    a separator row of `| --- | --- | …`.
    """
    rows: list = []
    lines = text.splitlines()
    i = 0
    while i < len(lines) - 1:
        line = lines[i].strip()
        nxt = lines[i + 1].strip()
        if line.startswith("|") and line.endswith("|") and _TABLE_SEPARATOR.match(nxt):
            headers = [c.strip() for c in line.strip("|").split("|")]
            i += 2  # skip header + separator
            while i < len(lines):
                row_line = lines[i].strip()
                if not (row_line.startswith("|") and row_line.endswith("|")):
                    break
                # Don't consume another separator-looking line (defensive)
                if _TABLE_SEPARATOR.match(row_line):
                    i += 1
                    continue
                cells = [c.strip().replace("\\|", "|") for c in row_line.strip("|").split("|")]
                if len(cells) == len(headers):
                    row = dict(zip(headers, cells))
                    if (row.get("active") or "true").lower() == "true":
                        row["profile_id"] = profile_id_for_source(row)
                        rows.append(row)
                i += 1
            return rows  # only first table
        i += 1
    return rows


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------

def inbox_dir() -> Path:
    d = UNPROCESSED_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_filename(s: str) -> str:
    """Strip filesystem-unfriendly chars from a name."""
    s = s.lower()
    s = re.sub(r"[^\w\-]+", "-", s, flags=re.UNICODE).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s or "unnamed"


def profile_id_for_source(source: dict) -> str:
    explicit = str(source.get("profile_id", "")).strip()
    if explicit:
        return safe_filename(explicit)
    name = str(source.get("name", "")).strip()
    if name in PROFILE_ID_BY_SOURCE_NAME:
        return PROFILE_ID_BY_SOURCE_NAME[name]
    return safe_filename(name)


def channel_for_source(source: dict) -> str:
    platform = str(source.get("platform", "")).strip().lower()
    name = str(source.get("name", "")).strip().lower()
    category = str(source.get("category", "")).strip().lower()
    url = str(source.get("url", "")).strip().lower()
    if platform == "twitter":
        return "x"
    if platform == "douyin":
        return "douyin"
    if platform in {"wechat", "wechat-rss"}:
        return "wechat"
    if "youtube.com/feeds/videos" in url or category.startswith("video-"):
        return "youtube"
    if "github.com" in url and "releases" in url:
        return "github"
    if platform == "scrape" or "blog" in name or "news" in name or "engineering" in name:
        return "blog"
    return safe_filename(platform or "web")


def item_slug(item: dict, max_len: int = 72) -> str:
    title = str(item.get("title") or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", title) or re.match(r"^[A-Z][a-z]{2} \d{1,2}", title):
        title = ""
    raw = title or item.get("text") or item.get("content") or item.get("url") or "item"
    slug = safe_filename(str(raw))[:max_len].strip("-")
    return slug or "item"


def item_identity(item: dict) -> str:
    value = str(item.get("url") or item.get("id") or item.get("title") or item.get("content") or "")
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def item_filename(source: dict, item: dict) -> str:
    published = str(item.get("published") or today())[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
        published = today()
    profile = profile_id_for_source(source)
    channel = channel_for_source(source)
    slug = item_slug(item)
    suffix = item_identity(item)
    return f"{published[2:]}-{profile}-{channel}-{slug}-{suffix}.md"


def profile_day_filename(source: dict, day: str | None = None) -> str:
    published = (day or today())[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
        published = today()
    return f"{published[2:]}-{profile_id_for_source(source)}.md"


# -----------------------------------------------------------------------------
# YAML frontmatter (simple, no nesting)
# -----------------------------------------------------------------------------

def parse_frontmatter(text: str) -> Tuple[dict, str]:
    """Extract simple key:value frontmatter; returns (fm_dict, body_string).
    Body excludes the closing '---' delimiter and following blank line.
    """
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 5 :]
    # strip leading blank lines from body
    body = body.lstrip("\n")
    fm = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, body


def parse_md_items(body: str) -> list:
    """Parse a source .md body (post-frontmatter) into a list of item dicts.

    Each item: {title, url, content}. Assumes our writer's format:
        ## <title>
        <metadata line>
        <blank>
        <content lines...>
    """
    items: list = []
    lines_all = body.splitlines()
    starts: list[int] = []
    for idx, line in enumerate(lines_all):
        if not line.startswith("## "):
            continue
        next_idx = idx + 1
        while next_idx < len(lines_all) and not lines_all[next_idx].strip():
            next_idx += 1
        if next_idx < len(lines_all) and "[link](" in lines_all[next_idx]:
            starts.append(idx)
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines_all)
        lines = lines_all[start:end]
        if not lines:
            continue
        title = lines[0].replace("## ", "", 1).strip()
        p = "\n".join(lines)
        url_match = re.search(r"\[link\]\(([^)]+)\)", p)
        url = url_match.group(1).strip() if url_match else ""
        meta = lines[1].strip() if len(lines) > 1 else ""
        date_match = re.search(r"\*(\d{4}-\d{2}-\d{2})", meta)
        content_lines = lines[2:] if len(lines) >= 3 else []
        content = "\n".join(content_lines).strip()
        author_match = re.search(r"author:\s*([^·*]+)", meta)
        source_match = re.search(r"source:\s*([^·*]+)", meta)
        handle_match = re.search(r"\(@([^)]+)\)", meta)
        conv_match = re.search(r"conv:\s*(\d+)", meta)
        items.append(
            {
                "title": title,
                "url": url,
                "content": content,
                "published": date_match.group(1) if date_match else "",
                "meta": meta,
                "source": source_match.group(1).strip() if source_match else "",
                "author": re.sub(r"\s*\(@[^)]+\)", "", author_match.group(1)).strip() if author_match else "",
                "handle": handle_match.group(1).strip() if handle_match else "",
                "conversation_id": conv_match.group(1) if conv_match else "",
            }
        )
    return items


def render_frontmatter(fm: dict) -> str:
    """Render simple key:value frontmatter block including delimiters."""
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


# -----------------------------------------------------------------------------
# Item rendering (markdown sections)
# -----------------------------------------------------------------------------

def _twitter_item_md(item: dict) -> str:
    text = (item.get("text") or item.get("content") or "").strip()
    title = item.get("title") or ""
    if not title or title == "Tweet":
        title = re.sub(r"\s+", " ", text)[:80].strip(" ，。,.") or item.get("time") or "Tweet"
    likes = item.get("likes", 0)
    rts = item.get("rts", 0)
    url = item.get("url", "")
    author = item.get("author", "")
    handle = item.get("handle", "")
    author_part = f"author: {author}"
    if handle and handle not in author:
        author_part += f" (@{handle})"
    source = item.get("source") or ""
    source_part = f"source: {source} · " if source else ""
    conv = item.get("conversation_id") or ""
    conv_part = f" · conv: {conv}" if conv else ""
    meta = f"**{source_part}{author_part} · likes: {likes} · rts: {rts}{conv_part}** · [link]({url})"
    parts = [f"## {title}", meta]
    if text:
        parts.extend(["", text])
    return "\n".join(parts)


def _article_item_md(item: dict) -> str:
    """For RSS / scrape / GitHub releases — items have title + url + published + content."""
    title = (item.get("title") or "Untitled").strip()
    url = item.get("url", "")
    published = item.get("published") or ""
    content = (item.get("content") or item.get("summary") or "").strip()
    meta_parts = []
    if item.get("source"):
        meta_parts.append(f"source: {item['source']}")
    if published:
        # Use just the date portion for cleanliness when full ISO available
        meta_parts.append(f"*{published[:10]}*")
    if url:
        meta_parts.append(f"[link]({url})")
    meta = " · ".join(meta_parts)
    parts = [f"## {title}"]
    if meta:
        parts.append(meta)
    if content:
        parts.extend(["", content])
    return "\n".join(parts)


def render_items_md(items: list, platform: str) -> str:
    if not items:
        return ""
    if platform == "twitter":
        renderer = _twitter_item_md
    else:
        renderer = _article_item_md
    return "\n\n".join(renderer(it) for it in items)


# -----------------------------------------------------------------------------
# Source output (markdown file, accumulating across runs)
# -----------------------------------------------------------------------------

def write_source_output(source: dict, new_items: list) -> Path:
    """Append fetched content units to one profile-day queue file.

    The queue is flat and profile-day based:
        inbox/unprocessed/<YY-MM-DD-profile_id>.md
    """
    profile = profile_id_for_source(source)
    platform = source["platform"]
    channel = channel_for_source(source)
    valid_items = []
    for item in new_items:
        if platform == "twitter" and not str(item.get("text") or item.get("content") or "").strip():
            log("write-source-output", f"skip empty twitter item: {item.get('url', '')}")
            continue
        valid_items.append(item)
    if not valid_items:
        return inbox_dir() / profile_day_filename(source)

    path = inbox_dir() / profile_day_filename(source)
    existing_fm: dict = {}
    existing_body = ""
    if path.exists():
        existing_fm, existing_body = parse_frontmatter(path.read_text(encoding="utf-8"))

    first_item = valid_items[0]
    existing_count = int(existing_fm.get("items", "0") or 0) if str(existing_fm.get("items", "0") or 0).isdigit() else 0
    fm = {
        "id": existing_fm.get("id") or hashlib.sha1(str(path.name).encode("utf-8")).hexdigest()[:10],
        "profile_id": profile,
        "profile_name": existing_fm.get("profile_name") or source.get("profile_name") or source["name"],
        "platform": "mixed",
        "channel": "mixed",
        "category": existing_fm.get("category") or source["category"],
        "published_at": existing_fm.get("published_at") or first_item.get("published", "") or today(),
        "fetched_at": existing_fm.get("fetched_at") or now_utc(),
        "first_fetch": existing_fm.get("first_fetch") or now_utc(),
        "last_fetch": now_utc(),
        "items": str(existing_count + len(valid_items)),
    }
    intro = existing_body.strip()
    if not intro:
        intro = (
            f"# {profile} · {today()}\n\n"
            f"> Profile: {profile} · pending raw inputs for the next digest.\n"
        )

    group_header = (
        f"\n\n---\n\n"
        f"**Source:** {source['name']} · **channel:** {channel} · **platform:** {platform} · "
        f"**category:** {source['category']} · [source link]({source['url']})\n\n"
    )
    enriched_items = [
        {
            **item,
            "source": source["name"],
            "channel": channel,
            "platform": platform,
            "category": source["category"],
        }
        for item in valid_items
    ]
    new_text = render_items_md(enriched_items, platform)
    path.write_text(render_frontmatter(fm) + intro.rstrip() + group_header + new_text + "\n", encoding="utf-8")
    return path


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

def log(component: str, msg: str) -> None:
    """Log to component-specific file + stderr."""
    LOGS.mkdir(exist_ok=True)
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    with open(LOGS / f"{component}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, file=sys.stderr)

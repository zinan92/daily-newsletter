#!/usr/bin/env python3
"""Import user-supplied one-off links from the vault inbox.

This is the collection surface for links the user wants in the next digest
without editing source configuration. It currently supports WeChat article URLs.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib import (
    INDEPENDENT_LINKS_DIR,
    PARKIO,
    load_sources,
    load_state,
    log,
    profile_id_for_source,
    safe_filename,
    save_state,
    today,
    write_source_output,
)

MANUAL_LINKS = PARKIO / "inbox" / "manual-links.md"
URL_RE = re.compile(r"https?://[^\s<>)\]]+")
WECHAT_URL_RE = re.compile(r"https://mp\.weixin\.qq\.com/s/[A-Za-z0-9_-]+")
SECTIONS = ("Pending", "Imported", "Failed")
TRAILING_URL_PUNCT = ".,;:!?，。；：！？)]）】"


def load_fetch_wechat():
    from ingestion.manual_links import wechat_seed

    return wechat_seed


def default_manual_links_text() -> str:
    return "\n".join(
        [
            "# Manual Links",
            "",
            "把你希望进入下一次 Daily Inbox 的单篇链接贴在这里，每行一个。",
            "系统会自动去重；导入成功后会自动从 Pending 移到 Imported。",
            "",
            "## Pending",
            "",
            "## Imported",
            "",
            "## Failed",
            "",
        ]
    )


def ensure_manual_links_file() -> None:
    if not MANUAL_LINKS.exists():
        MANUAL_LINKS.parent.mkdir(parents=True, exist_ok=True)
        MANUAL_LINKS.write_text(default_manual_links_text(), encoding="utf-8")


def section_text(text: str, section: str) -> str:
    match = re.search(rf"^## {re.escape(section)}\s*$", text, flags=re.M)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^## .+$", text[start:], flags=re.M)
    end = start + next_match.start() if next_match else len(text)
    return text[start:end]


def urls_in_section(text: str, section: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in WECHAT_URL_RE.findall(section_text(text, section)):
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def clean_url(url: str) -> str:
    return url.rstrip(TRAILING_URL_PUNCT)


def pending_lines() -> list[str]:
    ensure_manual_links_file()
    text = MANUAL_LINKS.read_text(encoding="utf-8")
    return [line.rstrip() for line in section_text(text, "Pending").splitlines() if line.strip()]


def urls_from_pending(lines: list[str], pattern: re.Pattern[str] = WECHAT_URL_RE) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        for raw_url in pattern.findall(line):
            url = clean_url(raw_url)
            if url not in seen:
                seen.add(url)
                out.append(url)
    return out


def line_has_processed_url(line: str, processed_urls: set[str]) -> bool:
    return any(clean_url(url) in processed_urls for url in URL_RE.findall(line))


def existing_url_record(url: str, records: list[dict]) -> dict | None:
    for record in records:
        if record.get("url") == url:
            return record
    return None


def record_from_library(url: str, library_paths: list[str]) -> dict | None:
    for raw_path in library_paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if url not in text:
            continue
        title = ""
        for line in text.splitlines():
            if line.startswith("# "):
                title = line.removeprefix("# ").strip()
                break
        return {
            "date": today(),
            "title": title or "已导入链接",
            "url": url,
            "profile": path.parents[2].name if "profiles" in path.parts and len(path.parents) > 2 else "独立链接",
            "library_path": str(path),
        }
    return None


def render_manual_links(
    imported_records: list[dict],
    failed_records: list[dict],
    pending: list[str] | None = None,
) -> None:
    pending = pending or []
    lines = [
        "# Manual Links",
        "",
        "把你希望进入下一次 Daily Inbox 的单篇链接贴在这里，每行一个。",
        "系统会自动去重；导入成功后会自动从 Pending 移到 Imported。",
        "",
        "## Pending",
        "",
    ]
    lines.extend(pending)
    if pending:
        lines.append("")
    lines.extend(["## Imported", ""])
    for record in imported_records[-200:]:
        title = str(record.get("title") or "已导入链接").replace("\n", " ").strip()
        date = record.get("date") or today()
        profile = record.get("profile") or ""
        url = record.get("url") or ""
        suffix = f" · {profile}" if profile else ""
        lines.append(f"- {date}{suffix} · [{title}]({url})")
    lines.extend(["", "## Failed", ""])
    for record in failed_records[-100:]:
        date = record.get("date") or today()
        url = record.get("url") or ""
        error = str(record.get("error") or "unknown error").replace("\n", " ").strip()
        lines.append(f"- {date} · {url} · {error}")
    lines.append("")
    MANUAL_LINKS.write_text("\n".join(lines), encoding="utf-8")


def source_for_article(account: str, user_name: str, url: str, sources: list[dict]) -> dict:
    account_norm = account.strip()
    user_norm = user_name.strip()
    for src in sources:
        if src.get("platform") != "wechat":
            continue
        names = {
            str(src.get("name", "")).strip(),
            str(src.get("profile_name", "")).strip(),
        }
        if account_norm and account_norm in names:
            return src
        if user_norm and user_norm in str(src.get("notes", "")):
            return src
    return {
        "name": account_norm or "手动公众号文章",
        "profile_id": "manual-link",
        "profile_name": account_norm or "手动公众号文章",
        "platform": "wechat",
        "category": "wechat-manual",
        "url": url,
        "notes": "manual inbox link",
    }


def save_independent_article(item: dict, html: str, account: str) -> str:
    date = today()
    title = safe_filename(item.get("title", "wechat-article"))[:90]
    out_dir = INDEPENDENT_LINKS_DIR / safe_filename(f"{date}-{title}")[:140]
    out_dir.mkdir(parents=True, exist_ok=True)
    article = out_dir / "article.md"
    raw = out_dir / "raw.html"
    article.write_text(
        "\n".join(
            [
                "---",
                f"source: {account or '手动公众号文章'}",
                f"url: {item.get('url', '')}",
                f"published: {item.get('published', '')}",
                "origin: manual-links",
                "---",
                "",
                f"# {item.get('title', '微信公众号文章')}",
                "",
                item.get("content", ""),
                "",
            ]
        ),
        encoding="utf-8",
    )
    raw.write_text(html, encoding="utf-8")
    return str(article)


def main() -> int:
    pending = pending_lines()
    urls = urls_from_pending(pending, WECHAT_URL_RE)
    unsupported_urls = [
        url for url in urls_from_pending(pending, URL_RE) if not WECHAT_URL_RE.fullmatch(url)
    ]
    log("fetch-manual-links", f"START — {len(urls)} url(s)")
    state = load_state()
    key = "manual-links"
    if not urls:
        render_manual_links(
            list(state.get(key, {}).get("imported_records", [])),
            list(state.get(key, {}).get("failed_records", [])),
            pending,
        )
        if unsupported_urls:
            log("fetch-manual-links", f"  preserved {len(unsupported_urls)} unsupported pending url(s)")
        log("fetch-manual-links", "DONE")
        return 0

    fw = load_fetch_wechat()
    sources = load_sources()
    seen = set(state.get(key, {}).get("seen_urls", []))
    imported_records = list(state.get(key, {}).get("imported_records", []))
    failed_records = list(state.get(key, {}).get("failed_records", []))
    imported_by_source: dict[str, tuple[dict, list[dict]]] = {}
    library_paths: list[str] = []
    errors: list[str] = []
    processed_urls: set[str] = set()

    for url in urls:
        if url in seen:
            processed_urls.add(url)
            if not existing_url_record(url, imported_records):
                record = record_from_library(url, state.get(key, {}).get("library_paths", []))
                imported_records.append(
                    record
                    or {
                        "date": today(),
                        "title": "已导入链接",
                        "url": url,
                        "profile": "",
                        "library_path": "",
                    }
                )
            continue
        try:
            html = fw.fetch_url(url)
            item = fw.parse_article(url, html)
            item["url"] = url
            item["published"] = today()
            account = str(item.get("content", "")).splitlines()
            account_name = ""
            user_name = ""
            for line in account[:6]:
                if line.startswith("公众号："):
                    account_name = line.removeprefix("公众号：").strip()
                elif line.startswith("WeChat ID："):
                    user_name = line.removeprefix("WeChat ID：").strip()
            src = source_for_article(account_name, user_name, url, sources)
            if profile_id_for_source(src) == "manual-link":
                library_path = save_independent_article(item, html, account_name)
            else:
                library_path = fw.save_article_to_library(src, item, html)
            library_paths.append(library_path)
            imported_by_source.setdefault(src["name"], (src, []))[1].append(item)
            imported_records.append(
                {
                    "date": today(),
                    "title": item.get("title", "微信公众号文章"),
                    "url": url,
                    "profile": profile_id_for_source(src),
                    "source": src["name"],
                    "library_path": library_path,
                }
            )
            seen.add(url)
            processed_urls.add(url)
        except Exception as ex:
            error = f"{type(ex).__name__}: {ex}"
            errors.append(f"{url}: {error}")
            failed_records.append({"date": today(), "url": url, "error": error})
            processed_urls.add(url)
            log("fetch-manual-links", f"  ERROR {url}: {error}")

    imported = 0
    for _name, (src, items) in imported_by_source.items():
        write_source_output(src, items)
        imported += len(items)
        log("fetch-manual-links", f"  {src['name']}: {len(items)} NEW")

    state[key] = {
        "last_fetch": today(),
        "seen_urls": sorted(seen),
        "imported": imported,
        "library_paths": library_paths[-50:],
        "imported_records": imported_records[-200:],
        "failed_records": failed_records[-100:],
        "errors": errors[-20:],
    }
    save_state(state)
    remaining_pending = [line for line in pending if not line_has_processed_url(line, processed_urls)]
    render_manual_links(state[key]["imported_records"], state[key]["failed_records"], remaining_pending)
    if unsupported_urls:
        log("fetch-manual-links", f"  preserved {len(unsupported_urls)} unsupported pending url(s)")
    log("fetch-manual-links", f"DONE — imported {imported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

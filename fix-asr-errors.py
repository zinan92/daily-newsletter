#!/usr/bin/env python3
"""
fix-asr-errors.py — Apply systematic ASR (whisper) error corrections to all
polished .md files in the 慢学AI corpus.

Replacements:
  - 曼学AI / 漫学AI / 蛮学AI → 慢学AI         (channel name homophones)
  - Cloud → Claude                              (whisper hears "Claude" as "Cloud")
       EXCLUSIONS: "Google Cloud", "Cloudflare", "GoogleCloudTech"
  - Antropic → Anthropic                        (typo)

Reports per-file change counts. Idempotent: re-runs on already-fixed files
make zero changes.
"""
import re
import sys
from pathlib import Path

ROOT = Path.home() / "park-io" / "library" / "profiles" / "manxue-ai" / "items"

# Simple literal replacements (no context needed)
LITERAL_REPLACEMENTS = {
    "曼学AI": "慢学AI",
    "漫学AI": "慢学AI",
    "蛮学AI": "慢学AI",
    "Antropic": "Anthropic",
}

# Context-aware: Cloud → Claude, but skip legit cloud refs
CLOUD_PATTERN = re.compile(r"(?<!Google )(?<!google )Cloud(?!flare)(?!Tech)(?!\.com)")


def fix_file(path: Path) -> dict:
    """Apply all fixes to a single .md file. Returns counts of changes."""
    text = path.read_text(encoding="utf-8")
    original = text
    counts: dict = {}

    # Literal replacements
    for old, new in LITERAL_REPLACEMENTS.items():
        n = text.count(old)
        if n:
            text = text.replace(old, new)
            counts[f"{old} → {new}"] = n

    # Cloud → Claude (context-aware)
    new_text, n = CLOUD_PATTERN.subn("Claude", text)
    if n:
        text = new_text
        counts["Cloud → Claude"] = n

    if text != original:
        path.write_text(text, encoding="utf-8")
    return counts


def main() -> None:
    md_files = sorted(ROOT.rglob("*.md"))
    print(f"Scanning {len(md_files)} .md files…\n")

    total = {}
    files_changed = 0
    for mf in md_files:
        counts = fix_file(mf)
        if counts:
            files_changed += 1
            for k, v in counts.items():
                total[k] = total.get(k, 0) + v

    print(f"Files modified: {files_changed} / {len(md_files)}\n")
    print("Replacement totals:")
    for k, v in sorted(total.items(), key=lambda kv: -kv[1]):
        print(f"  {v:4d}× {k}")


if __name__ == "__main__":
    main()

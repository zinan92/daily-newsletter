"""Contract tests for source-ingestion decomposition skeleton.

Run: python3 tests/test_ingestion_contracts.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_CONTRACTS = [
    "ingestion/common/CONTRACT.md",
    "ingestion/rss/CONTRACT.md",
    "ingestion/web_scrape/CONTRACT.md",
    "ingestion/release_feed/CONTRACT.md",
    "ingestion/x/CONTRACT.md",
    "ingestion/youtube/CONTRACT.md",
    "ingestion/douyin/CONTRACT.md",
    "ingestion/wechat_rss/CONTRACT.md",
    "ingestion/manual_links/CONTRACT.md",
    "enrichment/media/CONTRACT.md",
    "enrichment/quoted_article/CONTRACT.md",
    "aggregation/digest/CONTRACT.md",
]

EXPECTED_WORKFLOW_IDS = [
    "rss",
    "web_scrape",
    "release_feed",
    "x",
    "youtube",
    "douyin",
    "wechat_rss",
    "manual_links",
    "media_enrichment",
    "quoted_article",
    "digest",
]


def test_contract_files_exist_and_name_boundaries():
    for rel in EXPECTED_CONTRACTS:
        path = ROOT / rel
        assert path.exists(), f"missing {rel}"
        text = path.read_text(encoding="utf-8")
        assert rel.rsplit("/", 1)[0] in text or rel.startswith("contracts/"), rel
        assert "## Boundary" in text or rel == "ingestion/common/CONTRACT.md", rel


def test_ingestion_schema_is_parseable_and_strict():
    schema = json.loads((ROOT / "contracts/ingestion-artifact.schema.json").read_text(encoding="utf-8"))
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"schema_version", "channel", "source", "run", "items", "health", "errors"}
    assert "wechat_rss" in schema["properties"]["channel"]["enum"]
    assert "release_feed" in schema["properties"]["channel"]["enum"]


def test_workflow_spec_covers_all_paths_and_keeps_repo_as_source_of_truth():
    text = (ROOT / "workflow/daily-newsletter.workflow.yaml").read_text(encoding="utf-8")
    assert "source_of_truth: repo" in text
    assert "runtime_target: n8n-ready" in text
    assert "root_entrypoints_remain_public: true" in text
    assert "daily_output_must_remain_unchanged: true" in text
    for workflow_id in EXPECTED_WORKFLOW_IDS:
        assert f"id: {workflow_id}" in text, workflow_id


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    sys.exit(1 if failed else 0)

"""Regression tests for the AI-first five-stage Daily Inbox path.

Run: python3 tests/test_ai_process.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lib
from aggregation.digest import ai_process
from aggregation.digest import summarize
from enrichment.media import run as media_run
from stages.coarse_filter import run as coarse_run


def load_to_md():
    spec = importlib.util.spec_from_file_location("to_md", ROOT / "to-md.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_item(path: Path, idx: int, title: str, content: str, url: str = ""):
    path.write_text(
        "\n".join(
            [
                "---",
                f"id: item-{idx}",
                "source: X",
                f"author: Author {idx}",
                f"title: {title}",
                f"url: {url or f'https://example.com/{idx}'}",
                "published_at: 2026-06-11",
                "content_type: tweet",
                "fetched_at: 2026-06-11T08:00:00",
                "raw_path: raw.json",
                "---",
                "",
                f"# {title}",
                "",
                content,
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_to_md_normalizes_one_raw_json_to_one_markdown_item():
    to_md = load_to_md()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        raw = root / "raw"
        out = root / "out"
        raw.mkdir()
        (raw / "one.json").write_text(
            json.dumps(
                {
                    "id": "abc",
                    "source": "X",
                    "author": "Park",
                    "title": "AI 工作流更新",
                    "url": "https://example.com/abc",
                    "content_type": "tweet",
                    "content": "这是一条关于 AI 工作流的内容。",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        written = to_md.normalize_raw_day("2026-06-11", raw, out)
        assert len(written) == 1
        text = written[0].read_text(encoding="utf-8")
        assert "source: X" in text
        assert "profile_id:" in text
        assert "author: Park" in text
        assert "# AI 工作流更新" in text


def test_to_md_preserves_summary_only_raw_item_body():
    to_md = load_to_md()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        raw = root / "raw"
        out = root / "out"
        raw.mkdir()
        (raw / "summary.json").write_text(
            json.dumps(
                {
                    "id": "yt-1",
                    "source": "YouTube",
                    "title": "AI video",
                    "url": "https://www.youtube.com/watch?v=abc",
                    "summary": "这是一条只有 summary 字段的视频 feed 内容。",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        written = to_md.normalize_raw_day("2026-06-11", raw, out)
        text = written[0].read_text(encoding="utf-8")
        assert "这是一条只有 summary 字段的视频 feed 内容。" in text


def test_media_enrichment_reads_and_writes_one_item_markdown():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        item_dir = root / "_inbox" / "unprocessed" / "2026-06-11" / "items"
        item_dir.mkdir(parents=True)
        item_path = item_dir / "video.md"
        item_path.write_text(
            "\n".join(
                [
                    "---",
                    "source: YouTube",
                    "title: Long video",
                    "url: https://www.youtube.com/watch?v=abc",
                    "published_at: 2026-06-11",
                    "duration: 1800",
                    "---",
                    "",
                    "# Long video",
                    "",
                    "Video feed summary.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        old_parkio = media_run.PARKIO
        old_today = media_run.today
        try:
            media_run.PARKIO = root
            media_run.today = lambda: "2026-06-11"
            items = media_run.read_today_media_items()
            assert len(items) == 1
            assert items[0]["_path"] == str(item_path)
            media_run.write_transcript_to_markdown(item_path, "https://www.youtube.com/watch?v=abc", "完整转录内容")
        finally:
            media_run.PARKIO = old_parkio
            media_run.today = old_today
        assert "### Transcript" in item_path.read_text(encoding="utf-8")


def test_media_enrichment_only_reads_requested_date_items():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        today_dir = root / "_inbox" / "unprocessed" / "2026-06-12" / "items"
        old_dir = root / "_inbox" / "unprocessed" / "2026-06-11" / "items"
        today_dir.mkdir(parents=True)
        old_dir.mkdir(parents=True)
        today_path = today_dir / "today-video.md"
        old_path = old_dir / "old-video.md"
        for path, title, published in (
            (today_path, "Today video", "2026-06-12"),
            (old_path, "Old video", "2026-06-11"),
        ):
            path.write_text(
                "\n".join(
                    [
                        "---",
                        "source: YouTube",
                        f"title: {title}",
                        "url: https://www.youtube.com/watch?v=abc" + published[-2:],
                        f"published_at: {published}",
                        "duration: 1800",
                        "---",
                        "",
                        f"# {title}",
                        "",
                        "Video feed summary.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

        old_parkio = media_run.PARKIO
        try:
            media_run.PARKIO = root
            items = media_run.read_today_media_items("2026-06-12")
        finally:
            media_run.PARKIO = old_parkio
        assert [item["title"] for item in items] == ["Today video"]


def test_five_stage_folders_exist():
    for name in ("fetch", "to_md", "coarse_filter", "ai_process", "archive"):
        assert (ROOT / "stages" / name / "run.py").exists()


def test_coarse_filter_only_consumes_current_date_inputs():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        unprocessed = root / "unprocessed"
        today_items = unprocessed / "2026-06-12" / "items"
        old_items = unprocessed / "2026-06-11" / "items"
        today_items.mkdir(parents=True)
        old_items.mkdir(parents=True)
        write_item(today_items / "today.md", 1, "AI workflow", "AI workflow 内容", "https://example.com/today")
        write_item(old_items / "old.md", 2, "AI old", "AI old 内容", "https://example.com/old")

        old_unprocessed = coarse_run.UNPROCESSED_DIR
        old_processed_batch_dir = coarse_run.processed_batch_dir
        old_batch_id = coarse_run.batch_id
        old_today = coarse_run.today
        try:
            coarse_run.UNPROCESSED_DIR = unprocessed
            coarse_run.processed_batch_dir = lambda bid=None: root / "processed" / "26-06-12"
            coarse_run.batch_id = lambda: "26-06-12"
            coarse_run.today = lambda: "2026-06-12"
            assert coarse_run.main() == 0
        finally:
            coarse_run.UNPROCESSED_DIR = old_unprocessed
            coarse_run.processed_batch_dir = old_processed_batch_dir
            coarse_run.batch_id = old_batch_id
            coarse_run.today = old_today

        processed = list((root / "processed" / "26-06-12").rglob("*.md"))
        assert any(path.name == "today.md" for path in processed)
        assert (old_items / "old.md").exists()


def test_write_source_output_writes_raw_json_not_unprocessed_markdown_by_default():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        old_raw = lib.RAW_DIR
        old_unprocessed = lib.UNPROCESSED_DIR
        lib.RAW_DIR = root / "raw"
        lib.UNPROCESSED_DIR = root / "unprocessed"
        try:
            out = lib.write_source_output(
                {
                    "name": "X Test",
                    "platform": "twitter",
                    "category": "ai-tools",
                    "url": "https://x.com/test",
                    "profile_id": "x-test",
                },
                [
                    {
                        "id": "123",
                        "url": "https://x.com/test/status/123",
                        "text": "Claude Code 发布了新的 workflow 能力。",
                        "author": "Tester",
                        "published": "2026-06-11",
                    }
                ],
            )
        finally:
            lib.RAW_DIR = old_raw
            lib.UNPROCESSED_DIR = old_unprocessed

        raw_files = sorted((root / "raw").rglob("*.json"))
        assert raw_files
        assert out == raw_files[0].parent
        assert not (root / "unprocessed").exists()
        data = json.loads(raw_files[0].read_text(encoding="utf-8"))
        assert data["source_name"] == "X Test"
        assert data["profile_id"] == "x-test"


def test_extract_json_accepts_fenced_json_and_rejects_bad_text():
    assert ai_process.extract_json("```json\n{\"ok\": true}\n```") == {"ok": True}
    try:
        ai_process.extract_json("not json")
    except ai_process.AIProcessError as exc:
        assert "valid JSON" in str(exc)
    else:
        raise AssertionError("expected AIProcessError")


def test_extract_json_repairs_unescaped_inner_quotes_in_strings():
    raw = '''```json
[
  {
    "id": "one",
    "key_facts": [
      "新功能名为"调度任务"(Scheduled tasks)。"
    ]
  }
]
```'''
    data = ai_process.extract_json(raw)
    assert data[0]["key_facts"][0] == '新功能名为"调度任务"(Scheduled tasks)。'


def test_call_json_stage_repairs_inner_quotes_without_llm_retry():
    with tempfile.TemporaryDirectory() as td:
        ai_dir = Path(td) / "ai"
        calls = []
        original_llm = ai_process.llm_call

        def fake_llm(prompt, *args, **kwargs):
            calls.append(prompt)
            return '[{"title":"极简版的"AI时代知识维基标准""}]'

        try:
            ai_process.llm_call = fake_llm
            data = ai_process.call_json_stage(ai_dir, "item_understanding_01", "01-item-understanding.md", [])
        finally:
            ai_process.llm_call = original_llm

        assert data == [{"title": '极简版的"AI时代知识维基标准"'}]
        assert len(calls) == 1
        assert not (ai_dir / "error.json").exists()


def test_ai_process_four_stage_mock_writes_artifacts_and_discards():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        items_dir = root / "items"
        items_dir.mkdir()
        for idx in range(20):
            title = "Claude 官方发布 Managed Agents" if idx < 2 else f"普通 AI 工具内容 {idx}"
            content = "Claude 官方博客和 X 都在讨论同一个 Managed Agents 发布。" if idx < 2 else "这是一条可用于测试的 AI 工具内容。"
            write_item(items_dir / f"item-{idx}.md", idx, title, content, f"https://example.com/{idx}")

        calls = []
        original_llm = ai_process.llm_call

        def fake_llm(prompt, *args, **kwargs):
            calls.append(prompt)
            if "first AI processing stage" in prompt:
                payload = json.loads(prompt.split("INPUT JSON:\n", 1)[1])
                return json.dumps([
                    {
                        "id": item["id"],
                        "source": item["source"],
                        "author": item["author"],
                        "title": item["title"],
                        "url": item["url"],
                        "content_type": item["content_type"],
                        "main_claim": "AI 工具更新",
                        "key_facts": ["事实"],
                        "novelty": "新信息",
                        "practical_impact": "影响工作流",
                        "duplicate_key_hint": "claude-managed-agents" if item["id"] in {"item-0", "item-1"} else item["id"],
                        "content_quality_notes": "可用",
                    }
                    for item in payload
                ], ensure_ascii=False)
            if "second AI processing stage" in prompt:
                return json.dumps([
                    {
                        "event_id": "e1",
                        "event_title": "Claude Managed Agents 发布",
                        "sources": [
                            {"source": "Claude Blog", "author": "Claude", "title": "Managed Agents", "url": "https://example.com/0"},
                            {"source": "X", "author": "Author 1", "title": "Managed Agents", "url": "https://example.com/1"},
                        ],
                        "item_ids": ["item-0", "item-1"],
                        "merged_summary": "Claude 发布 Managed Agents。",
                        "evidence": "官方和 X 都指向同一发布。",
                        "discussion_level": "multiple_sources",
                    },
	                    {
	                        "event_id": "e2",
	                        "event_title": "低信息内容",
	                        "sources": [{"source": "X", "author": "Author 2", "title": "低信息", "url": "https://example.com/2"}],
	                        "item_ids": [f"item-{idx}" for idx in range(2, 20)],
	                        "merged_summary": "信息不足。",
	                        "evidence": "多条弱内容保留为待 selection 丢弃的低价值事件。",
	                        "discussion_level": "single",
	                    },
	                ], ensure_ascii=False)
            if "third AI processing stage" in prompt:
                return json.dumps({
                    "brief_universe": [{
                        "event_id": "e1",
                        "subsection": "底层工具",
                        "importance_score": 5,
                        "insight_score": 5,
                        "practical_impact_score": 5,
                        "decision_reason": "官方发布且有系统影响。",
                        "summary": "Claude 发布 Managed Agents，Agent 产品进入生产基础设施阶段。",
                    }],
                    "deep_candidates": [{
                        "event_id": "e1",
                        "parent_brief_event_id": "e1",
                        "importance_score": 5,
                        "insight_score": 5,
                        "practical_impact_score": 5,
                        "decision_reason": "官方发布且有系统影响。",
                        "reading_angle": "Agent 表面演化。",
                    }],
                    "discard": [{"event_id": "e2", "decision_reason": "低信息。"}],
                }, ensure_ascii=False)
            if "deep-read product" in prompt:
                return """# Daily Inbox 深读 — 2026-06-11

## 深读

### [Claude Managed Agents 发布](https://example.com/0)

Source: Claude Blog / X
Author: Claude / Author 1

Claude Managed Agents 说明 Agent 产品正在从单次对话走向可托管的长期任务表面。它值得读，因为它改变了对 AI 工具形态的判断：真正的竞争点不只是模型回答，而是任务状态、权限、执行和可追踪性。这个判断可以迁移到开发工具、内容自动化和企业内部流程。
"""
            return """# Daily Inbox 快讯 — 2026-06-11

## 快讯

### 底层工具

- **Claude Blog / Claude** | [Claude Managed Agents 发布](https://example.com/0)
  Claude 发布 Managed Agents，Agent 产品进入生产基础设施阶段。

### 工作流

*(今日无内容)*

### 内容

*(今日无内容)*
"""

        try:
            ai_process.llm_call = fake_llm
            result = ai_process.run_ai_process("2026-06-11", root)
        finally:
            ai_process.llm_call = original_llm

        assert "## 快讯" in result.markdown
        assert "## 深读" in result.deep_markdown
        assert (root / "ai" / "01-item-cards.json").exists()
        assert (root / "ai" / "02-events.json").exists()
        assert (root / "ai" / "03-selection.json").exists()
        assert (root / "ai" / "discard-log.json").exists()
        assert (root / "ai" / "04-brief.md").exists()
        assert (root / "ai" / "05-deep.md").exists()
        assert (root / f"review-{root.name}-selection.html").exists()
        assert result.push_urls == ["https://example.com/0", "https://example.com/1"]
        assert result.deep_urls == ["https://example.com/0", "https://example.com/1"]
        discard = json.loads((root / "ai" / "discard-log.json").read_text(encoding="utf-8"))
        assert discard[0]["event_id"] == "e2"
        assert len(calls) == 9


def test_final_markdown_missing_sections_fails_and_writes_error():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_item(root / "item.md", 1, "AI item", "AI 内容", "https://example.com/1")
        original_llm = ai_process.llm_call

        def fake_llm(prompt, *args, **kwargs):
            if "first AI processing stage" in prompt:
                return json.dumps([
                    {
                        "id": "item-1",
                        "source": "X",
                        "author": "Author 1",
                        "title": "AI item",
                        "url": "https://example.com/1",
                        "content_type": "tweet",
                        "main_claim": "AI 内容",
                        "key_facts": [],
                        "novelty": "测试",
                        "practical_impact": "测试",
                        "duplicate_key_hint": "ai-item",
                        "content_quality_notes": "测试",
                    }
                ], ensure_ascii=False)
            if "second AI processing stage" in prompt:
                return json.dumps([
                    {
                        "event_id": "e1",
                        "event_title": "AI item",
                        "sources": [{"source": "X", "author": "Author 1", "title": "AI item", "url": "https://example.com/1"}],
                        "item_ids": ["item-1"],
                        "merged_summary": "AI 内容。",
                        "evidence": "测试。",
                        "discussion_level": "single",
                    }
                ], ensure_ascii=False)
            if "third AI processing stage" in prompt:
                return json.dumps({
                    "brief_universe": [{
                        "event_id": "e1",
                        "subsection": "工作流",
                        "importance_score": 3,
                        "insight_score": 3,
                        "practical_impact_score": 3,
                        "decision_reason": "测试。",
                        "summary": "测试。",
                    }],
                    "deep_candidates": [],
                    "discard": [],
                }, ensure_ascii=False)
            return "# Broken\n\nNo sections"

        try:
            ai_process.llm_call = fake_llm
            try:
                ai_process.run_ai_process("2026-06-11", root)
            except ai_process.AIProcessError as exc:
                assert "missing ## 快讯" in str(exc)
            else:
                raise AssertionError("expected AIProcessError")
        finally:
            ai_process.llm_call = original_llm

        assert (root / "ai" / "error.json").exists()
        assert (root / "ai" / "raw-response.md").exists()


def test_selection_requires_deep_candidates_to_reference_brief_universe():
    events = [{"event_id": "e1"}, {"event_id": "e2"}]
    selection = {
        "brief_universe": [{
            "event_id": "e1",
            "subsection": "工作流",
            "decision_reason": "ok",
            "summary": "ok",
        }],
        "deep_candidates": [{
            "event_id": "e1",
            "parent_brief_event_id": "e2",
            "decision_reason": "bad",
            "reading_angle": "bad",
        }],
        "discard": [{"event_id": "e2", "decision_reason": "discarded"}],
    }
    try:
        ai_process.validate_selection_references(events, selection)
    except ai_process.AIProcessError as exc:
        assert "parent not in brief_universe" in str(exc)
    else:
        raise AssertionError("expected AIProcessError")


def test_selection_must_cover_every_event_as_brief_or_discard():
    events = [{"event_id": "e1"}, {"event_id": "e2"}]
    selection = {
        "brief_universe": [{
            "event_id": "e1",
            "subsection": "工作流",
            "decision_reason": "ok",
            "summary": "ok",
        }],
        "deep_candidates": [],
        "discard": [],
    }
    try:
        ai_process.validate_selection_references(events, selection)
    except ai_process.AIProcessError as exc:
        assert "selection missing event_id(s): e2" in str(exc)
    else:
        raise AssertionError("expected AIProcessError")


def test_brief_markdown_requires_one_bullet_per_selected_event():
    markdown = """# Daily Inbox 快讯 — 2026-06-11

## 快讯

### 底层工具

- **OpenAI X** | [Deployment Simulation](https://example.com/1)
  summary
- **OpenAI X** | [Simulated deployments](https://example.com/2)
  summary

### 工作流

*(今日无内容)*

### 内容

*(今日无内容)*
"""
    try:
        ai_process.validate_brief_markdown(markdown, expected_item_count=1)
    except ai_process.AIProcessError as exc:
        assert "brief markdown rendered 2 bullet item(s) for 1 selected event(s)" in str(exc)
    else:
        raise AssertionError("expected AIProcessError")


def test_event_merge_must_cover_every_item_card():
    with tempfile.TemporaryDirectory() as td:
        ai_dir = Path(td) / "ai"
        cards = [{"id": "item-1"}, {"id": "item-2"}]
        events = [{
            "event_id": "e1",
            "event_title": "one",
            "sources": [],
            "item_ids": ["item-1"],
            "merged_summary": "one",
            "evidence": "one",
            "discussion_level": "single",
        }]

        try:
            ai_process.validate_event_coverage(ai_dir, cards, events)
        except ai_process.AIProcessError as exc:
            assert "event_merge omitted 1 item card(s): item-2" in str(exc)
        else:
            raise AssertionError("expected AIProcessError")

        error = json.loads((ai_dir / "error.json").read_text(encoding="utf-8"))
        assert error["stage"] == "event_merge"


def test_event_merge_dedupes_repeated_item_ids_inside_one_event():
    with tempfile.TemporaryDirectory() as td:
        ai_dir = Path(td) / "ai"
        cards = [{"id": "item-1"}, {"id": "item-2"}]
        events = [{
            "event_id": "e1",
            "event_title": "one",
            "sources": [],
            "item_ids": ["item-1", "item-1", "item-2"],
            "merged_summary": "one",
            "evidence": "one",
            "discussion_level": "single",
        }]

        ai_process.validate_event_coverage(ai_dir, cards, events)

        assert events[0]["item_ids"] == ["item-1", "item-2"]
        assert not (ai_dir / "error.json").exists()


def test_event_merge_removes_repeated_item_ids_across_events():
    with tempfile.TemporaryDirectory() as td:
        ai_dir = Path(td) / "ai"
        cards = [{"id": "item-1"}, {"id": "item-2"}]
        events = [
            {
                "event_id": "e1",
                "event_title": "one",
                "sources": [],
                "item_ids": ["item-1"],
                "merged_summary": "one",
                "evidence": "one",
                "discussion_level": "single",
            },
            {
                "event_id": "e2",
                "event_title": "two",
                "sources": [],
                "item_ids": ["item-1", "item-2"],
                "merged_summary": "two",
                "evidence": "two",
                "discussion_level": "single",
            },
        ]

        ai_process.validate_event_coverage(ai_dir, cards, events)

        assert events[0]["item_ids"] == ["item-1"]
        assert events[1]["item_ids"] == ["item-2"]
        assert not (ai_dir / "error.json").exists()


def test_repair_event_merge_can_cover_missing_item_cards():
    cards = [{"id": "item-1", "title": "one"}, {"id": "item-2", "title": "two"}]
    events = [{
        "event_id": "e1",
        "event_title": "one",
        "sources": [],
        "item_ids": ["item-1"],
        "merged_summary": "one",
        "evidence": "one",
        "discussion_level": "single",
    }]

    old_llm_call = ai_process.llm_call
    try:
        ai_process.llm_call = lambda *args, **kwargs: json.dumps([
            {
                "event_id": "e1",
                "event_title": "one",
                "sources": [],
                "item_ids": ["item-1"],
                "merged_summary": "one",
                "evidence": "one",
                "discussion_level": "single",
            },
            {
                "event_id": "e2",
                "event_title": "two",
                "sources": [],
                "item_ids": ["item-2"],
                "merged_summary": "two",
                "evidence": "two",
                "discussion_level": "single",
            },
        ])
        repaired = ai_process.repair_event_merge(cards, events)
    finally:
        ai_process.llm_call = old_llm_call

    assert [event["event_id"] for event in repaired] == ["e1", "e2"]
    assert ai_process.missing_event_cards(cards, repaired) == []


def test_empty_deep_candidates_write_empty_state_not_fake_deep_markdown():
    selection = {
        "brief_universe": [{
            "event_id": "e1",
            "subsection": "工作流",
            "decision_reason": "ok",
            "summary": "ok",
        }],
        "deep_candidates": [],
        "discard": [],
    }
    events = [{"event_id": "e1", "sources": [{"url": "https://example.com/1"}]}]
    assert ai_process.validate_selection_references(events, selection) == selection


def test_deep_markdown_headings_get_primary_source_links():
    markdown = """# Daily Inbox 深读 — 2026-06-11

## 深读

### Agent 交付的真正瓶颈

正文。
"""
    linked = ai_process.ensure_deep_heading_links(markdown, ["https://example.com/deep"])

    assert "### [Agent 交付的真正瓶颈](https://example.com/deep)" in linked
    assert ai_process.validate_deep_markdown(linked, ["https://example.com/deep"]) == linked


def test_deep_markdown_requires_primary_heading_links():
    markdown = """# Daily Inbox 深读 — 2026-06-11

## 深读

### Agent 交付的真正瓶颈

正文。
"""
    try:
        ai_process.validate_deep_markdown(markdown, ["https://example.com/deep"])
    except ai_process.AIProcessError as exc:
        assert "deep markdown missing heading link" in str(exc)
    else:
        raise AssertionError("expected AIProcessError")


def test_invalid_selection_override_is_ignored_with_error_file():
    with tempfile.TemporaryDirectory() as td:
        ai_dir = Path(td) / "ai"
        ai_dir.mkdir()
        (ai_dir / "selection-override.json").write_text(
            json.dumps({
                "brief_universe": [],
                "deep_candidates": [{"event_id": "missing", "parent_brief_event_id": "missing"}],
                "discard": [],
            }),
            encoding="utf-8",
        )
        original = {
            "brief_universe": [{
                "event_id": "e1",
                "subsection": "工作流",
                "decision_reason": "ok",
                "summary": "ok",
            }],
            "deep_candidates": [],
            "discard": [],
        }
        events = [{"event_id": "e1"}]
        assert ai_process.selection_from_override(ai_dir, events, original) == original
        error = json.loads((ai_dir / "selection-override-error.json").read_text(encoding="utf-8"))
        assert error["action"] == "ignored_override_used_ai_selection"


def test_item_understanding_chunks_large_batches():
    items = [
        {"id": str(idx), "title": f"item {idx}", "content": "x" * 5000}
        for idx in range(8)
    ]
    chunks = ai_process.chunk_items_for_understanding(items)
    assert len(chunks) > 1
    assert sum(len(chunk) for chunk in chunks) == len(items)
    assert all(sum(ai_process.item_content_size(item) for item in chunk) <= ai_process.ITEM_UNDERSTANDING_MAX_CONTENT_CHARS for chunk in chunks)


def test_collect_processed_items_ignores_ai_debug_dirs():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_item(root / "item.md", 1, "AI item", "AI 内容", "https://example.com/1")
        debug_dir = root / "ai.backup-20260612"
        debug_dir.mkdir()
        write_item(debug_dir / "raw-response.md", 2, "raw-response", "debug", "https://example.com/debug")

        rows = ai_process.collect_processed_items(root)

    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/1"


def test_collect_processed_items_keeps_ai_prefixed_profile_dir():
    # Regression: the skip used `any(part.startswith("ai") ...)`, which also
    # dropped legitimate items whose profile_id starts with "ai" (e.g. a source
    # named "AI Engineering" -> profile_id "ai-engineering"). The artifact dir
    # `ai/` and debug dirs `ai.backup-*` must still be skipped, but `ai-*`
    # profile dirs must be collected.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        profile_dir = root / "ai-engineering"
        profile_dir.mkdir()
        write_item(profile_dir / "25-06-17.md", 1, "AI item", "AI agent 工具", "https://example.com/keep")
        artifact_dir = root / "ai"
        artifact_dir.mkdir()
        write_item(artifact_dir / "raw-response.md", 2, "artifact", "debug", "https://example.com/artifact")
        debug_dir = root / "ai.backup-20260612"
        debug_dir.mkdir()
        write_item(debug_dir / "raw-response.md", 3, "debug", "debug", "https://example.com/debug")

        rows = ai_process.collect_processed_items(root)

    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/keep"


def test_collect_processed_items_ignores_final_output_markdown():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_item(root / "item.md", 1, "AI item", "AI 内容", "https://example.com/1")
        write_item(root / "000-26-06-15.md", 2, "Brief output", "快讯正文", "https://example.com/brief")
        write_item(root / "deep-26-06-15.md", 3, "Deep output", "深读正文", "https://example.com/deep")

        rows = ai_process.collect_processed_items(root)

    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/1"


def test_production_push_script_does_not_call_score_or_quality_gate():
    text = (ROOT / "push-digest.sh").read_text(encoding="utf-8")
    assert "score.py" not in text
    assert "check-quality.py" not in text
    assert "stages/to_md/run.py" in text
    assert "stages/coarse_filter/run.py" in text
    assert "stages/archive/run.py" in text


def test_ai_footer_appends_source_health_and_contact():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        health = root / "source-health.json"
        contact = root / "contact.md"
        media = root / "media-summaries.json"
        health.write_text(
            json.dumps(
                {
                    "runs": [
                        {
                            "ts": "2026-06-12T09:00:00",
                            "sources": {
                                "Claude X": {
                                    "name": "Claude X",
                                    "platform": "twitter",
                                    "status": "failed",
                                }
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        contact.write_text(
            "\n".join(
                [
                    "| label | url | qr | note | active |",
                    "|---|---|---|---|---|",
                    "| 测试渠道 | https://example.com |  | 加入测试渠道 | true |",
                ]
            ),
            encoding="utf-8",
        )
        media.write_text("{}", encoding="utf-8")
        old_health = summarize.SOURCE_HEALTH_PATH
        old_contact = summarize.CONTACT_PATH
        old_media = summarize.MEDIA_SUMMARIES_PATH
        try:
            summarize.SOURCE_HEALTH_PATH = health
            summarize.CONTACT_PATH = contact
            summarize.MEDIA_SUMMARIES_PATH = media
            text = summarize.append_ai_footer("# Daily Inbox\n\n## 短讯\n\n## 深读\n")
        finally:
            summarize.SOURCE_HEALTH_PATH = old_health
            summarize.CONTACT_PATH = old_contact
            summarize.MEDIA_SUMMARIES_PATH = old_media
        assert "## Source Health" in text
        assert "Claude X" in text
        assert "## 关注与加入" in text
        assert "测试渠道" in text


def test_ai_process_prompts_keep_chinese_x_titles_chinese():
    event_prompt = (ROOT / "prompts" / "ai-process" / "02-event-merge.md").read_text(encoding="utf-8")
    brief_prompt = (ROOT / "prompts" / "ai-process" / "04-brief-writing.md").read_text(encoding="utf-8")

    assert "do not translate" in event_prompt.lower()
    assert "Chinese X posts into English" in event_prompt
    assert "Do not keep an English event_title for a Chinese X post" in brief_prompt


def test_summarize_main_writes_brief_and_deep_artifact_families():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        processed = root / "processed"
        processed.mkdir()
        brief_md = processed / "000-26-06-11.md"
        brief_html = processed / "000-26-06-11.html"
        brief_png = processed / "000-26-06-11.png"
        deep_md = processed / "deep-26-06-11.md"
        deep_html = processed / "deep-26-06-11.html"
        deep_png = processed / "deep-26-06-11.png"

        original_run_ai_process = ai_process.run_ai_process
        original_batch_artifact_paths = summarize.batch_artifact_paths
        original_deep_artifact_paths = summarize.deep_artifact_paths
        original_processed_batch_dir = summarize.processed_batch_dir
        original_today = summarize.today
        original_argv = sys.argv[:]

        def fake_run_ai_process(date, batch_dir):
            return ai_process.AIProcessResult(
                markdown="# Daily Inbox 快讯 — 2026-06-11\n\n## 快讯\n\n### 底层工具\n\n- brief\n\n### 工作流\n\n*(今日无内容)*\n\n### 内容\n\n*(今日无内容)*\n",
                deep_markdown="# Daily Inbox 深读 — 2026-06-11\n\n## 深读\n\n### deep\n\nDeep body.\n",
                processed_urls=["https://example.com/1"],
                push_urls=["https://example.com/1"],
                deep_urls=["https://example.com/1"],
            )

        try:
            ai_process.run_ai_process = fake_run_ai_process
            summarize.batch_artifact_paths = lambda: (brief_md, brief_html, brief_png)
            summarize.deep_artifact_paths = lambda: (deep_md, deep_html, deep_png)
            summarize.processed_batch_dir = lambda: processed
            summarize.today = lambda: "2026-06-11"
            sys.argv = ["summarize.py"]
            summarize.main()
        finally:
            ai_process.run_ai_process = original_run_ai_process
            summarize.batch_artifact_paths = original_batch_artifact_paths
            summarize.deep_artifact_paths = original_deep_artifact_paths
            summarize.processed_batch_dir = original_processed_batch_dir
            summarize.today = original_today
            sys.argv = original_argv

        assert "## 快讯" in brief_md.read_text(encoding="utf-8")
        assert "## Source Health" not in brief_md.read_text(encoding="utf-8")
        assert brief_html.exists()
        assert "## 深读" in deep_md.read_text(encoding="utf-8")
        assert deep_html.exists()


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

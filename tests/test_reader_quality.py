import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_reader_quality():
    spec = importlib.util.spec_from_file_location("reader_quality", ROOT / "reader_quality.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_artifacts(sent: Path, label: str = "26-06-25") -> None:
    sent.mkdir(parents=True, exist_ok=True)
    (sent / f"daily-{label}.md").write_text(
        "# Daily Newsletter\n\n## 今日包\n\n[快讯](</Users/wendy/park-io/001_daily newsletter/ai/26-06-25.md>)\n\n## Source Health\n\n- OK\n",
        encoding="utf-8",
    )
    (sent / f"{label}.md").write_text(
        "# Daily Inbox 快讯\n\n## 快讯\n\n### 底层工具\n\n- **A** | [T](https://example.com)\n  summary\n\n### 工作流\n\n### 内容\n",
        encoding="utf-8",
    )
    (sent / f"deep-{label}.md").write_text("# Daily Inbox 深读\n\n## 深读\n\n### [A](https://example.com)\n\nbody\n", encoding="utf-8")
    (sent / f"product-radar-{label}.md").write_text(
        "# 产品雷达\n\n## Top 1 Products To Build Today\n\n### 1. A\n\n## 数据质量\n\n- OK\n",
        encoding="utf-8",
    )


def test_reader_quality_passes_clean_reader_artifacts(tmp_path):
    rq = load_reader_quality()
    sent = tmp_path / "sent"
    write_artifacts(sent)

    report = rq.check_artifacts("2026-06-25", sent)

    assert report["status"] == "pass"
    assert report["fail_count"] == 0
    assert report["issues"] == []


def test_reader_quality_fails_raw_transcript_and_machine_markers(tmp_path):
    rq = load_reader_quality()
    sent = tmp_path / "sent"
    write_artifacts(sent)
    (sent / "26-06-25.md").write_text(
        "# Daily Inbox 快讯\n\n## 快讯\n\n### 底层工具\n\n- **A** | T\n  Transcript 是的。就是这样。就是这样。就是这样。\n\n### 工作流\n\n### 内容\n\n<!-- parkio-push-items:[] -->\n",
        encoding="utf-8",
    )

    report = rq.check_artifacts("2026-06-25", sent)

    assert report["status"] == "fail"
    codes = {row["code"] for row in report["issues"] if row["severity"] == "fail"}
    assert {"machine_comment", "raw_transcript", "repeated_filler"} <= codes

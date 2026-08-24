from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import daily_bundle


def test_daily_bundle_merges_three_processed_products(tmp_path):
    original_processed = daily_bundle.PROCESSED_DIR
    processed = tmp_path / "processed"
    batch = processed / "26-06-20"
    sent = tmp_path / "sent"
    batch.mkdir(parents=True)
    (batch / "000-26-06-20.md").write_text(
        "# Daily Inbox 快讯 — 2026-06-20\n\n## 快讯\n\n### 底层工具\n\n- **X** | [one](https://example.com/1)\n  summary\n",
        encoding="utf-8",
    )
    (batch / "deep-26-06-20.md").write_text(
        "# Daily Inbox 深读 — 2026-06-20\n\n## 深读\n\n### [Deep item](https://example.com/deep)\n\nbody\n",
        encoding="utf-8",
    )
    (batch / "product-radar-26-06-20.md").write_text(
        "# 产品雷达 — 2026-06-20\n\n## Top Three Products to Build Today\n\n1. 销售通话复盘助手：自动找出客户异议和下一步动作。\n",
        encoding="utf-8",
    )

    try:
        daily_bundle.PROCESSED_DIR = processed
        md = daily_bundle.render_markdown("2026-06-20", sent)
    finally:
        daily_bundle.PROCESSED_DIR = original_processed

    assert "# AI Daily Newsletter — 2026-06-20" in md
    assert "## 快讯" in md
    assert "## 深读" in md
    assert "## 产品雷达" in md
    assert "销售通话复盘助手" in md
    assert "### Top Three Products to Build Today" in md
    assert "product-radar-26-06-20.md" not in md
    assert "/Users/wendy" not in md


def test_daily_bundle_writes_one_markdown_and_no_html_or_png(tmp_path):
    original_processed = daily_bundle.PROCESSED_DIR
    processed = tmp_path / "processed"
    batch = processed / "26-06-20"
    sent = tmp_path / "sent"
    batch.mkdir(parents=True)
    (batch / "000-26-06-20.md").write_text(
        "# Daily Inbox 快讯 — 2026-06-20\n\n## 快讯\n\n### 内容\n\n- **X** | [one](https://example.com/1)\n  summary\n",
        encoding="utf-8",
    )

    try:
        daily_bundle.PROCESSED_DIR = processed
        result = daily_bundle.build_daily_bundle(
            "2026-06-20",
            sent_dir=sent,
            with_png=False,
            extra_warnings=["Product Radar 生成失败：fixture"],
        )
    finally:
        daily_bundle.PROCESSED_DIR = original_processed

    md = Path(result["markdown"]).read_text(encoding="utf-8")
    assert "## 快讯" in md
    assert "## 深读" in md
    assert "今日没有达到深读标准的内容。" in md
    assert "## 产品雷达" in md
    assert result["html"] == ""
    assert result["png"] == ""
    assert not (sent / "26-06-20.html").exists()
    assert not (sent / "26-06-20.png").exists()

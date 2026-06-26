from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import daily_bundle


def test_daily_bundle_links_three_reader_products(tmp_path):
    sent = tmp_path / "sent"
    sent.mkdir()
    (sent / "26-06-20.md").write_text(
        "# Daily Inbox 快讯 — 2026-06-20\n\n## 快讯\n\n### 底层工具\n\n- **X** | [one](https://example.com/1)\n  summary\n",
        encoding="utf-8",
    )
    (sent / "26-06-20.html").write_text("<html>brief</html>", encoding="utf-8")
    (sent / "deep-26-06-20.md").write_text(
        "# Daily Inbox 深读 — 2026-06-20\n\n## 深读\n\n### [Deep item](https://example.com/deep)\n\nbody\n",
        encoding="utf-8",
    )
    (sent / "product-radar-26-06-20.md").write_text(
        "# 产品雷达 — 2026-06-20\n\n## Top 5 Products To Build Today\n\n### 1. AI workflow builder\n\n- **可以 build 什么**：一个垂直 Agent。\n",
        encoding="utf-8",
    )

    md = daily_bundle.render_markdown("2026-06-20", sent)

    assert "# Daily Newsletter — 2026-06-20" in md
    assert "**快讯**：1 条快讯信号" in md
    assert "**深读**：1 条深读候选" in md
    assert "**产品雷达**：1 个可 build 产品方向" in md
    assert "product-radar-26-06-20.md" in md
    assert "今天最值得 build 的 5 个产品方向是什么" in md
    assert "WeChat / YouTube / 单个产品雷达源异常只进入健康提示，不阻塞每日 bundle 生成" in md


def test_daily_bundle_can_show_missing_product_as_degraded(tmp_path):
    sent = tmp_path / "sent"
    sent.mkdir()
    (sent / "26-06-20.md").write_text(
        "# Daily Inbox 快讯 — 2026-06-20\n\n## 快讯\n\n### 内容\n\n- **X** | [one](https://example.com/1)\n  summary\n",
        encoding="utf-8",
    )

    result = daily_bundle.build_daily_bundle(
        "2026-06-20",
        sent_dir=sent,
        with_png=False,
        extra_warnings=["Product Radar 生成失败：fixture"],
    )

    md = Path(result["markdown"]).read_text(encoding="utf-8")
    assert "**深读**：未生成。" in md
    assert "**产品雷达**：未生成。" in md
    assert "Product Radar 生成失败：fixture" in md
    assert Path(result["html"]).exists()

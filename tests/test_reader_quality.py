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
    (sent / f"{label}.md").write_text(
        "# AI Daily Newsletter — 2026-06-25\n\n"
        "## 快讯\n\n### 底层工具\n\n- **A** | [T](https://example.com)\n  summary\n\n### 工作流\n\n### 内容\n\n"
        "## 深读\n\n### [A](https://example.com)\n\nbody\n\n"
        "## 产品雷达\n\n### Top Three Products to Build Today\n\n1. 销售通话复盘助手：自动找出客户异议和下一步动作。\n",
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
        "# AI Daily Newsletter — 2026-06-25\n\n"
        "## 快讯\n\n### 底层工具\n\n- **A** | T\n  Transcript 是的。就是这样。就是这样。就是这样。\n\n### 工作流\n\n### 内容\n\n"
        "本地路径：/Users/wendy/park-io/001_daily newsletter/ai/26-06-25.md\n\n"
        "## 深读\n\n### A\n\nbody\n\n## 产品雷达\n\n### Top Three Products to Build Today\n\n1. A：解决一个具体问题。\n\n"
        "<!-- parkio-push-items:[] -->\n",
        encoding="utf-8",
    )

    report = rq.check_artifacts("2026-06-25", sent)

    assert report["status"] == "fail"
    codes = {row["code"] for row in report["issues"] if row["severity"] == "fail"}
    assert {"machine_comment", "raw_transcript", "repeated_filler", "local_path"} <= codes


def test_reader_quality_rejects_product_radar_ops_data_and_more_than_three_products(tmp_path):
    rq = load_reader_quality()
    sent = tmp_path / "sent"
    write_artifacts(sent)
    path = sent / "26-06-25.md"
    text = path.read_text(encoding="utf-8").replace(
        "1. 销售通话复盘助手：自动找出客户异议和下一步动作。",
        "1. A：价值。\n2. B：价值。\n3. C：价值。\n4. D：TrustMRR 已验证收入。",
    )
    path.write_text(text, encoding="utf-8")

    report = rq.check_artifacts("2026-06-25", sent)

    codes = {row["code"] for row in report["issues"] if row["severity"] == "fail"}
    assert {"product_radar_count", "product_radar_ops_data"} <= codes


def test_reader_quality_accepts_empty_product_radar_heading_only(tmp_path):
    rq = load_reader_quality()
    sent = tmp_path / "sent"
    write_artifacts(sent)
    path = sent / "26-06-25.md"
    text = path.read_text(encoding="utf-8").replace(
        "### Top Three Products to Build Today\n\n1. 销售通话复盘助手：自动找出客户异议和下一步动作。",
        "### No New Build Choices Today",
    )
    path.write_text(text, encoding="utf-8")

    report = rq.check_artifacts("2026-06-25", sent)

    assert report["status"] == "pass"


def test_reader_quality_rejects_empty_product_radar_explanation(tmp_path):
    rq = load_reader_quality()
    sent = tmp_path / "sent"
    write_artifacts(sent)
    path = sent / "26-06-25.md"
    text = path.read_text(encoding="utf-8").replace(
        "### Top Three Products to Build Today\n\n1. 销售通话复盘助手：自动找出客户异议和下一步动作。",
        "### No New Build Choices Today\n\n只回答一个问题。",
    )
    path.write_text(text, encoding="utf-8")

    report = rq.check_artifacts("2026-06-25", sent)

    codes = {row["code"] for row in report["issues"] if row["severity"] == "fail"}
    assert "product_radar_empty_state" in codes

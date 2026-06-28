import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_sender():
    spec = importlib.util.spec_from_file_location("send_feishu_digest", ROOT / "send-feishu-digest.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_feishu_digest_reads_env_and_finds_daily_artifact(tmp_path):
    sender = load_sender()
    config = tmp_path / "feishu.env"
    config.write_text(
        "FEISHU_WEBHOOK_URL=https://example.com/hook\nFEISHU_WEBHOOK_SECRET=secret\n",
        encoding="utf-8",
    )

    values = sender.load_env(config)

    assert values["FEISHU_WEBHOOK_URL"] == "https://example.com/hook"
    assert values["FEISHU_WEBHOOK_SECRET"] == "secret"
    assert sender.date_label("2026-06-25") == "26-06-25"


def test_feishu_digest_chunks_and_signs_text_without_network():
    sender = load_sender()

    chunks = sender.chunk_text("a\n" + ("b" * 20) + "\nc", limit=12)
    payload = sender.signed_payload("secret", "hello")

    assert len(chunks) == 3
    assert payload["msg_type"] == "text"
    assert payload["content"]["text"] == "hello"
    assert payload["timestamp"]
    assert payload["sign"]


def test_feishu_digest_inlines_reader_artifacts_instead_of_local_links(tmp_path):
    sender = load_sender()
    sent = tmp_path / "sent"
    sent.mkdir()
    label = "26-06-25"
    (sent / f"daily-{label}.md").write_text(
        "# Daily Newsletter\n\n[Markdown](</Users/wendy/park-io/001_daily newsletter/ai/26-06-25.md>)\n",
        encoding="utf-8",
    )
    (sent / f"{label}.md").write_text(
        "# 快讯\n\n- **Source** | [原文](https://example.com/a)\n  summary\n<!-- parkio-push-items:[] -->\n",
        encoding="utf-8",
    )
    (sent / f"deep-{label}.md").write_text("# 深读\n\nDeep body\n", encoding="utf-8")
    (sent / f"product-radar-{label}.md").write_text("# 产品雷达\n\nRadar body\n", encoding="utf-8")

    old_sent_dir = sender.SENT_DIR
    try:
        sender.SENT_DIR = sent
        text = sender.message_text("2026-06-25")
    finally:
        sender.SENT_DIR = old_sent_dir

    assert "/Users/wendy" not in text
    assert "快讯正文" in text
    assert "深读正文" in text
    assert "产品雷达正文" in text
    assert "原文 https://example.com/a" in text
    assert "parkio-push-items" not in text


def test_feishu_digest_writes_delivery_receipt(tmp_path):
    sender = load_sender()
    old_dir = sender.RECEIPT_DIR
    try:
        sender.RECEIPT_DIR = tmp_path / "receipts"
        receipt = {
            "schema": 1,
            "date": "2026-06-25",
            "sent_at": "2026-06-25T09:00:00",
            "status": "sent",
            "chunks": 2,
            "chars": 5000,
        }

        path = sender.write_receipt(receipt)

        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert '"status": "sent"' in text
        assert '"chunks": 2' in text
    finally:
        sender.RECEIPT_DIR = old_dir

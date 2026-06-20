from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_push_digest_generates_product_radar_and_daily_bundle():
    text = (ROOT / "push-digest.sh").read_text(encoding="utf-8")
    assert "build-product-radar.py" in text
    assert "build-daily-bundle.py" in text
    assert "continue with degraded daily bundle" in text


def test_recoverable_source_auth_no_longer_blocks_by_default():
    text = (ROOT / "push-digest.sh").read_text(encoding="utf-8")
    assert "continue scheduled push with degraded source health" in text
    assert "PARKIO_PREFLIGHT_BLOCK" in text
    assert "skip scheduled push" in text

"""retry-digest.sh must be safe to run any number of times."""
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _script():
    return (ROOT / "retry-digest.sh").read_text()


def test_retry_never_starts_a_second_pipeline_while_one_runs():
    s = _script()
    assert 'pgrep -f "push-digest.sh|build-digest.py"' in s
    assert s.index("pgrep") < s.index("push-digest.sh\"")


def test_retry_resumes_an_opened_batch_instead_of_reopening():
    s = _script()
    assert 'PARKIO_RESUME_BATCH="$BID"' in s


def test_retry_only_sends_through_the_idempotent_sender():
    s = _script()
    # the sender skips dates that already have a successful receipt; no --force here
    assert "send-feishu-digest.py" in s and "--force" not in s


def test_push_digest_resume_skips_batch_opening():
    s = (ROOT / "push-digest.sh").read_text()
    assert 'RESUME_BATCH="${PARKIO_RESUME_BATCH:-}"' in s
    assert 'BATCH_ID="$RESUME_BATCH"' in s


def test_scripts_parse():
    for name in ("push-digest.sh", "retry-digest.sh"):
        assert subprocess.run(["bash", "-n", str(ROOT / name)]).returncode == 0

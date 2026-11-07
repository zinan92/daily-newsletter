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


# ---------------------------------------------------------------------------
# Publishing after a retry. Runs the real retry-digest.sh in a sandbox where the
# pipeline, Feishu sender and site publish script are stubs that only record
# their call, so nothing here can reach Feishu or the website.
# ---------------------------------------------------------------------------
SHORT = "26-11-07"


def _sandbox(tmp_path, *, pipeline_writes_daily=True, pipeline_running=False, feishu_exit=0, hook=True):
    box = tmp_path / "repo"
    (box / "logs").mkdir(parents=True)
    sent = tmp_path / "sent"
    processed = tmp_path / "processed"
    sent.mkdir()
    (processed / SHORT).mkdir(parents=True)
    calls = tmp_path / "calls"
    calls.touch()

    (box / "retry-digest.sh").write_text(_script())
    (box / "lib.py").write_text(f"SENT_DIR = {str(sent)!r}\nPROCESSED_DIR = {str(processed)!r}\n")
    write_daily = f'touch "{sent}/{SHORT}.md"' if pipeline_writes_daily else ":"
    (box / "push-digest.sh").write_text(f'echo pipeline >> "{calls}"\n{write_daily}\n')
    (box / "send-feishu-digest.py").write_text(
        f"import sys\nopen({str(calls)!r}, 'a').write('feishu\\n')\nsys.exit({feishu_exit})\n"
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "pgrep").write_text(f"#!/bin/bash\nexit {0 if pipeline_running else 1}\n")
    (bin_dir / "pgrep").chmod(0o755)
    (bin_dir / "date").write_text(
        '#!/bin/bash\ncase "$1" in\n'
        "  '+%F') echo 2026-11-07 ;;\n"
        f"  '+%y-%m-%d') echo {SHORT} ;;\n"
        "  '+%Y%m%d') echo 20261107 ;;\n"
        "  *) echo 2026-11-07 10:30:00 ;;\nesac\n"
    )
    (bin_dir / "date").chmod(0o755)

    hook_path = tmp_path / "refresh-newsletter.sh"
    if hook:
        hook_path.write_text(f'echo publish >> "{calls}"\n')

    def run():
        env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "PARKIO_PUBLISH_SCRIPT": str(hook_path)}
        result = subprocess.run(["/bin/bash", str(box / "retry-digest.sh")], env=env)
        return result.returncode, calls.read_text().split(), (box / "logs" / "push-digest.log").read_text()

    return sent, run


def test_daily_built_by_the_retry_is_published(tmp_path):
    # 11/07: the 07:00 run died, the 09:30 retry finished at 10:28, nothing published it.
    _, run = _sandbox(tmp_path)
    code, calls, _ = run()
    assert code == 0
    assert calls == ["pipeline", "feishu", "publish"]


def test_daily_a_late_run_left_behind_is_published(tmp_path):
    # The 07:00 run finished after 09:30: the file is there, only the publish is missing.
    sent, run = _sandbox(tmp_path)
    (sent / f"{SHORT}.md").touch()
    code, calls, _ = run()
    assert code == 0
    assert calls == ["feishu", "publish"]


def test_feishu_failure_does_not_block_publishing(tmp_path):
    _, run = _sandbox(tmp_path, feishu_exit=1)
    _, calls, _ = run()
    assert calls == ["pipeline", "feishu", "publish"]


def test_no_publish_while_the_pipeline_still_runs(tmp_path):
    sent, run = _sandbox(tmp_path, pipeline_running=True)
    (sent / f"{SHORT}.md").touch()
    code, calls, _ = run()
    assert code == 0
    assert calls == []


def test_no_publish_when_there_is_still_no_daily(tmp_path):
    _, run = _sandbox(tmp_path, pipeline_writes_daily=False)
    code, calls, _ = run()
    assert code == 1
    assert calls == ["pipeline"]


def test_fresh_clone_without_the_site_repo_skips_publishing(tmp_path):
    _, run = _sandbox(tmp_path, hook=False)
    code, calls, log = run()
    assert code == 0
    assert calls == ["pipeline", "feishu"]
    assert "publish skipped" in log

"""A fresh clone must run on someone else's machine without Park's ~/park-io."""
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lib  # noqa: E402


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _import_lib_with(env: dict) -> dict:
    """Import lib in a clean child process and report the resolved paths."""
    code = (
        "import json, lib; print(json.dumps({'sources': str(lib.SOURCES_PATH), "
        "'download': str(lib.DOWNLOAD_CAPABILITY), 'home': str(lib.PARKIO)}))"
    )
    base = {"PATH": os.environ.get("PATH", ""), "HOME": env.pop("HOME")}
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env={**base, **env},
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out.strip().splitlines()[-1])


def test_env_file_fills_missing_values_only(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "DN_TEST_PLAIN=one\n"
        "export DN_TEST_QUOTED=\"two words\"\n"
        "DN_TEST_EMPTY=\n"
        "DN_TEST_TILDE=~/data\n"
        "DN_TEST_SET=from-file\n",
        encoding="utf-8",
    )
    keys = ["DN_TEST_PLAIN", "DN_TEST_QUOTED", "DN_TEST_EMPTY", "DN_TEST_TILDE", "DN_TEST_SET"]
    with patch.dict(os.environ, {"DN_TEST_SET": "from-env"}):
        for key in keys[:-1]:
            os.environ.pop(key, None)
        lib.load_env_file(env_file)
        assert os.environ["DN_TEST_PLAIN"] == "one"
        assert os.environ["DN_TEST_QUOTED"] == "two words"
        assert "DN_TEST_EMPTY" not in os.environ  # empty = keep the code default
        assert os.environ["DN_TEST_TILDE"] == str(Path.home() / "data")
        assert os.environ["DN_TEST_SET"] == "from-env"  # real env wins


def test_shell_env_loader_matches_python_loader(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("A=1\nB=\nexport C='x y'\nD=~/p\n", encoding="utf-8")
    out = subprocess.run(
        ["bash", "-c", f'. "{ROOT}/scripts/load-env.sh" "{env_file}"; echo "$A|${{B-unset}}|$C|$D"'],
        capture_output=True, text=True, check=True, env={"PATH": os.environ["PATH"], "HOME": str(tmp_path)},
    ).stdout.strip()
    assert out == f"1|unset|x y|{tmp_path}/p"


def test_fresh_machine_uses_shipped_sources_and_vendored_downloader(tmp_path):
    resolved = _import_lib_with({"HOME": str(tmp_path), "PARKIO_HOME": str(tmp_path / "park-io")})
    assert resolved["sources"] == str(ROOT / "sources.md")
    assert resolved["download"] == str(ROOT / "vendor")


def test_owner_live_sources_win_over_shipped_copy(tmp_path):
    live = tmp_path / "park-io" / "_source management" / "sources.md"
    live.parent.mkdir(parents=True)
    live.write_text("| id | name |\n|---|---|\n| 1 | x |\n", encoding="utf-8")
    resolved = _import_lib_with({"HOME": str(tmp_path), "PARKIO_HOME": str(tmp_path / "park-io")})
    assert resolved["sources"] == str(live)

    mine = tmp_path / "mine.md"
    resolved = _import_lib_with({"HOME": str(tmp_path), "PARKIO_HOME": str(tmp_path / "park-io"), "PARKIO_SOURCES": str(mine)})
    assert resolved["sources"] == str(mine)


def test_shipped_source_list_is_complete_and_portable():
    text = (ROOT / "sources.md").read_text(encoding="utf-8")
    assert "/Users/" not in text
    rows = lib._parse_first_md_table(text)
    platforms = {row["platform"] for row in rows}
    assert len(rows) >= 80
    assert {"rss", "scrape", "twitter", "douyin", "wechat", "github"} <= platforms
    assert "## User Context" in text


def test_vendored_downloader_is_in_repo():
    pkg = ROOT / "vendor" / "content_downloader"
    assert (pkg / "adapters" / "douyin" / "api_client.py").exists()
    assert (pkg / "adapters" / "douyin" / "adapter.py").exists()
    assert not list(pkg.rglob("__pycache__"))


def test_anthropic_official_api_key_goes_to_api_anthropic_com():
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse({"content": [{"type": "text", "text": "ok"}]})

    env = {"ANTHROPIC_API_KEY": "sk-test"}
    with patch.dict(os.environ, env), \
            patch.object(lib, "LLM_PROVIDER", "anthropic"), \
            patch.object(lib, "LLM_FALLBACK_PROVIDER", ""), \
            patch("urllib.request.urlopen", fake_urlopen):
        os.environ.pop("PARKIO_ANTHROPIC_ENDPOINT", None)
        os.environ.pop("PARKIO_ANTHROPIC_MODEL", None)
        assert lib.llm_call("hi", max_tokens=100, retries=1, timeout=30) == "ok"

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "sk-test"
    assert captured["body"]["model"] == "claude-sonnet-5-5"
    assert captured["body"]["thinking"] == {"type": "between_tools"}


def test_anthropic_without_official_key_keeps_cliproxy():
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse({"content": [{"type": "text", "text": "ok"}]})

    with patch.dict(os.environ, {"PARKIO_CLIPROXY_KEY": "proxy"}), \
            patch.object(lib, "LLM_PROVIDER", "anthropic"), \
            patch.object(lib, "LLM_FALLBACK_PROVIDER", ""), \
            patch("urllib.request.urlopen", fake_urlopen):
        for key in ("ANTHROPIC_API_KEY", "PARKIO_ANTHROPIC_KEY", "PARKIO_ANTHROPIC_ENDPOINT", "PARKIO_ANTHROPIC_MODEL"):
            os.environ.pop(key, None)
        lib.llm_call("hi", max_tokens=100, retries=1, timeout=30)

    assert captured["url"] == lib.CLIPROXY_ENDPOINT
    assert captured["body"]["model"] == lib.CLIPROXY_MODEL
    assert "thinking" not in captured["body"]


def test_claude_cli_provider_runs_print_mode_without_tools():
    calls = []

    class Done:
        returncode = 0
        stdout = "answer\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return Done()

    with patch.object(lib, "LLM_PROVIDER", "claude"), \
            patch.object(lib, "LLM_FALLBACK_PROVIDER", ""), \
            patch.object(lib.subprocess, "run", fake_run):
        assert lib.llm_call("the prompt", max_tokens=100, retries=1, timeout=30) == "answer"

    cmd, kwargs = calls[0]
    assert cmd[:2] == [lib.CLAUDE_BIN, "-p"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "--no-session-persistence" in cmd
    assert kwargs["input"] == "the prompt"  # stdin, not argv
    assert kwargs["cwd"] == lib.CODEX_WORKDIR


def test_missing_claude_cli_is_a_config_error_not_a_retry():
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    with patch.object(lib, "LLM_PROVIDER", "claude"), \
            patch.object(lib, "LLM_FALLBACK_PROVIDER", ""), \
            patch.object(lib.subprocess, "run", fake_run):
        try:
            lib.llm_call("x", retries=1)
        except lib.LLMNonRetryable as exc:
            assert "claude CLI not found" in str(exc)
        else:
            raise AssertionError("expected LLMNonRetryable")

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import product_radar


def test_parse_product_hunt_feed():
    atom = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <updated>2026-06-18T00:01:00-07:00</updated>
  <entry>
    <title>VELA</title>
    <published>2026-06-18T01:00:00-07:00</published>
    <link rel="alternate" href="https://www.producthunt.com/products/vela-7"/>
    <content type="html">&lt;p&gt;Securely execute AI-generated &amp;amp; untrusted code&lt;/p&gt;</content>
  </entry>
</feed>"""
    rows = product_radar.parse_product_hunt_feed(atom)
    assert len(rows) == 1
    assert rows[0].title == "VELA"
    assert "Securely execute" in rows[0].summary
    assert "ai_agents" in rows[0].tags
    assert "security_privacy" in rows[0].tags


def test_parse_trustmrr_homepage_card():
    html = """
<a class="card" href="/startup/corsproxy">
  <h3 class="font-bold">CORSPROXY</h3>
  <p class="text-[10px] text-muted-foreground truncate">SaaS</p>
  <p>Revenue</p><p class="font-mono">$1.4k</p>
  <p>Price</p><p class="font-mono">$35k</p>
  <p>Multiple</p><p class="font-mono">2.1x</p>
</a>
"""
    rows = product_radar.parse_trustmrr_homepage(html)
    assert len(rows) == 1
    assert rows[0].title == "CORSPROXY"
    assert rows[0].url == "https://trustmrr.com/startup/corsproxy"
    assert "Revenue/MRR $1.4k" in rows[0].metric
    assert "revenue_saas" in rows[0].tags


def test_render_markdown_contract_sections():
    signals = [
        product_radar.score_signal(product_radar.Signal(
            source="Product Hunt",
            title="AI Workflow Builder",
            url="https://www.producthunt.com/products/ai-workflow-builder",
            summary="Build agent workflow automations",
        )),
        product_radar.score_signal(product_radar.Signal(
            source="TrustMRR",
            title="Leadbomb",
            url="https://trustmrr.com/startup/leadbomb",
            summary="SaaS; Revenue/MRR $2.6k",
            metric="Revenue/MRR $2.6k",
        )),
        product_radar.score_signal(product_radar.Signal(
            source="Hacker News",
            title="Ask HN: What developer tools do you pay for?",
            url="https://news.ycombinator.com/item?id=1",
            summary="Developers discuss paid tools",
            metric="120 points · 88 comments · askstories",
        )),
    ]
    md = product_radar.render_markdown(signals, [{"source": "x", "method": "fixture", "fetched": 1}], "2026-06-18")
    assert md.startswith("# 产品雷达 — 2026-06-18")
    assert "## 可行动机会" in md
    assert "## 新产品雷达（Product Hunt）" in md
    assert "## 真实收入信号（TrustMRR）" in md
    assert "## 需求与痛点（Hacker News）" in md
    assert "TrustMRR 当前使用公开页面抓取" in md


def test_fetch_product_hunt_uses_official_feed(monkeypatch):
    atom = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <updated>2026-06-20T00:01:00-07:00</updated>
  <entry>
    <title>Shipyard AI</title>
    <published>2026-06-20T01:00:00-07:00</published>
    <link rel="alternate" href="https://www.producthunt.com/products/shipyard-ai"/>
    <content type="html">&lt;p&gt;Build AI agent workflow automation&lt;/p&gt;</content>
  </entry>
</feed>"""
    seen = []

    def fake_fetch_text(url, timeout=30):
        seen.append((url, timeout))
        return atom

    monkeypatch.setattr(product_radar, "fetch_text", fake_fetch_text)

    signals, meta = product_radar.fetch_product_hunt()

    assert seen == [(product_radar.PRODUCT_HUNT_FEED, 30)]
    assert len(signals) == 1
    assert signals[0].title == "Shipyard AI"
    assert meta["source"] == "Product Hunt"
    assert meta["method"] == "official Atom feed"
    assert meta["fetched"] == 1
    assert meta["updated"] == "2026-06-20T00:01:00-07:00"


def test_fetch_trustmrr_reports_public_scrape_and_api_note(monkeypatch):
    homepage = """
<a class="card" href="/startup/leadbomb">
  <h3 class="font-bold">Leadbomb</h3>
  <p class="text-[10px] text-muted-foreground truncate">SaaS</p>
  <p>Revenue</p><p class="font-mono">$2.6k</p>
</a>
"""
    calls = []

    def fake_fetch_text(url, timeout=30):
        calls.append((url, timeout))
        if url == product_radar.TRUSTMRR_HOME:
            return homepage
        if url == product_radar.TRUSTMRR_FAQ:
            return "TrustMRR API uses Authorization: Bearer tmrr_..."
        raise AssertionError(url)

    monkeypatch.setattr(product_radar, "fetch_text", fake_fetch_text)

    signals, meta = product_radar.fetch_trustmrr()

    assert calls == [(product_radar.TRUSTMRR_HOME, 30), (product_radar.TRUSTMRR_FAQ, 20)]
    assert len(signals) == 1
    assert signals[0].title == "Leadbomb"
    assert "Revenue/MRR $2.6k" in signals[0].metric
    assert meta["source"] == "TrustMRR"
    assert meta["method"] == "public scrape; API exists but needs tmrr_ key"
    assert meta["fetched"] == 1


def test_fetch_hacker_news_keeps_successes_and_records_failures(monkeypatch):
    def fake_fetch_json(url, timeout=30):
        if url.endswith("/topstories.json"):
            return [101, 102]
        if url.endswith("/showstories.json"):
            raise TimeoutError("fixture timeout")
        if url.endswith("/askstories.json") or url.endswith("/newstories.json"):
            return []
        if url == product_radar.hn_item_url(101):
            return {
                "id": 101,
                "title": "Ask HN: Which AI dev tools do you pay for?",
                "url": "https://example.com/ai-devtools",
                "score": 120,
                "descendants": 88,
                "time": 1781930000,
            }
        if url == product_radar.hn_item_url(102):
            raise ConnectionError("fixture item failure")
        raise AssertionError(url)

    monkeypatch.setattr(product_radar, "fetch_json", fake_fetch_json)

    signals, meta = product_radar.fetch_hacker_news(max_items=2)

    assert len(signals) == 1
    assert signals[0].source == "Hacker News"
    assert signals[0].title == "Ask HN: Which AI dev tools do you pay for?"
    assert meta["source"] == "Hacker News"
    assert meta["method"] == "official Firebase API"
    assert meta["fetched"] == 1
    assert "showstories: TimeoutError" in meta["errors"]
    assert "item 102: ConnectionError" in meta["errors"]


def test_collect_signals_degrades_when_one_fetcher_fails(monkeypatch):
    trust_signal = product_radar.score_signal(product_radar.Signal(
        source="TrustMRR",
        title="Revenue Tool",
        url="https://trustmrr.com/startup/revenue-tool",
        summary="SaaS; Revenue/MRR $4.2k",
        metric="Revenue/MRR $4.2k",
    ))
    hn_signal = product_radar.score_signal(product_radar.Signal(
        source="Hacker News",
        title="Show HN: Agent workflow monitor",
        url="https://news.ycombinator.com/item?id=9",
        metric="80 points · 40 comments · showstories",
    ))

    def failing_product_hunt():
        raise RuntimeError("fixture PH outage")
    failing_product_hunt.__name__ = "fetch_product_hunt"

    monkeypatch.setattr(product_radar, "fetch_product_hunt", failing_product_hunt)
    monkeypatch.setattr(product_radar, "fetch_trustmrr", lambda: ([trust_signal], {"source": "TrustMRR", "fetched": 1}))
    monkeypatch.setattr(product_radar, "fetch_hacker_news", lambda: ([hn_signal], {"source": "Hacker News", "fetched": 1}))

    signals, meta = product_radar.collect_signals()

    assert {s.source for s in signals} == {"TrustMRR", "Hacker News"}
    failed = [row for row in meta if row["source"] == "product_hunt"]
    assert failed
    assert failed[0]["fetched"] == 0
    assert failed[0]["errors"] == ["RuntimeError: fixture PH outage"]


def test_previous_signal_keys_filter_recent_duplicates(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw" / "2026-06-20"
    raw_dir.mkdir(parents=True)
    (raw_dir / "product-radar.json").write_text(
        """{
  "signals": [
    {"source": "Product Hunt", "title": "Repeated Tool", "url": "https://example.com/repeated/"},
    {"source": "TrustMRR", "title": "Revenue Tool", "url": "https://trustmrr.com/startup/revenue-tool"}
  ]
}""",
        encoding="utf-8",
    )
    monkeypatch.setattr(product_radar, "INBOX", tmp_path)

    repeated = product_radar.score_signal(product_radar.Signal(
        source="Product Hunt",
        title="Repeated Tool",
        url="https://example.com/repeated",
        summary="Old rolling feed item",
    ))
    fresh = product_radar.score_signal(product_radar.Signal(
        source="Hacker News",
        title="Fresh HN Demand",
        url="https://news.ycombinator.com/item?id=100",
        summary="New demand signal",
    ))

    previous = product_radar.previous_signal_keys("2026-06-21")
    assert "https://example.com/repeated" in previous
    assert product_radar.new_signals_only([repeated, fresh], previous) == [fresh]


def test_build_product_radar_renders_only_new_signals_but_snapshots_all(tmp_path, monkeypatch):
    (tmp_path / "raw" / "2026-06-20").mkdir(parents=True)
    (tmp_path / "raw" / "2026-06-20" / "product-radar.json").write_text(
        '{"signals":[{"source":"Product Hunt","title":"Old Tool","url":"https://example.com/old"}]}',
        encoding="utf-8",
    )
    sent = tmp_path / "sent"
    monkeypatch.setattr(product_radar, "INBOX", tmp_path)
    monkeypatch.setattr(product_radar, "SENT_DIR", sent)
    old = product_radar.score_signal(product_radar.Signal(
        source="Product Hunt",
        title="Old Tool",
        url="https://example.com/old",
        summary="Repeated rolling item",
    ))
    fresh = product_radar.score_signal(product_radar.Signal(
        source="Hacker News",
        title="Fresh Pain",
        url="https://news.ycombinator.com/item?id=200",
        summary="Fresh user pain",
        metric="55 points · 20 comments · topstories",
    ))
    monkeypatch.setattr(
        product_radar,
        "collect_signals",
        lambda: ([old, fresh], [{"source": "fixture", "method": "mock", "fetched": 2}]),
    )

    result = product_radar.build_product_radar("2026-06-21", with_png=False)
    markdown = Path(result["markdown"]).read_text(encoding="utf-8")
    raw = Path(result["raw"]).read_text(encoding="utf-8")

    assert result["signals"] == 2
    assert result["reader_signals"] == 1
    assert result["repeated_signals"] == 1
    assert "Fresh Pain" in markdown
    assert "Old Tool" not in markdown
    assert "读者版新增信号：1 条；完整抓取快照：2 条；隐藏近期重复：1 条" in markdown
    assert "Old Tool" in raw
    assert "Fresh Pain" in raw

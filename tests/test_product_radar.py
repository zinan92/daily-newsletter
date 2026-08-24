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
    choices = [
        product_radar.ProductChoice(
            name="AI 销售通话复盘助手",
            value="自动找出销售通话中的异议和下一步动作，帮助小团队缩短成交周期。",
            evidence_ids=("signal-001",),
        ),
        product_radar.ProductChoice(
            name="独立开发者退款风险台",
            value="在退款发生前识别高风险用户，并给出可以挽回订阅的服务动作。",
            evidence_ids=("signal-002",),
        ),
    ]
    md = product_radar.render_markdown(choices, "2026-06-18")
    assert md.startswith("# 产品雷达 — 2026-06-18")
    assert "## Top Three Products to Build Today" in md
    assert "1. AI 销售通话复盘助手：自动找出销售通话中的异议" in md
    assert "2. 独立开发者退款风险台：在退款发生前识别高风险用户" in md
    assert "**" not in md
    for hidden in ("Product Hunt", "TrustMRR", "Hacker News", "数据质量", "可以 build 什么", "为什么是今天", "证据", "MVP 切入"):
        assert hidden not in md


def test_render_markdown_allows_empty_without_faking_products():
    md = product_radar.render_markdown([], "2026-06-18")

    assert "## Top Three Products to Build Today" in md
    assert "今天没有新的产品值得优先考虑。" in md
    assert "1." not in md


def test_generate_product_choices_uses_ai_json_and_keeps_sources_internal():
    signal = product_radar.score_signal(product_radar.Signal(
        source="TrustMRR",
        title="ClinicScribe",
        url="https://example.com/clinic-scribe",
        summary="Medical note workflow",
        metric="Revenue/MRR $8k",
    ))
    seen = {}

    def fake_client(prompt, **kwargs):
        seen["prompt"] = prompt
        return '{"products":[{"name":"小诊所病历整理助手","value":"把问诊录音整理成可审核病历，减少医生下班后的文书时间。","evidence_ids":["signal-001"]}]}'

    choices, raw, rows = product_radar.generate_product_choices([signal], {"旧产品"}, client=fake_client)

    assert choices == [product_radar.ProductChoice(
        name="小诊所病历整理助手",
        value="把问诊录音整理成可审核病历，减少医生下班后的文书时间。",
        evidence_ids=("signal-001",),
    )]
    assert raw.startswith('{"products"')
    assert rows[0]["source"] == "TrustMRR"
    assert '"recent_product_names": ["旧产品"]' in seen["prompt"]


def test_parse_product_choices_fails_loudly_on_reader_ops_data():
    raw = '{"products":[{"name":"AI 工具","value":"TrustMRR 显示它已有收入。","evidence_ids":["signal-001"]}]}'

    try:
        product_radar.parse_product_choices(raw, {"signal-001"})
    except product_radar.ProductRadarAIError as exc:
        assert "source names" in str(exc)
    else:
        raise AssertionError("reader-facing source data should fail validation")


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
    processed = tmp_path / "processed"
    monkeypatch.setattr(product_radar, "INBOX", tmp_path)
    monkeypatch.setattr(product_radar, "SENT_DIR", sent)
    monkeypatch.setattr(product_radar, "PROCESSED_DIR", processed)
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
        summary="Fresh user pain for AI research monitoring",
        metric="55 points · 20 comments · topstories",
    ))
    monkeypatch.setattr(
        product_radar,
        "collect_signals",
        lambda: ([old, fresh], [{"source": "fixture", "method": "mock", "fetched": 2}]),
    )
    seen = {}

    def fake_generate(signals, recent_names):
        seen["signals"] = signals
        return (
            [product_radar.ProductChoice(
                name="产品需求变化监控器",
                value="持续追踪用户讨论中的新痛点，帮助创始人更早发现可验证的产品切口。",
                evidence_ids=("signal-001",),
            )],
            '{"products":[]}',
            [{"id": "signal-001", "title": "Fresh Pain"}],
        )

    monkeypatch.setattr(product_radar, "generate_product_choices", fake_generate)

    result = product_radar.build_product_radar("2026-06-21", with_png=False)
    markdown = Path(result["markdown"]).read_text(encoding="utf-8")
    raw = Path(result["raw"]).read_text(encoding="utf-8")
    selection = Path(result["selection"]).read_text(encoding="utf-8")

    assert result["signals"] == 2
    assert result["reader_signals"] == 1
    assert result["repeated_signals"] == 1
    assert result["products"] == 1
    assert seen["signals"] == [fresh]
    assert "产品需求变化监控器" in markdown
    assert "Fresh Pain" not in markdown
    assert "Old Tool" not in markdown
    assert "数据质量" not in markdown
    assert "Fresh Pain" in selection
    assert "Old Tool" in raw
    assert "Fresh Pain" in raw


def test_build_product_radar_records_ai_failure_without_reader_fallback(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    batch = processed / "26-06-21"
    batch.mkdir(parents=True)
    (batch / "product-radar-26-06-21.md").write_text("stale reader output", encoding="utf-8")
    monkeypatch.setattr(product_radar, "INBOX", tmp_path)
    monkeypatch.setattr(product_radar, "SENT_DIR", tmp_path / "sent")
    monkeypatch.setattr(product_radar, "PROCESSED_DIR", processed)
    signal = product_radar.score_signal(product_radar.Signal(
        source="Product Hunt",
        title="Specific Product",
        url="https://example.com/specific-product",
        summary="A specific workflow product",
    ))
    monkeypatch.setattr(product_radar, "collect_signals", lambda: ([signal], []))

    def fail_generation(signals, recent_names):
        raise product_radar.ProductRadarAIError("invalid JSON", raw_response="not-json")

    monkeypatch.setattr(product_radar, "generate_product_choices", fail_generation)

    try:
        product_radar.build_product_radar("2026-06-21")
    except product_radar.ProductRadarAIError:
        pass
    else:
        raise AssertionError("invalid AI output must fail the Product Radar build")

    assert (batch / "product-radar-error.json").exists()
    assert (batch / "product-radar-raw-response.md").read_text(encoding="utf-8") == "not-json"
    assert not (batch / "product-radar-26-06-21.md").exists()


def test_previous_product_names_reads_only_product_radar_section(tmp_path, monkeypatch):
    sent = tmp_path / "sent"
    sent.mkdir()
    (sent / "26-06-25.md").write_text(
        "# AI Daily Newsletter — 2026-06-25\n\n"
        "## 快讯\n\n1. 不是产品雷达\n\n"
        "## 产品雷达\n\n### Top Three Products to Build Today\n\n"
        "1. 销售异议复盘助手：把通话变成跟进动作。\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(product_radar, "SENT_DIR", sent)

    assert product_radar.previous_product_names("2026-06-26") == {"销售异议复盘助手"}


def test_product_radar_tag_matching_does_not_match_inside_words():
    tags = product_radar.tag_signal("Apple raises prices of MacBooks and iPads")

    assert "growth_sales" not in tags
    assert "revenue_saas" not in tags

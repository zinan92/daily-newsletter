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

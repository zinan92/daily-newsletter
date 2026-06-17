"""Phase 4 reader-quality contract tests.

This file is the consolidated regression lock for the GSD Phase 4 success
criteria. Focused tests still cover the details; these assertions keep the
product-level contract visible in one place.

Run: python3 tests/test_reader_quality_contract.py
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import digest_config
import lib
import summarize
import digest_events
from aggregation.digest import ai_quality


def load_quality_check():
    spec = importlib.util.spec_from_file_location("quality_check", ROOT / "quality-check.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


quality_check = load_quality_check()


def test_x_titles_reject_truncated_first_sentence_prefixes():
    cases = [
        (
            "Codex 昨晚上线的这个 Site 插件非",
            "Codex 昨晚上线的这个 Site 插件非常厉害。它本质上感觉类似于 Claude Design。",
        ),
        (
            "长文《想做高级咨询风视觉",
            "长文《想做高级咨询风视觉？这套麦肯锡风格提示词可以直接复制》最近很火。",
        ),
    ]
    for title, body in cases:
        assert summarize.x_title_looks_truncated(title, body), title


def test_media_requires_transcript_backed_non_promo_summary():
    no_transcript = {
        "title": "Team thinking, visualized by Claude",
        "status": "no_transcript",
        "error": "audio transcript too short: 149 chars",
        "summary": None,
        "bullets": None,
    }
    promo = {
        "title": "It's time to fly | Codex",
        "status": "summarized",
        "summary": "OpenAI Codex 宣传片以火箭发射倒计时为隐喻，展现用自然语言命令即可让 AI 实时编写代码。",
        "bullets": ["视频通过类比传递体验。"],
    }
    deep = {
        "title": "Dwarkesh × Researcher: scaling laws",
        "status": "summarized",
        "summary": "访谈深入讨论了模型迭代速度如何决定能力提升，并解释了数据修复比新算法更关键的原因。",
        "bullets": ["团队迭代速度是模型进步的核心驱动。", "训练流程中的 BUG 修复带来质量提升。"],
    }

    assert not summarize.media_record_is_publishable(no_transcript)
    assert not summarize.media_record_is_publishable(promo)
    assert summarize.media_record_is_publishable(deep)


def test_active_douyin_sources_are_loaded_from_source_config():
    original_loader = lib.load_sources
    original_cache = digest_config._ACTIVE_DOUYIN_CACHE

    def fake_load_sources():
        return [
            {"platform": "douyin", "active": "true", "name": "柱子哥TzFilm"},
            {"platform": "douyin", "active": "false", "name": "已停用抖音源"},
            {"platform": "wechat", "active": "true", "name": "不是抖音源"},
        ]

    try:
        lib.load_sources = fake_load_sources
        digest_config._ACTIVE_DOUYIN_CACHE = None
        active = digest_config.active_douyin_source_names()
        douyin_group = digest_config.source_names_for_group("douyin")
    finally:
        lib.load_sources = original_loader
        digest_config._ACTIVE_DOUYIN_CACHE = original_cache

    assert "柱子哥TzFilm" in active
    assert "柱子哥TzFilm" in douyin_group
    assert "已停用抖音源" not in active
    assert "不是抖音源" not in active


def test_visible_product_gate_covers_reader_quality_leaks():
    assert "no_transcript" in quality_check.BAD_PATTERNS
    assert "转录失败" in quality_check.BAD_PATTERNS
    assert "一位博主" in quality_check.BAD_PATTERNS
    assert "公众号：" in quality_check.BAD_PATTERNS
    assert "source_name" in quality_check.METADATA_PATTERNS
    assert quality_check.raw_english_body_lines(
        "This line is raw English prose from an unrevised source.\n"
        "这行中文读者正文是可以的。"
    )


def test_ai_qc_allows_reader_visible_health_and_issue_pool():
    assert not ai_quality.valid_blocking_issue({
        "type": "metadata_leak",
        "location": "未进入正文",
        "text": "转录未完成：YouTube 要求登录/反 bot 验证",
        "fix": "删除未进入正文",
    })
    assert not ai_quality.valid_blocking_issue({
        "type": "producer_voice",
        "location": "今日结论",
        "text": "获取 5 条 → 收录 5 条 → 展示 2 条 · 未进入正文 1 条",
        "fix": "删除今日结论",
    })


def test_today_conclusion_uses_additive_item_and_event_pools():
    breakdown = {
        "total": 10,
        "paths": [{
            "key": "x",
            "label": "X 应用层",
            "bypass": False,
            "fetched": 10,
            "kept": 3,
            "filtered": 7,
            "events": 3,
            "rendered": 2,
            "channels_total": 1,
        }],
    }
    stats = {"x": {"high_value": 2, "display": 1, "issues": 0}}
    text = "\n".join(summarize.render_today_conclusion_md(breakdown, stats))
    assert "获取 10 → 收录 3（score >= 3，未收录 7 条）" in text
    assert "→ 展示 1 + 未进入正文 0 + 合并 2" in text
    assert "Accepted" not in text
    assert "Display" not in text
    assert "Issue " not in text
    assert "合并吸收" not in text
    assert "Merged" not in text


def test_media_title_cleans_anthropic_data_agent_series():
    item = {"title": "Anthropic 数据 Agent 95% 准确率背后③ Anthropic 数据 Agent 95% 准确率…普通公司最小成本怎么开始"}
    assert summarize.media_update_title(item) == "Anthropic 数据 Agent：普通公司如何低成本开始"


def test_html_renders_funnel_and_contact_images_from_markdown():
    md = """# AI 情报日报 — 2026-06-07

## 今日结论
- **X 应用层** — 获取 10 → 收录 3（score >= 3，未收录 7 条） → 展示 1 + 未进入正文 0 + 合并 2

## 关注与加入

### [X](https://x.com/xparkzz)

![X](/Users/wendy/park-io/_contact/x.jpg)

@xparkzz
"""
    html = summarize.render_html_from_markdown(md, "2026-06-07")
    assert "pipeline-card" in html
    assert "获取" in html
    assert "<strong>10</strong>" in html
    assert "<span>展示</span><b>1</b>" in html
    assert "parkio-funnel" not in html
    assert "contact-entry" in html
    assert 'src="../../../_contact/x.jpg"' in html
    assert 'contact-entry contact-x' in html
    assert 'contact-mark contact-mark-x' in html
    assert "<span>X</span>" in html
    contact_part = html.split('<section class="card contact-card">', 1)[1]
    assert "link-icon icon-x" not in contact_part


def test_markdown_html_heading_divergence_is_detected():
    visible_md = "## 今日精选\n\n### 厂商动态\n\n##### 新模型上线\n"
    visible_html = "<h2>今日精选</h2><h3>厂商动态</h3>"
    assert quality_check.heading_divergence(visible_md, visible_html) == ["新模型上线"]


def test_inline_code_asterisk_does_not_break_bold_html():
    line = '- **deny 规则支持 glob（`"*"` 禁止所有工具）**：权限管理更清晰'
    html = summarize.render_html_from_markdown(line, "2026-06-07")
    assert "**deny" not in html
    assert "<strong>deny 规则支持 glob（<code>&quot;*&quot;</code> 禁止所有工具）</strong>" in html


def test_editorial_packet_includes_high_signal_items_after_group_caps():
    candidates = []
    for idx in range(65):
        candidates.append({
            "kind": "item",
            "group": "工具工作流",
            "title": f"高分候选 {idx}",
            "url": f"https://example.com/high-{idx}",
            "source": "X",
            "summary": "这是一个可用于生成短讯的高分候选。",
            "score": 5,
        })
    target = {
        "kind": "item",
        "group": "工具工作流",
        "title": "一个专门给产品经理准备的 Skill，五天 13k Stars",
        "url": "https://x.com/vista8/status/2064611893566640275",
        "source": "X",
        "summary": "产品经理 Skill 包展示了 AI 原生工作流产品化机会，但需要警惕大而全模板。",
        "score": 4,
    }
    candidates.append(target)

    selected = summarize.select_editorial_candidates(candidates)
    assert target["url"] in {cand.get("url") for cand in selected}


def test_editorial_cleaner_rewrites_internal_business_line_terms():
    text = summarize.sanitize_editorial_markdown(
        "## 短讯\n\n"
        "- 产品线会复用同一套判断轴，内容线和交易线也会受影响。"
    )
    assert "产品线" not in text
    assert "内容线" not in text
    assert "交易线" not in text
    assert "产品矩阵" in text


def test_editorial_cleaner_removes_bare_candidate_ids():
    text = summarize.sanitize_editorial_markdown(
        "## 短讯\n\n"
        "1. Agent 定时任务开始变重要（C3, C19）。\n\n"
        "## 今日深读\n\n"
        "1. 现在可以测试迁移窗口。（来源：C24）"
    )
    assert "C3" not in text
    assert "C19" not in text
    assert "C24" not in text
    assert "来源：" not in text


def test_official_render_is_flat_numbered_and_drops_low_info_items():
    events = [
        {
            "primary": {"source": "Anthropic News", "title": "Claude Code Release：v2.1.163", "url": "u1", "content": "x"},
            "items": [{"source": "Anthropic News", "title": "Claude Code Release：v2.1.163", "url": "u1", "content": "x"}],
            "summary": "Claude Code 发布了版本范围管理能力，方便团队控制依赖和升级节奏。",
        },
        {
            "primary": {"source": "Anthropic News", "title": "Claude Code Release：v2.1.165", "url": "u2", "content": "x"},
            "items": [{"source": "Anthropic News", "title": "Claude Code Release：v2.1.165", "url": "u2", "content": "x"}],
            "summary": "Claude Code 修复了会话恢复和工具调用细节，让长任务继续执行更稳定。",
        },
        {
            "primary": {
                "source": "openai-codex-releases",
                "title": "OpenAI Codex Release：rust-v0.138.0-alpha.5",
                "url": "u3",
                "content": "Release 0.138.0-alpha.5",
            },
            "items": [{
                "source": "openai-codex-releases",
                "title": "OpenAI Codex Release：rust-v0.138.0-alpha.5",
                "url": "u3",
                "content": "Release 0.138.0-alpha.5",
            }],
            "summary": "Release 0.138.0-alpha.5",
        },
    ]
    text = "\n".join(summarize.render_official_company_group_md("Anthropic / Claude", events, heading_level=4))
    assert "开发与集成层" not in text
    assert "对你的价值" not in text
    assert "相关链接" not in text
    assert "1. [Anthropic News：Claude Code Release：v2.1.163]" in text
    assert "2. [Anthropic News：Claude Code Release：v2.1.165]" in text
    assert "rust-v0.138.0-alpha.5" not in text


def test_application_category_prefers_ai_tools_and_filters_payment_news():
    ai_event = {
        "primary": {"source": "ai_xiaomu", "title": "大型代码库 Vibe Coding 靠文档", "content": "Vibe Coding 在大型代码库里需要文档体系和 Claude Code。", "url": "u"},
        "items": [{"source": "ai_xiaomu", "title": "大型代码库 Vibe Coding 靠文档", "content": "Vibe Coding 在大型代码库里需要文档体系和 Claude Code。", "url": "u"}],
    }
    pay_event = {
        "primary": {"source": "ai_xiaomu", "title": "U卡新闻", "content": "虚拟卡和 Bitget Wallet 的支付卡新闻。", "url": "u"},
        "items": [{"source": "ai_xiaomu", "title": "U卡新闻", "content": "虚拟卡和 Bitget Wallet 的支付卡新闻。", "url": "u"}],
    }
    generic_news = {
        "primary": {"source": "ai_xiaomu", "title": "行业快讯", "content": "这是一条泛新闻，只讨论普通市场动态。", "url": "u"},
        "items": [{"source": "ai_xiaomu", "title": "行业快讯", "content": "这是一条泛新闻，只讨论普通市场动态。", "url": "u"}],
    }
    assert summarize.application_event_category(ai_event) == "AI 工具用法"
    assert not summarize.application_event_is_publishable(pay_event)
    assert not summarize.application_event_is_publishable(generic_news)


def test_application_same_author_same_vibe_coding_topic_merges():
    events = [
        {
            "primary": {
                "source": "OP7418",
                "author": "歸藏",
                "title": "大型代码库Vibe Coding很依赖文档，文档占代码21%",
                "content": "大型代码库 Vibe Coding 依赖文档，文档占代码 21%。",
                "url": "https://x.com/op7418/status/1",
                "score": 4,
            },
            "items": [],
            "score": 4,
            "event_key": "u1",
        },
        {
            "primary": {
                "source": "OP7418",
                "author": "歸藏",
                "title": "大型代码库Vibe Coding高度依赖文档，文档占代码比例达21%",
                "content": "CodePilot v0.55.0 支持多执行引擎切换，大型代码库 Vibe Coding 高度依赖文档，文档占代码比例达 21%。",
                "url": "https://x.com/op7418/status/2",
                "score": 4,
            },
            "items": [],
            "score": 4,
            "event_key": "u2",
        },
    ]
    for event in events:
        event["items"] = [event["primary"]]
    merged = summarize.merge_application_duplicate_events(events)
    assert len(merged) == 1
    assert len(merged[0]["items"]) == 2


def test_application_event_key_does_not_merge_all_xianyu_posts():
    a = {
        "source": "ai_xiaomu",
        "title": "用 Claude 搞闲鱼店铺",
        "content": "讨论闲鱼选品和标题改写。",
        "url": "https://x.com/a/1",
    }
    b = {
        "source": "ai_xiaomu",
        "title": "程序员从零搭建 AI 自动化开发工作流",
        "content": "讲自动化开发工作流，不是同一个闲鱼运营事件。",
        "url": "https://x.com/a/2",
    }
    assert digest_events.event_key(a) != digest_events.event_key(b)


def test_application_section_is_flat_score_sorted_with_author_in_title():
    original_value_paragraph = summarize.value_paragraph

    def fake_value_paragraph(item):
        return "这是中文摘要，说明这条 X 内容的核心信息。"

    events = [
        {
            "primary": {
                "source": "rwayne",
                "author": "Roland.W",
                "title": "低分但同样可读",
                "content": "Claude Code 低分测试内容。",
                "url": "https://x.com/rwayne/status/1",
                "score": 4,
            },
            "items": [],
            "score": 4,
            "event_key": "low",
        },
        {
            "primary": {
                "source": "ai_xiaomu",
                "author": "黄小木",
                "title": "高分应该排在前面",
                "content": "Claude Code 高分测试内容。",
                "url": "https://x.com/ai_xiaomu/status/2",
                "score": 5,
            },
            "items": [],
            "score": 5,
            "event_key": "high",
        },
    ]
    for event in events:
        event["items"] = [event["primary"]]
    try:
        summarize.value_paragraph = fake_value_paragraph
        text = "\n".join(summarize.render_application_events_md(events))
    finally:
        summarize.value_paragraph = original_value_paragraph

    assert "**黄小木**" not in text
    assert "**Roland.W**" not in text
    assert "· 黄小木" in text
    assert "· Roland.W" in text
    assert text.index("· 黄小木") < text.index("· Roland.W")


def test_value_paragraph_rejects_third_person_narration_for_wechat():
    original_llm_call = summarize.llm_call
    original_source_item_paragraph = summarize.source_item_paragraph

    item = {
        "source": "数字生命卡兹克",
        "source_name": "数字生命卡兹克",
        "platform": "wechat",
        "category": "wechat-ai",
        "title": "AI 工具测试文章",
        "content": "这是一篇自动公众号文章，内容足够长，用来验证公众号摘要也不能出现有博主、一位用户这类旁白称呼。"
        * 6,
        "url": "https://mp.weixin.qq.com/s/test-third-person",
        "score": 4,
    }

    try:
        summarize.llm_call = lambda *args, **kwargs: "今年高考季，有博主让12款顶级AI同步挑战语文和数学全国一卷。"
        summarize.source_item_paragraph = lambda item: "数字生命卡兹克整理了 AI 工具测试文章。"
        text = summarize.value_paragraph(item)
    finally:
        summarize.llm_call = original_llm_call
        summarize.source_item_paragraph = original_source_item_paragraph

    assert "有博主" not in text
    assert text == "数字生命卡兹克整理了 AI 工具测试文章。"


def test_value_paragraph_rejects_generic_wechat_article_narration():
    original_llm_call = summarize.llm_call
    original_source_item_paragraph = summarize.source_item_paragraph

    item = {
        "source": "数字生命卡兹克",
        "source_name": "数字生命卡兹克",
        "platform": "wechat",
        "category": "wechat-ai",
        "title": "Agent 工作流文章",
        "content": "这是一篇自动公众号文章，内容足够长，用来验证摘要不能把公众号作者泛称为一篇公众号文章。"
        * 6,
        "url": "https://mp.weixin.qq.com/s/test-generic-wechat",
        "score": 4,
    }

    try:
        summarize.llm_call = lambda *args, **kwargs: "一篇公众号文章分享了将 GitHub 项目转化为元 Skill 工作流的方法。"
        summarize.source_item_paragraph = lambda item: "数字生命卡兹克分享了 Agent 工作流文章。"
        text = summarize.value_paragraph(item)
    finally:
        summarize.llm_call = original_llm_call
        summarize.source_item_paragraph = original_source_item_paragraph

    assert "一篇公众号文章" not in text
    assert text == "数字生命卡兹克分享了 Agent 工作流文章。"


def test_saved_fallback_never_dumps_raw_first_person_or_broken_cut():
    item = {
        "source": "dontbesilent",
        "author": "dontbesilent",
        "title": "2 天，2 亿 token，dontbesilent 内容资产工程系统｜已免费开源",
        "content": "我是 Codex 过去 2 天，我和 dontbesilent 做了一件事：把他本地已经堆到很大规模的内容资产，搭成了一套可以继续运行的结构化系统，这件事的核心，是把一个长期写作者散落在本地的内容。",
        "url": "https://x.com/dontbesilent/status/1",
    }
    text = summarize.saved_fallback_paragraph(item)
    assert "我是 Codex" not in text
    assert "我是…" not in text
    assert "2330 个文件，中" not in text
    assert text.endswith("。")


def test_x_source_fallback_never_dumps_raw_first_person():
    item = {
        "source": "ai_xiaomu",
        "author": "黄小木",
        "title": "从 Claude Code 转向 Codex 的模式差异",
        "content": "经过我一天的实践，目前已经完全从 claude code 转向了 codex。codex 的目标模式，用过和没用过的已经是两个物种。",
        "url": "https://x.com/ai_xiaomu/status/1",
    }
    text = summarize.source_item_paragraph(item)
    assert "经过我" not in text
    assert "目前已经完全" not in text
    assert "黄小木 分享了" in text


def test_saved_fallback_does_not_quote_raw_english_titles():
    item = {
        "source": "我的 X 收藏",
        "author": "Claude",
        "title": "Introducing Claude Fable 5: a Mythos-class model",
        "content": "Introducing Claude Fable 5: a Mythos-class model that we made safe for general use.",
        "url": "https://x.com/trq212/status/1",
    }
    text = summarize.saved_fallback_paragraph(item)
    assert "Introducing Claude Fable" not in text
    assert "Claude 分享了一条围绕" in text


def test_official_duplicate_signature_dedupes_same_chatgpt_memory_event():
    events = [
        {
            "primary": {"source": "ChatGPT X", "title": "ChatGPT 将记忆用户偏好与上下文", "url": "u1", "content": "ChatGPT memory remembers preferences and context."},
            "items": [{"source": "ChatGPT X", "title": "ChatGPT 将记忆用户偏好与上下文", "url": "u1", "content": "ChatGPT memory remembers preferences and context."}],
            "summary": "ChatGPT 升级记忆系统，能记住用户偏好与上下文，并支持用户管理。",
        },
        {
            "primary": {"source": "Sam Altman", "title": "ChatGPT 今日推出更强记忆系统", "url": "u2", "content": "ChatGPT memory is better and carries context."},
            "items": [{"source": "Sam Altman", "title": "ChatGPT 今日推出更强记忆系统", "url": "u2", "content": "ChatGPT memory is better and carries context."}],
            "summary": "Sam Altman 宣布 ChatGPT 记忆系统升级，能够跨对话保持上下文。",
        },
    ]
    text = "\n".join(summarize.render_official_company_group_md("OpenAI / ChatGPT / Codex", events, heading_level=4))
    assert text.count("记忆") >= 1
    assert "2. [" not in text


def test_v2_deep_reads_exclude_release_and_short_x_updates():
    release = {
        "kind": "official",
        "group": "底层变化",
        "title": "Claude Code Release：v2.1.170",
        "url": "https://github.com/anthropics/claude-code/releases/tag/v2.1.170",
        "source": "Claude Code Release",
        "summary": "Claude Code 发布了一个版本更新。",
        "score": 5,
        "event": {
            "primary": {"source": "claude-code-releases", "title": "Claude Code Release：v2.1.170", "url": "u1", "content": "Bug fixes."},
            "items": [{"source": "claude-code-releases", "title": "Claude Code Release：v2.1.170", "url": "u1", "content": "Bug fixes."}],
        },
    }
    short_x = {
        "kind": "official",
        "group": "底层变化",
        "title": "Claude Fable 5 is generally available",
        "url": "https://x.com/ClaudeDevs/status/1",
        "source": "Claude Devs",
        "summary": "Claude Devs 发布了一条模型上线短讯。",
        "score": 5,
        "event": {
            "primary": {"source": "Claude Devs X", "title": "Claude Fable 5 is generally available", "url": "u2", "content": "Claude Fable 5 is generally available."},
            "items": [{"source": "Claude Devs X", "title": "Claude Fable 5 is generally available", "url": "u2", "content": "Claude Fable 5 is generally available."}],
        },
    }
    official_long = {
        "kind": "official",
        "group": "底层变化",
        "title": "Claude Fable 5 and Claude Mythos 5",
        "url": "https://www.anthropic.com/news/claude-fable-5-mythos-5",
        "source": "Anthropic News",
        "summary": "Anthropic 发布了模型分层说明。",
        "score": 5,
        "event": {
            "primary": {"source": "Anthropic News", "title": "Claude Fable 5 and Claude Mythos 5", "url": "u3", "content": "Claude Fable 5 and Claude Mythos 5 introduce model tiers."},
            "items": [{"source": "Anthropic News", "title": "Claude Fable 5 and Claude Mythos 5", "url": "u3", "content": "Claude Fable 5 and Claude Mythos 5 introduce model tiers."}],
        },
    }
    long_case = {
        "kind": "application",
        "group": "内容 / 分发 / 变现",
        "title": "长文《用 Agent 跑 SEO/GEO 工作流的真实搭法》",
        "url": "https://x.com/wadezone/status/1",
        "source": "Wade",
        "summary": "这是一篇关于 Agent、SEO 和 GEO 增长系统的长文案例。",
        "score": 5,
        "event": {
            "primary": {
                "source": "wadezone",
                "title": "长文《用 Agent 跑 SEO/GEO 工作流的真实搭法》",
                "url": "u4",
                "content": "长文《用 Agent 跑 SEO/GEO 工作流的真实搭法》讲述一个独立开发者如何把搜索需求、内容结构、页面生产、分发和复盘串成持续迭代的增长系统。" * 3,
            },
            "items": [],
        },
    }
    long_case["event"]["items"] = [long_case["event"]["primary"]]
    duplicate_long_case = {
        **long_case,
        "url": "https://x.com/ai_xiaomu/status/1",
        "source": "黄小木",
        "event": {
            "primary": {
                **long_case["event"]["primary"],
                "source": "ai_xiaomu",
                "url": "u5",
            },
            "items": [],
        },
    }
    duplicate_long_case["event"]["items"] = [duplicate_long_case["event"]["primary"]]

    text = "\n".join(summarize.render_deep_reads_md([release, short_x, official_long, long_case, duplicate_long_case]))
    assert "Claude Code Release：v2.1.170" not in text
    assert "Claude Devs" not in text
    assert "Claude Fable 5 and Claude Mythos 5" in text
    assert "用 Agent 跑 SEO/GEO 工作流" in text
    assert text.count("用 Agent 跑 SEO/GEO 工作流") == 1
    assert "**核心论点：**" in text
    assert "**它改变了什么判断：**" in text
    assert "对你的判断价值" not in text
    assert "建议动作" not in text
    assert "Daily Inbox" not in text


def test_unknown_english_release_notes_fall_back_to_chinese_summary():
    text = summarize.translate_release_note_source(
        "Introducing Claude Fable 5: a Mythos-class model that we have made safe for general use."
    )
    assert "Introducing Claude Fable" not in text
    assert "Mythos-class model" not in text
    assert "Claude 系列模型" in text


def test_quality_gate_locks_v2_deep_read_contract():
    ok = """# Daily Inbox V2 — 2026-06-10

## 今日深读

### 1. [长文案例](https://example.com)

来源：Example

**核心论点：**
这是一篇中文深度案例，讨论平台机制和内容资产。

**为什么值得读：**
它能帮助读者理解结构性变化。

**它改变了什么判断：**
读完后应更新对平台机制的判断。

**可迁移启发：**
可迁移到内容生产和产品设计。
"""
    assert quality_check.deep_read_contract_issues(ok) == []
    bad = ok.replace("**它改变了什么判断：**", "**对你的判断价值：**")
    issues = quality_check.deep_read_contract_issues(bad)
    assert any("对你的判断价值" in issue for issue in issues)
    assert any("missing field" in issue for issue in issues)


def test_quality_gate_allows_transcription_failure_inside_source_health():
    md = """# Daily Inbox V2 — 2026-06-10

## 短讯

### 底层变化

- [模型更新](https://example.com)：模型能力提升。判断价值：需要重新评估工具选型。

## 今日深读

### 1. [Agent 工作流](https://example.com/agent)

**核心论点：**
Agent 正在从一次性工具变成长期流程。

**为什么值得读：**
它解释了调度和权限为什么重要。

**它改变了什么判断：**
读者应从单次生成转向流程评估。

**可迁移启发：**
可迁移到研发和内容生产。

## Source Health

- 音视频转录失败 2 条，相关内容只保留标题级线索。
"""
    visible = quality_check.visible_markdown(md)
    assert "转录失败" not in quality_check.markdown_without_section(visible, "Source Health")


def test_editorial_cleaner_removes_internal_candidate_ids_and_speculative_health():
    raw = """# Temporary

## 短讯

### 底层变化

- [Fable 5](https://example.com/fable)：发生了什么。判断价值：需要重新评估模型路由。

## 今日深读

### 1. [Loop Engineering](https://example.com/loop)

**核心论点：**
Agent 价值来自循环。

**为什么值得读：**
它解释了可验证流程。

**它改变了什么判断：**
读者应从 prompt 转向系统。

**可迁移启发：**
可迁移到研发和运营。

## Source Health

- 音视频转录异常：一个视频转录失败，未进入深读。
- **评分未完成** 的内容被过滤，未进入正文。
"""
    text = summarize.clean_editorial_markdown(raw, "2026-06-10")
    assert text.startswith("# Daily Inbox V2 — 2026-06-10")
    assert "[C1]" not in text
    assert "评分未完成" not in text
    assert "被过滤，未进入正文" not in text
    assert "转录异常" in text


def test_v2_editorial_generation_uses_one_shot_editor_prompt():
    original_llm_call = summarize.llm_call
    calls = []

    def fake_llm_call(prompt, max_tokens=2000, **kwargs):
        calls.append({"prompt": prompt, "max_tokens": max_tokens, **kwargs})
        return """# Daily Inbox V2 — 2026-06-10

## 短讯

### 底层变化

- [Claude Fable 5](https://example.com/fable)：模型分层改变了工具选型方式。判断价值：读者要同时看能力、权限和成本。

### 工具工作流

- [Loop Engineering](https://example.com/loop)：重点从写 prompt 转向设计循环。判断价值：Agent 的价值来自可验证的持续执行。

### 内容 / 分发 / 变现

- [内容信任](https://example.com/content)：复述型内容价值下降。判断价值：创作者要用一手经验建立信任。

## 今日深读

### 1. [Loop Engineering](https://example.com/loop)

**核心论点：**
未来不是手写 prompt，而是设计能驱动 agent 自我迭代的 loop。

**为什么值得读：**
它解释了 Agent 从工具变成系统所需要的条件。

**它改变了什么判断：**
读者应把注意力从单次生成效果转向状态、评估和回滚。

**可迁移启发：**
可迁移到研发、内容、数据分析和运营自动化。

## Source Health

- 今日没有阻塞正文理解的来源异常。
"""

    candidate = {
        "kind": "application",
        "group": "工具工作流",
        "title": "Loop Engineering",
        "url": "https://example.com/loop",
        "source": "Cell",
        "summary": "Loop Engineering 讨论了如何从手写 prompt 转向可运行的 agent 循环。",
        "score": 5,
        "event": {
            "primary": {
                "source": "x",
                "title": "Loop Engineering",
                "url": "https://example.com/loop",
                "content": "Loop Engineering 正在取代手写 prompt。核心是设计系统来 prompt agent，并用评估循环直到任务完成。",
                "reason": "说明 agent 工作流如何系统化。",
                "score": 5,
            },
            "items": [],
        },
    }
    candidate["event"]["items"] = [candidate["event"]["primary"]]
    try:
        summarize.llm_call = fake_llm_call
        text = summarize.render_editorial_v2_md(
            "2026-06-10",
            [candidate],
            {"totals": {"items": 1, "kept": 1, "filtered": 0}},
            [],
            {"raw": 1, "accepted": 1, "filtered": 0, "source_files": 1},
        )
    finally:
        summarize.llm_call = original_llm_call

    assert text.startswith("# Daily Inbox V2 — 2026-06-10")
    assert "你是一名信息产品主编" in calls[0]["prompt"]
    assert "Candidate Materials" in calls[0]["prompt"]
    assert "Loop Engineering 正在取代手写 prompt" in calls[0]["prompt"]
    assert calls[0]["max_tokens"] >= 8000
    assert "## 短讯" in text
    assert "## Source Health" in text
    assert "## 今日判断" not in text
    assert "## 可行动机会" not in text


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    sys.exit(1 if failed else 0)

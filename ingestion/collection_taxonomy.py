"""Classify personal collection items into Wendy's four durable buckets."""
from __future__ import annotations

import re
from dataclasses import dataclass

CATEGORY_AI = "AI类"
CATEGORY_COGNITION = "认知提升类"
CATEGORY_CONTENT = "做内容类"
CATEGORY_FINANCE = "金融交易类"

CATEGORIES = (CATEGORY_AI, CATEGORY_COGNITION, CATEGORY_CONTENT, CATEGORY_FINANCE)


@dataclass(frozen=True)
class CollectionTaxonomy:
    category: str
    tags: list[str]


CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    CATEGORY_FINANCE: (
        "btc",
        "bitcoin",
        "crypto",
        "polymarket",
        "美股",
        "股票",
        "金融",
        "交易",
        "投资",
        "投研",
        "期权",
        "收益率",
        "etf",
        "alpha",
        "serenity",
        "crux",
        "海力士",
        "mrvl",
        "nok",
        "半导体",
        "portfolio",
    ),
    CATEGORY_CONTENT: (
        "内容",
        "创作",
        "写作",
        "短视频",
        "视频",
        "剪辑",
        "口播",
        "公众号",
        "小红书",
        "抖音",
        "自媒体",
        "newsletter",
        "配图",
        "ppt",
        "visual",
        "标题",
        "文案",
        "排版",
        "流量",
        "获客",
        "增长",
        "粉丝",
        "运营",
        "转化",
    ),
    CATEGORY_AI: (
        "ai",
        "agent",
        "agents",
        "claude",
        "codex",
        "openai",
        "anthropic",
        "chatgpt",
        "cursor",
        "mcp",
        "llm",
        "prompt",
        "skill",
        "skills",
        "vibe coding",
        "loop engineering",
        "github",
        "repo",
        "代码",
        "开发",
        "自动化",
        "工具",
        "模型",
    ),
    CATEGORY_COGNITION: (
        "认知",
        "思维",
        "原则",
        "方法论",
        "工作流",
        "研究",
        "学习",
        "判断",
        "决策",
        "策略",
        "战略",
        "心智",
        "角色",
        "组织",
        "产品",
        "创业",
        "效率",
    ),
}

TAG_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Claude Code", ("claude code", "claude-code")),
    ("Claude", ("claude",)),
    ("Codex", ("codex",)),
    ("OpenAI", ("openai", "chatgpt")),
    ("Anthropic", ("anthropic",)),
    ("AI Agent", ("agent", "agents", "智能体")),
    ("Skill", ("skill", "skills")),
    ("Prompt", ("prompt", "提示词")),
    ("MCP", ("mcp",)),
    ("Vibe Coding", ("vibe coding",)),
    ("Loop Engineering", ("loop engineering",)),
    ("GitHub", ("github", "repo", "开源")),
    ("Obsidian", ("obsidian",)),
    ("前端设计", ("frontend", "前端", "设计规范", "网页设计")),
    ("自动化", ("自动化", "workflow", "工作流", "harness")),
    ("AI工具", ("ai工具", "工具测评", "工具", "模型")),
    ("内容创作", ("内容创作", "内容生产", "创作", "写作")),
    ("短视频", ("短视频", "视频", "剪辑", "口播", "remotion")),
    ("公众号", ("公众号", "微信", "wechat")),
    ("小红书", ("小红书",)),
    ("抖音", ("抖音", "douyin")),
    ("PPT", ("ppt", "slides", "幻灯片")),
    ("配图", ("配图", "图片", "视觉", "visual")),
    ("获客", ("获客", "转化", "成交", "客户")),
    ("增长", ("增长", "流量", "粉丝", "运营", "算法")),
    ("认知模型", ("认知", "思维", "心智", "模型")),
    ("研究方法", ("研究", "research", "信息源", "资料源")),
    ("判断决策", ("判断", "决策", "策略", "战略")),
    ("产品", ("产品", "pmf", "product")),
    ("创业", ("创业", "商业", "生意", "公司")),
    ("金融交易", ("交易", "投资", "投研", "金融")),
    ("美股", ("美股", "股票", "etf", "mrvl", "nok", "海力士", "半导体")),
    ("BTC", ("btc", "bitcoin", "crypto")),
    ("Alpha", ("alpha", "serenity", "crux")),
    ("Polymarket", ("polymarket",)),
    ("期权", ("期权", "options")),
)

CATEGORY_DEFAULT_TAG = {
    CATEGORY_AI: "AI工具",
    CATEGORY_COGNITION: "认知模型",
    CATEGORY_CONTENT: "内容创作",
    CATEGORY_FINANCE: "金融交易",
}

CATEGORY_TAG_PRIORITY = {
    CATEGORY_AI: ("AI Agent", "Claude Code", "Claude", "Codex", "OpenAI", "Anthropic", "Skill", "Prompt", "MCP"),
    CATEGORY_COGNITION: ("认知模型", "研究方法", "判断决策", "工作流", "产品", "创业"),
    CATEGORY_CONTENT: ("内容创作", "短视频", "公众号", "小红书", "抖音", "PPT", "配图", "获客", "增长"),
    CATEGORY_FINANCE: ("金融交易", "美股", "BTC", "Alpha", "Polymarket", "期权"),
}

STRONG_COGNITION_KEYWORDS = ("认知", "思维", "原则", "方法论", "研究", "判断", "决策", "格局", "research")

def _norm(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _contains(text: str, keyword: str) -> bool:
    return keyword.lower() in text


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        value = str(value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def split_tags(value: object) -> list[str]:
    if isinstance(value, list):
        return _dedupe([str(item).strip() for item in value])
    text = str(value or "").strip()
    if not text or text == "-":
        return []
    return _dedupe([part.strip() for part in re.split(r"[,，、;；]+", text) if part.strip()])


def tag_string(tags: list[str]) -> str:
    return ", ".join(_dedupe(tags))


def order_tags_for_category(category: str, tags: list[str], limit: int = 8) -> list[str]:
    tags = _dedupe(tags)
    priority = CATEGORY_TAG_PRIORITY.get(category, ())
    ordered = [tag for tag in priority if tag in tags]
    ordered.extend(tag for tag in tags if tag not in ordered)
    return ordered[:limit]


def classify_collection_text(
    *,
    title: str = "",
    body: str = "",
    url: str = "",
    source: str = "",
    author: str = "",
    existing_tags: object = "",
) -> CollectionTaxonomy:
    title_text = _norm(title)
    text = _norm(" ".join([title, body, url, source, author]))
    scores = {category: 0 for category in CATEGORIES}
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if _contains(text, keyword):
                scores[category] += 1

    strong_cognition_title = any(_contains(title_text, keyword) for keyword in STRONG_COGNITION_KEYWORDS)

    if scores[CATEGORY_FINANCE] > 0:
        category = CATEGORY_FINANCE
    elif strong_cognition_title:
        category = CATEGORY_COGNITION
    elif scores[CATEGORY_CONTENT] > 0 and scores[CATEGORY_CONTENT] >= scores[CATEGORY_AI]:
        category = CATEGORY_CONTENT
    elif scores[CATEGORY_COGNITION] >= 2 and scores[CATEGORY_COGNITION] >= scores[CATEGORY_AI]:
        category = CATEGORY_COGNITION
    elif scores[CATEGORY_AI] > 0:
        category = CATEGORY_AI
    elif scores[CATEGORY_CONTENT] > 0:
        category = CATEGORY_CONTENT
    elif scores[CATEGORY_COGNITION] > 0:
        category = CATEGORY_COGNITION
    else:
        category = CATEGORY_COGNITION

    tags = split_tags(existing_tags)
    for tag, keywords in TAG_RULES:
        if any(_contains(text, keyword) for keyword in keywords):
            tags.append(tag)
    if not tags:
        tags.append(CATEGORY_DEFAULT_TAG[category])
    return CollectionTaxonomy(category=category, tags=order_tags_for_category(category, tags))

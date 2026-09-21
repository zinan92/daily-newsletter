"""Shared digest configuration.

Keep product policy constants here so summarize.py stays focused on orchestration
and rendering.
"""

SCORE_THRESHOLD = 3
HIGH_VALUE_SCORE = 4
TOP_DIGEST_EVENTS = 10

OFFICIAL_CATEGORY_ORDER = [
    "产品体验层",
    "开发与集成层",
    "模型与性能层",
    "商业化与使用规则层",
    "外部合作与生态信号",
]

SOURCE_ROLES = {
    "Anthropic News": "company_official",
    "Anthropic Engineering": "company_official",
    "Claude Blog": "company_official",
    "OpenAI Blog": "company_official",
    "OpenAI X": "company_official",
    "ChatGPT X": "company_official",
    "Anthropic X": "company_official",
    "Claude X": "company_official",
    "Claude Devs X": "company_official",
    "Anthropic YouTube": "company_official",
    "Claude YouTube": "company_official",
    "OpenAI YouTube": "company_official",
    "ChatGPT YouTube": "company_official",
    "openai-codex-releases": "company_official",
    "claude-code-releases": "company_official",
    "Sam Altman": "company_person",
    "Greg Brockman": "company_person",
    "Kevin Weil": "company_person",
    "Mark Chen": "company_person",
    "Dario Amodei": "company_person",
    "Daniela Amodei": "company_person",
    "Mike Krieger": "company_person",
    "op7418": "application_practice",
    "vista8": "application_practice",
    "wadezone": "application_practice",
    "lijigang": "application_practice",
    "rwayne": "application_practice",
    "Thariq": "application_practice",
    "dontbesilent": "creator_growth",
    "longdechen12": "creator_growth",
    "ai_xiaomu": "creator_growth",
    "Dwarkesh Podcast": "longform_interview",
    "Latent Space": "longform_interview",
    "No Priors Podcast": "longform_interview",
    "Y Combinator YouTube": "longform_interview",
    "a16z YouTube": "longform_interview",
    "小君小宇宙 Podcast": "longform_interview",
    "Lex Fridman Podcast": "longform_interview",
    "Joe Rogan / PowerfulJRE": "longform_interview",
    "Why Not TV": "longform_interview",
    "慢学AI": "creator_growth",
    "我的 X 收藏": "user_saved",
    "数字生命卡兹克": "wechat_article",
    "AGI Hunt": "wechat_article",
    "卡尔的AI沃茨": "wechat_article",
    "海外独角兽": "wechat_article",
    "嘉妍Kea": "wechat_article",
    "峥嵘岁月AI": "wechat_article",
    "深思SenseAI": "wechat_article",
    "克劳德猎手": "wechat_article",
}

SOURCE_AUTHORITY = {
    "Anthropic News": 100,
    "Anthropic Engineering": 98,
    "Claude Blog": 96,
    "OpenAI Blog": 100,
    "OpenAI X": 92,
    "ChatGPT X": 90,
    "Anthropic X": 92,
    "Claude X": 91,
    "Claude Devs X": 95,
    "Claude YouTube": 96,
    "openai-codex-releases": 97,
    "claude-code-releases": 97,
    "Sam Altman": 86,
    "Greg Brockman": 84,
    "Kevin Weil": 84,
    "Mark Chen": 82,
    "Dario Amodei": 86,
    "Daniela Amodei": 84,
    "Mike Krieger": 84,
    "lijigang": 76,
    "ai_xiaomu": 72,
    "rwayne": 74,
    "Thariq": 74,
    "我的 X 收藏": 88,
}

# ---------------------------------------------------------------------------
# Official vendor channels (2026-09-21): the same coverage we built for
# Anthropic and OpenAI — blog / X / YouTube / GitHub releases — replicated for
# nine more model vendors. Every source name below is a row in sources.md.
# ---------------------------------------------------------------------------

COMPANY_ORDER = [
    "Anthropic / Claude",
    "OpenAI / ChatGPT / Codex",
    "Google / Gemini",
    "xAI / Grok",
    "Meta / Muse",
    "千问 / Qwen",
    "DeepSeek",
    "Kimi / 月之暗面",
    "智谱 / GLM",
    "MiniMax",
    "豆包 / 字节 Seed",
    "其他厂商",
]

# source name -> (company label, role, authority, short label)
OFFICIAL_SOURCES = {
    # Anthropic
    "Anthropic News": ("Anthropic / Claude", "company_official", 100, "Anthropic News"),
    "Anthropic Engineering": ("Anthropic / Claude", "company_official", 98, "Anthropic Engineering"),
    "Anthropic Institute": ("Anthropic / Claude", "company_official", 96, "Anthropic Institute"),
    "Claude Blog": ("Anthropic / Claude", "company_official", 96, "Claude Blog"),
    "Anthropic X": ("Anthropic / Claude", "company_official", 92, "Anthropic"),
    "Claude X": ("Anthropic / Claude", "company_official", 91, "Claude"),
    "Claude Devs X": ("Anthropic / Claude", "company_official", 95, "Claude Devs"),
    "Anthropic YouTube": ("Anthropic / Claude", "company_official", 90, "Anthropic YouTube"),
    "Claude YouTube": ("Anthropic / Claude", "company_official", 96, "Claude YouTube"),
    "claude-code-releases": ("Anthropic / Claude", "company_official", 97, "Claude Code Release"),
    "Dario Amodei": ("Anthropic / Claude", "company_person", 86, "Dario Amodei"),
    "Daniela Amodei": ("Anthropic / Claude", "company_person", 84, "Daniela Amodei"),
    "Mike Krieger": ("Anthropic / Claude", "company_person", 84, "Mike Krieger"),
    # OpenAI
    "OpenAI Blog": ("OpenAI / ChatGPT / Codex", "company_official", 100, "OpenAI Blog"),
    "OpenAI X": ("OpenAI / ChatGPT / Codex", "company_official", 92, "OpenAI"),
    "ChatGPT X": ("OpenAI / ChatGPT / Codex", "company_official", 90, "ChatGPT"),
    "OpenAI YouTube": ("OpenAI / ChatGPT / Codex", "company_official", 90, "OpenAI YouTube"),
    "ChatGPT YouTube": ("OpenAI / ChatGPT / Codex", "company_official", 88, "ChatGPT YouTube"),
    "openai-codex-releases": ("OpenAI / ChatGPT / Codex", "company_official", 97, "OpenAI Codex Release"),
    "OpenAI Devs X": ("OpenAI / ChatGPT / Codex", "company_official", 94, "OpenAI Devs"),
    "Sam Altman": ("OpenAI / ChatGPT / Codex", "company_person", 86, "Sam Altman"),
    "Greg Brockman": ("OpenAI / ChatGPT / Codex", "company_person", 84, "Greg Brockman"),
    "Kevin Weil": ("OpenAI / ChatGPT / Codex", "company_person", 84, "Kevin Weil"),
    "Mark Chen": ("OpenAI / ChatGPT / Codex", "company_person", 82, "Mark Chen"),
    # Google / Gemini
    "Gemini Blog": ("Google / Gemini", "company_official", 98, "Gemini Blog"),
    "Google DeepMind Blog": ("Google / Gemini", "company_official", 98, "Google DeepMind"),
    "Google Developers Blog": ("Google / Gemini", "company_official", 94, "Google Developers"),
    "Google AI Blog": ("Google / Gemini", "company_official", 92, "Google AI"),
    "Google DeepMind X": ("Google / Gemini", "company_official", 92, "Google DeepMind"),
    "Gemini App X": ("Google / Gemini", "company_official", 90, "Gemini"),
    "Google AI Devs X": ("Google / Gemini", "company_official", 93, "Google AI Devs"),
    "Google DeepMind YouTube": ("Google / Gemini", "company_official", 88, "Google DeepMind YouTube"),
    "Google for Developers YouTube": ("Google / Gemini", "company_official", 84, "Google for Developers"),
    "Demis Hassabis": ("Google / Gemini", "company_person", 86, "Demis Hassabis"),
    "Logan Kilpatrick": ("Google / Gemini", "company_person", 86, "Logan Kilpatrick"),
    # xAI / Grok
    "SpaceXAI X": ("xAI / Grok", "company_official", 92, "SpaceXAI"),
    "Grok X": ("xAI / Grok", "company_official", 90, "Grok"),
    "Grok YouTube": ("xAI / Grok", "company_official", 86, "Grok YouTube"),
    # Meta
    "AI at Meta X": ("Meta / Muse", "company_official", 92, "AI at Meta"),
    "Alexandr Wang": ("Meta / Muse", "company_person", 84, "Alexandr Wang"),
    # Qwen
    "Qwen X": ("千问 / Qwen", "company_official", 92, "Qwen"),
    "qwen-code-releases": ("千问 / Qwen", "company_official", 95, "Qwen Code Release"),
    "Qwen YouTube": ("千问 / Qwen", "company_official", 84, "Qwen YouTube"),
    "Junyang Lin": ("千问 / Qwen", "company_person", 86, "Junyang Lin"),
    "Binyuan Hui": ("千问 / Qwen", "company_person", 82, "Binyuan Hui"),
    # DeepSeek
    "DeepSeek X": ("DeepSeek", "company_official", 92, "DeepSeek"),
    # Kimi
    "Kimi X": ("Kimi / 月之暗面", "company_official", 92, "Kimi"),
    "kimi-cli-releases": ("Kimi / 月之暗面", "company_official", 95, "Kimi CLI Release"),
    "Kimi YouTube": ("Kimi / 月之暗面", "company_official", 86, "Kimi YouTube"),
    # Zhipu
    "Z.ai X": ("智谱 / GLM", "company_official", 92, "Z.ai"),
    # MiniMax
    "MiniMax X": ("MiniMax", "company_official", 92, "MiniMax"),
    "Hailuo X": ("MiniMax", "company_official", 86, "Hailuo"),
    "minimax-code-releases": ("MiniMax", "company_official", 95, "MiniMax Code Release"),
    # ByteDance
    "ByteDance OSS X": ("豆包 / 字节 Seed", "company_official", 84, "ByteDance OSS"),
}

OFFICIAL_COMPANY_BY_SOURCE = {name: row[0] for name, row in OFFICIAL_SOURCES.items()}
OFFICIAL_SOURCE_LABELS = {name: row[3] for name, row in OFFICIAL_SOURCES.items()}
CODE_RELEASE_SOURCES = {name for name in OFFICIAL_SOURCES if name.endswith("-releases")}
OFFICIAL_ITEM_CATEGORIES = {"ai-official", "ai-personal", "video-official"}

# Keyword fallback for items whose source name is not in the table (e.g. an X
# timeline post about a vendor). Checked in order; first hit wins.
COMPANY_KEYWORDS = [
    ("anthropic", "Anthropic / Claude"), ("claude", "Anthropic / Claude"),
    ("openai", "OpenAI / ChatGPT / Codex"), ("chatgpt", "OpenAI / ChatGPT / Codex"), ("codex", "OpenAI / ChatGPT / Codex"),
    ("deepmind", "Google / Gemini"), ("gemini", "Google / Gemini"), ("google", "Google / Gemini"),
    ("spacexai", "xAI / Grok"), ("xai", "xAI / Grok"), ("grok", "xAI / Grok"),
    ("meta", "Meta / Muse"), ("muse", "Meta / Muse"), ("llama", "Meta / Muse"),
    ("qwen", "千问 / Qwen"), ("千问", "千问 / Qwen"), ("通义", "千问 / Qwen"),
    ("deepseek", "DeepSeek"),
    ("kimi", "Kimi / 月之暗面"), ("moonshot", "Kimi / 月之暗面"), ("月之暗面", "Kimi / 月之暗面"),
    ("z.ai", "智谱 / GLM"), ("zhipu", "智谱 / GLM"), ("智谱", "智谱 / GLM"), ("glm", "智谱 / GLM"),
    ("minimax", "MiniMax"), ("hailuo", "MiniMax"), ("海螺", "MiniMax"),
    ("doubao", "豆包 / 字节 Seed"), ("豆包", "豆包 / 字节 Seed"), ("bytedance", "豆包 / 字节 Seed"), ("字节", "豆包 / 字节 Seed"), ("seedance", "豆包 / 字节 Seed"), ("seedream", "豆包 / 字节 Seed"),
]


def company_for_text(text: str) -> str:
    lower = (text or "").lower()
    for keyword, company in COMPANY_KEYWORDS:
        if keyword in lower:
            return company
    return "其他厂商"


def company_for_source(source: str, fallback_text: str = "") -> str:
    company = OFFICIAL_COMPANY_BY_SOURCE.get(source)
    if company:
        return company
    return company_for_text(f"{source} {fallback_text}")

for _name, (_company, _role, _authority, _label) in OFFICIAL_SOURCES.items():
    SOURCE_ROLES.setdefault(_name, _role)
    SOURCE_AUTHORITY.setdefault(_name, _authority)


BAD_LLM_MARKERS = (
    "I appreciate you sharing",
    "I'm Claude Code",
    "outside what I'm built for",
    "我是 Claude Code",
    "我是Claude Code",
    "我注意到你",
    "我注意到您",
    "我注意到这条",
    "我理解你的要求",
    "您的请求",
    "你的请求",
    "创意写作任务",
    "不在我的专业范围",
    "这不是给我的任务指令",
    "根据要求，我来改写",
    "我来改写这条信息",
    "根据你的要求",
    "根据这条信息",
    "为您准备以下摘要",
    "我需要指出",
    "不应该拒绝",
    "似乎是虚构",
    "信息似乎是虚构",
    "远在未来",
    "不会发布 Anthropic",
    "不会发布Anthropic",
    "如果你想让我",
    "如果这不是你需要",
    "如果需要我",
    "请明确指出",
    "相互矛盾",
    "我注意到这两条",
    "其实是独立的两个事件",
    "它们来自不同的官方发布",
    "没有信息重复或关联关系",
    "摘要如下",
    "中文字符",
    "专门用于帮助软件工程",
    "信息摘要和内容创作不在",
    "我不能处理",
    "不能帮助",
    "无法处理",
    "我需要看到 Twitter",
    "我需要看到Twitter",
    "我需要看到实际",
    "需要看到实际",
    "才能为其写标题",
    "才能写标题",
    "撰写标题",
    "请提供 Twitter/X",
    "请提供Twitter/X",
    "请提供完整的推文",
    "请提供完整的 Twitter",
    "请提供完整的Twitter",
    "字数统计",
    "符合你的要求",
    "Line 1",
    "Line 2",
    "Line 3",
    "产品线",
    "交易线",
    "内容线",
    "内容策划",
    "对我们",
    "我们的三条线",
    "对这个产品产品线",
    "应指",
    "应该指",
    "应该是指",
    "Anthropic 的 Codex",
    "Anthropic Codex",
    "Anthropic 发布的 Codex",
    "Anthropic 发布 Codex",
)


_ACTIVE_DOUYIN_CACHE: set[str] | None = None


def active_douyin_source_names() -> set[str]:
    """Names of every active Douyin source declared in sources.md.

    Douyin sources are curated video channels the owner wants by default; the
    media section must follow sources.md rather than a hand-maintained whitelist,
    so a newly-added channel (e.g. 柱子哥TzFilm) is never silently dropped. Lazy
    import keeps digest_config import-cycle-free (lib does not import this module);
    the result is cached because this is read on a per-item hot path.
    """
    global _ACTIVE_DOUYIN_CACHE
    if _ACTIVE_DOUYIN_CACHE is not None:
        return _ACTIVE_DOUYIN_CACHE
    names: set[str] = set()
    try:
        from lib import load_sources

        for src in load_sources():
            if src.get("platform") != "douyin":
                continue
            if src.get("active") not in (None, "true", True):
                continue
            name = (src.get("name") or "").strip()
            if name:
                names.add(name)
    except Exception:
        names = set()
    _ACTIVE_DOUYIN_CACHE = names
    return names


def source_names_for_group(group: str) -> set[str]:
    groups = {
        "twitter": {
            "dontbesilent",
            "op7418",
            "longdechen12",
            "vista8",
            "wadezone",
            "lijigang",
            "ai_xiaomu",
            "rwayne",
            "Thariq",
        },
        "code": set(CODE_RELEASE_SOURCES),
        "official": {
            name
            for name, row in OFFICIAL_SOURCES.items()
            if row[1] == "company_official" and name not in CODE_RELEASE_SOURCES and "YouTube" not in name
        },
        "people": {name for name, row in OFFICIAL_SOURCES.items() if row[1] == "company_person"},
        "podcast": {
            "OpenAI YouTube",
            "ChatGPT YouTube",
            "Anthropic YouTube",
            "Claude YouTube",
            "Grok YouTube",
            "Google DeepMind YouTube",
            "Google for Developers YouTube",
            "Kimi YouTube",
            "Qwen YouTube",
            "Dwarkesh Podcast",
            "Latent Space",
            "No Priors Podcast",
            "Y Combinator YouTube",
            "a16z YouTube",
            "小君小宇宙 Podcast",
            "Lex Fridman Podcast",
            "Joe Rogan / PowerfulJRE",
            "Why Not TV",
            "YouTube",
            "Podcast",
        },
        "douyin": {"慢学AI", "抖音"} | active_douyin_source_names(),
        "saved": {"我的 X 收藏"},
        "wechat": {
            "手动公众号文章",
            "数字生命卡兹克",
            "AGI Hunt",
            "卡尔的AI沃茨",
            "嘉妍Kea",
            "峥嵘岁月AI",
            "深思SenseAI",
            "克劳德猎手",
        },
    }
    return groups[group]


def media_source_names() -> set[str]:
    return source_names_for_group("podcast") | source_names_for_group("douyin")

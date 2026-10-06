# Park-IO Sources

This is the machine-readable source configuration for input-to-park.

> **This is Park's complete source list, shipped as-is (snapshot 2026-10-06).**
> A fresh clone reads this file. Park's own machine reads his live copy at
> `$PARKIO_HOME/_source management/sources.md` first, so this snapshot can lag it.
> Set `PARKIO_SOURCES=/path/to/your-sources.md` to use your own file instead.
>
> - Rows with `platform` = `rss` / `scrape` / `github` work out of the box.
> - `twitter`, `douyin`, YouTube-video rows and `wechat` need the logins listed in
>   the README's "前置条件" table; without them those rows are skipped and show
>   as DOWN on the status page. Set `active` to `false` to silence them.
> - `## User Context` below is **whose taste the AI judges by**. It is Park's.
>   Rewrite it to get a daily ranked for you instead.

## Tracking List

Sources fetched automatically every 4 hours. Edit this table to add / remove / disable sources. The pipeline parses the first table in this file directly.

- To **disable** a source without removing: set `active` to `false`.
- To **add** a source: append a new row at the bottom of the table.
- To **remove** permanently: delete the row.

| id | profile_id | name | platform | url | category | priority | frequency | active | added_date | notes |
|----|------------|------|----------|-----|----------|----------|-----------|--------|------------|-------|
| 001 | anthropic | Anthropic News | scrape | https://www.anthropic.com/news | ai | high | 4h | true | 2026-04-30 | RSS 已失效 - 改 HTML scrape |
| 002 | manxue-ai | 慢学AI | douyin | https://www.douyin.com/user/MS4wLjABAAAAX4enn5sxJQWvIqyONRmab7wNVacTbrmAXJXAfaR6ENM | ai | high | 4h | true | 2026-05-01 | 历史归档已迁入 references；4小时更新监控已接入 Douyin fetcher |
| 003 | dontbesilent | dontbesilent | twitter | https://x.com/dontbesilent | 自媒体 | high | 4h | true | 2026-05-01 |  |
| 004 | guizang | op7418 | twitter | https://x.com/op7418 | ai | high | 4h | true | 2026-05-01 | Humanizer-zh 作者 |
| 005 | anthropic | Anthropic Engineering | scrape | https://www.anthropic.com/engineering | ai | high | 4h | true | 2026-05-01 | 无 RSS - 需 HTML 抓取 |
| 006 | anthropic | Claude Blog | scrape | https://claude.com/blog | ai | high | 4h | true | 2026-05-01 | 无 RSS - 需 HTML 抓取 |
| 007 | openai | openai-codex-releases | rss | https://github.com/openai/codex/releases.atom | ai | high | 4h | true | 2026-05-01 | GitHub atom feed |
| 008 | anthropic | claude-code-releases | rss | https://github.com/anthropics/claude-code/releases.atom | ai | high | 4h | true | 2026-05-01 | GitHub atom feed |
| 009 | longdechen | longdechen12 | twitter | https://x.com/longdechen12 | 自媒体 | high | 4h | true | 2026-05-01 | 内容偏经营/培训类 - LLM 自动归类一致 |
| 010 | vista8 | vista8 | twitter | https://x.com/vista8 | ai | high | 4h | true | 2026-05-01 |  |
| 011 | wadezone | wadezone | twitter | https://x.com/wadezone | ai | high | 4h | true | 2026-05-01 |  |
| 012 | openai | OpenAI Blog | rss | https://openai.com/news/rss.xml | ai-official | high | 4h | true | 2026-05-14 | 官方 RSS，覆盖 OpenAI Blog / News |
| 013 | openai | OpenAI X | twitter | https://x.com/OpenAI | ai-official | high | 4h | true | 2026-05-14 | OpenAI 官方 X |
| 014 | openai | ChatGPT X | twitter | https://x.com/ChatGPT | ai-official | high | 4h | true | 2026-05-14 | ChatGPT 官方 X；2026-07-25 后账号从 @ChatGPTapp 改名 @ChatGPT，抓取断了两个月，2026-09-21 修正 |
| 015 | anthropic | Anthropic X | twitter | https://x.com/AnthropicAI | ai-official | high | 4h | true | 2026-05-14 | Anthropic 官方 X |
| 016 | anthropic | Claude X | twitter | https://x.com/claudeai | ai-official | high | 4h | true | 2026-05-14 | Claude 官方 X |
| 017 | anthropic | Claude Devs X | twitter | https://x.com/ClaudeDevs | ai-official | high | 4h | true | 2026-05-14 | Claude developer updates / changelog |
| 018 | openai | Sam Altman | twitter | https://x.com/sama | ai-personal | high | 4h | true | 2026-05-14 | OpenAI CEO，观察发布节奏与 access/limits 变化 |
| 019 | openai | Greg Brockman | twitter | https://x.com/gdb | ai-personal | high | 4h | true | 2026-05-14 | OpenAI cofounder，常转发 demo / launch |
| 020 | openai | Kevin Weil | twitter | https://x.com/kevinweil | ai-personal | high | 4h | true | 2026-05-14 | OpenAI product lead，观察 ChatGPT/Codex 产品动向 |
| 021 | openai | Mark Chen | twitter | https://x.com/markchen90 | ai-personal | high | 4h | true | 2026-05-14 | OpenAI research lead，观察模型/研究动向 |
| 022 | anthropic | Dario Amodei | twitter | https://x.com/DarioAmodei | ai-personal | high | 4h | true | 2026-05-14 | Anthropic CEO，观察公司方向 |
| 023 | anthropic | Daniela Amodei | twitter | https://x.com/DanielaAmodei | ai-personal | high | 4h | true | 2026-05-14 | Anthropic President，观察产品/组织方向 |
| 024 | anthropic | Mike Krieger | twitter | https://x.com/mikeyk | ai-personal | high | 4h | true | 2026-05-14 | Anthropic product / Labs，观察 Claude 产品方向 |
| 025 | openai | OpenAI YouTube | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCXZCJLdBC09xxGZ6gcdrc6A | video-official | high | 4h | true | 2026-05-14 | OpenAI 官方 YouTube |
| 026 | openai | ChatGPT YouTube | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCBLFIFNuazNgxGvlmD_I9TA | video-official | high | 4h | true | 2026-05-14 | ChatGPT 官方 YouTube |
| 027 | anthropic | Anthropic YouTube | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCrDwWp7EBBv4NwvScIpBDOA | video-official | high | 4h | true | 2026-05-14 | Anthropic 官方 YouTube |
| 050 | anthropic | Claude YouTube | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCV03SRZXJEz-hchIAogeJOg | video-official | high | 4h | true | 2026-05-27 | Claude 官方 YouTube @claude；RSS 可能 404，fetch-rss 使用 YouTube page fallback |
| 028 | dwarkesh | Dwarkesh Podcast | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCXl4i9dYBrFOabk0xGmbkRA | video-podcast | high | 4h | true | 2026-05-14 | AI / science long-form interviews |
| 029 | latent-space | Latent Space | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCxBcwypKK-W3GHd_RZ9FZrQ | video-podcast | high | 4h | true | 2026-05-14 | AI engineering podcast |
| 030 | no-priors | No Priors Podcast | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCSI7h9hydQ40K5MJHnCrQvw | video-podcast | high | 4h | true | 2026-05-14 | AI / startups / policy interviews |
| 031 | y-combinator | Y Combinator YouTube | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCcefcZRL2oaA_uBNeo5UOWg | video-podcast | medium | 4h | true | 2026-05-14 | startup / founder signal |
| 032 | a16z | a16z YouTube | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UC9cn0TuPq4dnbTY-CBsm8XA | video-podcast | medium | 4h | true | 2026-05-14 | AI / startup / industry interviews |
| 033 | zhang-xiaojun | 小君小宇宙 Podcast | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UC3Sv1JuKpbOx3csUO8FAo5g | video-podcast | medium | 4h | true | 2026-05-14 | 中文长访谈 / AI 与商业内容 |
| 034 | lex-fridman | Lex Fridman Podcast | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCSHZKyawb77ixDdsGog4iWA | video-podcast | medium | 4h | true | 2026-05-18 | Long-form science / AI / technology interviews |
| 035 | joe-rogan | Joe Rogan / PowerfulJRE | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCzQUP1qoWDoEbmsQxvdjxgQ | video-podcast | medium | 4h | true | 2026-05-18 | Long-form interviews; mostly link-only unless clearly relevant |
| 036 | shuzi-shengming-kazike | 数字生命卡兹克 | wechat | https://mp.weixin.qq.com/s/vTv0Vu4RgrMkmLbXGvnSug | wechat-ai | high | 4h | true | 2026-05-18 | seed article; user_name gh_94dba26f8ca0 |
| 037 | agi-hunt | AGI Hunt | wechat | https://mp.weixin.qq.com/s/pvtCp_Ari7QWJgnuWrtg8A | wechat-ai | high | 4h | true | 2026-05-18 | seed article; user_name gh_a93be09821ac; extra_seed https://mp.weixin.qq.com/s/mo5f0jodbWMgp1tWbTbpUw |
| 039 | karls-ai-watts | 卡尔的AI沃茨 | wechat | https://mp.weixin.qq.com/s/OAeFH-pSZNskAKEgg3TsPA | wechat-ai | high | 4h | true | 2026-05-18 | seed article; user_name gh_1421d5e48ca9 |
| 040 | lijigang | lijigang | twitter | https://x.com/lijigang | ai | high | 4h | true | 2026-05-19 | 李继刚；AI 写作/提示词/认知表达 |
| 041 | huang-xiaomu | ai_xiaomu | twitter | https://x.com/ai_xiaomu | 自媒体 | high | 4h | true | 2026-05-19 | 黄小木；AI 自媒体/OPC/个人商业化 |
| 042 | roland-w | rwayne | twitter | https://x.com/rwayne | ai | high | 4h | true | 2026-05-19 | Roland.W；企业 AI 转型/AI 医疗/商业应用 |
| 043 | why-not-tv | Why Not TV | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UC5xLV_gJAP9psKcyrJ3ZIcw | video-podcast | medium | 4h | true | 2026-05-19 | YouTube channel @whynottv1999；按已筛选视频源处理 |
| 044 | haiwai-dujiaoshou | 海外独角兽 | wechat | https://mp.weixin.qq.com/s/sA20Zc74FYWxKOu9Nu-T1Q | wechat-ai | high | 4h | false | 2026-05-20 | disabled by user; seed article; user_name gh_f5da058782fb |
| 045 | kea | 嘉妍Kea | wechat | https://mp.weixin.qq.com/s/xg-n6sZV7CZ-7FKDHF3V1A | wechat-ai | high | 4h | true | 2026-05-20 | seed article; user_name gh_cff68de0127a |
| 046 | zhengrong-suiyue-ai | 峥嵘岁月AI | wechat | https://mp.weixin.qq.com/s/MMqwW9IVSFueg8jpmLldwg | wechat-ai | high | 4h | true | 2026-05-20 | seed article; user_name gh_83268b02b5e0; extra_seed https://mp.weixin.qq.com/s/6M-QkF5NFhulPSfTdfIHdw |
| 047 | xiaotian-fotos | 小天fotos | douyin | https://www.douyin.com/user/MS4wLjABAAAALt54qyyG0n4QKc9diYjo6lwt2XVg3O2p837R12Gwd2k | ai | high | 4h | true | 2026-05-22 | AI agent / Claude Code / OpenClaw short videos; user-added Douyin source |
| 048 | dontbesilent | dontbesilent聊赚钱 | douyin | https://www.douyin.com/user/MS4wLjABAAAADfe0DjnkPQmNF3mVrRTQ2JyTFHnjYxl5FSZmjuf4O90 | content-business | high | 4h | true | 2026-05-22 | dontbesilent Douyin account; same profile as X source |
| 049 | myelc | MyElc | douyin | https://www.douyin.com/user/MS4wLjABAAAAeesGWnVSgGiyxDWrQtGwI9ucHfQy4RAleN5b7XQ-dKM | ai-video | high | 4h | true | 2026-05-22 | AI video prompting / AI visual creation; user-added Douyin source |
| 051 | zhuzi-tzfilm | 柱子哥TzFilm | douyin | https://www.douyin.com/user/MS4wLjABAAAAjN32ZoC90W_FXxpeck2ATV5PCQcnnHM2cSzm8SHdcGCEC3P_fxGweCSTutk3Mvqq | ai-business | high | 4h | true | 2026-05-29 | AI / API / creator business short videos; user-added Douyin source |
| 052 | shensi-senseai | 深思SenseAI | wechat | https://mp.weixin.qq.com/s/Y5Cmu15ISrO5mYt71gMn6w | wechat-ai | high | 4h | true | 2026-05-29 | seed article; user_name gh_a54fc6d3826c; author 深思圈 |
| 053 | claude-hunter | 克劳德猎手 | wechat | https://mp.weixin.qq.com/s/NwhmKiGW1vnV3rt3eOjk6A | wechat-ai | high | 4h | true | 2026-06-03 | seed article; user_name gh_c4e5d8c9bdc6; author 克劳德猎手; focus Claude / Anthropic product leaks |
| 054 | thariq | Thariq | twitter | https://x.com/trq212 | ai | high | 4h | true | 2026-06-04 | verified X account; AI/product signal |
| 055 | anthropic | Anthropic Institute | scrape | https://www.anthropic.com/institute | ai-official | high | 4h | true | 2026-06-05 | Anthropic Institute research / policy essays; covers /institute/* |
| 056 | alchainhust | AlchainHust | twitter | https://x.com/AlchainHust | ai | high | 4h | true | 2026-06-09 | user-added X source; source management thread |
| 057 | thsottiaux | thsottiaux | twitter | https://x.com/thsottiaux | ai | high | 4h | true | 2026-06-09 | user-added X source; source management thread |
| 058 | canghe | canghe | twitter | https://x.com/canghe | ai | high | 4h | true | 2026-06-11 | user-added X source; source management thread |
| 059 | oran-ge | oran_ge | twitter | https://x.com/oran_ge | ai | high | 4h | true | 2026-06-11 | user-added X source; source management thread |
| 060 | bcherny | bcherny | twitter | https://x.com/bcherny | ai | high | 4h | true | 2026-06-13 | user-added X source; source management thread |
| 061 | nate-herk | Nate Herk - AI Automation | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UC2ojq-nuP8ceeHqiroeKhBA | video-podcast | medium | 4h | true | 2026-06-24 | user-added YouTube source @nateherk; AI automation / workflow tutorials |
| 062 | github-trending | GitHub Trending | github | https://github.com/trending?since=daily | ai | high | daily | true | 2026-09-18 | 日榜；仓库首次上榜（或 7 天后回榜）写一条；同时喂产品雷达（#20） |
| 063 | xai | SpaceXAI X | twitter | https://x.com/SpaceXAI | ai-official | high | 4h | true | 2026-09-21 | xAI 并入 SpaceX 后的公司主号（206 万粉）；旧号 @xai 已迁移 |
| 064 | xai | Grok X | twitter | https://x.com/grok | ai-official | high | 4h | true | 2026-09-21 | Grok 产品号（909 万粉） |
| 065 | xai | Grok YouTube | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCxgo0OMZU9SiaYpJsuZKWkQ | video-official | high | 4h | true | 2026-09-21 | Grok 官方 YouTube @grok；多为 Imagine 演示 |
| 066 | google | Gemini Blog | rss | https://blog.google/products/gemini/rss/ | ai-official | high | 4h | true | 2026-09-21 | Gemini 产品博客官方 RSS |
| 067 | google | Google DeepMind Blog | rss | https://deepmind.google/blog/rss.xml | ai-official | high | 4h | true | 2026-09-21 | DeepMind 模型与研究发布 |
| 068 | google | Google Developers Blog | rss | https://developers.googleblog.com/feeds/posts/default | ai-official | high | 4h | true | 2026-09-21 | Gemini API / Agent Platform 开发者向更新 |
| 069 | google | Google AI Blog | rss | https://blog.google/technology/ai/rss/ | ai-official | high | 4h | true | 2026-09-21 | Google AI 总览博客，与 Gemini/DeepMind 有重叠 |
| 070 | google | Google DeepMind X | twitter | https://x.com/GoogleDeepMind | ai-official | high | 4h | true | 2026-09-21 | 153 万粉 |
| 071 | google | Gemini App X | twitter | https://x.com/GeminiApp | ai-official | high | 4h | true | 2026-09-21 | Gemini 用户向产品号（58 万粉） |
| 072 | google | Google AI Devs X | twitter | https://x.com/googleaidevs | ai-official | high | 4h | true | 2026-09-21 | 开发者向（12 万粉） |
| 073 | google | Demis Hassabis | twitter | https://x.com/demishassabis | ai-personal | high | 4h | true | 2026-09-21 | DeepMind CEO，观察模型与研究方向 |
| 074 | google | Logan Kilpatrick | twitter | https://x.com/OfficialLoganK | ai-personal | high | 4h | true | 2026-09-21 | Gemini API / AI Studio 负责人，开发者视角最直接 |
| 075 | google | Google DeepMind YouTube | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCP7jMXSY2xbc3KCAE0MHQ-A | video-official | high | 4h | true | 2026-09-21 | @GoogleDeepMind |
| 076 | google | Google for Developers YouTube | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw | video-official | high | 4h | true | 2026-09-21 | @GoogleDevelopers；频道很宽，Android/Cloud 也在 |
| 077 | meta | AI at Meta X | twitter | https://x.com/AIatMeta | ai-official | high | 4h | true | 2026-09-21 | Meta AI / Muse 主渠道（85 万粉）；官方博客纯 JS 暂不抓 |
| 078 | meta | Alexandr Wang | twitter | https://x.com/alexandr_wang | ai-personal | high | 4h | true | 2026-09-21 | Meta Superintelligence Labs 负责人 |
| 079 | zhipu | Z.ai X | twitter | https://x.com/Zai_org | ai-official | high | 4h | true | 2026-09-21 | 智谱海外主号（16 万粉） |
| 080 | moonshot | Kimi X | twitter | https://x.com/Kimi_Moonshot | ai-official | high | 4h | true | 2026-09-21 | 36 万粉 |
| 081 | moonshot | kimi-cli-releases | rss | https://github.com/MoonshotAI/kimi-cli/releases.atom | ai | high | 4h | true | 2026-09-21 | GitHub atom feed |
| 082 | moonshot | Kimi YouTube | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UC7JnPttpEOzDE_pxQRX_20Q | video-official | high | 4h | true | 2026-09-21 | @KimiMoonshot；产品更新为主 |
| 083 | deepseek | DeepSeek X | twitter | https://x.com/deepseek_ai | ai-official | high | 4h | true | 2026-09-21 | 113 万粉，唯一稳定的官方渠道 |
| 084 | minimax | MiniMax X | twitter | https://x.com/MiniMax_AI | ai-official | high | 4h | true | 2026-09-21 | 单下划线；12 万粉 |
| 085 | minimax | Hailuo X | twitter | https://x.com/Hailuo_AI | ai-official | high | 4h | true | 2026-09-21 | 视频产品号（8 万粉） |
| 086 | minimax | minimax-code-releases | rss | https://github.com/MiniMax-AI/MiniMax-Code/releases.atom | ai | high | 4h | true | 2026-09-21 | GitHub atom feed |
| 087 | bytedance | ByteDance OSS X | twitter | https://x.com/ByteDanceOSS | ai-official | high | 4h | true | 2026-09-21 | 字节开源账号（4.7 千粉）；豆包/Seed 在 X 上没有可信官方号 |
| 088 | qwen | Qwen X | twitter | https://x.com/Alibaba_Qwen | ai-official | high | 4h | true | 2026-09-21 | 29 万粉 |
| 089 | qwen | Junyang Lin | twitter | https://x.com/JustinLin610 | ai-personal | high | 4h | true | 2026-09-21 | Qwen 技术负责人，发布前常有预告 |
| 090 | qwen | Binyuan Hui | twitter | https://x.com/huybery | ai-personal | high | 4h | true | 2026-09-21 | Qwen Code 方向 |
| 091 | qwen | qwen-code-releases | rss | https://github.com/QwenLM/qwen-code/releases.atom | ai | high | 4h | true | 2026-09-21 | GitHub atom feed |
| 092 | qwen | Qwen YouTube | rss | https://www.youtube.com/feeds/videos.xml?channel_id=UCWeqUXS57KQhmup0wlymlIQ | video-official | high | 4h | true | 2026-09-21 | @QwenLM |
| 093 | openai | OpenAI Devs X | twitter | https://x.com/OpenAIDevs | ai-official | high | 4h | true | 2026-09-21 | OpenAI 开发者官方号（43 万粉）：Codex 与 OpenAI Platform 更新；查 @ChatGPTapp 改名时发现漏配 |

## Product Radar Sources

These sources feed the independent `产品雷达` reader product. They are not part of the first machine-parsed fetch table, so they do not get mixed into the existing `快讯` / `深读` pipeline. The owner script is `build-product-radar.py`.

| id | name | url | acquisition | cadence | status | added_date | notes |
|----|------|-----|-------------|---------|--------|------------|-------|
| product-radar-001 | Product Hunt | https://www.producthunt.com/ | official Atom feed: https://www.producthunt.com/feed | daily | active | 2026-06-18 | 新产品供给；用于发现今天上线/被讨论的新产品 |
| product-radar-002 | Hacker News | https://news.ycombinator.com/ | official Firebase API: https://github.com/HackerNews/API | daily | active | 2026-06-18 | 需求、痛点、争议与 builder 讨论；重点看 top/show/ask/new stories |
| product-radar-003 | TrustMRR | https://trustmrr.com/ | public scrape; optional API needs `tmrr_` key | daily | active | 2026-06-18 | 真实收入信号；先用公开页面抓取，拿到 API key 后升级 |

## User Context

This is the baseline context for `input-to-park`. Scoring and summaries should judge information by whether it helps these lines move forward, not by generic AI-news importance.

### Line 1: Development / Product / Agent tooling

What we are doing:
- Building local, file-first agent workflows and productized tooling around Codex, Claude Code, repo evaluation, and personal information operations.
- Turning raw workflows into inspectable products: HTML dashboards, daily intelligence panels, reusable scripts, and automation surfaces.

Current stage:
- Active productization. The useful signal is concrete capability change, workflow design, implementation detail, reliability improvement, or a source that changes how we should build.

What to prioritize:
- Codex, Claude Code, agent orchestration, local automation, developer UX, release notes with actual workflow impact, reliable CLI/API behavior, examples of agent products people are shipping.

### Line 2: Trading / Market intelligence

What we are doing:
- Building a semi-automated Trading OS for cross-asset idea generation, planning, review, and journal workflows.
- Execution remains manual by default; the product should improve insight generation, preparation, and risk discipline.

Current stage:
- Semi-automated intelligence and planning layer. The useful signal is market regime insight, tooling that improves research/review speed, and examples of decision-support systems.

What to prioritize:
- Macro liquidity, A-share themes, crypto/BTC, US tech, gold, risk management, market structure, repeatable research workflows, and tools that make daily review more insight-first.

### Line 3: Content / Media / Education

What we are doing:
- Turning current AI/product/trading practice into consumable content for past-self audiences, courses, and media channels.
- Building source material for short video, long-form explanation, knowledge products, and audience operations.

Current stage:
- Packaging and distribution. The useful signal is content angle, narrative frame, creator workflow, audience insight, educational structure, and specific examples worth adapting.

What to prioritize:
- AI content strategy, short video/Douyin/Xiaohongshu, YouTube/podcast interviews, course packaging, practical creator operations, and ideas that explain "what this means for builders/operators".

### Scoring Principle

An item is valuable when it clearly advances at least one line:
- `development`: helps us build or operate better products/workflows.
- `trading`: helps us produce stronger market insight or better trading preparation.
- `content`: helps us create clearer, more useful content or education.

Generic AI excitement is not enough. A good item should answer: "What can we do differently after reading this?"

## Source Personas

Use this section to interpret sources before scoring. A source is not valuable because it is famous; it is valuable when its usual role maps to our three lines.

### AI Official Channels

#### OpenAI Blog / OpenAI X / OpenAI YouTube

Persona:
- Company-level product, research, policy, and launch signal.

Usefulness:
- Best for confirmed releases, capability shifts, pricing/access changes, official demos, developer/product direction, and timing of rollout.

Watch for:
- Codex, ChatGPT, API, agent features, model launches, rate-limit/access changes, developer workflow demos, and Windows/macOS/local tooling details.

#### ChatGPT Blog / ChatGPT X / ChatGPT YouTube

Persona:
- User-facing product and distribution signal.

Usefulness:
- Best for understanding what mainstream users will see and what content angles are likely to matter.

Watch for:
- New ChatGPT features, workspace/productivity flows, voice/video/screen usage, education/team workflows, and user-facing launch language.

#### Anthropic News / Anthropic Engineering / Anthropic Institute / Claude Blog / Anthropic X / Claude X / Claude Devs / Anthropic YouTube / Claude YouTube

Persona:
- Claude product, model, safety, developer, and engineering signal.

Usefulness:
- Best for Claude Code, agent workflows, API/tooling changes, applied safety, and enterprise/product adoption.

Watch for:
- Claude Code release notes, MCP/tool-use patterns, API changelogs, Claude app/workspace changes, enterprise workflow announcements, and official technical talks.

#### xAI / Grok — SpaceXAI X / Grok X / Grok YouTube

Persona:
- Grok model, Grok Build (coding agent) and Grok Bot (always-on agents) launch signal; the company posts to x.ai/news first and X within the hour.

Watch for:
- Model versions, Grok Build / Bot rollouts, platform integrations (Copilot, Bedrock, Foundry), pricing/plan changes.

#### Google / Gemini — Gemini Blog / DeepMind Blog / Developers Blog / DeepMind X / Gemini App X / Google AI Devs X / YouTube

Persona:
- Gemini model and app, Gemini API / AI Studio, DeepMind research. The most complete RSS coverage of any vendor.

Watch for:
- Gemini model releases, API changelog-grade changes, Gemini CLI / Agent Platform, DeepMind research with product implications.

#### Meta / Muse — AI at Meta X

Persona:
- Muse model line (Muse Spark, Muse Image / Video) and open-source releases. Low cadence; X is the only channel we can read without a browser.

#### 千问 / Qwen — Qwen X / Qwen Code releases / Qwen YouTube

Persona:
- Highest release cadence of the domestic vendors (several posts a month). Official blog is JS-only; X and GitHub carry the same announcements.

#### DeepSeek — DeepSeek X

Persona:
- Terse, infrequent, high-signal. Almost every DeepSeek announcement lands on X first.

#### Kimi / 月之暗面 — Kimi X / kimi-cli releases / Kimi YouTube

Persona:
- Kimi model and Kimi Work / Kimi CLI product updates.

#### 智谱 / GLM — Z.ai X

Persona:
- GLM model releases and Z.ai coding plan; docs.z.ai carries dated release notes if a scraper is added later.

#### MiniMax — MiniMax X / Hailuo X / MiniMax Code releases

Persona:
- M-series models, MiniMax Code, Hailuo video. Corporate site is IR press releases; skip.

#### 豆包 / 字节 Seed — ByteDance OSS X

Persona:
- Weakest coverage: no trusted official X account for Doubao or Seed; ByteDance OSS covers open-source releases only. Primary channels are WeChat and Volcengine docs, both out of scope.

### AI Company Personal Accounts

#### OpenAI people

Core accounts to monitor:
- Sam Altman (`@sama`): company direction, launches, access/limits, strategic framing.
- Greg Brockman (`@gdb`): demos, technical launches, product/research amplification.
- Kevin Weil (`@kevinweil`): product direction and user-facing changes.
- Mark Chen (`@markchen90`): research/model direction.

Usefulness:
- These accounts often surface rollout details, access changes, demos, and product emphasis before or around official blog posts.

#### Anthropic people

Core accounts to monitor:
- Dario Amodei (`@DarioAmodei`): company direction, policy, major model/safety framing.
- Daniela Amodei (`@DanielaAmodei`): company/product and operating context.
- Mike Krieger (`@mikeyk`): product direction, Claude app, labs/product announcements.

Usefulness:
- These accounts can explain why Anthropic is moving in a direction, but should not outrank official Claude developer/product channels unless they contain concrete updates.

#### Other vendor people

Core accounts to monitor:
- Demis Hassabis (`@demishassabis`): DeepMind direction, model/research framing.
- Logan Kilpatrick (`@OfficialLoganK`): Gemini API / AI Studio; the most developer-facing Google account.
- Alexandr Wang (`@alexandr_wang`): Meta Superintelligence Labs.
- Junyang Lin (`@JustinLin610`), Binyuan Hui (`@huybery`): Qwen release previews and Qwen Code.

### Independent / Creator Sources

#### 硅基流动 and similar AI content sources

Persona:
- AI content interpreter and distributor.

Usefulness:
- Useful when it turns official/company news into clearer mental models, content angles, or practical workflows for our audience.

Position in our bigger picture:
- Not primary truth source. It belongs in the `content` line as packaging/reference material, and in the `development` line only when it contains concrete workflow or implementation insight.

#### Current Twitter creator sources

Usefulness:
- Keep when they provide practical AI workflow observations, content hooks, product demos, or operator-level interpretation.
- Filter when they are only generic excitement, vague commentary, or ungrounded prediction.

### Ranking Rule

For the same topic:
1. Official release/channel confirms what happened.
2. Key employee/personal account explains rollout details or intent.
3. Independent creator/source helps us package, interpret, or apply it.

The daily panel should combine these into one useful judgment instead of showing duplicate fragments.

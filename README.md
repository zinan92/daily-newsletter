<div align="center">

# Daily Newsletter

**把分散在官方渠道、X、播客和公众号里的 AI 信息，每天自动凝练成一份中文摘要，定时推送到 Telegram。**

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-6%20suites-green.svg)](tests/)
[![Pipeline](https://img.shields.io/badge/pipeline-deterministic-0f766e.svg)](inbox-workflow.yaml)
[![License](https://img.shields.io/badge/license-private-lightgrey.svg)](#license)

</div>

---

```
in   官方渠道 (Anthropic/OpenAI/Claude/Codex) + X 关注账号 + 播客/YouTube/抖音 + 手动链接/公众号
out  一份中文日报 (Markdown + HTML + 长图) → Telegram，每天 08:30

fail LLM 端点 502        → 重试 3 次；仍失败则官方/手动/媒体照常出，普通 feed 缺失但状态页可见
fail 评分服务中断        → 写 scoring-health.json + 状态页红色横幅（不静默）
fail 正文含英文/元数据   → 质量门拦截推送，绝不发出英文堆砌或 "公众号:/作者:" 泄漏
fail 某来源抓取失败      → 跳过并在状态页标记，不影响其他来源
```

路由是确定性的（source → profile → section）。AI 只在**节点内部**工作：打分、写摘要、质检。

## 示例输出

一份日报固定四个 section，每条都是内容衍生的中文标题 + 摘要 + 原文链接：

```markdown
# Park-IO Daily Summary — 2026-05-30

## 今日精选

### AI 官方与代码源
#### Anthropic / Claude
1. [Claude Code Release：v2.1.157](https://github.com/anthropics/claude-code/releases/...)
   Claude Code v2.1.157 简化了插件系统：插件可直接放进 .claude/skills 自动加载，
   新增 claude plugin init 命令快速生成骨架……
   **对你的价值：**
   - 插件直接放目录自动加载，不用再折腾 marketplace，本地调试更快
2. [Claude Devs：Opus 4.8 支持对话中途添加系统指令且不破坏提示缓存](https://x.com/ClaudeDevs/...)

### Twitter / X 应用层
### Podcast / YouTube / 抖音
### 我的收藏 / Manual Links
```

> 终端运行时每个阶段都会打印进度，例如：
> ```
> [score] DONE — total scored: 2412
> [summarize] DONE — wrote .../000-26-05-30.md and .../000-26-05-30.html
> [quality-check] PASS 2026-05-30: 13 events, 10 push URLs
> ```

## 架构：四条独立路径

每条路径从抓取入口一路走到自己的 newsletter section，互不污染。路由确定，AI 只在节点内。

```
                  ┌──────────────── 官方/代码源 ──────────────┐
  Anthropic/      │ fetch → score(AI) → brief(AI) → cluster   │──▶ Section 1  AI 官方与代码源
  OpenAI/Claude   └───────────────────────────────────────────┘
                  ┌──────────────── X 关注账号 ───────────────┐
  黄小木/归藏/...  │ fetch → score(AI) → brief(AI) → thread合并 │──▶ Section 2  Twitter / X 应用层
                  └───────────────────────────────────────────┘
                  ┌──────────────── 音视频 ───────────────────┐
  Podcast/YT/抖音  │ fetch → MLX Whisper转录 → 修ASR(AI) → brief│──▶ Section 3  Podcast/YouTube/抖音
                  └───────────────────────────────────────────┘
                  ┌──────────────── 收藏/手动 ────────────────┐
  manual-links/   │ fetch → bypass score → brief(AI)          │──▶ Section 4  我的收藏/Manual Links
  X收藏/公众号     └───────────────────────────────────────────┘
                                                                      │
              四个 section 汇聚 ──▶ 质量门(确定性 + AI二审) ──▶ Telegram 08:30
```

节点类型：`script`（确定性）· `ai`（带 system prompt）· `local_model`（MLX Whisper，本地）· `human`（手动输入）· `sink`（section）。
图的唯一真源是 [`inbox-workflow.yaml`](inbox-workflow.yaml)（v12），由 `render-workflow-diagram.py` 渲染成 HTML/PNG，渲染前自动跑 `validate-workflow.py` 校验闭合性。

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/zinan92/daily-newsletter
cd daily-newsletter

# 2. 配置 LLM（默认 DeepSeek）— key 存到本地 secret 文件，不进 env 历史
mkdir -p ~/park-io/secrets
printf "YOUR_DEEPSEEK_KEY" > ~/park-io/secrets/deepseek-key && chmod 600 ~/park-io/secrets/deepseek-key
# 或者临时用 env：export PARKIO_DEEPSEEK_KEY="..."

# 3. 跑测试，确认环境
for t in tests/test_*.py; do python3 "$t"; done

# 4. 手动跑一遍当天 pipeline
./fetch-all.sh                                    # 抓取（cron 每 4h）
BATCH=$(python3 open-batch.py | tail -1)
PARKIO_BATCH_ID=$BATCH python3 score.py           # 打分
PARKIO_BATCH_ID=$BATCH python3 build-digest.py    # 生成 md/html/png
PARKIO_BATCH_ID=$BATCH python3 check-quality.py   # 质量门
PARKIO_BATCH_ID=$BATCH python3 archive-items.py
PARKIO_BATCH_ID=$BATCH PARKIO_FORCE_PUSH=1 python3 send-artifacts.py
```

日常由 launchd 驱动：`fetch-all.sh` 每 4 小时抓取，`push-digest.sh` 每天 08:30 构建并推送。

## Pipeline 阶段

| 阶段 | 脚本 | Handler | 说明 |
|------|------|---------|------|
| 抓取 | `fetch.py` / `fetch-*.py` | script | RSS/scrape/X/微信/抖音；写入 `inbox/unprocessed` |
| 转录 | `fetch-media-transcripts.py` | local_model + ai | MLX Whisper 本地转录 → AI 修 ASR 错字 + 中文摘要 |
| 开批 | `open-batch.py` | script | 把 pending 移入 `processed/<YY-MM-DD>` |
| 打分 | `score.py` → `score-items.py` | ai | Sonnet 评分；官方/手动/媒体 bypass；失败写 `scoring-health.json` |
| 摘要 | `build-digest.py` → `summarize.py` | ai | 内容衍生中文标题 + 摘要 + 四 section 组装 + 长图 |
| 质检 | `check-quality.py` → `quality-check.py` | script + ai | 确定性红线门（硬拦）+ AI 二审（非阻塞） |
| 归档 | `archive-items.py` | script | 写 `library/profiles/<id>/items/`，长期留存 |
| 推送 | `send-artifacts.py` → `push-telegram.py` | script | Telegram；`sent/` 只留 `YY-MM-DD.md` |
| 状态 | `generate-status.py` | script | 维护者状态页 `status.html`（抓取/评分/健康） |

## 回归不变量（GOTCHAS）

这个项目的核心是一套硬规则——哪些内容必须出、哪些绝不能进正文。全部记录在 [`GOTCHAS.md`](GOTCHAS.md)，并由 `tests/`（6 个套件）+ 确定性质量门锁死。改 `summarize.py` / `digest_events.py` / `quality-check.py` / `fetch-*.py` 前先对照。重点：

- **官方/手动/媒体 bypass 评分**——评分服务挂了，官方区也不能消失。
- **正文必须是中文摘要**——英文原文、`公众号:/作者:`、`t.co`、内部元数据一律被门拦截。
- **标题来自当前内容**——不复用跨天的硬编码模板标题。
- **同 thread 合并、空内容剔除**——X thread 回复合并成一个事件；纯链接的空推不进正文。
- **去重只看当天 batch**——`state.json` 只管抓取去重，不决定今天展示什么。

## 配置

LLM 默认走 **DeepSeek**（OpenAI 兼容 API）。Key 从 env 或 `~/park-io/secrets/deepseek-key` 读取，**不进代码、不进 git**。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PARKIO_LLM_PROVIDER` | LLM 提供方：`deepseek` 或 `anthropic` | `deepseek` |
| `PARKIO_DEEPSEEK_KEY` | DeepSeek API key（或写入 `~/park-io/secrets/deepseek-key`） | 无（必填） |
| `PARKIO_DEEPSEEK_MODEL` | DeepSeek 模型 | `deepseek-chat` |
| `PARKIO_DEEPSEEK_ENDPOINT` | DeepSeek 端点 | `https://api.deepseek.com/v1/chat/completions` |
| `PARKIO_CLIPROXY_KEY` | （仅 anthropic 模式）本地代理密钥；或 `~/park-io/secrets/cliproxy-key` | 无 |
| `PARKIO_CLIPROXY_MODEL` | （仅 anthropic 模式）模型 | `claude-sonnet-4-5-20250929` |
| `PARKIO_BATCH_ID` | 指定批次（手动跑某天） | 当天 |
| `PARKIO_STRICT_AI_QUALITY` | 让 AI 质检变成硬门 | 未设（非阻塞） |
| `PARKIO_PYTHON` | fetch 阶段的 Python 3.11+ 解释器 | 自动探测 |

`sources.md`（在 `~/park-io/`）是来源清单、用户画像、评分标定的单一真源。

## 项目结构

```
daily-newsletter/
├── fetch*.py / fetch-all.sh   # 抓取层（RSS/X/微信/抖音/手动）
├── score-items.py             # AI 打分（官方/手动/媒体 bypass）
├── summarize.py               # 摘要 + 标题 + 四 section 组装（核心）
├── digest_events.py           # 事件聚类 + thread 合并
├── digest_text.py             # 文本清洗（strip_source_meta 等）
├── quality-check.py           # 确定性质量门
├── ai-quality-check.py        # AI 二审
├── push-telegram.py           # Telegram 投递
├── generate-status.py         # 维护者状态页
├── lib.py                     # 共享：路径、解析、llm_call(带重试)
├── inbox-workflow.yaml        # 工作流图真源 (v12 四路径)
├── GOTCHAS.md                 # 回归不变量清单
├── tests/                     # 6 个回归测试套件
└── AGENTS.md                  # 给 AI agent 的编辑规则
```

数据目录在 `~/park-io/`：`inbox/`（unprocessed/processed/sent）、`library/profiles/<id>/items/`（长期归档）、`status.html`（维护者面板）。

## For AI Agents

这是一个 **CLI / cron 流水线**，不暴露 HTTP API。集成或修改前，请读 `AGENTS.md` 和 `GOTCHAS.md`。

```yaml
name: daily-newsletter
capability:
  summary: Aggregate AI news from official channels, X, podcasts, and manual links
           into a daily Chinese digest pushed to Telegram.
  in:  source configs (sources.md) + manual-links.md
  out: inbox/sent/YY-MM-DD.md  +  Telegram message (text + HTML + long image)
  fail:
    - "LLM 502 → retry 3x; official/manual/media still ship, outage surfaced in status"
    - "raw English or meta in body → quality-check.py blocks the push"
  handlers: [script (deterministic routing), ai (scoring/summary/QC), local_model (MLX Whisper)]
entrypoints:
  fetch:   ./fetch-all.sh                 # every 4h
  digest:  ./push-digest.sh               # daily 08:30 (open-batch→score→build→quality→archive→send)
verify:    for t in tests/test_*.py; do python3 "$t"; done
invariants: GOTCHAS.md            # 24 regression rules, status-tagged
contract:   inbox-workflow.yaml   # v12, four independent paths; validated by validate-workflow.py
```

修改的安全流程：先跑 `tests/`，改完再跑一次；任何 reader-facing 改动都要让 `quality-check.py` 通过；编辑工作流图前跑 `validate-workflow.py`。

## License

Private. Personal project.

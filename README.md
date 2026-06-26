<div align="center">

# Daily Newsletter

**把分散在官方渠道、X、播客和公众号里的 AI 信息，每天自动凝练成一份中文摘要，保存成本地 Markdown / HTML / 长图。**

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-all%20suites-green.svg)](tests/)
[![Pipeline](https://img.shields.io/badge/pipeline-5--stage%20AI--first-0f766e.svg)](workflow/daily-newsletter.workflow.yaml)
[![License](https://img.shields.io/badge/license-private-lightgrey.svg)](#license)

</div>

---

```
in   官方渠道 (Anthropic/OpenAI/Claude/Codex) + X 关注账号 + 播客/YouTube/抖音 + 手动链接/公众号
out  一份中文日报 (Markdown + HTML + 长图) → `inbox/processed/<YY-MM-DD>/`，每天 08:30

fail LLM 端点 502/SSL    → DeepSeek 重试 3 次；仍失败则自动转 CLIProxy/Sonnet；配置错误不兜底
fail AI 结构化输出失败   → 写 processed/<YY-MM-DD>/ai/error.json + raw-response.md，直接停止，不 fallback
fail 最终 Markdown 缺栏目 → build-digest 失败，不生成假成功产物
fail 某来源抓取失败      → 跳过并在状态页标记，不影响其他来源
```

生产链路现在是 5-stage：`fetch -> to_md -> coarse_filter -> ai_process -> archive`。脚本只负责下载、转写、粗筛、保存和推送；内容判断、合并、打分、分类、快讯全集/深读子集选择全部交给 AI system prompt。

## 示例输出

Daily Newsletter 是 umbrella，每天固定组织三个读者产品：

- `000-YY-MM-DD.md/html/png` 是默认**快讯**产品，回答“今天有哪些新信号值得知道”。
- `deep-YY-MM-DD.md/html/png` 是可选**深读**产品，只在当天有 `deep_candidates` 时生成，回答“哪些内容值得花 10-30 分钟理解”。
- `product-radar-YY-MM-DD.md/html/png` 是独立**产品雷达**产品，读取 Product Hunt / Hacker News / TrustMRR，只回答“今天最值得 build 的产品方向是什么，以及证据是什么”；最多给 5 个，少于 5 个时不硬凑。
- `daily-YY-MM-DD.md/html/png` 是 umbrella index，只链接三份产品并记录健康/降级状态，不重新改写正文。

深读必须是快讯全集的子集，并通过 `parent_brief_event_id` 可追踪。`Source Health` 留在状态页和 run-report，不进入读者正文。
产品雷达不进入快讯/深读的 AI selection universe；它是同一个 daily routine 里的第三个产品，避免产品机会源污染资讯判断。

```markdown
# Daily Inbox 快讯 — 2026-06-10

## 快讯
### 底层工具
- **Claude Code Release** | [Claude Code Release：v2.1.170](https://github.com/...)
  版本更新说明，适合快速知道工具变化。

### 工作流
- **X / 向阳乔木** | [一句话操作浏览器](https://x.com/...)
  浏览器 Agent 正在进入真实内容/运营工作流。

### 内容
- **X / Yenita_Su** | [小红书创作窗口解析](https://x.com/...)
  平台扶持方向变化，适合做机会扫描。
```

```markdown
# Daily Inbox 深读 — 2026-06-10
## 深读
### 1. [Claude Fable 5 and Claude Mythos 5](https://www.anthropic.com/news/...)

来源：Anthropic News

**核心论点：**
模型能力正在按开放层级、安全边界和使用权限重新分层。

**为什么值得读：**
它提供了一个观察 AI 平台竞争的新角度。

**它改变了什么判断：**
选择 AI 工具时，不能只看 benchmark，还要看开放稳定性、权限和成本结构。

**可迁移启发：**
可迁移到 AI 产品分层、企业自动化架构和开发者工具设计。

```

> 终端运行时每个阶段都会打印进度，例如：
> ```
> [ai-process] item_understanding START — 148 items
> [ai-process] selection START — 41 events
> [summarize] DONE — wrote .../000-26-05-30.md and .../000-26-05-30.html
> ```

## 架构：5-stage AI-first

抓取入口仍按来源拆分，但生产边界按 stage folder 固化。最终正文只输出 `短讯` 和 `深读`。

```
fetch → raw/<YYYY-MM-DD>
      → to_md → unprocessed/<YYYY-MM-DD>/items/*.md
      → coarse_filter → processed/<YY-MM-DD>/items/*.md + coarse-rejects.jsonl
      → ai_process → ai/01-item-cards.json → ai/02-events.json → ai/03-selection.json
                   → 000-YY-MM-DD.md/html/png + optional deep-YY-MM-DD.md/html/png
      → archive → library selected items + sent artifacts
```

实现入口固定在 `stages/`，根目录脚本只是兼容 wrapper：

```text
stages/fetch/run.py
stages/to_md/run.py
stages/coarse_filter/run.py
stages/ai_process/run.py
stages/archive/run.py
```

节点类型：`script`（抓取/转写/粗筛/保存/推送）· `ai`（理解/合并/选择/写作）· `local_model`（MLX Whisper，本地转录）· `human`（手动输入）· `sink`（artifact）。
当前 repo 内 workflow 合同是 `workflow/daily-newsletter.workflow.yaml`；如果后续恢复 vault 里的 reader-facing 图，再把它作为发布视图同步，不要让不存在的 vault 文件成为运行依据。

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/zinan92/daily-newsletter
cd daily-newsletter

# 2. 配置 LLM（默认 DeepSeek）— key 存到本地 secret 文件，不进 env 历史
mkdir -p ~/park-io/_secrets
printf "YOUR_DEEPSEEK_KEY" > ~/park-io/_secrets/deepseek-key && chmod 600 ~/park-io/_secrets/deepseek-key
# 或者临时用 env：export PARKIO_DEEPSEEK_KEY="..."

# 3. 跑测试，确认环境
for t in tests/test_*.py; do python3 "$t"; done

# 4. 手动跑一遍当天 pipeline
./fetch-all.sh                                    # Stage 1: 抓取 raw/legacy input
python3 stages/to_md/run.py                       # Stage 2: raw → one-item markdown + media transcript
BATCH=$(python3 stages/coarse_filter/run.py | tail -1) # Stage 3: coarse filter → processed
PARKIO_BATCH_ID=$BATCH python3 build-digest.py    # Stage 4: AI → 快讯 artifact + optional 深读 artifact
PARKIO_BATCH_ID=$BATCH python3 stages/archive/run.py
PARKIO_BATCH_ID=$BATCH python3 finalize-local.py  # Stage 5: 写 sent/YY-MM-DD.* 和 optional sent/deep-YY-MM-DD.*
python3 build-product-radar.py --date "$(date +%F)" # Product Radar：独立产品机会雷达
python3 build-daily-bundle.py --date "$(date +%F)"  # Daily umbrella：链接快讯/深读/产品雷达
python3 reader_quality.py --date "$(date +%F)"       # Reader QA：检查最终读者产物
python3 send-feishu-digest.py --date "$(date +%F)"   # Feishu：发送完整正文并写 delivery receipt
# Telegram 当前临时关闭：默认生成 processed/ 并写本地 sent/。
# 恢复 Telegram 后再手动执行：
# PARKIO_BATCH_ID=$BATCH PARKIO_FORCE_PUSH=1 python3 send-artifacts.py
```

日常由 launchd 驱动：`fetch-all.sh` 每小时只抓取 raw/source data 并刷新状态健康；`push-digest.sh` 每天 08:30 依次执行 `to-md -> open-batch -> build-digest -> archive -> finalize -> product-radar -> daily-bundle -> reader-qa -> status`，保存到 `processed/` 并写入本地定稿 `sent/YY-MM-DD.{md,html,png}`；如果当天有深读候选，同时写 `sent/deep-YY-MM-DD.{md,html,png}`；产品雷达写 `sent/product-radar-YY-MM-DD.{md,html,png}`；umbrella 写 `sent/daily-YY-MM-DD.{md,html,png}`。WeChat / YouTube 等可恢复登录态异常会进入状态页和 daily bundle 的健康提示，默认不阻塞当天生成；临时恢复旧阻塞行为可设置 `PARKIO_PREFLIGHT_BLOCK=1`。`push-feishu-digest.sh` 在 `push-digest.sh` 后执行 `send-feishu-digest.py`，向飞书发送完整正文并落 delivery receipt。Telegram token 修复前，`push-digest.sh` 默认跳过发送；恢复发送时用 `PARKIO_SKIP_SEND=0 ./push-digest.sh`。

## Pipeline 阶段

| 阶段 | 脚本 | Handler | 说明 |
|------|------|---------|------|
| Fetch | `stages/fetch/run.py` | script | 只下载 raw data；公共 writer 默认写 `inbox/raw/<YYYY-MM-DD>/`，少数直接写入的旧 fetcher 仍兼容迁移 |
| To MD | `stages/to_md/run.py` | script + local_model | raw artifact 统一成 `inbox/unprocessed/<YYYY-MM-DD>/items/*.md`，一个 item 一个 markdown；默认处理今天和昨天尚未转写的 pending raw，避免 X 收藏等 late-arriving raw 永久卡在 raw；视频/音频转录在这里完成 |
| Coarse Filter | `stages/coarse_filter/run.py` | script | 只删明显垃圾，写 `processed/<YY-MM-DD>/coarse-rejects.jsonl`；不打分、不合并、不做产品判断 |
| 选题工作台 | `build-topics.py` | script | 手动/独立读取 `inbox/unprocessed`，生成 `topics.html` / `topics.md`；不参与生产 digest |
| AI Process | `stages/ai_process/run.py` | ai | AI：item cards → events → selection → 快讯写作 + optional 深读写作；失败直接停止，不 fallback |
| 运行报告 | `run_report.py` | script | 为同一个 batch 生成 `run-report.json`；日报、status、health alert 共用这一份健康事实 |
| 归档 | `stages/archive/run.py` | script | 按 `ai/03-selection.json` 归档 `brief_universe` / `deep_candidates`；discard 只保留 decision log |
| 本地定稿 | `finalize-local.py` | script | 不依赖 Telegram，写 `sent/YY-MM-DD.{md,html,png}` 和 optional `sent/deep-YY-MM-DD.{md,html,png}` |
| 产品雷达 | `build-product-radar.py` | script | 独立抓取 Product Hunt / HN / TrustMRR，输出当天新的 Top N build choices，写 `sent/product-radar-YY-MM-DD.{md,html,png}` 和 raw snapshot |
| Daily Umbrella | `build-daily-bundle.py` | script | 不重写正文，只链接快讯/深读/产品雷达并记录健康/降级状态 |
| Reader QA | `reader_quality.py` | script | 检查实际读者 Markdown：禁止 raw transcript、机器 marker、本地路径泄漏、缺失核心 section；失败则停止推送 |
| 飞书推送 | `send-feishu-digest.py` | script | 发送完整正文，不依赖本地 Markdown 链接；写 `processed/receipts/feishu/*.json` delivery receipt |
| 推送 | `send-artifacts.py` → `push-telegram.py` | script | 当前默认跳过；恢复后发送 Telegram |
| 状态 | `generate-status.py` | script | 维护者状态页 `status.html`（抓取/依赖/健康），并同步 `park-ai-intel/public/source-health-live.json` |
| 渠道健康 | `channel-health.py` | script | 按 fetch 日志真值 + feed 新鲜度，分 DOWN/STALE/QUIET/NEW |

## 渠道健康与可观测性

53 个 source 分布在 5 个平台（scrape / rss / twitter / wechat / douyin）。**核心原则：渠道「挂了」绝不能显示成「没更新」。**

- `channel-health.py` 是健康真值源：读 **fetch 日志**（不是会撒谎的 `state.json`）+ 探测 feed 新鲜度，把每个渠道判成五态之一——
  - **DOWN**：抓取报错或自动渠道未配置（超时 / 拒连 / cookie 过期 / WeWe RSS pending）
  - **STALE**：抓取成功但上游 feed 冻结（如 wewe-rss 的微信读书登录过期，feed 多日不更新）
  - **QUIET**：抓取成功、feed 新鲜、确实没有新内容
  - **NEW**：有新内容入库
  - **FILTERED**（状态页「抓到但过滤」）：抓到了新内容，但 0 条进入当天正文（被 coarse filter 或 AI selection 丢掉）
- `status.html` 的逐源健康与依赖检查都走 `channel-health` 真值；依赖检查是**功能型**（cookie/登录态按真实抓取结果判定、wewe-rss 检查 feed 新鲜度而非仅可达）。`wewe-auth-monitor.py` 每次 fetch 都会查询 WeWe RSS 的 `account.list`；读书账号失效时写 `~/park-io/_inbox/wewe-auth-alert.json` 和 `wewe-auth-qr.png`，并在 `status.html` 顶部显示扫码恢复入口。
- `processed/<YY-MM-DD>/run-report.json` 是日报、`status.html`、`health-alerts.md` 的共享事实源：同一个 batch 的 AI 输入、粗筛丢弃、合并事件、快讯/深读/产品雷达数量、source 异常、音视频转录失败、Reader QA、Feishu receipt 必须从这里读，不能各自重新计算。
- `run-report.json` / `status.html` 会显示 pending raw 总数和 pending X 收藏数；如果 X 收藏已经抓到但晚于当天 AI batch，它会显示为 `pending_x_saved_raw`，下一轮 `to_md` 会把它补进 `unprocessed/<date>/items/`。
- `reader_quality.py` 是最终读者产物 QA，只检查 `sent/` 中实际要被读者看到的 Markdown，不重写正文、不做 fallback；发现 raw transcript、重复 filler、机器 marker 或正文内本地路径会失败。
- `send-feishu-digest.py` 会把快讯、深读、产品雷达正文 inline 发送到飞书，并在 `processed/receipts/feishu/` 写入发送回执；如果飞书失败，也要落 failed receipt，便于 status/James 复盘。
- `generate-status.py` 每次刷新 `status.html` 时同步 `park-ai-intel/public/source-health-live.json`，前端可用 `generatedAt` 判断 dashboard 是否 stale。
- 状态页带**渠道告警条**：哪些渠道挂了 / 冻结 / 音视频转录失败一眼可见；最终 newsletter 正文不展示 RuntimeError、cookie 文件名等内部报错。
- `status.html` 允许被 hourly fetch 刷新，但必须区分“最新日报 batch”和“当前 unprocessed 下一批”，不能把二者混成同一个“今日待处理”数字。

### 运行时依赖（外部，需留意）

| 依赖 | 服务谁 | 风险 |
|------|--------|------|
| `wewe-rss`（Colima/Docker，`localhost:4000`） | 8 个公众号的 RSS | 微信读书登录会过期 → feed 冻结；需偶尔重新扫码。**失效会在 digest/status 红字告警；status 顶部会显示扫码二维码。** |
| `content-toolkit`（`~/content-toolkit/capabilities/download`） | `fetch-douyin` / `fetch-media-transcripts` 的抖音抓取 | 该 repo 已 archive，但仍是运行时依赖 |
| `twitter-auth.env` | 20 个 X 账号 | 登录态过期会导致全部 X 抓取失败 |
| `~/park-io/_secrets/youtube-cookies.txt`（Netscape 格式，权限 600，仓库外） | YouTube/播客视频的 yt-dlp 下载+转录 | cookie 过期会触发 "Sign in to confirm you're not a bot" → 视频下不下来。**换法**：浏览器装 cookies.txt 扩展导出 youtube.com cookie，覆盖该文件即可（可用 `PARKIO_YTDLP_COOKIES_FILE` 改路径）。失效会在 status/digest 告警。 |

> 微信公众号没有官方开放 feed，任何方案都得借「微信读书登录」这类会过期的中介——所以策略是：**保留 wewe-rss 作主力 + 登录失效即告警/显示二维码 + RSS 恢复后按 `seen_urls` 回补所有未见过的文章 + 最在乎的号用 `manual-links.md` 兜底**。公众号 RSS 不按“今天日期”截断；桥恢复后，断更期间的 7/8/9 号文章只要之前没记录过，就会进入下一次 newsletter。

## 回归不变量（GOTCHAS）

这个项目的核心是一套硬规则——哪些内容必须被 AI 判断、哪些绝不能由脚本偷偷代替判断。全部记录在 [`GOTCHAS.md`](GOTCHAS.md)，并由 `tests/test_*.py` + AI output structural checks 锁死。改 `summarize.py` / `aggregation/digest/ai_process.py` / `open-batch.py` / `fetch-*.py` 前先对照。重点：

- **脚本不做产品判断**——除了 coarse filter 的明显垃圾，merge / score / selection / writing 都在 AI process。
- **失败不 fallback**——AI JSON 错、结构错、最终 Markdown 缺栏目，直接写 `ai/error.json` 并停止。
- **快讯/深读同一事实源**——`brief_universe` 生成默认快讯，`deep_candidates` 必须是快讯子集并生成 optional 深读。
- **Daily umbrella 三产品**——产品雷达独立生成，`daily-YY-MM-DD.*` 只链接快讯/深读/产品雷达，不在 Markdown 基础上二次重写。
- **读者正文不放 Source Health**——渠道健康只进 `status.html`、`run-report.json` 和 health alerts。
- **归档以 AI selection 为准**——`brief_universe` / `deep_candidates` 进 library，`discard` 只保留 decision log。

## 配置

LLM 默认走 **DeepSeek**（OpenAI 兼容 API）。DeepSeek 发生 SSL/429/5xx 这类临时故障时，默认自动转 **CLIProxy/Sonnet**；401/400 等配置错误不兜底，直接暴露。Key 从 env 或 `~/park-io/_secrets/<name>` 读取，**不进代码、不进 git**。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PARKIO_LLM_PROVIDER` | LLM 提供方：`deepseek` 或 `anthropic` | `deepseek` |
| `PARKIO_LLM_FALLBACK_PROVIDER` | 主 LLM 临时故障时的备用 provider；设为 `none` 可关闭 | `anthropic` |
| `PARKIO_DEEPSEEK_KEY` | DeepSeek API key（或写入 `~/park-io/_secrets/deepseek-key`） | 无（必填） |
| `PARKIO_DEEPSEEK_MODEL` | DeepSeek 模型 | `deepseek-v4-flash` |
| `PARKIO_DEEPSEEK_ENDPOINT` | DeepSeek 端点 | `https://api.deepseek.com/v1/chat/completions` |
| `PARKIO_CLIPROXY_KEY` | Anthropic/备用模式的本地代理密钥；或 `~/park-io/_secrets/cliproxy-key` | 无 |
| `PARKIO_CLIPROXY_MODEL` | Anthropic/备用模式模型 | `claude-sonnet-4-5-20250929` |
| `PARKIO_BATCH_ID` | 指定批次（手动跑某天） | 当天 |
| `PARKIO_PYTHON` | fetch 阶段的 Python 3.11+ 解释器 | 自动探测 |

`sources.md`（在 `~/park-io/_source management- james/`）是来源清单和用户画像的单一真源；评分标定已经迁移到 `prompts/ai-process/03-selection.md`。

## 项目结构

```
daily-newsletter/
├── fetch*.py / fetch-all.sh   # public 抓取入口（兼容 wrapper）
├── to-md.py                   # raw artifact → one-item markdown
├── build-digest.py            # public 构建入口（兼容 wrapper）
├── summarize.py               # public summarize import/CLI（兼容 wrapper）
├── ingestion/                 # channel-owned ingestion implementations
│   ├── rss/                   # RSS / YouTube feed fallback
│   ├── web_scrape/            # official site scrape
│   ├── x/                     # X timeline + saved items
│   ├── douyin/                # Douyin profile monitoring
│   ├── wechat_rss/            # WeWe RSS + exporter bridge
│   └── manual_links/          # manual links + seeded WeChat parser
├── enrichment/media/          # transcript + media summary enrichment
├── aggregation/digest/        # ai_process/build/summarize/archive/finalize
├── stages/                    # 5-stage physical boundary; root scripts wrap these
│   ├── fetch/
│   ├── to_md/
│   ├── coarse_filter/
│   ├── ai_process/
│   └── archive/
├── prompts/ai-process/        # four-pass AI system prompts
├── contracts/                 # standard ingestion artifact schema
├── workflow/                  # n8n-ready workflow-as-code map
├── digest_events.py           # 事件聚类 + thread 合并
├── digest_text.py             # 文本清洗（strip_source_meta 等）
├── push-telegram.py           # Telegram 投递
├── generate-status.py         # 维护者状态页
├── run_report.py              # batch 健康事实源：digest/status/health alert 共用
├── lib.py                     # 共享：路径、解析、llm_call(带重试)
├── GOTCHAS.md                 # 回归不变量清单
├── tests/                     # 回归测试套件
└── AGENTS.md                  # 给 AI agent 的编辑规则
```

数据目录在 `~/park-io/`：`_inbox/`（raw/unprocessed/processed/sent）、`references/`（长期 intake 归档，item 直接平铺）、`workbench/`（Wendy 的内容项目工作区）、`knowledge/`（角色、prompt、playbook、gotchas 等 know-how）、`productions/`（最终内容资产包）、`_inbox/status.html`（维护者面板）。

## Agent-Claimable Task Graph

未来的大改动先写进 repo-local task graph，再让 agent 认领 ready task：

```bash
python3 scripts/task_graph_validate.py
python3 scripts/task_graph_ready.py
python3 scripts/task_next.py
python3 scripts/task_agent_loop.py --agent codex
python3 scripts/task_graph_threads.py
python3 scripts/task_graph_github_export.py --task AG-002 --json
python3 scripts/task_claim.py TG-001 --agent codex
python3 scripts/task_complete.py TG-001 --agent codex --commit <sha>
```

当前图在 `tasks/daily-inbox-task-graph.json`，schema 在 `tasks/schema.json`。GitHub Issues / n8n sync 是后续层；本地 task graph 先保持 source of truth。

每个 execution thread 完成前，用 `tasks/review-checklist.md` 做验收；agent 认领规则在 `tasks/agent-claim-protocol.md`。

## Executable Workflow Diagram

Daily Inbox runtime diagram 的最小可执行版本在 `workflow/diagram/`：

```bash
python3 scripts/workflow_graph_validate.py
python3 scripts/workflow_graph_dry_run.py
python3 scripts/workflow_graph_dry_run.py --json
python3 scripts/workflow_graph_run.py
```

`workflow/diagram/daily-newsletter.graph.json` 里的 `edges` 决定 dry-run 顺序。改 edge 后，dry-run 输出会变；这就是 diagram-as-source-of-truth 的第一层。

`workflow_graph_run.py` 默认也只 dry-run。真实执行必须限定节点并显式确认：

```bash
python3 scripts/workflow_graph_run.py --node status_after_fetch --run --confirm-production
```

可生成 n8n JSON：

```bash
python3 scripts/n8n_export.py --dry-run
python3 scripts/n8n_export.py --output workflow/n8n/daily-newsletter.workflow.json
```

可检查 n8n visual workflow 是否偏离 canonical graph：

```bash
python3 scripts/n8n_import_diff.py
```

## For AI Agents

这是一个 **CLI / cron 流水线**，不暴露 HTTP API。集成或修改前，请读 `AGENTS.md` 和 `GOTCHAS.md`。

```yaml
name: daily-newsletter
capability:
  summary: Aggregate AI news from official channels, X, podcasts, and manual links
           into a daily Chinese digest saved under inbox/processed.
  in:  source configs (sources.md) + manual-links.md
  out: inbox/sent/daily-YY-MM-DD.{md,html,png} linking brief, deep, and product radar artifacts
  fail:
    - "LLM 502/SSL → retry DeepSeek 3x then fail over to CLIProxy/Sonnet; config errors fail fast"
    - "AI JSON/Markdown structure failure → write ai/error.json + raw-response.md and stop"
  handlers: [script (fetch/to_md/coarse_filter/archive/push), ai (understand/merge/select/write), local_model (MLX Whisper)]
entrypoints:
  fetch:   ./fetch-all.sh                 # hourly; fetch raw/source data and refresh health only
  digest:  ./push-digest.sh               # daily 08:30 (to-md→open-batch→build→archive→finalize→product-radar→daily-bundle; send skipped by default)
verify:    for t in tests/test_*.py; do python3 "$t"; done
invariants: GOTCHAS.md
contract:   workflow/daily-newsletter.workflow.yaml
```

修改的安全流程：先跑 `tests/`，改完再跑一次；任何 reader-facing 改动都要让 AI structural checks 通过；编辑 workflow spec 后同步 `tests/test_ingestion_contracts.py`。

## License

Private. Personal project.

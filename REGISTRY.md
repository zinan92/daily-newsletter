# daily-newsletter

## 要去哪里
AI 日报管道:多源抓取 → 加工 → 每日 08:30 飞书全文推送;源健康可观测;日报自己知道自己漏了什么（覆盖率账本 + 新名词雷达）。

## 现在在哪里(2026-09-18)
- 修掉漏读 bug（#17 / PR #18）：批处理只读当天目录，前一天 08:30 之后抓的从不进批，自 06-26 起每天约三分之二被丢。现在读 3 天内所有待处理目录（`PARKIO_PENDING_LOOKBACK_DAYS`）。09-14 到 09-17 的 376 条已回填成四期补刊 `26-09-1x-晚`（processed 目录）。06-26 到 09-13 仍有 8,283 条积压未回填，等 Park 决定。
- 三层覆盖率账本（#19 / PR #23）：`coverage_ledger.py`，抓到 → 进批 → 进日报，写 `_source management/coverage-ledger.jsonl`，日报末尾有"覆盖率"小节。
- 新源 GitHub Trending 日榜（#20 / PR #24）：`fetch-github-trending.py`，sources.md 第 062 行；同时喂产品雷达。
- 新源 X 首页时间线（#21 / PR #25）：`fetch-twitter-home.py`，launchd `com.wendy.parkio-x-home` 每 6 小时（02 / 08 / 14 / 20 点）；故意不进 sources.md；`ai-timeline` 类目在粗筛须有 AI 词才进批。
- 新名词雷达（#22 / PR #26 #27）：`term_radar.py`，跨 ≥3 源且首见 ≤14 天进候选，`_source management/term-candidates/<date>.md`，日报有"新名词雷达"小节。09-17 抓到 Jev（4 源）、09-18 RLCD / JEV。
- AI 阶段重跑复用已生成的 item cards（PR #28）。
- 测试：`python3 -m pytest tests` 全绿（308）。

## 下一步
- Park 决定 06-26 到 09-13 的 8,283 条积压是否回填（估算 item cards 成本约为四天回填的 22 倍）。
- 外部大事对照（当天前 10 件大事我们抓到几件）：等覆盖率账本跑一周后开 issue。
- 候选源试用期 / 降级规则（14 天、≥2 条 High/Watch、30 天零产出）：等 Park 拍板阈值。
- 源健康告警自动化(连续失败自动开 issue)。

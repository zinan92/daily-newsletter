# Decision log — daily-newsletter

> Keep only durable decisions. A functional PR records its decision and
> Gotchas; a pure deploy/status change is exempt unless it changes a durable
> operating fact.

## YYYY-MM-DD — <decision title>

- **Context:** <what required a decision>
- **Decision:** <what was approved/selected>
- **Why:** <evidence and trade-off>
- **Alternatives rejected:** <briefly, with reason>
- **Evidence:** <PR, issue, test, mockup, source, or receipt links>
- **Gotchas:** <constraint a future agent must not forget>

---

## 2026-09-18 — 批处理按天窗口清空待处理队列，不按"今天"目录

- **Context:** Park 指出日报漏了 Jev；查到 vista8 / oran_ge 的帖子已抓到但从未进批。coarse_filter 只读 `unprocessed/<today>/`，而抓取每小时按抓取日期落盘。
- **Decision:** coarse_filter 清空 3 天内所有日期目录（`PARKIO_PENDING_LOOKBACK_DAYS`），更旧的记日志不动；run-report 增加 `pending_unprocessed`。
- **Why:** 06-26 起每天约三分之二的抓取从未被读；这是管道最大的单点损失，且修法只是读取范围。
- **Alternatives rejected:** 把批处理改到每天两次（成本翻倍且不解决跨日）；让 to_md 直接写进当天目录（会把昨晚的条目标成今天，覆盖率账本会失真）。
- **Evidence:** #17, PR #18, `tests/test_coarse_filter_pending.py`；四期补刊 `26-09-14-晚` … `26-09-17-晚`。
- **Gotchas:** 06-26 到 09-13 的 8,283 条积压仍在 `unprocessed/`，超出窗口不会被自动处理；回填一次 376 条的 event_merge 会因输出过长失败，必须按天拆批（见 PR #28 的 card 复用）。

## 2026-09-18 — 覆盖率分三层记账，"漏了"先定位在哪层

- **Context:** Jev 抓到没进批，Hypit 根本没源，我自己搜得太泛；三种病一个症状。
- **Decision:** `coverage_ledger.py` 按 URL 记 抓到 / 进批 / 进日报 三层与积压，日报末尾展示；push-digest 每天写一行 jsonl。
- **Why:** 没有分层计数，所有遗漏都会被归咎于 AI 选题，修错地方。
- **Alternatives rejected:** 只记"进日报率"（看不出批处理丢件）。
- **Evidence:** #19, PR #23, `tests/test_coverage_ledger.py`。
- **Gotchas:** "进批"以 `ai/00-input-items.json` 为准；当天（as_of 同日）的未进批是正常的，明早进批，不要当故障。

## 2026-09-18 — 两条新源：GitHub Trending 日榜、X 首页时间线；一个新阶段：名词雷达

- **Context:** Hypit 靠 GitHub Trending 和 Park 的时间线传播，59 个订阅源没有一个覆盖；"很多人在说"是跨源频次，不是编辑判断。
- **Decision:** GitHub Trending 进 sources.md（platform github）并喂产品雷达；X 首页每天 08:00 / 20:00 抓，不进 sources.md，`ai-timeline` 类目在粗筛须有 AI 词；`term_radar.py` 跨 ≥3 独立来源且首见 ≤14 天进候选，模板型雷达源（TrustMRR / Product Hunt）只算一个来源。
- **Why:** 时间线原始信号三分之二是币圈和政治，必须在进 AI 前拦；名词雷达确定性、零 token，09-17 回溯即抓到 Jev。
- **Alternatives rejected:** 用 LLM 判"新名词"（不可复现、要花钱）；把 X 首页写进 sources.md（fetch-twitter 会对 `home` 调 user-posts）。
- **Evidence:** #20 PR #24；#21 PR #25；#22 PR #26 #27；实测 09-17 Jev 4 源、09-18 RLCD 4 源。
- **Gotchas:** 名词雷达的噪音只能加进 `KNOWN_TERMS` / `STOPWORDS`，不做按日覆盖；08:00 抓取依赖 08:30 批处理，20:00 抓取依赖 to_md 回看一天 + 粗筛窗口，两者不能单独收紧。


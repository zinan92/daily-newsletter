# daily-newsletter

## 要去哪里
AI 日报管道:多源抓取 → 加工 → 每日 08:30 飞书全文推送;源健康可观测。

## 现在在哪里(2026-09-03)
- 管道使用 5-stage fetch → to_md → coarse_filter → ai_process → archive，每日 08:30 生成单一 Markdown 并推送飞书。
- DeepSeek 是主模型；余额/额度不足时自动切换 Codex CLI，结构化输出缺失时会按 item id 做 focused repair。
- WeWe RSS 自动桥已从生产链路、preflight、status 和 health cron 移除；手动公众号 seed、manual links 和飞书收藏仍保留。
- 2026-09-03 的日报已使用 Codex fallback 生成并成功发送，Reader QA 通过。

## 下一步
- 继续观察 Codex fallback 的长请求延迟和 focused repair 命中率；失败必须保留 error，不生成半成品。
- 继续维护 X、YouTube、抖音和手动公众号入口的 source health。

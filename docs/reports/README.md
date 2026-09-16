# 验收报告索引

| 报告 | 结论 | 当前可复现性 |
|---|---|---|
| [Wan3 UAT](wan3-uat.md) | 报告记录 480P/2s 真实任务成功 | 当前 venv 缺 Pillow，完整套件收集失败 |
| [FFmpeg 集成](ffmpeg-integration.md) | 报告记录 normalize/concat/probe 19/19 | 当前配置找不到 FFmpeg，7 项集成测试失败 |

## 证据要求

报告用于证明某个 commit 在特定环境下的结果，至少应包含：

- 测试日期和时区；
- git commit SHA 与工作区状态；
- OS、Node、Python 和外部工具版本；
- 依赖锁文件或安装命令；
- 精确测试命令；
- 原始 passed/failed/skipped 输出；
- 外部 API 模型、地域和非敏感参数；
- 成本与产物校验。

当前两份报告的日期是 2026-09-17，晚于 2026-09-16 状态基线。发布前需由报告作者确认日期和环境来源。


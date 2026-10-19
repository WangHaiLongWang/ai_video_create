# 项目全量验证与 Platform Hardening 收口（2026-10-16）

> 环境：Windows / Node 22.21.1 / npm 10.9.4 / Python 3.12.3
> 基线：工作树（父提交 `ef8ad99`；最终提交和远端 CI 尚未生成）

## 结论

本地可控 H0–H4、H6 工程项已完成，测试门禁全绿。未关闭项只剩必须在最终提交产生后执行的远端同 SHA Actions/制品归档、付费 Provider 复证，以及 Doubao 账号模型激活；不得把这些外部证据标为代码完成。

## 门禁结果

| 门禁 | 命令/结果 |
|---|---|
| Runtime | Node 22.21.1 preflight passed；Python 3.12 constraints + `pip check` passed |
| Frontend unit | 24 files / 414 passed；无 React act warning |
| Frontend type/build | passed；index 143.29 kB，最大 chunk 185.73 kB |
| Backend non-external | 2181 passed / 8 skipped / 21 deselected / 0 failed / 0 warning |
| Chromium E2E | 143 passed / 0 failed / 0 skipped；真实 Mock FastAPI |
| Ruff blocking rules | syntax/undefined-name gate passed |
| Release/DB/version | 6 passed；metadata/preflight/backup-restore passed |
| Security scan | 0 critical；6 个命中均为构造参数名或脱敏测试夹具，报告可归档 |
| 默认生产路径 | MiMo / Qwen Image 3.0 / Wan3 三 Provider healthy；Agent 六节点 preview 可应用 |

全量验证中额外修复：

- image-only workflow 使用显式 `output.asset`，前后端端口契约同步；
- Mock modify 正确实现“删除输出节点”，破坏性确认 E2E 恢复；
- 测试默认强制 Mock Provider，避免 `.env`/持久化配置触发真实付费请求；
- TestClient 生命周期收口，Windows socket warning 清零；
- 重复 workflow ID 返回 409，不再向 ASGI 日志泄漏 SQLite traceback；
- 非 Mock Provider 失败不再生成 synthetic 成功资产。

## 外部发布边界

| 项 | 当前证据 | 下一动作 |
|---|---|---|
| RC-004 / HARD-501/502 | `a2b6079` 的 [CI](https://github.com/WangHaiLongWang/ai_video_create/actions/runs/39222357198) 与 [Security](https://github.com/WangHaiLongWang/ai_video_create/actions/runs/39222357209) 全绿；三平台 JUnit/build/Playwright/security artifacts 已归档 | ✅ 关闭 |
| RC-008 / HARD-503/504 | `78a99ac` MiMo/Qwen/Wan3 受控 1+1+1 调用成功，产物哈希/job ID/配置估算费用已归档 | ✅ 技术 UAT 关闭；实际账单由供应商控制台财务核对 |
| RC-007 / HARD-505 | Doubao adapter/配置/Mock/失败处理完成 | 账号激活 Seedream/Seedance 或提供 Endpoint ID 后运行真实 UAT |
| HARD-601/604 tag | `v1.0.0-rc.1` metadata/checklist/manifest 完成 | ✅ tag 指向已验证 `a2b6079` |
| RC-009 滑雪内容 | 三批 6 图；2 图→2×3s 视频→6.06s 合成技术通过 | 后脚/空固定器硬约束未稳定满足；需局部重绘/ControlNet/换模型 |

远端只读复核：`git push --dry-run origin main` 与 `git ls-remote` 均因 GitHub 443 超时失败；REST API 只能查询到旧 SHA `ef8ad99` 的 Security success / CI failure。因此本轮无法形成新 SHA Actions URL，属于可复现的网络/远端状态阻断。

历史真实链路证据：[real-chain-uat-2026-10-12.md](real-chain-uat-2026-10-12.md)。

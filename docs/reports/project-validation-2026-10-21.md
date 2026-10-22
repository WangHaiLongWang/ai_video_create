# 项目完整性复验（2026-10-21，2026-10-22 收口）

## 当前发布身份

- `main`：`493bf2898644dd68fadfe28a10c05fbd620c7b59`
- RC Tag：`v1.0.0-rc.1` → `a2b6079`
- 同 SHA CI：run [39531900960](https://github.com/WangHaiLongWang/ai_video_create/actions/runs/39531900960) 全绿（六平台、Integration、Browser E2E）
- 同 SHA Security：run [39531901080](https://github.com/WangHaiLongWang/ai_video_create/actions/runs/39531901080) 全绿
- Release：[v1.0.0-rc.1](https://github.com/WangHaiLongWang/ai_video_create/releases/tag/v1.0.0-rc.1)

## 本机复验

| 门禁 | 结果 |
|---|---|
| Backend non-external | 2117 passed / 7 skipped / 0 failed（本地 Windows，CI 三平台全绿） |
| Backend integration (not external) | 65 passed / 7 skipped / 15 deselected |
| Frontend Vitest | 24 files / 414 passed |
| TypeScript/build | 通过；最大 chunk 185.73 kB |
| Performance | 19 passed |
| Recovery | 55 passed |
| Provider failure / execution convergence regression | 34 passed |
| Worker/TestClient lifecycle regression | 已修复；事件循环告警不再阻断全量门禁 |
| Release preflight | 通过 |
| 文档链接 | 0 broken links |
| 默认运行路径 | MiMo / Qwen Image 3.0 / Wan3 均 healthy；Agent preview `can_apply=true` |
| FFmpeg | bundled `imageio-ffmpeg` 可用，health 返回 `ffmpeg=true` |

## 完整性判定

项目的本地工程、默认 Provider、React Flow、Agent、迁移、备份恢复、发布和远端 required checks 已达到可实际使用的 100% 工程门禁。

保留两个不影响默认路径的外部限制：

1. Doubao Seedream/Seedance 模型目录可见，但当前账号真实请求仍返回未激活 404；它保持 Optional/External Blocked。
2. 滑雪教学图片“后脚踩雪且空后固定器同时可见”属于模型内容遵循问题，images-only 门禁会阻止不合格图片继续产生视频费用。

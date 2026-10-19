# v1.0.0-rc.1 发布证据（2026-10-19）

## 发布身份

- Tag：`v1.0.0-rc.1`
- 验证提交：`a2b60791dc228796e090f3d20f6730110c0fbc07`
- CI：[run 39222357198](https://github.com/WangHaiLongWang/ai_video_create/actions/runs/39222357198)
- Security：[run 39222357209](https://github.com/WangHaiLongWang/ai_video_create/actions/runs/39222357209)

## 同 SHA 门禁

以下 job 均为 `success`：

- Backend：Linux、Windows、macOS
- Frontend：Linux、Windows、macOS
- Integration：Ubuntu
- Browser E2E：Ubuntu / Chromium
- Security Scan

## 制品

| Artifact | ID | 字节数 |
|---|---:|---:|
| backend-junit-Windows | 12172710634 | 29,053 |
| backend-junit-macOS | 12172461049 | 29,167 |
| backend-junit-Linux | 12171684480 | 28,400 |
| frontend-build | 12172650526 | 214,212 |
| playwright-report | 12172317716 | 324,936 |
| security-scan-report | 12172152544 | 791 |

Artifacts 受 GitHub retention policy 管理。长期事实基线保留在本报告、项目状态和真实 Provider UAT 报告中。

## 默认运行路径

本机持久化默认值已校准为：

```text
MiMo mimo-v2.5-pro
  → Qwen Image 3.0
  → Wan3 Video 480P
  → bundled FFmpeg concat
```

三个 Provider 健康检查通过，真实 Agent 六节点 preview 为 `can_apply=true`，MiMo/Qwen/Wan3 真实链路及滑雪工作流技术链均已通过。

## 已知外部限制

- Doubao Seedream 5.0 Pro / Seedance 2.5：模型目录可见，但当前账号真实请求仍返回未激活 404；默认路径不使用 Doubao。
- 滑雪教学的“学员后脚踩雪且空后固定器同时清晰可见”内容硬约束在三批候选中未稳定满足；images-only 人工门禁会阻止不合格首帧继续产生视频费用。

# ai_video_create 已知问题

本文档记录当前版本中已知的问题、限制和解决方法。

> 基线版本：v1.0.0-rc.1 (2026-09-22)

## 目录

- [通用已知问题](#通用已知问题)
- [平台特定问题](#平台特定问题)
- [Provider 相关问题](#provider-相关问题)
- [开发与测试限制](#开发与测试限制)

---

## 通用已知问题

### Pydantic V3 迁移未完成

**状态：** 进行中

当前项目使用 Pydantic V2 的 `ConfigDict` 配置方式。Pydantic V3 发布后可能需要进一步迁移。当前功能不受影响，但升级 Pydantic 大版本时需要关注。

**影响范围：** 后端数据模型定义
**计划修复：** 待 Pydantic V3 稳定后统一迁移
**临时处理：** 保持当前 Pydantic V2 兼容模式

### Doubao Provider 模型未激活

**状态：** 代码已完成，待模型激活

Doubao Seedream/Seedance Provider 的代码集成已完成，但火山方舟控制台中对应模型可能尚未激活。在模型权限未解除前，Doubao Provider 不能作为生产可用选项。

**影响范围：** 图像/视频生成 Provider 选择
**临时处理：** 使用 Mock、DashScope (Qwen Image) 或 Wan3 Provider 作为替代
**参考文档：** [Doubao Provider 集成文档](../integrations/doubao-seedance-2.5.md)

### Scene Roundtrip 测试需要后端运行

**状态：** 已知限制

Scene 的完整导入导出 roundtrip 测试在没有后端服务运行时会跳过。这是测试设计的预期行为，非功能缺陷。

**影响范围：** 测试覆盖率
**临时处理：** 运行测试前先启动后端服务

### FFmpeg 未捆绑

**状态：** 设计决策

FFmpeg 未随项目捆绑安装，需要用户自行安装。不安装 FFmpeg 时，图片和视频生成节点仍可运行，仅最终视频合成步骤会跳过。

**影响范围：** 视频合成工作流
**解决方案：** 参见 [安装指南 - 安装 FFmpeg](INSTALL.md#安装-ffmpeg可选)

### Agent v1 部分 Acceptance 测试失败

**状态：** 待修复

旧版 Agent v1 的部分 acceptance 测试在当前代码库中存在 3 项失败，正在修复中。

**影响范围：** 后端测试集
**临时处理：** 这些失败不影响新 Agent v2 功能

### PyPI cryptography 依赖在干净 venv 中可能安装失败

**状态：** 已知环境问题

在某些环境下（特别是缺少编译工具时），`cryptography` 包的安装可能失败。该包用于 AES-256-GCM 加密存储。

**影响范围：** 安全功能（加密密钥存储）
**解决方案：**
- 安装编译工具（Windows: Visual C++ Build Tools; Linux: `build-essential`; macOS: Xcode Command Line Tools）
- 或使用预编译轮子：`pip install --only-binary=:all: cryptography`

---

## 平台特定问题

### Windows

#### 长路径限制

**症状：** `OSError: [Errno 206] The filename or extension is too long`

**原因：** Windows 默认最大路径长度为 260 字符，`node_modules` 中的深层嵌套可能超出限制。

**解决方案：**
1. 将项目放在较短的路径下（如 `D:\avc\` 而非 `D:\Projects\ai_video_create\`）
2. 启用 Windows 长路径支持（需要管理员权限）：
   ```
   注册表: HKLM\SYSTEM\CurrentControlSet\Control\FileSystem
   设置 LongPathsEnabled = 1
   ```
3. 在 PowerShell 中运行 `npm ci` 时添加 `--maxsockets=1` 减少并发

#### PowerShell 执行策略

**症状：** 无法加载 `Activate.ps1` 脚本

**解决方案：**
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

#### 中文路径编码

**症状：** 路径中包含中文字符时出现编码错误

**解决方案：**
1. 将项目移到纯英文路径下
2. 或在系统设置中启用 UTF-8 支持

### macOS

#### FFmpeg 安装

通过 Homebrew 安装 FFmpeg 是推荐方式：
```bash
brew install ffmpeg
```

Homebrew 安装的 FFmpeg 通常自动可用。如需指定路径：
```
AI_VIDEO_FFMPEG_PATH=/opt/homebrew/bin/ffmpeg
```

#### Apple Silicon 兼容性

项目在 Apple Silicon (M1/M2/M3/M4) 设备上原生运行，无需 Rosetta。Python 和 Node.js 均有原生 ARM64 版本。

#### Python 版本

使用 Homebrew 安装 Python 时，命令为 `python3` 而非 `python`：
```bash
brew install python@3.12
python3 -m venv backend/.venv
```

### Linux

#### Pillow 依赖 libgl1

**症状：** Pillow 安装失败或导入时报 `ImportError`

**解决方案：**
```bash
# Ubuntu/Debian
sudo apt install libgl1-mesa-glx

# CentOS/RHEL
sudo yum install mesa-libGL
```

#### python3-venv 包

**症状：** `python -m venv` 报错 `ModuleNotFoundError`

**解决方案：**
```bash
# Ubuntu/Debian
sudo apt install python3.12-venv

# Fedora
sudo dnf install python3-virtualenv
```

---

## Provider 相关问题

### DashScope / Wan3 API 配额

**症状：** Provider 返回 429 或配额超限错误

**解决方案：**
1. 检查阿里云百炼控制台的 API 配额
2. 减少并发 Worker 数量：`AI_VIDEO_WORKER_COUNT=1`
3. 增加请求间隔
4. 使用 Mock Provider 进行开发调试

### Ollama 本地模型

**症状：** LLM 请求超时

**解决方案：**
1. 确认 Ollama 服务正在运行：`curl http://localhost:11434/api/tags`
2. 检查模型是否已下载：`ollama list`
3. 增加超时时间：`AI_VIDEO_OPENAI_COMPAT_TIMEOUT=300`
4. 使用较小的模型以获得更快响应

### ComfyUI 连接失败

**症状：** `Connection refused` 或超时

**解决方案：**
1. 确认 ComfyUI 服务正在运行：`curl http://localhost:8188/system_stats`
2. 检查端口配置：`AI_VIDEO_COMFYUI_API_URL`
3. 确认 ComfyUI 已加载所需的模型 checkpoint

---

## 开发与测试限制

### Playwright E2E 测试

- Playwright Chromium 测试需要后端和前端服务同时运行
- 在 CI 环境中使用 Mock backend 运行
- 本地运行完整 E2E 需要先执行 `npm run dev` 启动前后端

### 测试覆盖率

- 后端测试在排除 `cryptography` 相关阻断文件后通过率较高
- 完整的后端测试收集需要所有依赖正确安装
- 前端测试使用 happy-dom 环境运行

### 数据库迁移

- 迁移文件是**向前兼容**的，不支持回滚
- 新增的数据库列会保留，旧版本代码会忽略它们
- 如果需要完全清理，需要手动操作 SQLite

---

## 反馈与报告

如发现新的 Bug 或问题，请通过以下方式报告：

1. 在 GitHub 上创建 Issue，包含：
   - 操作系统和版本
   - Python/Node.js 版本
   - 完整的错误信息和堆栈跟踪
   - 复现步骤

2. 对于安全相关问题，请参见 [安全指南](SECURITY.md)

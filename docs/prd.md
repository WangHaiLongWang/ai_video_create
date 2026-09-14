产品需求文档（PRD）
1. 产品定位
Flow Agent Studio —— 一个完全运行在本地、可视化编排 AI 内容生成流程的桌面级 Web 平台。

用户通过拖拽节点、连线，自定义一条 AI 处理流水线，平台负责执行编排。内置“提示词 → 文本 → 图片 → 视频 → 拼接”的完整内容生产模板，一键加载即可生成短视频。

核心价值：

零基础设施：无需 Docker、数据库、消息队列，本地 Node + Python 即可运行

零锁定：LLM 可本地可远程，图像/视频生成可接本地 ComfyUI 也可接云端 API

可视化：所有流程所见即所得，非技术用户也能编排复杂 AI 工作流

2. 目标用户
用户角色	典型场景	核心诉求
内容创作者	批量生产短视频	提示词一键出片，可视化调参
AI 工程师	快速验证多模型流水线	灵活切换 LLM/生图/生视频后端
产品经理	原型演示 AI 能力	拖拽即出效果，无需写代码
教育者	讲解 AI 工作流原理	流程图直观展示数据流
3. 功能清单
3.1 工作流编辑器（P0）
功能	描述	验收标准
节点拖拽	从左侧面板拖入画布	节点跟随鼠标，释放后落位
节点连线	从输出 handle 拖到输入 handle	连线成功创建，非法连接拒绝
节点配置	点击节点，右侧面板编辑参数	修改实时生效，保存到工作流
节点删除	选中 + Delete 键	相关连线一并删除
画布缩放/平移	滚轮缩放，空格拖拽平移	流畅无卡顿
撤销/重做	Ctrl+Z / Ctrl+Shift+Z	支持至少 20 步
工作流保存	保存到 SQLite	刷新后恢复
工作流导入/导出	JSON 文件	导出后再导入结构一致
3.2 节点类型（P0）
节点	输入	输出	配置项
文本输入	—	text	默认文本
LLM	text, system_prompt	text	provider_id, model, temperature, max_tokens, stream
文本分段	text	text[]	分段数, 分段策略
文生图	text	image	后端（ComfyUI/云端）, 尺寸, 风格
图生视频	image	video	后端, 时长, 运镜, 分辨率
视频拼接	video[]	video	转场类型, 输出格式
输出	任意	—	展示/下载
3.3 执行与监控（P0）
功能	描述
一键执行	点击 Run，DAG 引擎解析并调度
状态可视化	节点边框颜色：灰=等待，蓝=执行中，绿=完成，红=失败
实时进度	WebSocket 推送节点状态，无需刷新
节点预览	完成后节点内展示图片缩略图/视频播放器
执行历史	每次执行记录入 SQLite，可查看历史
失败重试	失败节点可单独重试，不影响已完成的
中断执行	支持取消正在执行的流程
3.4 LLM 管理（P0）
功能	描述
Provider 列表	展示已配置的所有 Provider
新增/编辑	表单填写 base_url, api_key, models
连通性测试	一键 health_check()
模型列表	拉取 Provider 可用模型
热重载	修改配置后无需重启
节点级选择	每个 LLM 节点可独立选择 Provider 和模型
3.5 模板工作流（P1）
预置“提示词 → 短视频”模板：

text
[文本输入] → [LLM 分段] → [文本分段] → [文生图 ×N] → [图生视频 ×N] → [视频拼接] → [输出]
用户点击“加载模板”后，画布自动生成完整节点图，只需填提示词即可运行。

3.6 文件管理（P1）
功能	描述
产物列表	展示所有生成的图片/视频
下载	单个或批量下载
清理	手动清理旧产物
存储路径配置	在 config/app.yaml 中设置
3.7 高级功能（P2）
自定义节点 SDK（用户编写 Python Handler + 前端组件）

工作流版本管理

条件分支节点（if/else）

循环节点（对数组逐项执行）

定时执行（cron 表达式）

4. 核心用户流程
4.1 从零创建流程
text
打开平台
  → 拖入 [文本输入] 节点，填写提示词
  → 拖入 [LLM] 节点，选择 Provider 和模型，连接上游
  → 拖入 [文本分段] 节点，设置分 5 段
  → 拖入 5 个 [文生图] 节点（或 1 个自动广播）
  → 拖入 [图生视频] 节点
  → 拖入 [视频拼接] 节点
  → 拖入 [输出] 节点
  → 连线
  → 点击 Run
  → 实时观察节点变绿
  → 在 [输出] 节点下载最终视频
4.2 切换 LLM 后端
text
进入 /settings/llm
  → 点击“新增 Provider”
  → 填写类型（Ollama/OpenAI 兼容）、base_url、api_key
  → 点击“测试连接”
  → 保存
  → 回到画布，在 LLM 节点的属性面板选择新 Provider
  → 重新执行
5. 非功能需求
维度	要求
启动时间	冷启动 < 5 秒
依赖数量	Python 依赖 < 15 个，Node 依赖 < 30 个
磁盘占用	空载 < 200MB（不含 AI 模型）
并发执行	单机支持 2-4 个 Worker 并行
数据持久化	SQLite 单文件，可备份/迁移
网络依赖	除 LLM/生图/生视频调用外，完全离线可用
跨平台	Windows / macOS / Linux 均可运行
浏览器兼容	Chrome/Edge/Safari 最新版
6. 数据模型
sql
-- 工作流
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    graph_json TEXT NOT NULL,     -- {nodes: [], edges: []}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 执行记录
CREATE TABLE executions (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    status TEXT NOT NULL,          -- running / completed / failed / cancelled
    inputs TEXT,                   -- JSON
    outputs TEXT,                  -- JSON
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 任务队列（见 4.2）

-- LLM Provider（YAML 之外的 UI 配置）
CREATE TABLE llm_providers (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
7. 里程碑
阶段	周期	交付物
M1 · 画布 MVP	1.5 周	React Flow 画布 + 节点拖拽/连线 + 保存到 SQLite
M2 · 执行引擎	1.5 周	SQLite 队列 + Worker + LLM 节点 + 文本分段节点 + WebSocket 状态
M3 · LLM 组件化	1 周	Provider 抽象 + 三个内置 Provider + 配置热加载 + 设置页
M4 · 多模态节点	2 周	文生图 + 图生视频 + 视频拼接 + FFmpeg 集成
M5 · 模板与打磨	1 周	模板工作流 + 执行历史 + 错误处理 + 文档
总计约 7 周（单人全职）。

8. 风险与对策
风险	影响	对策
SQLite 并发写冲突	高并发下任务卡顿	本地场景并发低；使用 WAL 模式 + BEGIN IMMEDIATE
FFmpeg 未安装	视频拼接失败	启动时检测，缺失则给出明确提示
云端 LLM 超时	节点卡住	节点级 timeout + 重试策略
视频生成耗时长	用户等待焦虑	节点内显示进度条 + 预估剩余时间
SQLite 文件损坏	数据丢失	提供 npm run backup 导出命令
模型文件巨大	磁盘爆满	产物目录可配置 + 定期清理策略
六、与上一版架构的对比
维度	上一版（Docker + Redis）	本版（极简本地）
运行依赖	Docker + Docker Compose	Node + Python
数据库	PostgreSQL 容器	SQLite 单文件
队列	Redis + ARQ/Celery	SQLite 表 + asyncio
文件存储	MinIO 容器	本地目录
实时通信	Redis Pub/Sub	WebSocket 直连
LLM 接入	硬编码/环境变量	组件化 + YAML 配置 + 热加载
启动命令	docker compose up	npm run dev
首次启动时间	5-10 分钟（拉镜像）	< 30 秒
部署复杂度	中	极低
适用场景	团队协作、生产部署	个人开发、本地验证、单机生产
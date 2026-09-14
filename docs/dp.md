极简本地架构：Node + Python + 可配置 LLM
本次架构彻底去除 Docker、PostgreSQL、MinIO、Redis 等所有中间件依赖，只需一台装有 Node 和 Python 的机器即可运行。数据落 SQLite 单文件，文件落本地磁盘，任务队列在进程内调度，LLM 完全配置化（远程/本地均可）。

一、架构总览图
text
┌────────────────────────────────────────────────────────────────────┐
│                     宿主机 (Windows / macOS / Linux)                │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              浏览器 (Chrome / Edge / Safari)                  │ │
│  │   ┌────────────────────────────────────────────────────┐    │ │
│  │   │  可视化画布 (React Flow)                            │    │ │
│  │   │  节点拖拽 · 连线 · 属性编辑 · 执行监控               │    │ │
│  │   └────────────────────────────────────────────────────┘    │ │
│  └────────────────────────┬─────────────────────────────────────┘ │
│                           │ HTTP / WebSocket                       │
│  ┌────────────────────────▼─────────────────────────────────────┐ │
│  │          前端进程 (Node.js + Vite, 端口 5173)                 │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐      │ │
│  │  │ 画布模块    │  │ 节点注册表  │  │ 执行状态订阅        │      │ │
│  │  │ React Flow │  │ Schema     │  │ WebSocket Client   │      │ │
│  │  └────────────┘  └────────────┘  └────────────────────┘      │ │
│  │                    Zustand 状态管理                            │ │
│  └────────────────────────┬─────────────────────────────────────┘ │
│                           │ REST + WebSocket                       │
│  ┌────────────────────────▼─────────────────────────────────────┐ │
│  │          后端进程 (Python + FastAPI, 端口 8000)               │ │
│  │                                                               │ │
│  │  ┌──────────────────────────────────────────────────────┐   │ │
│  │  │               API 层 (FastAPI 路由)                    │   │ │
│  │  │  工作流 CRUD · 执行触发 · 文件服务 · LLM 管理 · WS     │   │ │
│  │  └────────────┬─────────────────────────┬───────────────┘   │ │
│  │               │                          │                    │ │
│  │  ┌────────────▼────────────┐  ┌─────────▼────────────────┐  │ │
│  │  │   DAG 执行引擎           │  │  LLM 组件层               │  │ │
│  │  │  · 图解析                │  │  ┌────────────────────┐  │  │ │
│  │  │  · 拓扑排序 (Kahn)       │  │  │ Provider 注册表     │  │  │ │
│  │  │  · 节点调度              │  │  ├────────────────────┤  │  │ │
│  │  │  · 上下文传递            │  │  │ OllamaProvider     │  │  │ │
│  │  └────────────┬────────────┘  │  │ OpenAICompat       │  │  │ │
│  │               │                │  │ MockProvider       │  │  │ │
│  │  ┌────────────▼────────────┐  │  └────────────────────┘  │  │ │
│  │  │  SQLite 任务队列         │  │  配置驱动 · 热重载        │  │ │
│  │  │  (进程内 asyncio Worker) │  └─────────────────────────┘  │ │
│  │  └────────────┬────────────┘                                │ │
│  │               │                                              │ │
│  │  ┌────────────▼────────────┐  ┌──────────────────────────┐ │ │
│  │  │  节点执行器 Handler       │  │  本地文件服务              │ │ │
│  │  │  LLM / Split / T2I /     │  │  ./data/assets/          │ │ │
│  │  │  I2V / Concat / Output   │  │  (静态文件 + 缩略图)       │ │ │
│  │  └────────────┬────────────┘  └──────────────────────────┘ │ │
│  └───────────────┼──────────────────────────────────────────────┘ │
│                  │                                                │
│  ┌───────────────▼──────────────┐   ┌──────────────────────────┐ │
│  │  SQLite 数据库                │   │  外部 AI 服务 (可选)       │ │
│  │  ./data/flow.db               │   │  ┌────────────────────┐  │ │
│  │  · workflows                  │   │  │ Ollama (本地)      │  │ │
│  │  · executions                 │   │  │ :11434             │  │ │
│  │  · tasks                      │   │  ├────────────────────┤  │ │
│  │  · node_configs               │   │  │ OpenAI / DeepSeek  │  │ │
│  │  · llm_providers              │   │  │ 通义千问 / 智谱     │  │ │
│  └──────────────────────────────┘   │  ├────────────────────┤  │ │
│                                      │  │ ComfyUI (本地)     │  │ │
│  ┌──────────────────────────────┐   │  │ :8188              │  │ │
│  │  FFmpeg (本地可执行文件)       │   │  ├────────────────────┤  │ │
│  │  视频拼接 / 转码 / 转场        │   │  │ 云端生图/生视频 API │  │ │
│  └──────────────────────────────┘   │  └────────────────────┘  │ │
│                                      └──────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
Mermaid 版本（可在支持 Mermaid 的渲染器中查看）：





















二、技术栈（极简）
层	选型	说明
前端运行时	Node.js 18+	自带，npm/pnpm 管理依赖
前端框架	Vite + React 18 + TypeScript	秒级热更新，无 SSR 复杂度
画布	@xyflow/react (React Flow)	节点拖拽/连线事实标准
状态管理	Zustand	轻量，无 Provider 嵌套
UI 组件	TailwindCSS + shadcn/ui	无需设计系统从零搭建
后端运行时	Python 3.10+	自带，venv 隔离依赖
后端框架	FastAPI + Uvicorn	异步、自带 OpenAPI 文档
数据库	SQLite (stdlib sqlite3)	单文件，零安装
任务队列	SQLite 表 + asyncio Worker	进程内调度，无外部依赖
文件存储	本地目录 ./data/assets/	FastAPI 静态挂载
视频处理	FFmpeg 可执行文件	需系统预装，PATH 可访问
LLM 接入	自研 Provider 组件	Ollama / OpenAI 兼容 / Mock
实时通信	WebSocket (FastAPI 原生)	执行状态推送
零中间件：无 Redis、无 PostgreSQL、无 MinIO、无 Docker。

三、目录结构
text
flow-platform/
├── README.md
├── package.json                 # 根级脚本（同时启动前后端）
├── .env                         # 环境变量
│
├── frontend/                    # Node 进程
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/                 # 后端 API 客户端
│       │   ├── client.ts
│       │   └── ws.ts            # WebSocket 订阅
│       ├── stores/              # Zustand 状态
│       │   ├── workflowStore.ts
│       │   └── executionStore.ts
│       ├── components/
│       │   ├── Canvas/          # React Flow 画布
│       │   │   ├── FlowCanvas.tsx
│       │   │   └── nodeTypes.ts
│       │   ├── Nodes/           # 自定义节点组件
│       │   │   ├── LLMNode.tsx
│       │   │   ├── TextSplitNode.tsx
│       │   │   ├── T2INode.tsx
│       │   │   ├── I2VNode.tsx
│       │   │   ├── ConcatNode.tsx
│       │   │   └── OutputNode.tsx
│       │   ├── Panels/          # 侧边栏面板
│       │   │   ├── NodePalette.tsx
│       │   │   ├── PropertyPanel.tsx
│       │   │   └── ExecutionPanel.tsx
│       │   └── Settings/
│       │       └── LLMSettings.tsx   # Provider 管理页
│       └── types/
│           └── workflow.ts
│
├── backend/                     # Python 进程
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置加载
│   │   ├── db.py                # SQLite 连接与迁移
│   │   ├── models.py            # Pydantic 数据模型
│   │   │
│   │   ├── api/                 # 路由层
│   │   │   ├── workflows.py     # 工作流 CRUD
│   │   │   ├── executions.py    # 执行触发/查询
│   │   │   ├── assets.py        # 文件上传/下载
│   │   │   ├── llm.py           # Provider 管理
│   │   │   └── ws.py            # WebSocket 端点
│   │   │
│   │   ├── engine/              # DAG 执行引擎
│   │   │   ├── graph.py         # 图解析 + 拓扑排序
│   │   │   ├── scheduler.py     # 调度器
│   │   │   ├── queue.py         # SQLite 任务队列
│   │   │   ├── worker.py        # asyncio Worker
│   │   │   └── context.py       # 执行上下文
│   │   │
│   │   ├── handlers/            # 节点执行器
│   │   │   ├── base.py
│   │   │   ├── llm.py
│   │   │   ├── split.py
│   │   │   ├── text_to_image.py
│   │   │   ├── image_to_video.py
│   │   │   ├── concat.py
│   │   │   └── output.py
│   │   │
│   │   ├── llm/                 # LLM 组件层
│   │   │   ├── base.py          # 抽象接口
│   │   │   ├── registry.py      # Provider 注册表
│   │   │   ├── config.py        # 配置模型
│   │   │   └── providers/
│   │   │       ├── ollama.py
│   │   │       ├── openai_compat.py
│   │   │       └── mock.py
│   │   │
│   │   └── services/            # 外部服务适配
│   │       ├── comfyui.py
│   │       ├── ffmpeg.py
│   │       └── storage.py
│   │
│   └── scripts/
│       └── init_db.py           # 首次运行初始化
│
├── config/
│   ├── llm.yaml                 # LLM Provider 配置
│   └── app.yaml                 # 应用配置（端口、路径等）
│
└── data/                        # 运行时数据（gitignore）
    ├── flow.db                  # SQLite 数据库
    └── assets/                  # 生成的图片/视频
        ├── images/
        ├── videos/
        └── thumbnails/
四、核心模块设计
4.1 后端启动与进程内 Worker
FastAPI 启动时用 lifespan 钩子启动一个 asyncio Worker 协程，与 API 进程共存于同一 Python 进程内。无需独立 Worker 进程，无需 Celery/ARQ。

python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    await init_db()                         # 建表
    await registry.reload_from_config()     # 加载 LLM Provider
    workers = [asyncio.create_task(worker_loop(i)) for i in range(2)]
    yield
    # 关闭时
    for w in workers:
        w.cancel()

app = FastAPI(lifespan=lifespan)
4.2 SQLite 任务队列
无需 Redis，直接用 SQLite 表作为队列。SQLite 单写入者模型完全够用（本地场景下并发量低），且事务原子性天然保证不重复领取。

sql
CREATE TABLE tasks (
    id              TEXT PRIMARY KEY,
    execution_id    TEXT NOT NULL,
    node_id         TEXT NOT NULL,
    node_type       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    payload         TEXT,                    -- JSON
    result          TEXT,                    -- JSON
    error           TEXT,
    retry_count     INTEGER DEFAULT 0,
    depends_on      TEXT,                    -- JSON 数组
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP
);
CREATE INDEX idx_tasks_status ON tasks(status, created_at);
Worker 领取任务（利用 SQLite 的事务 + BEGIN IMMEDIATE 实现原子领取）：

python
async def claim_task() -> dict | None:
    async with db.transaction(immediate=True):
        row = await db.fetchone("""
            SELECT * FROM tasks
            WHERE status = 'pending'
              AND NOT EXISTS (
                  SELECT 1 FROM tasks dep
                  WHERE dep.id IN (SELECT value FROM json_each(tasks.depends_on))
                    AND dep.status != 'completed'
              )
            ORDER BY created_at ASC
            LIMIT 1
        """)
        if not row:
            return None
        await db.execute(
            "UPDATE tasks SET status='running', started_at=CURRENT_TIMESTAMP WHERE id=?",
            (row["id"],)
        )
        return row
Worker 循环：

python
async def worker_loop(worker_id: int):
    while True:
        task = await claim_task()
        if task is None:
            await asyncio.sleep(0.5)
            continue
        try:
            handler = HANDLERS[task["node_type"]]
            result = await handler.execute(json.loads(task["payload"]))
            await complete_task(task["id"], result)
            await notify_ws(task["execution_id"], task["node_id"], "completed")
        except Exception as e:
            await fail_task(task["id"], str(e))
            await notify_ws(task["execution_id"], task["node_id"], "failed")
4.3 LLM 组件层
统一接口：

python
# app/llm/base.py
class LLMProvider(ABC):
    provider_id: str
    provider_type: str

    @abstractmethod
    async def chat(self, req: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    async def stream(self, req: LLMRequest) -> AsyncIterator[str]: ...

    @abstractmethod
    async def list_models(self) -> list[str]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
三个内置 Provider：

Provider	覆盖场景	端点
OllamaProvider	本地 Ollama	http://localhost:11434/api/chat
OpenAICompatProvider	OpenAI、DeepSeek、通义千问、Moonshot、vLLM、LM Studio、LocalAI、One-API	{base_url}/v1/chat/completions
MockProvider	开发调试（无 GPU 也能跑通全链路）	返回固定文本
配置文件驱动：

yaml
# config/llm.yaml
llm:
  default_provider: local-ollama

  providers:
    - id: local-ollama
      type: ollama
      name: "本地 Ollama"
      base_url: http://localhost:11434
      models: [qwen2.5:7b, llama3.1:8b]

    - id: local-lmstudio
      type: openai_compat
      name: "LM Studio"
      base_url: http://localhost:1234
      api_key: not-needed
      models: [qwen2.5-7b-instruct]

    - id: deepseek
      type: openai_compat
      name: "DeepSeek 云端"
      base_url: https://api.deepseek.com
      api_key: ${DEEPSEEK_API_KEY}
      models: [deepseek-chat]

    - id: qwen-cloud
      type: openai_compat
      name: "通义千问"
      base_url: https://dashscope.aliyuncs.com/compatible-mode
      api_key: ${DASHSCOPE_API_KEY}
      models: [qwen-plus, qwen-max]

    - id: mock
      type: mock
      name: "调试"
      models: [mock]
热重载：POST /api/llm/reload 触发重新读取 YAML 并重建 Provider 实例，无需重启服务。前端 /settings/llm 页面可管理。

节点级指定：LLM 节点的属性面板暴露 provider_id 和 model 字段，不同节点可用不同 Provider——脚本生成用本地 Ollama，优化提示词用云端 DeepSeek，完全按需。

4.4 节点执行器
每个节点类型对应一个 Handler，实现统一接口：

python
class NodeHandler(ABC):
    @abstractmethod
    async def execute(self, payload: dict) -> dict: ...
内置 Handler：

节点类型	Handler	依赖
llm	LLMHandler	LLM Registry
text_split	TextSplitHandler	纯 Python
text_to_image	T2IHandler	ComfyUI 或云端生图 API
image_to_video	I2VHandler	ComfyUI 或云端生视频 API
video_concat	ConcatHandler	FFmpeg
output	OutputHandler	本地文件服务
新增节点类型只需：写 Handler + 在前端注册对应组件。

4.5 前端画布
React Flow 画布 + Zustand 状态：

typescript
// stores/workflowStore.ts
interface WorkflowState {
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  addNode: (type: string, position: XYPosition) => void;
  updateNodeConfig: (id: string, config: object) => void;
}
自定义节点通过 nodeTypes 注册，每个节点组件渲染：图标 + 标题 + 状态徽章 + 多个 <Handle> 连接点。属性面板根据节点类型渲染对应的配置表单。

执行时通过 WebSocket 订阅：

typescript
// api/ws.ts
const ws = new WebSocket(`ws://localhost:8000/ws/executions/${executionId}`);
ws.onmessage = (e) => {
  const event = JSON.parse(e.data);
  useExecutionStore.getState().updateNodeStatus(event.node_id, event.status);
};
4.6 本地文件服务
生成的图片/视频落 ./data/assets/，FastAPI 挂载静态目录：

python
app.mount("/assets", StaticFiles(directory="data/assets"), name="assets")
前端 <img src="http://localhost:8000/assets/images/xxx.png"> 直接展示，无需对象存储。

五、启动方式
bash
# 1. 克隆项目
git clone <repo> && cd flow-platform

# 2. 后端依赖
cd backend
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/init_db.py           # 初始化 SQLite

# 3. 前端依赖
cd ../frontend
npm install

# 4. 配置 LLM（编辑 config/llm.yaml 选择本地或远程）

# 5. 一键启动（根目录）
cd ..
npm run dev
# 等价于并行运行：
#   backend: uvicorn app.main:app --reload --port 8000
#   frontend: vite --port 5173

# 6. 访问 http://localhost:5173
根级 package.json 用 concurrently 实现一键启动：

json
{
  "scripts": {
    "dev": "concurrently -n backend,frontend -c blue,green \"npm run dev:backend\" \"npm run dev:frontend\"",
    "dev:backend": "cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000",
    "dev:frontend": "cd frontend && vite --port 5173"
  }
}
唯一系统依赖：Python 3.10+、Node 18+、FFmpeg（加入 PATH）。其余全部通过 pip/npm 安装。

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
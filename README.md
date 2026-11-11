# AI原生CRM（AI-Native CRM）

> 这只是个demo 别直接上手就用，我只是整合了这些技术，该搭框架搭框架，还有n8n，Coze，dify，在另外一套里面，下面有跟其他开源的同类型对比，别上手就用，别上手就用，别上手就用
> Python + Tornado + PostgreSQL/MySQL + NumPy，实现 **RAG、Agent + Tool Calling、Workflow Automation**，
> 预留 **ComfyUI / TTS / ASR / FFmpeg** AIGC 能力与 **Playwright / Browser-use / Airtest** 数字员工扩展。

---

## 1. 项目定位

传统 CRM 是"记录系统"，AI 原生 CRM 是"执行系统"——五层 AI 能力直接嵌入业务闭环：

| AI 能力 | 在 CRM 中的落地 | 本项目实现 |
|---|---|---|
| **RAG** | 售前资料/话术/FAQ 检索问答 | NumPy 向量库 + Embedding API + 检索增强生成 |
| **Agent + Tool Calling** | 自然语言查客户、写跟进、做统计 | OpenAI Function Calling 循环，工具直连业务库 |
| **Workflow Automation** | 新客破冰话术、跟进提醒、成交答谢 | 事件驱动规则引擎（LLM 生成 + 自动落库） |
| **AIGC** | 营销素材生成、通话语音处理 | ComfyUI 客户端 / TTS / ASR / FFmpeg 工具集 |
| **数字员工** | 浏览器/安卓端自动化操作 | Playwright（确定性）/ Browser-use（LLM 自主）/ Airtest（安卓） |

**MVP 已实现**（开箱即跑，零外部依赖）：客户表 CRUD、最小 RAG、带 Tool Calling 的 Agent、事件工作流。

## 2. 系统架构

```
┌────────────────────────────────────────────────────────────────┐
│                    Tornado API 服务层 (main.py)                  │
│   /api/customers   /api/rag/*   /api/agent/chat   /api/workflow │
└───────────────┬──────────────────────────────┬─────────────────┘
                │                              │
┌───────────────▼──────────────────────────────▼─────────────────┐
│                       AI 核心能力层 (app/ai)                     │
│                                                                 │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │   RAG   │ │  Agent   │ │ Workflow │ │  AIGC（扩展）          │ │
│  │ 检索增强 │ │ 工具调用  │ │ 事件驱动  │ │ ComfyUI/TTS/ASR/     │ │
│  │ 生成问答 │ │ 自主循环  │ │ 流程自动化 │ │ FFmpeg               │ │
│  └────┬────┘ └────┬─────┘ └────┬─────┘ └──────────┬───────────┘ │
│       │           │            │                   │             │
│  ┌────▼───────────▼────────────▼───────────────────▼───────────┐ │
│  │            LLM 客户端（OpenAI 兼容：火山方舟/DeepSeek/GLM）    │ │
│  │            未配 Key 自动降级 Mock → 全链路离线可演示           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌──────────────────── 数字员工（扩展）─────────────────────────┐ │
│  │  Playwright 浏览器自动化 │ Browser-use │ Airtest 安卓自动化   │ │
│  └─────────────────────────────────────────────────────────────┘ │
└───────────────┬─────────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────────┐
│              数据库层 (app/db)：SQLite(演示) / MySQL(生产)         │
│         customers │ follow_ups │ kb_documents（幂等建表）          │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 目录结构

```
ai-native-crm/
├── main.py                          # Tornado 启动入口（依赖组装/路由/初始化）
├── config.py                        # 全局配置（.env 加载，支持离线演示模式）
├── requirements.txt                 # 依赖清单（核心 + 扩展分组注释）
├── .env.example                     # 环境变量模板
├── app/
│   ├── handlers/                    # —— Tornado API 层 ——
│   │   ├── base.py                  #   统一响应/错误处理/CORS/健康检查
│   │   ├── customer_handler.py      #   客户 CRUD + 跟进记录（创建即触发工作流）
│   │   ├── rag_handler.py           #   RAG 问答 / 知识导入 / 文档列表
│   │   ├── agent_handler.py         #   Agent 对话（返回 answer + steps 执行轨迹）
│   │   └── workflow_handler.py      #   工作流手动触发（调试/演示）
│   ├── services/
│   │   └── customer_service.py      # 客户领域服务（API 与 Agent 工具共用）
│   ├── ai/                          # —— AI 核心能力层 ——
│   │   ├── llm/client.py            #   LLM客户端：OpenAI兼容 + Mock离线演示
│   │   ├── rag/
│   │   │   ├── embedder.py          #   向量化：API / 本地hash双实现
│   │   │   ├── vector_store.py      #   NumPy 余弦检索向量库
│   │   │   ├── pipeline.py          #   RAG管道：索引 + 检索增强问答
│   │   │   └── seed_docs.py         #   内置种子知识库（首启自动导入）
│   │   ├── agent/
│   │   │   ├── tools.py             #   CRM工具Schema与实现（查/写/统计）
│   │   │   └── agent.py             #   Agent循环：LLM⇄Tool，带steps轨迹
│   │   ├── workflow/engine.py       #   事件驱动工作流引擎（内置3条AI规则）
│   │   ├── aigc/                    #   —— AIGC 能力（扩展，按需启用）——
│   │   │   ├── comfyui.py           #   ComfyUI 客户端（文生图/排队/下载）
│   │   │   ├── tts.py               #   语音合成（Edge-TTS免费 / 方舟骨架）
│   │   │   ├── asr.py               #   语音转写（faster-whisper本地）
│   │   │   └── ffmpeg.py            #   视频后处理（去水印/字幕/换音轨/拼接）
│   │   └── digital_employee/        #   —— 数字员工（扩展，按需启用）——
│   │       ├── browser_playwright.py#   确定性浏览器自动化（采集/登录）
│   │       ├── browser_use_worker.py#   LLM自主浏览器操作（Browser-use）
│   │       └── android_airtest.py   #   安卓自动化（企微自动跟进）
│   └── db/
│       └── database.py              # 数据库门面：SQLite/MySQL双后端，SQL方言屏蔽
├── scripts/
│   └── seed_data.py                 # 演示客户数据导入（可选）
└── tests/
    └── smoke_test.py                # 全链路冒烟测试（含Agent/RAG/工作流）
```

## 4. 快速开始

### 4.1 环境要求

- Python 3.10+（开发环境 3.12 验证通过）
- 无需预装数据库：默认 SQLite 零配置演示；无需 LLM Key：自动离线演示模式

### 4.2 安装与启动

**方式一：一键脚本（推荐）**

```bash
start.bat        # Windows 双击启动：自动定位Python3.10+ → 缺依赖自动装 → 首次生成.env → 起服务
stop.bat         # 停止服务（按端口精准结束进程）
run_smoke.bat    # 一键冒烟测试（服务未起会自动拉起）
./start.sh       # Linux / macOS
```

**方式二：手动命令**

```bash
cd ai-native-crm
pip install -r requirements.txt     # 核心依赖很小（tornado/numpy/httpx/aiosqlite）
python main.py                       # 启动，默认 http://127.0.0.1:8888
```

启动后自动完成：建表 → 导入种子知识库(5篇) → 重建 RAG 索引 → 服务就绪。

### 4.3 启用真实 LLM（推荐）

复制 `.env.example` 为 `.env`，配置任意 OpenAI 兼容平台：

```ini
# 火山方舟（默认）
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_API_KEY=你的Key
LLM_MODEL=doubao-seed-evolving-v1.5     # 或接入点 ep-xxxx
EMBEDDING_MODEL=                        # 留空=本地向量；填 doubao-embedding 系列启用语义检索

# 或 DeepSeek：LLM_BASE_URL=https://api.deepseek.com  LLM_MODEL=deepseek-chat
# 或 智谱GLM：LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4  LLM_MODEL=glm-4-flash
```

### 4.4 切换生产数据库（MySQL）

```ini
DB_BACKEND=mysql
MYSQL_HOST=127.0.0.1
MYSQL_USER=root
MYSQL_PASSWORD=***
MYSQL_DATABASE=ai_crm       # 需先建库：CREATE DATABASE ai_crm DEFAULT CHARSET utf8mb4;
```

建表由启动时 `init_schema()` 幂等完成，无需手工执行 SQL。
PostgreSQL：按 `app/db/database.py` 的接口实现 asyncpg 版门面即可，业务层零改动。

### 4.5 冒烟验证

```bash
python scripts/seed_data.py      # 可选：导入8位演示客户
python tests/smoke_test.py       # 全链路冒烟：CRUD/RAG/Agent/Workflow 共14项断言
```

## 5. API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查（返回LLM/Embedding模式、数据规模） |
| GET | `/api/customers?keyword=&status=&page=` | 客户分页列表/搜索 |
| POST | `/api/customers` | 创建客户（**自动触发工作流生成破冰话术**） |
| GET/PATCH/DELETE | `/api/customers/{id}` | 客户详情 / 更新阶段 / 删除 |
| GET/POST | `/api/customers/{id}/follow_ups` | 跟进记录（写入即生成下次跟进建议） |
| POST | `/api/rag/query` | RAG 问答：`{"question": "价格是多少"}` |
| POST | `/api/rag/index` | 批量导入知识：`{"documents": [{"title","content"}]}` |
| GET | `/api/rag/documents` | 知识库文档列表 |
| POST | `/api/agent/chat` | Agent 对话：`{"message": "查一下意向客户"}` |
| POST | `/api/workflow/trigger` | 手动触发工作流（调试用） |

### 体验示例

```bash
# Agent 自然语言查客户（真实执行SQL工具，返回执行轨迹）
curl -X POST http://127.0.0.1:8888/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我查一下智能制造行业的客户"}'

# Agent 做统计
curl -X POST http://127.0.0.1:8888/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "统计一下销售漏斗各阶段情况"}'

# RAG 知识问答
curl -X POST http://127.0.0.1:8888/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question": "客户嫌价格贵怎么回"}'
```

Agent 响应结构（steps 为可观测执行轨迹）：

```json
{
  "code": 0, "data": {
    "answer": "找到1位智能制造行业客户：李思颖（深圳市星河智造科技）...",
    "steps": [
      {"iteration": 1, "tool": "search_customers",
       "arguments": {"keyword": "智能制造"},
       "output": {"count": 1, "customers": [{"id": 2, "name": "李思颖", "...": "..."}]},
       "status": "ok"}
    ]
  }
}
```

## 6. 核心设计说明

### 6.1 RAG（`app/ai/rag/`）

- **双实现可切换**：`APIEmbedder`（OpenAI 兼容 `/embeddings`）/ `MockEmbedder`（本地 bigram-hash 确定性向量），配置驱动，离线可测；
- **NumPy 向量库**：向量归一化后余弦检索退化为点积（矩阵乘），十万级文档内性能充裕；接口与 pgvector/Milvus 对齐，替换无侵入；
- **知识即数据**：文档存 `kb_documents` 表，启动时全量重建索引，无缓存一致性问题；
- **可解释**：回答附带 `sources`（文档标题、相似度、片段）。

### 6.2 Agent（`app/ai/agent/`）

- 标准 **ReAct 循环**：`LLM推理 → tool_calls → 执行 → 结果回填 → 继续推理`，`max_iterations` 防死循环；
- **工具即业务能力**：5 个工具（搜索/详情/写跟进/改阶段/统计）直接复用 `CustomerService`，AI 与人工共享同一套校验规则；
- **失败自愈**：工具异常不中断循环，错误信息回填 LLM 自我修正（如参数缺失时自动补齐重试）；
- **可观测**：`steps` 记录每轮工具调用与结果，支撑前端渲染"AI 做了什么"与审计。

### 6.3 Workflow（`app/ai/workflow/engine.py`）

事件驱动：`trigger(event, payload) → 规则匹配 → 顺序执行`。内置规则演示 AI 原生闭环：

| 事件 | 触发时机 | AI 动作 |
|---|---|---|
| `customer.created` | 创建客户接口调用后 | LLM 生成行业化破冰话术 → **自动写入首条跟进** |
| `follow_up.created` | 写入跟进后 | LLM 生成下次跟进时机与切入建议 |
| `customer.won` | 客户阶段改为 won | LLM 生成答谢+转介绍话术 |

业务代码零侵入接入：`engine.register("your.event", async_handler)`。

## 7. 扩展指南

### 7.1 对接 ComfyUI（AIGC 素材生成）

**模块**：`app/ai/aigc/comfyui.py`（完整客户端：提交/轮询/下载/文生图模板）

```bash
# 前置：本机 ComfyUI 已启动（默认 http://127.0.0.1:8188，可在.env改COMFYUI_URL）
python -m app.ai.aigc.comfyui        # 跑通演示（生成营销图）
```

代码接入：

```python
from app.ai.aigc.comfyui import ComfyUIClient

client = ComfyUIClient()             # 或读 CONFIG.comfyui_url
files = await client.text2image(prompt="SaaS CRM宣传海报...", checkpoint="你的模型.safetensors")
```

进阶：把文生图注册为工作流动作或 Agent 工具（在 `tools.py` 增加 schema + 实现），即可"自然语言生成营销素材"；图生视频（首帧参考） workflow 同样通过 `submit()/wait_result()` 提交，配合 `ffmpeg.py` 完成去水印、字幕、换音轨后处理。

### 7.2 浏览器自动化（数字员工）

**两条技术路线按场景分工**：

| 路线 | 模块 | 适用 | 启用 |
|---|---|---|---|
| Playwright（确定性） | `digital_employee/browser_playwright.py` | 固定流程：线索采集、定时登录导报表 | `pip install playwright && playwright install chromium` |
| Browser-use（LLM自主） | `digital_employee/browser_use_worker.py` | 页面多变/探索任务：竞品调研、信息核验 | `pip install browser-use && playwright install chromium` + 配置 `LLM_API_KEY` |

```bash
python -m app.ai.digital_employee.browser_playwright   # 页面采集/截图演示
python -m app.ai.digital_employee.browser_use_worker   # 自然语言驱动浏览器（需LLM Key）
```

落地编排示例：WorkflowEngine 注册定时规则 → `crawl_leads_from_page()` 采集 →
调用 `POST /api/customers` 入库 → 自动触发破冰话术工作流。**采集→入库→跟进建议全链无人值守**。

### 7.3 Android 自动化（移动端数字员工）

**模块**：`digital_employee/android_airtest.py`（企业微信自动跟进骨架）

```bash
pip install airtest          # 前置：adb devices 可见真机/模拟器
```

生产编排：查询 `next_follow_up_at <= now` 的客户 → LLM 生成个性化话术 →
`run_followup_batch()` 批量发送 → 写回跟进记录（channel=`wecom_auto`）。
Airtest 为同步 API，接入 Tornado 用 `run_in_executor` 包装即可（模块注释含示例）。

### 7.4 TTS / ASR / FFmpeg 多媒体管线

```bash
pip install edge-tts faster-whisper    # 免费方案
python -m app.ai.aigc.tts              # 话术合成语音（外呼/企微语音跟进）
python -m app.ai.aigc.asr 通话录音.wav  # 通话录音转写
python -m app.ai.aigc.ffmpeg           # 视频后处理工具演示
```

组合链路（销售语音闭环）：通话录音 → `asr.transcribe()` → LLM 提取需求/异议/下一步（`asr.llm_extract_follow_up()`）→ Agent 写入跟进记录；话术 → `tts.synthesize()` → 企微语音/AI外呼。
AIGC 视频链路：ComfyUI 生成片段 → `FFmpegToolkit.postprocess_ai_clip()`（去水印→字幕→换原声）→ 素材库归档。

### 7.5 生产化演进路线

| 方向 | MVP现状 | 演进 |
|---|---|---|
| 数据库 | SQLite/MySQL 双后端 | PostgreSQL(asyncpg)、读写分离、迁移工具(alembic) |
| 向量检索 | NumPy 内存库 | pgvector / Milvus，支持增量索引与混合检索(BM25+向量) |
| Agent | 单轮任务 | 多Agent协作(规划/执行/审查)、记忆(会话表)、LangSmith式轨迹回放 |
| Workflow | 内存规则 | 规则持久化+可视化编排、定时触发(APScheduler)、人工审批节点、重试/死信 |
| 权限 | 单租户 | JWT认证、RBAC、多租户隔离、操作审计 |
| 可观测 | steps日志 | OpenTelemetry 全链路追踪、LLM成本/质量监控 |

## 8. 开发节奏（已完成 MVP，后续迭代）

- **MVP（本次交付）**：客户表+跟进记录、最小RAG、Agent Tool Calling、事件工作流、冒烟测试 ✅
- **T1**：接入真实LLM/Embedding全链路验证、RAG文档管理界面、Agent会话记忆
- **T2**：ComfyUI素材生成注册为Agent工具；通话ASR→LLM→自动跟进闭环
- **T3**：数字员工编排（Playwright线索采集→入库→跟进建议全链）；企微Airtest跟进
- **T4**：认证/多租户/权限；工作流可视化；向量化生产组件(pgvector)

---

**演示数据**：`python scripts/seed_data.py` 导入 8 位各阶段演示客户；知识库 5 篇文档首启自动导入。

**验证方式**：`python tests/smoke_test.py`（14 项）+ `python tests/edge_test.py`（13 项，错误路径/并发/Agent自我修正）——离线演示模式下即可全绿，CI 同款（`.github/workflows/ci.yml`）。

**竞品对比与优化路线**：见 [docs/competitive-analysis.md](docs/competitive-analysis.md)（对比 Twenty CRM / NocoBase / Comp AI 等同类项目，含真实差距清单与 P0-P2 优化方案）。

# 竞品对比分析与优化路线（Competitive Analysis & Roadmap）

> 基于全量功能实测（smoke 14 项 + edge 13 项，含并发/异常路径）的诚实复盘：
> 我们做对了什么、与市面同类项目的真实差距在哪、下一步怎么补。
> 评测时间：2026-11。

---

## 1. 自测报告

### 1.1 测试覆盖与结果

| 套件 | 用例数 | 结果 |
|---|---|---|
| `tests/smoke_test.py` 全链路冒烟 | 14 | 全部通过 |
| `tests/edge_test.py` 边界与异常路径 | 13 | 全部通过（1 项按运行模式跳过语义断言，见 1.2） |

已验证能力：客户 CRUD 全路径、参数校验（400/404 业务错误而非 500）、RAG 检索命中与来源引用、Agent 工具调用真实落库（含写操作）、Agent 工具错误回填不中断、工作流三类事件闭环、10 并发请求、未知事件容错。

### 1.2 实测发现的问题（诚实清单）

1. **Mock 向量假阳性**（已定位）：离线模式的 bigram-hash 向量无语义能力，无关问题（如"薛定谔方程"）会因字符 n-gram 偶然重叠命中知识库（相似度阈值 0.05 过低）。已将该用例改为仅在 API Embedding 模式下做严格断言。**结论：Mock 只用于链路演示，语义检索质量必须依赖真实 Embedding。**
2. **无认证**：所有接口（含 DELETE）裸奔，`Access-Control-Allow-Origin: *`。演示可接受，部署即事故。
3. **Agent 无服务端会话记忆**：多轮对话需客户端自行传 `history`，服务端不落库。
4. **无流式输出**：Agent/RAG 回答需等待全量生成，长回答体验差。

---

## 2. 市面同类项目对比

对比对象选取（2026 年活跃度与代表性）：

- **Twenty CRM**（开源，AI-native 后起之秀）：数据聊天、workflow 内自主 Agent、MCP Server、Apps 扩展框架
- **NocoBase**（开源低代码平台 + CRM）：AI Agent + 工作流集成、自动洞察、RBAC、自托管
- **Comp AI CRM**（开源，agentic-first）：持久化研究 Agent 自动丰富联系人/公司/商机（"数据库即 Agent 笔记"）
- **EspoCRM / Odoo**（传统开源 + AI 外挂）：OpenAI 集成架构 / 企业版 AI
- **Salesforce Agentforce / 销售易 / 纷享销客**（商业标杆）：Agent 编排平台、行业模型、全链路合规

| 能力维度 | 本项目 (MVP) | Twenty CRM | NocoBase | Comp AI | 商业标杆 |
|---|---|---|---|---|---|
| 客户/商机数据模型 | ✅ 五阶段漏斗（单表） | ✅✅ 自定义对象/字段/关系 | ✅✅ 低代码建模 | ✅ | ✅✅ 行业模型 |
| RAG 知识问答 | ✅ 纯向量+来源引用 | —（以数据问答为主） | ✅ | — | ✅✅ 企业知识图谱 |
| Agent + Tool Calling | ✅ 5工具/错误自愈/steps轨迹 | ✅✅ workflow内自主agent | ✅ | ✅✅ 常驻durable agent | ✅✅ 多agent编排 |
| 工作流自动化 | ✅ 内存规则/3内置事件 | ✅✅ 可视化编排 | ✅✅ 可视化+定时 | ✅ | ✅✅ 审批/重试/SLA |
| AIGC（图/音/视频） | ✅ 客户端demo（ComfyUI/TTS/ASR/FFmpeg） | ❌ | ❌ | ❌ | 部分（营销云） |
| 数字员工（浏览器/安卓） | ✅ demo骨架 | ❌ | ❌ | ❌ | ✅（Einstein/销售易部分） |
| 前端 UI | ❌ 纯 API | ✅✅ 看板/表格/自动化 | ✅✅ | ✅ | ✅✅ |
| 认证与权限 | ❌ | ✅✅ RBAC | ✅✅ RBAC | ✅ | ✅✅ 多租户 |
| MCP 协议 | ❌ | ✅ | 部分 | ❌ | ✅ |
| 部署体验 | 脚本启动 | Docker/云 | Docker/云 | Docker | SaaS |
| 测试/CI | ✅ 27项集成测试 | ✅ | ✅ | ✅ | 商业级 |

### 2.1 我们的差异化优势（值得保留并放大）

1. **AIGC + 数字员工是独有牌**：对比对象没有一个内置 ComfyUI/TTS/ASR/FFmpeg 多媒体管线与 Playwright/Browser-use/Airtest 三端自动化——这是"AI 应用开发工程师"岗位最直接的能力证明，也是真实业务（营销素材生产、无人值守线索采集）的方向。
2. **零配置离线演示**：无 Key、无数据库全链路可跑，27 项测试离线全绿——竞品普遍需要 Docker + 外部服务才能起。
3. **Agent 可观测性**：steps 轨迹返回是面试演示的加分设计。

### 2.2 真实差距（按严重度排序）

| # | 差距 | 对标 | 影响 |
|---|---|---|---|
| G1 | 无认证/权限/多租户 | 全部竞品 | 不可用于生产 |
| G2 | 无前端 | 全部竞品 | 演示感染力大打折扣 |
| G3 | 数据模型单薄（无自定义字段、无导入导出） | Twenty/NocoBase | 只能演示不能实用 |
| G4 | RAG 策略原始：整篇单向量、无分块/混合检索/重排序 | NocoBase/商业标杆 | 长文档检索质量受限 |
| G5 | Agent 无会话记忆/流式输出/多 Agent | Twenty/Comp AI | 体验与工程完整度差距 |
| G6 | 工作流不可视化、无定时/审批/重试 | Twenty/NocoBase | 自动化深度不足 |
| G7 | 扩展模块未接线：AIGC 与数字员工是 demo 而非服务内能力 | Twenty Apps/MCP | 亮点没进主链路 |
| G8 | 无 Docker/CI、无单元测试 | 全部竞品 | 开源项目门面缺失 |
| G9 | 单 SQLite 连接/单进程，无缓存与水平扩展设计 | 全部竞品 | 性能天花板低 |

---

## 3. 优化方案（按优先级，可直接转为 Issue）

### P0 — 开源门面与安全（上 GitHub 前后两周内）

| 项 | 方案 | 对应差距 |
|---|---|---|
| 认证与RBAC | JWT 登录 + 角色（admin/sales/viewer）中间件；CORS 白名单化 | G1 |
| CI | GitHub Actions：push 时跑 `smoke_test + edge_test`（sqlite 模式零外部依赖，天然适合 CI）+ ruff lint | G8 |
| Docker | `Dockerfile`（python:3.12-slim）+ `docker-compose.yml`（app + mysql + 可选 pgvector） | G8/G9 |
| 单元测试 | pytest 覆盖 CustomerService/VectorStore/MockEmbedder（数据库用内存 sqlite） | G8 |
| 门面资产 | LICENSE(MIT)、`CONTRIBUTING.md`、英文 README（双语）、GitHub Topics/Actions 徽章 | G8 |

### P1 — AI 核心能力补强（1~2 个月）

| 项 | 方案 | 对应差距 |
|---|---|---|
| RAG 升级 | 文档分块（语义 512 token + overlap）；混合检索（SQLite FTS5/BM25 + 向量加权融合）；接 Rerank API；阈值与 top-k 自适应 | G4 |
| 向量库演进 | 保持 `VectorStore` 接口不变，落地 `pgvector` 实现（compose 一键起）；索引增量更新替代全量重建 | G4/G9 |
| Agent 会话 | `conversations`/`messages` 表存多轮历史；Agent 自动携带近 N 轮；总结式长记忆 | G5 |
| 流式输出 | Tornado SSE handler，LLM 客户端改流式（OpenAI `stream=true`），steps 事件化推送 | G5 |
| AIGC 接线 | ComfyUI/TTS 注册为 Agent 工具与 REST 路由（`/api/aigc/*`）；素材生成进 workflow 动作 | G7 |
| 工作流增强 | 规则落库 + APScheduler 定时触发（如"3天未跟进自动提醒"）；失败重试 | G6 |

### P2 — 产品化与差异化放大（2~3 个月）

| 项 | 方案 | 对应差距 |
|---|---|---|
| 前端 | Vue 3 + Vite + Element Plus + Pinia + ECharts：客户看板、Agent 对话（流式+steps 时间线）、知识库管理、工作流配置 | G2 |
| 数据模型 | 自定义字段（EAV/JSON 列）；CSV/Excel 导入导出（openpyxl） | G3 |
| 数字员工中心 | 任务编排 API：Playwright 采集 → 入库 → 破冰话术 → 企微 Airtest 发送，全链无人值守；执行日志与截图留痕 | G7 |
| MCP Server | 将 CRM 工具暴露为 MCP 协议（Twenty 已验证此路线），让任意 AI 客户端直接操作本 CRM | G6/G7 |
| 可观测 | OpenTelemetry trace（请求/LLM调用/工具执行三层）；LLM token 成本统计表与看板 | G5 |
| 多租户 | tenant_id 隔离 + 管理员赋权（对齐"管理员直接创建租户"的产品设定） | G1 |

### 3.1 一句话定位建议

> 不做"更好的 Twenty"，做 **"自带 AIGC 内容工厂与三端数字员工的轻量 AI-CRM 内核"**——
> 后端 API + Agent 内核足够轻（对比 Twenty 的重型全栈），但 AI 能力半径（图/音/视频/浏览器/安卓）是独家的。
> 前端用 Vue 3 补齐演示体验后，这套定位在开源市场有清晰空档。

---

## 4. 已知限制（README 同步声明）

- 离线 Mock 模式的检索为词法级（bigram），存在假阳性命中，仅用于链路演示；
- MySQL 后端已实现但未在 CI 中覆盖（无固定 MySQL 实例），建议 compose 起 mysql 后扩展 CI 矩阵；
- AIGC 与数字员工模块需按需安装扩展依赖（见 requirements.txt 注释），默认不随主服务启动。

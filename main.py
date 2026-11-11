"""AI原生CRM —— Tornado 启动入口。

启动流程：
  连接数据库(幂等建表) → 导入种子知识库(首次) → 重建RAG索引
  → 组装依赖容器(db/rag/agent/workflow) → 监听端口

运行：python main.py
"""
import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import tornado.web

sys.path.insert(0, str(Path(__file__).parent))  # 保证 app.* 可导入

from app.ai.agent.agent import CRMAgent  # noqa: E402
from app.ai.agent.tools import build_tool_registry  # noqa: E402
from app.ai.llm.client import LLMClient  # noqa: E402
from app.ai.rag.embedder import build_embedder  # noqa: E402
from app.ai.rag.pipeline import RAGPipeline  # noqa: E402
from app.ai.rag.seed_docs import ensure_kb_seed  # noqa: E402
from app.ai.rag.vector_store import NumpyVectorStore  # noqa: E402
from app.ai.workflow.engine import WorkflowEngine  # noqa: E402
from app.db.database import Database  # noqa: E402
from app.handlers import (AgentChatHandler, AigcStatusHandler,  # noqa: E402
                          AigcText2ImageHandler, CustomerDetailHandler,
                          CustomerListHandler, FollowUpListHandler, HealthHandler,
                          RAGDocumentListHandler, RAGIndexHandler, RAGQueryHandler,
                          StatsHandler, WorkflowTriggerHandler)
from app.services.customer_service import CustomerService  # noqa: E402
from config import CONFIG  # noqa: E402

STATIC_DIR = Path(__file__).parent / "app" / "static"


class IndexHandler(tornado.web.RequestHandler):
    """GET / —— 可视化管理台（单文件前端，见 app/static/index.html）。"""

    async def get(self) -> None:
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.finish((STATIC_DIR / "index.html").read_bytes())

logging.basicConfig(
    level=logging.DEBUG if CONFIG.debug else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("main")

ROUTES = [
    (r"/", IndexHandler),
    (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": STATIC_DIR}),
    (r"/api/health", HealthHandler),
    # ---- 客户 / 跟进 ----
    (r"/api/customers", CustomerListHandler),
    (r"/api/customers/(\d+)", CustomerDetailHandler),
    (r"/api/customers/(\d+)/follow_ups", FollowUpListHandler),
    (r"/api/stats", StatsHandler),
    # ---- AIGC（ComfyUI）----
    (r"/api/aigc/text2image", AigcText2ImageHandler),
    (r"/api/aigc/status", AigcStatusHandler),
    (r"/aigc/(.*)", tornado.web.StaticFileHandler, {"path": Path(__file__).parent / "data" / "aigc"}),
    # ---- RAG 知识库 ----
    (r"/api/rag/query", RAGQueryHandler),
    (r"/api/rag/index", RAGIndexHandler),
    (r"/api/rag/documents", RAGDocumentListHandler),
    # ---- Agent ----
    (r"/api/agent/chat", AgentChatHandler),
    # ---- Workflow ----
    (r"/api/workflow/trigger", WorkflowTriggerHandler),
]


class Application(tornado.web.Application):
    def __init__(self, ctx: SimpleNamespace) -> None:
        super().__init__(ROUTES, debug=CONFIG.debug)
        self.ctx = ctx  # 依赖容器，Handler 通过 self.ctx 访问


async def build_context() -> SimpleNamespace:
    """组装并初始化所有模块（依赖注入）。"""
    # 1) 数据库
    db = Database(CONFIG)
    await db.connect()
    await db.init_schema()

    # 2) 首次启动：导入种子知识库，保证 RAG 开箱可用
    imported = await ensure_kb_seed(db)
    if imported:
        logger.info("已导入种子知识库 %s 篇", imported)

    # 3) AI 能力组装
    llm = LLMClient(CONFIG)
    embedder = build_embedder(CONFIG)
    store = NumpyVectorStore()
    rag = RAGPipeline(llm, embedder, store, db)
    kb_total = await rag.rebuild_index()
    logger.info("RAG索引就绪：%s 篇文档（embedding=%s）", kb_total,
                "API" if CONFIG.use_api_embedding else "本地Mock")

    customers = CustomerService(db)
    agent = CRMAgent(llm, build_tool_registry(customers))
    workflow = WorkflowEngine(llm, customers)

    return SimpleNamespace(
        db=db, llm=llm, embedder=embedder, store=store,
        rag=rag, customers=customers, agent=agent, workflow=workflow,
    )


async def main() -> None:
    ctx = await build_context()
    app = Application(ctx)
    app.listen(CONFIG.port)

    banner = f"""
============================================================
  AI原生CRM (MVP) 已启动  http://127.0.0.1:{CONFIG.port}
------------------------------------------------------------
  数据库      : {CONFIG.db_backend} ({'演示模式' if CONFIG.db_backend == 'sqlite' else '生产'})
  LLM 模式    : {'API已接入 - ' + CONFIG.llm_model if CONFIG.llm_configured else '离线演示(Mock)——配置 .env LLM_API_KEY 启用'}
  Embedding  : {'API - ' + CONFIG.embedding_model if CONFIG.use_api_embedding else '本地Mock向量'}
  知识库文档  : {ctx.store.size} 篇
------------------------------------------------------------
  快速体验:
   GET  /api/health                      健康检查
   POST /api/agent/chat                  AI销售助理对话
   POST /api/rag/query                   RAG知识问答
   POST /api/customers                   创建客户(自动触发工作流)
   完整API见 README.md
============================================================"""
    print(banner)
    await asyncio.Event().wait()  # 常驻运行


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务已停止")

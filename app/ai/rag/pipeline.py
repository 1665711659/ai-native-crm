"""RAG Pipeline：知识库索引 + 检索增强问答。

流程：
  索引:  kb_documents 表 → Embedder 批量向量化 → NumpyVectorStore
  问答:  question → 向量化 → Top-K 检索 → 拼装上下文 → LLM 生成（带来源）

未配置 LLM Key 时自动退化为「纯检索模式」：直接返回命中的知识片段，
保证接口离线可用；配置后即为完整 RAG 问答。
"""
import json
from datetime import datetime

from app.ai.llm.client import LLMClient
from app.ai.rag.embedder import BaseEmbedder
from app.ai.rag.vector_store import NumpyVectorStore

RAG_SYSTEM_PROMPT = (
    "你是「智赢CRM」的售前/销售知识助手。请严格根据下方【知识库检索结果】回答用户问题，"
    "不要编造知识库中没有的内容；若检索结果无法回答，请如实说明并建议转人工。"
    "回答需简洁、结构清晰（适当使用列表），并在结尾以 [来源: 文档标题] 标注引用。"
)


class RAGPipeline:
    def __init__(self, llm: LLMClient, embedder: BaseEmbedder,
                 store: NumpyVectorStore, db) -> None:
        self.llm = llm
        self.embedder = embedder
        self.store = store
        self.db = db

    # ------------------------------------------------------------------
    # 索引管理
    # ------------------------------------------------------------------
    async def index_documents(self, documents: list[dict]) -> dict:
        """批量导入知识文档并重建索引。documents: [{title, content, source?}]"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for doc in documents:
            if not (doc.get("title") or "").strip() or not (doc.get("content") or "").strip():
                raise ValueError(f"知识文档缺少 title/content: {doc}")
            await self.db.execute(
                "INSERT INTO kb_documents (title, content, source, created_at) VALUES (?,?,?,?)",
                (doc["title"].strip(), doc["content"].strip(), doc.get("source", ""), now),
            )
        total = await self.rebuild_index()
        return {"imported": len(documents), "kb_total": total}

    async def rebuild_index(self) -> int:
        """从 kb_documents 全量重建向量索引（启动时调用；文档量小，重建成本低）。"""
        rows = await self.db.fetch_all(
            "SELECT id, title, content, source FROM kb_documents ORDER BY id"
        )
        if not rows:
            self.store.build([], np_empty(len(rows), 1))
            return 0
        vectors = await self.embedder.embed([r["content"] for r in rows])
        return self.store.build(rows, vectors)

    async def list_documents(self) -> list[dict]:
        return await self.db.fetch_all(
            "SELECT id, title, source, created_at FROM kb_documents ORDER BY id DESC"
        )

    # ------------------------------------------------------------------
    # 检索问答
    # ------------------------------------------------------------------
    async def query(self, question: str, top_k: int = 3) -> dict:
        if not (question or "").strip():
            raise ValueError("问题不能为空")

        qvec = (await self.embedder.embed([question]))[0]
        hits = self.store.search(qvec, top_k=top_k)
        sources = [
            {
                "id": h["doc"]["id"],
                "title": h["doc"]["title"],
                "score": h["score"],
                "snippet": h["doc"]["content"][:120],
            }
            for h in hits
        ]
        if not hits:
            return {"answer": "知识库中未检索到相关内容，建议补充知识文档或转人工处理。", "sources": []}

        context = "\n\n".join(
            f"【文档{i + 1}】{h['doc']['title']}\n{h['doc']['content']}" for i, h in enumerate(hits)
        )

        # 离线演示：纯检索模式
        if not self.llm.cfg.llm_configured:
            return {
                "answer": "[纯检索模式·未配置LLM] 命中知识片段：\n\n" + context,
                "sources": sources,
            }

        result = await self.llm.chat([
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": f"【知识库检索结果】\n{context}\n\n【用户问题】{question}"},
        ], temperature=0.3)
        return {"answer": result.content, "sources": sources}


def np_empty(n: int, d: int):
    """延迟导入占位（避免顶层 import numpy 与类型注解冲突的小工具）。"""
    import numpy as np
    return np.zeros((n, d))

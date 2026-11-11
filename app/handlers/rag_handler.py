"""RAG 知识库问答接口。"""
from app.handlers.base import ApiError, BaseHandler


class RAGQueryHandler(BaseHandler):
    """POST /api/rag/query  {question, top_k?}"""

    async def post(self) -> None:
        body = self.get_json_body()
        top_k = min(int(body.get("top_k", 3) or 3), 10)
        try:
            result = await self.ctx.rag.query(body.get("question", ""), top_k=top_k)
        except ValueError as e:
            raise ApiError(str(e)) from e
        self.ok(result)


class RAGIndexHandler(BaseHandler):
    """POST /api/rag/index  {documents: [{title, content, source?}]}  批量导入知识并重建索引"""

    async def post(self) -> None:
        body = self.get_json_body()
        documents = body.get("documents")
        if not isinstance(documents, list) or not documents:
            raise ApiError("documents 必须是非空数组: [{title, content, source?}]")
        try:
            result = await self.ctx.rag.index_documents(documents)
        except ValueError as e:
            raise ApiError(str(e)) from e
        self.ok(result)


class RAGDocumentListHandler(BaseHandler):
    """GET /api/rag/documents  知识库文档列表"""

    async def get(self) -> None:
        items = await self.ctx.rag.list_documents()
        self.ok({"items": items, "total": len(items)})

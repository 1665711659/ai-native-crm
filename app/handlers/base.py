"""Handler 基类：统一 JSON 响应、异常处理、CORS、依赖容器访问。"""
import json
import logging
import traceback

import tornado.web

from config import CONFIG

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """业务异常：message 直接返回给客户端。"""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


class BaseHandler(tornado.web.RequestHandler):
    """所有业务 Handler 的基座。"""

    def set_default_headers(self) -> None:
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")

    def options(self) -> None:  # CORS 预检
        self.set_status(204)
        self.finish()

    # ------------------------------------------------------------------
    # 统一响应
    # ------------------------------------------------------------------
    def ok(self, data=None, msg: str = "ok") -> None:
        self._write_json({"code": 0, "msg": msg, "data": data})

    def fail(self, msg: str, status: int = 400) -> None:
        self.set_status(status)
        self._write_json({"code": 1, "msg": msg, "data": None})

    def _write_json(self, payload: dict) -> None:
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.finish(json.dumps(payload, ensure_ascii=False, default=str))

    def write_error(self, status_code: int, **kwargs) -> None:
        """统一错误出口：ApiError 返回业务信息，未知异常返回500（debug时带堆栈）。"""
        exc = kwargs.get("exc_info")
        if exc and isinstance(exc[1], ApiError):
            self.fail(str(exc[1]), status=exc[1].status)
            return
        if exc:
            logger.error("未处理异常: %s", "".join(traceback.format_exception(*exc)))
        detail = "".join(traceback.format_exception(*exc)) if (exc and CONFIG.debug) else ""
        self.fail(detail or "服务内部错误，请稍后重试", status=500)

    # ------------------------------------------------------------------
    # 便捷工具
    # ------------------------------------------------------------------
    @property
    def ctx(self):
        """依赖容器（main.py 中注入：db / rag / agent / customers / workflow ...）。"""
        return self.application.ctx

    def get_json_body(self) -> dict:
        try:
            data = json.loads(self.request.body or b"{}")
            if not isinstance(data, dict):
                raise ValueError("body必须是JSON对象")
            return data
        except json.JSONDecodeError as e:
            raise ApiError(f"请求体不是合法JSON: {e}") from e

    @staticmethod
    def to_int(value, default: int, name: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ApiError(f"参数 {name} 必须是整数") from None


class HealthHandler(BaseHandler):
    """GET /api/health —— 健康检查与运行时信息。"""

    async def get(self) -> None:
        customers = await self.ctx.db.fetch_one("SELECT COUNT(*) AS c FROM customers")
        kb = await self.ctx.db.fetch_one("SELECT COUNT(*) AS c FROM kb_documents")
        self.ok({
            "service": "ai-native-crm",
            "version": "0.1.0-mvp",
            "db_backend": CONFIG.db_backend,
            "llm_mode": "api" if CONFIG.llm_configured else "mock(离线演示)",
            "embedding_mode": "api" if CONFIG.use_api_embedding else "mock(本地向量)",
            "customers": int(customers["c"]) if customers else 0,
            "kb_documents": int(kb["c"]) if kb else 0,
        })

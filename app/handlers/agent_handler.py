"""Agent 对话接口。"""
from app.handlers.base import ApiError, BaseHandler


class AgentChatHandler(BaseHandler):
    """POST /api/agent/chat  {message, history?: [{role, content}]}

    返回 {answer, steps}：steps 为工具调用执行轨迹（可观测性），
    前端可据此渲染「AI做了什么」，也便于调试与审计。
    """

    async def post(self) -> None:
        body = self.get_json_body()
        message = (body.get("message") or "").strip()
        if not message:
            raise ApiError("message 不能为空")
        history = body.get("history") or []
        if not isinstance(history, list):
            raise ApiError("history 必须是 [{role, content}] 数组")

        result = await self.ctx.agent.run(message, history=history)
        self.ok(result)

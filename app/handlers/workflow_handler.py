"""Workflow 手动触发接口（调试/演示用；生产中由业务事件自动触发）。"""
from app.handlers.base import ApiError, BaseHandler


class WorkflowTriggerHandler(BaseHandler):
    """POST /api/workflow/trigger  {event, payload}

    支持事件：customer.created / follow_up.created / customer.won
    """

    async def post(self) -> None:
        body = self.get_json_body()
        event = (body.get("event") or "").strip()
        if not event:
            raise ApiError("event 不能为空")
        payload = body.get("payload") or {}
        if not isinstance(payload, dict):
            raise ApiError("payload 必须是对象")
        results = await self.ctx.workflow.trigger(event, payload)
        self.ok({"event": event, "results": results})

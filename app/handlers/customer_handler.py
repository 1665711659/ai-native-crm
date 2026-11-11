"""客户 CRUD 与跟进记录 REST 接口。

创建客户后会自动触发 WorkflowEngine 的 customer.created 事件，
生成AI破冰话术并写入首条跟进建议 —— 展示「AI原生」业务闭环。
"""
import tornado.web

from app.handlers.base import ApiError, BaseHandler


class CustomerListHandler(BaseHandler):
    """GET/POST /api/customers"""

    async def get(self) -> None:
        result = await self.ctx.customers.list_customers(
            page=self.to_int(self.get_argument("page", 1), 1, "page"),
            page_size=min(self.to_int(self.get_argument("page_size", 20), 20, "page_size"), 100),
            keyword=self.get_argument("keyword", ""),
            status=self.get_argument("status", ""),
        )
        self.ok(result)

    async def post(self) -> None:
        body = self.get_json_body()
        try:
            customer = await self.ctx.customers.create(body)
        except ValueError as e:
            raise ApiError(str(e)) from e
        # AI原生闭环：新客户 → 工作流自动生成破冰话术跟进
        workflow_results = await self.ctx.workflow.trigger("customer.created", customer)
        self.ok({"customer": customer, "workflow": workflow_results})


class CustomerDetailHandler(BaseHandler):
    """GET/PATCH/DELETE /api/customers/{id}"""

    async def get(self, cid: str) -> None:
        try:
            customer = await self.ctx.customers.get(self.to_int(cid, 0, "id"))
        except ValueError as e:
            raise ApiError(str(e), status=404) from e
        self.ok(customer)

    async def patch(self, cid: str) -> None:
        body = self.get_json_body()
        try:
            customer = await self.ctx.customers.update(self.to_int(cid, 0, "id"), body)
        except ValueError as e:
            raise ApiError(str(e)) from e
        # 阶段变为 won 时触发成交答谢工作流
        if body.get("status") == "won":
            workflow = await self.ctx.workflow.trigger("customer.won", customer)
            return self.ok({"customer": customer, "workflow": workflow})
        self.ok({"customer": customer})

    async def delete(self, cid: str) -> None:
        await self.ctx.customers.delete(self.to_int(cid, 0, "id"))
        self.ok({"deleted": True})


class FollowUpListHandler(BaseHandler):
    """GET/POST /api/customers/{id}/follow_ups"""

    async def get(self, cid: str) -> None:
        items = await self.ctx.customers.list_follow_ups(self.to_int(cid, 0, "id"))
        self.ok({"items": items})

    async def post(self, cid: str) -> None:
        body = self.get_json_body()
        try:
            record = await self.ctx.customers.add_follow_up(
                self.to_int(cid, 0, "id"),
                content=body.get("content", ""),
                channel=body.get("channel", "phone"),
                next_follow_up_at=body.get("next_follow_up_at"),
            )
        except ValueError as e:
            raise ApiError(str(e)) from e
        workflow = await self.ctx.workflow.trigger("follow_up.created", record)
        self.ok({"follow_up": record, "workflow": workflow})

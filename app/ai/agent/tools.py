"""CRM Agent 工具集：OpenAI Function Calling 规范的工具定义 + 实现。

工具即能力（Tools-as-Capabilities）：Agent 通过这些工具直接读写业务数据库，
复用 CustomerService 领域逻辑 —— AI 与人工操作共享同一套数据规则与校验。

新增工具三步走：
1. 在 TOOLS_SCHEMA 增加函数 JSON Schema（name/description/parameters）；
2. 在 build_tool_registry 增加同名 async 实现（返回可JSON序列化的dict）；
3. 完成。Agent 的 LLM 会自动根据 description 决定何时调用。
"""
import json
from typing import Any

from app.services.customer_service import CustomerService, VALID_STATUS, STATUS_LABELS


def build_tools_schema() -> list[dict]:
    """OpenAI Function Calling 工具Schema（与 registry 的 key 一一对应）。"""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_customers",
                "description": "按关键词/阶段搜索客户列表（姓名、公司、行业、手机号模糊匹配）。"
                               "用户询问『有哪些客户 / 找一下XX』时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "搜索关键词，可留空返回全部"},
                        "status": {"type": "string", "enum": list(VALID_STATUS),
                                   "description": "客户阶段筛选，可留空"},
                        "limit": {"type": "integer", "description": "返回条数，默认5，最大20"},
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_customer_detail",
                "description": "查询单个客户的完整档案，含最近跟进记录。用户提供客户ID或明确指向某客户时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "integer", "description": "客户ID"}},
                    "required": ["customer_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_follow_up",
                "description": "为客户写一条跟进记录。当用户要求『记录跟进 / 安排回访』时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "integer", "description": "客户ID"},
                        "content": {"type": "string", "description": "跟进内容摘要"},
                        "channel": {"type": "string", "enum": ["phone", "wechat", "email", "visit", "other"],
                                    "description": "跟进渠道，默认phone"},
                        "next_follow_up_at": {"type": "string",
                                              "description": "下次跟进时间，格式 YYYY-MM-DD HH:MM:SS，可空"},
                    },
                    "required": ["customer_id", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_customer_status",
                "description": "更新客户销售阶段。当用户明确要求推进/修改客户阶段时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "integer", "description": "客户ID"},
                        "status": {"type": "string", "enum": list(VALID_STATUS),
                                   "description": "目标阶段"},
                        "reason": {"type": "string", "description": "变更原因，可空"},
                    },
                    "required": ["customer_id", "status"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_sales_stats",
                "description": "获取销售漏斗统计：各阶段客户数量与金额、总额汇总。用户询问业绩/统计/漏斗时调用。",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    ]


def build_tool_registry(svc: CustomerService) -> dict[str, Any]:
    """构建 工具名 -> async实现 的注册表。所有实现返回 dict（自动JSON化回填对话）。"""

    async def search_customers(keyword: str = "", status: str = "", limit: int = 5) -> dict:
        items = await svc.search(keyword=keyword or "", status=status or "", limit=min(int(limit or 5), 20))
        return {"count": len(items), "customers": items}

    async def get_customer_detail(customer_id: int) -> dict:
        customer = await svc.get(int(customer_id))
        follow_ups = await svc.list_follow_ups(int(customer_id), limit=10)
        return {"customer": customer, "recent_follow_ups": follow_ups}

    async def create_follow_up(customer_id: int, content: str,
                               channel: str = "phone", next_follow_up_at: str | None = None) -> dict:
        record = await svc.add_follow_up(
            int(customer_id), content, channel=channel or "phone",
            next_follow_up_at=next_follow_up_at or None,
        )
        return {"success": True, "follow_up": record}

    async def update_customer_status(customer_id: int, status: str, reason: str = "") -> dict:
        customer = await svc.update(int(customer_id), {"status": status})
        return {"success": True, "customer": customer, "note": f"阶段已更新，原因：{reason or '未说明'}"}

    async def get_sales_stats() -> dict:
        return await svc.stats()

    return {
        "search_customers": search_customers,
        "get_customer_detail": get_customer_detail,
        "create_follow_up": create_follow_up,
        "update_customer_status": update_customer_status,
        "get_sales_stats": get_sales_stats,
    }


def dumps_tool_result(result: Any) -> str:
    """工具结果序列化为 tool message content（容错非可序列化对象）。"""
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception:  # pragma: no cover
        return json.dumps({"error": "工具结果序列化失败"}, ensure_ascii=False)

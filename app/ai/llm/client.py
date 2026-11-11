"""LLM 客户端：OpenAI 兼容协议（chat/completions + tool_calls）。

- 一行配置切换火山方舟 / DeepSeek / GLM 等任何 OpenAI 兼容平台（.env）。
- 未配置 API Key 时自动降级为 MockLLMClient（规则模拟）：
  保证 Agent Tool-Calling 循环、RAG 等全链路在离线环境下也能完整演示。
- 统一返回 ChatResult，屏蔽各平台响应差异，上层（Agent/RAG/Workflow）零感知。
"""
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    """统一的 Chat 响应。tool_calls 已归一化为 [{id, name, arguments:dict}]。"""
    content: Optional[str]
    tool_calls: Optional[list[dict]] = None
    raw_message: dict = field(default_factory=dict)  # OpenAI 原始 assistant message（回填对话用）


# ---------------------------------------------------------------------------
# 真实客户端（OpenAI 兼容）
# ---------------------------------------------------------------------------
class LLMClient:
    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.http = httpx.AsyncClient(timeout=120)

    async def chat(
        self, messages: list[dict], tools: Optional[list[dict]] = None,
        temperature: float = 0.7, model: Optional[str] = None,
    ) -> ChatResult:
        # 离线演示模式：无 Key 时走 Mock（保证接口/链路可跑）
        if not self.cfg.llm_configured:
            return await MockLLMClient().chat(messages, tools)

        body: dict[str, Any] = {
            "model": model or self.cfg.llm_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        resp = await self.http.post(
            f"{self.cfg.llm_base_url}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {self.cfg.llm_api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]

        tool_calls = None
        if msg.get("tool_calls"):
            tool_calls = []
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({"id": tc.get("id"), "name": fn.get("name"), "arguments": args})

        return ChatResult(content=msg.get("content"), tool_calls=tool_calls or None, raw_message=msg)


# ---------------------------------------------------------------------------
# Mock 客户端（离线演示模式）
# ---------------------------------------------------------------------------
class MockLLMClient:
    """无 API Key 时的规则模拟客户端：
    - 命中关键词 => 返回模拟 tool_call，驱动 Agent 循环真实执行工具；
    - 已有工具结果 => 汇总生成最终回复，完成闭环。
    """

    async def chat(
        self, messages: list[dict], tools: Optional[list[dict]] = None, **_: Any
    ) -> ChatResult:
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        if tool_msgs:
            summary = "\n\n".join(
                f"· 调用 [{m.get('name', 'tool')}] -> {m.get('content', '')}" for m in tool_msgs
            )
            return ChatResult(
                content=f"[Mock LLM 演示回复] 已通过工具获取真实数据：\n{summary}\n\n"
                        f"提示：在 .env 配置 LLM_API_KEY 后，将由此模型智能总结并回答。"
            )

        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )

        if tools:
            # 演示规则：按关键词触发对应工具调用
            if any(k in last_user for k in ("统计", "多少", "业绩", "漏斗", "汇总")):
                return self._tool_call("get_sales_stats", {})
            if any(k in last_user for k in ("跟进", "回访", "记录一下")):
                cid = self._extract_id(last_user) or 1
                return self._tool_call(
                    "create_follow_up",
                    {"customer_id": cid, "content": "（演示）电话回访：沟通需求与预算，推进方案"},
                )
            if any(k in last_user for k in ("客户", "线索", "查", "找", "搜索")):
                kw = self._extract_keyword(last_user)
                return self._tool_call("search_customers", {"keyword": kw} if kw else {})
            if any(k in last_user for k in ("详情", "跟进历史", "客户档案")):
                return self._tool_call("get_customer_detail", {"customer_id": self._extract_id(last_user) or 1})

        return ChatResult(
            content="[Mock LLM] 当前未配置 LLM_API_KEY，处于离线演示模式。"
                    "请在 .env 中配置任意 OpenAI 兼容平台的 Key 后重启服务。"
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_id(text: str) -> Optional[int]:
        m = re.search(r"(?:ID|id|编号|#)\s*(\d+)|(\d{1,6})", text)
        if m:
            return int(m.group(1) or m.group(2))
        return None

    @staticmethod
    def _extract_keyword(text: str) -> str:
        """从演示指令中粗提搜索词（去掉常见动词/助词）。"""
        kw = re.sub(r"(帮我|请|查一下|查询|搜索|查找|找一下|所有|全部|的|一下|客户|线索)", "", text)
        return kw.strip()[:32]

    def _tool_call(self, name: str, arguments: dict) -> ChatResult:
        call_id = f"mock_{uuid.uuid4().hex[:8]}"
        raw = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": call_id, "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
            }],
        }
        return ChatResult(content=None, tool_calls=[{"id": call_id, "name": name, "arguments": arguments}], raw_message=raw)

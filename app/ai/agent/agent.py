"""CRM Agent：LLM + Tool Calling 的自主任务循环（ReAct 范式）。

执行循环：
    用户消息 → LLM 推理
      ├─ 返回 tool_calls → 执行工具 → 结果回填对话 → 继续推理（可多轮）
      └─ 返回自然语言 → 作为最终答案结束

工程要点：
- max_iterations 防死循环；
- 工具执行异常不中断循环，而是把错误信息回填给 LLM 让其自我修正；
- 记录 steps 执行轨迹（可观测性）：便于前端展示"AI做了什么"，也方便调试。
"""
import json
import logging
from datetime import datetime
from typing import Any, Optional

from app.ai.agent.tools import build_tools_schema, dumps_tool_result
from app.ai.llm.client import LLMClient

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """你是「智赢CRM」的智能销售助理Agent，服务一线销售人员。

行为准则：
1. 涉及客户数据（查询/统计/跟进/阶段变更）时，必须调用对应工具获取或写入真实数据，严禁编造客户姓名、金额、时间。
2. 金额回答需带单位（元）；多个客户信息用表格或列表清晰呈现。
3. 工具返回为空时，如实告知"未找到相关客户"，并给出建议（如调整关键词）。
4. 写操作（创建跟进、修改阶段）前，若用户未说清关键信息（哪个客户、什么内容），先追问确认。
5. 回答简洁专业，优先给出可执行的下一步建议。

当前时间：{now}"""


class CRMAgent:
    def __init__(self, llm: LLMClient, tool_registry: dict, max_iterations: int = 8) -> None:
        self.llm = llm
        self.registry = tool_registry
        self.schema = build_tools_schema()
        self.max_iterations = max_iterations

    async def run(self, message: str, history: Optional[list[dict]] = None) -> dict:
        """执行一次Agent任务。返回 {answer, steps}。"""
        system = {"role": "system",
                  "content": AGENT_SYSTEM_PROMPT.format(now=datetime.now().strftime("%Y-%m-%d %H:%M"))}
        messages: list[dict] = [system] + list(history or []) + [{"role": "user", "content": message}]
        steps: list[dict] = []

        for i in range(self.max_iterations):
            result = await self.llm.chat(messages, tools=self.schema, temperature=0.4)

            # 无工具调用 => 最终答案
            if not result.tool_calls:
                return {"answer": result.content or "", "steps": steps}

            # 回填 assistant 的 tool_calls 消息（OpenAI 协议要求）
            messages.append(result.raw_message)

            # 依次执行每个工具调用，结果以 role=tool 回填
            for tc in result.tool_calls:
                name, args = tc["name"], tc.get("arguments") or {}
                step = {"iteration": i + 1, "tool": name, "arguments": args}
                try:
                    if name not in self.registry:
                        raise ValueError(f"未知工具: {name}")
                    output = await self.registry[name](**args)
                    step["status"] = "ok"
                except Exception as e:  # noqa: BLE001 —— 错误回填LLM自我修正，不中断循环
                    output = {"error": f"{type(e).__name__}: {e}"}
                    step["status"] = "error"
                    logger.warning("Agent工具执行失败 %s(%s): %s", name, args, e)
                step["output"] = output
                steps.append(step)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": dumps_tool_result(output),
                })

        return {
            "answer": f"已达到最大推理轮数（{self.max_iterations}），请细化您的需求后重试。",
            "steps": steps,
        }

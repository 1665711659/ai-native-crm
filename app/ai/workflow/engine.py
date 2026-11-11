"""轻量事件驱动工作流引擎（MVP）。

模型：事件(event) → 匹配规则 → 依次执行动作(action)
- 规则注册在内存（生产可持久化到 workflow_rules 表，做可视化管理）；
- 动作是任意 async 函数：LLM生成 / 写库 / 调AIGC / 触发数字员工……
- 内置三条示例规则，展示「AI原生」的自动化闭环：
    customer.created  → LLM生成破冰话术 → 自动写入首条跟进建议
    followup.created  → LLM生成下次跟进建议（仅返回，不落库，避免递归）
    customer.won      → LLM生成感谢+转介绍话术

扩展路线：定时触发（APScheduler）、DAG编排、条件分支、人工审批节点、重试与死信。
"""
import logging
from typing import Any, Awaitable, Callable

from app.ai.llm.client import LLMClient
from app.services.customer_service import CustomerService

logger = logging.getLogger(__name__)

Handler = Callable[[dict], Awaitable[dict]]


class WorkflowEngine:
    def __init__(self, llm: LLMClient, svc: CustomerService) -> None:
        self.llm = llm
        self.svc = svc
        self._rules: dict[str, list[Handler]] = {}
        self._register_builtin_rules()

    # ------------------------------------------------------------------
    # 引擎核心
    # ------------------------------------------------------------------
    def register(self, event: str, handler: Handler) -> None:
        """注册规则（业务扩展点）。"""
        self._rules.setdefault(event, []).append(handler)

    async def trigger(self, event: str, payload: dict) -> list[dict]:
        """触发事件：执行该事件下全部规则，逐个返回结果（失败隔离，不互相阻塞）。"""
        results = []
        for handler in self._rules.get(event, []):
            name = getattr(handler, "__name__", str(handler))
            try:
                result = await handler(payload or {})
                results.append({"rule": name, "ok": True, "result": result})
                logger.info("[Workflow] %s -> %s ok", event, name)
            except Exception as e:  # noqa: BLE001
                results.append({"rule": name, "ok": False, "error": f"{type(e).__name__}: {e}"})
                logger.warning("[Workflow] %s -> %s 失败: %s", event, name, e)
        return results

    # ------------------------------------------------------------------
    # LLM 辅助：无Key时使用内置模板兜底（离线可演示）
    # ------------------------------------------------------------------
    async def _llm_text(self, prompt: str, fallback: str) -> str:
        if self.llm.cfg.llm_configured:
            result = await self.llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.7
            )
            if result.content:
                return result.content.strip()
        return fallback

    # ------------------------------------------------------------------
    # 内置规则
    # ------------------------------------------------------------------
    def _register_builtin_rules(self) -> None:
        self.register("customer.created", self._on_customer_created)
        self.register("follow_up.created", self._on_follow_up_created)
        self.register("customer.won", self._on_customer_won)

    async def _on_customer_created(self, customer: dict) -> dict:
        """新客户 → 生成破冰话术 → 自动写入首条跟进建议。"""
        industry = customer.get("industry") or "综合"
        suggestion = await self._llm_text(
            f"你是资深销售教练。针对新录入的客户：{customer.get('name')}（{customer.get('company') or '独立客户'}，"
            f"行业：{industry}，来源：{customer.get('source') or '未知'}），"
            f"请生成一段3句以内的首次电话破冰话术，包含开场、需求探寻提问、约见钩子。",
            fallback=(
                f"您好{customer.get('name')}，注意到贵司深耕{industry}领域。"
                f"我们近期帮多家同行业客户将客户转化率提升了30%，"
                f"想请教您目前团队在客户管理上最头疼的问题是什么？本周方便约15分钟简单交流吗？"
            ),
        )
        follow_up = await self.svc.add_follow_up(
            customer["id"], f"[工作流自动生成·破冰话术建议]\n{suggestion}", channel="workflow"
        )
        return {"action": "auto_first_follow_up", "suggestion": suggestion, "follow_up_id": follow_up["id"]}

    async def _on_follow_up_created(self, payload: dict) -> dict:
        """新跟进 → 生成下次跟进建议。"""
        suggestion = await self._llm_text(
            f"销售刚完成一次跟进：{payload.get('content', '')}。"
            f"请用一句话给出下一次跟进的最佳时机与切入动作。",
            fallback="建议3天内回访，围绕上次沟通的未决问题给出具体方案与报价。",
        )
        return {"action": "next_step_suggestion", "suggestion": suggestion}

    async def _on_customer_won(self, payload: dict) -> dict:
        """成交 → 感谢+转介绍话术。"""
        customer = await self.svc.get(payload["id"])
        message = await self._llm_text(
            f"客户 {customer['name']}（{customer['company']}）刚刚成交，合同金额 {customer['value']} 元。"
            f"请生成一段成交感谢+转介绍请求的话术（3句以内）。",
            fallback=(
                f"感谢{customer['name']}的信任！接下来我们会全力保障交付质量。"
                f"如果您身边有朋友有类似需求，欢迎引荐，我们为成功推荐准备了专属权益。"
            ),
        )
        return {"action": "won_message", "message": message}

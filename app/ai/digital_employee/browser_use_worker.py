"""数字员工示例2：Browser-use（LLM 驱动的自主浏览器操作 / Computer Use）。

与 Playwright 的分工：
- Playwright：固定流程，步骤写死，稳定高效 —— 适合"每天必须做"的动作；
- Browser-use：给自然语言目标，LLM 实时观察页面并决策下一步操作 ——
  适合"页面结构经常变 / 一次性探索"的任务（如竞品调研、信息核验）。

安装：
    pip install browser-use
    playwright install chromium
    需在 .env 配置 LLM_API_KEY（走 OpenAI 兼容协议）
运行 demo：
    python -m app.ai.digital_employee.browser_use_worker
"""
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


def build_browser_use_llm():
    """把本项目的 OpenAI 兼容 LLM 配置映射为 browser-use 所需的 ChatOpenAI。"""
    from langchain_openai import ChatOpenAI  # browser-use 依赖 langchain 接口

    from config import CONFIG

    return ChatOpenAI(
        model=CONFIG.llm_model,
        api_key=CONFIG.llm_api_key,
        base_url=f"{CONFIG.llm_base_url}/v1" if "/api/v3" not in CONFIG.llm_base_url
        else f"{CONFIG.llm_base_url}",  # 火山方舟等平台 base_url 透传
        temperature=0.0,
    )


async def run_browser_task(task: str, max_steps: int = 25) -> str:
    """给数字员工下达一个自然语言浏览器任务，返回执行结果摘要。

    示例 task：
      "打开 https://xxx.com/pricing，把专业版和旗舰版的价格整理成表格"
      "在本CRM (http://127.0.0.1:8888) 查询所有'prospect'阶段客户并汇报数量"
    """
    from browser_use import Agent as BrowserAgent, Browser

    agent = BrowserAgent(
        task=task,
        llm=build_browser_use_llm(),
        browser=Browser(config={"headless": False}),  # 可视化便于观察AI操作
        max_steps=max_steps,
    )
    result = await agent.run()
    return result.final_result() or "(任务未产出明确结果)"


async def demo() -> None:
    logging.basicConfig(level=logging.INFO)
    if not os.getenv("LLM_API_KEY"):
        print("请先在 .env 配置 LLM_API_KEY（Browser-use 需要 LLM 驱动）")
        return
    task = "打开 http://127.0.0.1:8888/api/health，读取返回JSON并汇报 llm_mode 字段的值"
    summary = await run_browser_task(task)
    print(f"\n数字员工执行结果：\n{summary}")


if __name__ == "__main__":
    asyncio.run(demo())

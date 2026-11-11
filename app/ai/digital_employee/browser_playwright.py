"""数字员工示例1：Playwright 浏览器自动化（确定性流程）。

适用场景：固定步骤的网页操作 —— 线索采集、竞品价格监控、
自动登录第三方平台后台拉取报表等。

安装：
    pip install playwright
    playwright install chromium
运行 demo：
    python -m app.ai.digital_employee.browser_playwright
"""
import asyncio
from dataclasses import dataclass, field


@dataclass
class Lead:
    """采集到的销售线索。"""
    name: str
    company: str
    detail: str = ""
    url: str = ""
    extra: dict = field(default_factory=dict)


async def crawl_leads_from_page(url: str, wait_selector: str = "body") -> list[Lead]:
    """通用线索采集骨架：打开页面 → 等待渲染 → 提取结构化数据。

    实际项目中按目标站点结构编写选择器；此处演示采集逻辑的组织方式。
    """
    from playwright.async_api import async_playwright

    leads: list[Lead] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(wait_selector, timeout=15000)

            # —— 按目标站点结构提取（示例选择器，按实际站点调整） ——
            items = await page.query_selector_all(".lead-card")
            for el in items:
                name_el = await el.query_selector(".name")
                company_el = await el.query_selector(".company")
                if not name_el:
                    continue
                company_text = (await company_el.inner_text()).strip() if company_el else ""
                leads.append(Lead(
                    name=(await name_el.inner_text()).strip(),
                    company=company_text,
                    url=page.url,
                ))
        finally:
            await browser.close()
    return leads


async def screenshot_page(url: str, out_path: str = "data/digital_employee/page.png") -> str:
    """整页截图（监控类任务的取证产物）。"""
    from playwright.async_api import async_playwright
    from pathlib import Path

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.screenshot(path=out_path, full_page=True)
        await browser.close()
    return out_path


async def login_and_export(base_url: str, username: str, password: str) -> dict:
    """自动登录示例骨架：填写表单 → 提交 → 校验登录态 → 拉取数据。"""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 调试期可视化
        page = await browser.new_page()
        await page.goto(f"{base_url}/login")
        await page.fill('input[name="username"]', username)
        await page.fill('input[name="password"]', password)
        await page.click("button[type=submit]")
        await page.wait_for_url("**/dashboard**", timeout=15000)
        # 登录成功后即可拉取数据 / 下载报表 …
        await browser.close()
    return {"logged_in": True}


async def demo() -> None:
    """演示：对本CRM健康检查接口截图取证。"""
    path = await screenshot_page("https://example.com")
    print(f"页面截图已保存: {path}")
    print("更多能力：crawl_leads_from_page() 线索采集 / login_and_export() 自动登录导出")


if __name__ == "__main__":
    asyncio.run(demo())

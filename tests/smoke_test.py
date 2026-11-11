"""冒烟测试：覆盖 MVP 全链路（健康检查/CRUD/RAG/Agent/Workflow）。

前置：服务已启动（python main.py）
运行：python tests/smoke_test.py
"""
import asyncio
import sys

import httpx

BASE = "http://127.0.0.1:8888"
PASSED = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    PASSED.append(ok)
    print(f"  [{mark}] {name}" + (f"  -> {detail}" if detail else ""))


async def main() -> None:
    async with httpx.AsyncClient(timeout=120) as c:
        # 1. 健康检查
        r = (await c.get(f"{BASE}/api/health")).json()
        check("健康检查", r["code"] == 0 and r["data"]["service"] == "ai-native-crm",
              f"db={r['data']['db_backend']}, llm={r['data']['llm_mode']}")

        # 1.1 可视化管理台（根路径返回前端页面）
        r = await c.get(f"{BASE}/")
        check("管理台首页(/)", r.status_code == 200 and "AI 原生 CRM" in r.text)

        # 1.2 销售漏斗统计
        r = (await c.get(f"{BASE}/api/stats")).json()
        check("统计接口(/api/stats)",
              r["code"] == 0 and len(r["data"]["by_status"]) == 5)

        # 2. 创建客户（自动触发工作流生成破冰话术）
        r = (await c.post(f"{BASE}/api/customers", json={
            "name": "冒烟测试客户", "company": "测试科技有限公司",
            "industry": "软件互联网", "value": 30000, "source": "冒烟测试",
        })).json()
        cid = r["data"]["customer"]["id"]
        wf_ok = any(w["ok"] and "suggestion" in str(w.get("result", {})) for w in r["data"]["workflow"])
        check("创建客户", r["code"] == 0 and cid > 0, f"id={cid}")
        check("创建触发工作流(自动生成破冰话术)", wf_ok)

        # 3. 列表 / 详情 / 更新
        r = (await c.get(f"{BASE}/api/customers", params={"keyword": "冒烟"})).json()
        check("客户搜索", r["code"] == 0 and r["data"]["total"] >= 1)
        r = (await c.get(f"{BASE}/api/customers/{cid}")).json()
        check("客户详情", r["code"] == 0 and r["data"]["name"] == "冒烟测试客户")
        r = (await c.patch(f"{BASE}/api/customers/{cid}", json={"status": "prospect"})).json()
        check("更新客户阶段", r["code"] == 0 and r["data"]["customer"]["status"] == "prospect")

        # 4. 跟进记录
        r = (await c.post(f"{BASE}/api/customers/{cid}/follow_ups", json={
            "content": "冒烟测试跟进：电话沟通需求", "channel": "phone",
        })).json()
        check("写入跟进记录", r["code"] == 0 and r["data"]["follow_up"]["id"] > 0)
        r = (await c.get(f"{BASE}/api/customers/{cid}/follow_ups")).json()
        check("查询跟进记录", r["code"] == 0 and len(r["data"]["items"]) >= 2)  # 工作流已自动写1条

        # 5. RAG 问答
        r = (await c.post(f"{BASE}/api/rag/query", json={"question": "产品价格是多少"})).json()
        check("RAG检索命中知识库", r["code"] == 0 and len(r["data"]["sources"]) >= 1,
              f"命中: {[s['title'] for s in r['data']['sources']]}")
        r = (await c.post(f"{BASE}/api/rag/query", json={"question": "新线索应该怎么跟进"})).json()
        check("RAG命中跟进SOP", r["code"] == 0 and any("SOP" in s["title"] or "跟进" in s["title"]
                                                        for s in r["data"]["sources"]))

        # 6. Agent：自然语言查客户（真实执行工具调用）
        r = (await c.post(f"{BASE}/api/agent/chat",
                          json={"message": "帮我查一下冒烟测试客户"})).json()
        steps = r["data"]["steps"]
        check("Agent工具调用(search_customers)", r["code"] == 0 and
              any(s["tool"] == "search_customers" and s["status"] == "ok" for s in steps),
              f"steps={len(steps)}")
        check("Agent返回最终答案", bool(r["data"]["answer"]))

        # 7. Agent：自然语言做统计
        r = (await c.post(f"{BASE}/api/agent/chat",
                          json={"message": "给我统计一下销售漏斗"})).json()
        check("Agent统计(get_sales_stats)", r["code"] == 0 and
              any(s["tool"] == "get_sales_stats" for s in r["data"]["steps"]))

        # 8. 清理冒烟数据
        r = (await c.delete(f"{BASE}/api/customers/{cid}")).json()
        check("删除冒烟客户", r["code"] == 0)

    print("\n" + ("全部通过 ✔" if all(PASSED) else f"存在失败项：{PASSED.count(False)} 个"))
    sys.exit(0 if all(PASSED) else 1)


if __name__ == "__main__":
    asyncio.run(main())

"""边界与异常路径测试：验证 API 容错、Agent 写操作、工作流事件闭环。

前置：服务已启动。运行：python tests/edge_test.py
"""
import asyncio
import sys

import httpx

BASE = "http://127.0.0.1:8888"
PASSED = []


def check(name, ok, detail=""):
    PASSED.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))


async def main() -> None:
    async with httpx.AsyncClient(timeout=120) as c:
        # ---- 异常路径：非法输入应有明确业务错误而非500 ----
        r = await c.post(f"{BASE}/api/customers", json={})
        check("创建缺name -> 400", r.status_code == 400 and r.json()["code"] == 1,
              r.json().get("msg", "")[:40])
        r = await c.post(f"{BASE}/api/customers",
                         json={"name": "X", "status": "hack"})
        check("非法status -> 400", r.status_code == 400)
        r = await c.get(f"{BASE}/api/customers/99999")
        check("客户不存在 -> 404", r.status_code == 404)
        r = await c.post(f"{BASE}/api/rag/query", json={"question": ""})
        check("RAG空问题 -> 400", r.status_code == 400)
        r = await c.post(f"{BASE}/api/agent/chat", json={})
        check("Agent空消息 -> 400", r.status_code == 400)
        r = await c.post(f"{BASE}/api/workflow/trigger", json={})
        check("工作流缺event -> 400", r.status_code == 400)
        r = await c.post(f"{BASE}/api/workflow/trigger",
                         json={"event": "unknown.event", "payload": {}})
        check("未知事件 -> 空结果不报错", r.status_code == 200 and r.json()["data"]["results"] == [])

        # ---- RAG 无关问题：真实Embedding下应如实未命中 ----
        # 已知限制：离线Mock向量是词法级bigram统计，无语义能力，可能假阳性命中；
        # 故仅在使用API Embedding时做严格断言（详见 docs/competitive-analysis.md）
        health = (await c.get(f"{BASE}/api/health")).json()["data"]
        r = (await c.post(f"{BASE}/api/rag/query",
                          json={"question": "量子力学薛定谔方程怎么解"})).json()
        if "api" in health["embedding_mode"]:
            check("RAG无关问题 -> 如实未命中", r["code"] == 0 and r["data"]["sources"] == [])
        else:
            check("RAG无关问题(mock模式, 词法检索已知限制, 见docs)",
                  r["code"] == 0, f"sources={len(r['data']['sources'])}(语义断言跳过)")

        # ---- Agent 写操作：自然语言写跟进（Mock规则触发真实落库）----
        # 自包含：先创建客户再让Agent写跟进，不依赖种子数据
        r = (await c.post(f"{BASE}/api/customers",
                          json={"name": "Agent写跟进测试客户"})).json()
        cid = r["data"]["customer"]["id"]
        r = (await c.post(f"{BASE}/api/agent/chat",
                          json={"message": f"帮客户{cid}记录一下跟进：电话回访，确认预算"})).json()
        used_tool = any(s["tool"] == "create_follow_up" and s["status"] == "ok"
                        for s in r["data"]["steps"])
        check("Agent写跟进(真实落库)", used_tool)
        r = (await c.get(f"{BASE}/api/customers/{cid}/follow_ups")).json()
        check("跟进已入库",
              r["code"] == 0 and any("电话回访" in f["content"] for f in r["data"]["items"]))
        await c.delete(f"{BASE}/api/customers/{cid}")

        # ---- 成交工作流：PATCH won 触发答谢话术 ----
        r = (await c.post(f"{BASE}/api/customers",
                          json={"name": "成交测试客户", "value": 10000})).json()
        cid = r["data"]["customer"]["id"]
        r = (await c.patch(f"{BASE}/api/customers/{cid}", json={"status": "won"})).json()
        check("PATCH won 触发答谢工作流",
              any(w["ok"] and "won_message" in str(w.get("result", {}))
                  for w in r["data"]["workflow"]))
        await c.delete(f"{BASE}/api/customers/{cid}")

        # ---- Agent 参数自我修正：客户ID不存在时错误回填不中断 ----
        r = (await c.post(f"{BASE}/api/agent/chat",
                          json={"message": "查一下客户99999的详情"})).json()
        check("Agent工具错误不中断(错误回填)", r["code"] == 0 and bool(r["data"]["answer"]))

        # ---- 并发冒烟：10个并发请求 ----
        async def one(i):
            resp = await c.get(f"{BASE}/api/customers", params={"page": 1, "page_size": 5})
            return resp.status_code == 200
        results = await asyncio.gather(*[one(i) for i in range(10)])
        check("10并发列表请求全部成功", all(results))

    print("\n" + ("全部通过 ✔" if all(PASSED) else f"失败 {PASSED.count(False)} 项"))
    sys.exit(0 if all(PASSED) else 1)


if __name__ == "__main__":
    asyncio.run(main())

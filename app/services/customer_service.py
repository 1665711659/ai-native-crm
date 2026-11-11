"""客户领域服务：封装 CRM 客户 / 跟进记录的全部业务规则。

该层同时服务于：
- Tornado API 层（REST CRUD）
- Agent 工具层（tools.py 直接复用，保证 AI 与人操作同一套数据规则）
"""
from datetime import datetime
from typing import Any, Optional

# 客户阶段（销售漏斗）；应用层校验，保持 SQLite/MySQL 双端兼容（不用ENUM）
VALID_STATUS = ("lead", "prospect", "negotiating", "won", "lost")
STATUS_LABELS = {
    "lead": "潜在线索",
    "prospect": "意向客户",
    "negotiating": "商务谈判",
    "won": "已成交",
    "lost": "已流失",
}

_CUSTOMER_FIELDS = (
    "name", "company", "phone", "email", "industry",
    "status", "value", "source", "notes",
)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class CustomerService:
    def __init__(self, db) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # 客户 CRUD
    # ------------------------------------------------------------------
    @staticmethod
    def _validate(data: dict, partial: bool = False) -> None:
        if not partial and not (data.get("name") or "").strip():
            raise ValueError("客户姓名(name)不能为空")
        if "status" in data and data["status"] not in VALID_STATUS:
            raise ValueError(f"非法客户阶段: {data['status']}，可选值 {list(VALID_STATUS)}")

    @staticmethod
    def _normalize(row: dict) -> dict:
        """统一数据类型（MySQL Decimal → float），便于JSON序列化。"""
        if row:
            row["value"] = float(row.get("value") or 0)
            row["status_label"] = STATUS_LABELS.get(row.get("status", ""), row.get("status"))
        return row

    async def create(self, data: dict) -> dict:
        self._validate(data, partial=False)
        now = _now()
        fields = {k: data.get(k, "" if k != "value" else 0) for k in _CUSTOMER_FIELDS}
        cid = await self.db.execute(
            """INSERT INTO customers
               (name, company, phone, email, industry, status, `value`, source, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fields["name"], fields["company"], fields["phone"], fields["email"],
                fields["industry"], fields.get("status") or "lead",
                float(fields["value"] or 0), fields["source"], fields["notes"], now, now,
            ),
        )
        return await self.get(cid)

    async def get(self, customer_id: int) -> Optional[dict]:
        row = await self.db.fetch_one("SELECT * FROM customers WHERE id = ?", (customer_id,))
        if not row:
            raise ValueError(f"客户不存在: id={customer_id}")
        return self._normalize(row)

    async def update(self, customer_id: int, data: dict) -> dict:
        self._validate(data, partial=True)
        sets, params = [], []
        for k in _CUSTOMER_FIELDS:
            if k in data:
                sets.append(f"{k} = ?")
                params.append(float(data[k]) if k == "value" else data[k])
        if not sets:
            return await self.get(customer_id)
        sets.append("updated_at = ?")
        params.append(_now())
        params.append(customer_id)
        await self.db.execute(f"UPDATE customers SET {', '.join(sets)} WHERE id = ?", tuple(params))
        return await self.get(customer_id)

    async def delete(self, customer_id: int) -> None:
        await self.get(customer_id)  # 不存在则抛错
        await self.db.execute("DELETE FROM follow_ups WHERE customer_id = ?", (customer_id,))
        await self.db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))

    async def list_customers(
        self, page: int = 1, page_size: int = 20,
        keyword: str = "", status: str = "",
    ) -> dict:
        """分页列表，支持姓名/公司/行业关键词与阶段筛选。"""
        where, params = [], []
        if keyword:
            where.append("(name LIKE ? OR company LIKE ? OR industry LIKE ?)")
            params += [f"%{keyword}%"] * 3
        if status:
            where.append("status = ?")
            params.append(status)
        w = (" WHERE " + " AND ".join(where)) if where else ""

        total = (await self.db.fetch_one(f"SELECT COUNT(*) AS c FROM customers{w}", tuple(params)))["c"]
        rows = await self.db.fetch_all(
            f"SELECT * FROM customers{w} ORDER BY id DESC LIMIT ? OFFSET ?",
            tuple(params) + (page_size, (max(page, 1) - 1) * page_size),
        )
        return {"items": [self._normalize(r) for r in rows], "total": total, "page": page, "page_size": page_size}

    async def search(self, keyword: str = "", status: str = "", limit: int = 5) -> list[dict]:
        """Agent 工具用：轻量检索，返回精简字段。"""
        where, params = [], []
        if keyword:
            where.append("(name LIKE ? OR company LIKE ? OR industry LIKE ? OR phone LIKE ?)")
            params += [f"%{keyword}%"] * 4
        if status:
            where.append("status = ?")
            params.append(status)
        w = (" WHERE " + " AND ".join(where)) if where else ""
        rows = await self.db.fetch_all(
            f"SELECT id, name, company, industry, status, `value`, updated_at FROM customers{w} "
            f"ORDER BY `value` DESC LIMIT ?",
            tuple(params) + (int(limit),),
        )
        return [self._normalize(r) for r in rows]

    async def stats(self) -> dict:
        """漏斗统计：各阶段客户数与金额（Agent / 仪表盘共用）。"""
        rows = await self.db.fetch_all(
            "SELECT status, COUNT(*) AS cnt, COALESCE(SUM(`value`),0) AS total_value "
            "FROM customers GROUP BY status"
        )
        by_status = {r["status"]: {"count": int(r["cnt"]), "value": float(r["total_value"])} for r in rows}
        return {
            "by_status": [
                {"status": s, "label": STATUS_LABELS[s],
                 "count": by_status.get(s, {}).get("count", 0),
                 "value": by_status.get(s, {}).get("value", 0.0)}
                for s in VALID_STATUS
            ],
            "total_customers": sum(v["count"] for v in by_status.values()),
            "total_value": sum(v["value"] for v in by_status.values()),
        }

    # ------------------------------------------------------------------
    # 跟进记录
    # ------------------------------------------------------------------
    async def add_follow_up(
        self, customer_id: int, content: str,
        channel: str = "phone", next_follow_up_at: Optional[str] = None,
    ) -> dict:
        await self.get(customer_id)  # 校验存在
        if not (content or "").strip():
            raise ValueError("跟进内容不能为空")
        fid = await self.db.execute(
            "INSERT INTO follow_ups (customer_id, content, channel, next_follow_up_at, created_at) "
            "VALUES (?,?,?,?,?)",
            (customer_id, content, channel, next_follow_up_at, _now()),
        )
        return {"id": fid, "customer_id": customer_id, "content": content,
                "channel": channel, "next_follow_up_at": next_follow_up_at, "created_at": _now()}

    async def list_follow_ups(self, customer_id: int, limit: int = 10) -> list[dict]:
        await self.get(customer_id)
        return await self.db.fetch_all(
            "SELECT * FROM follow_ups WHERE customer_id = ? ORDER BY id DESC LIMIT ?",
            (customer_id, limit),
        )

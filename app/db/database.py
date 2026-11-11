"""数据库层：统一异步数据库门面（Database Facade）。

设计要点：
1. MVP 默认 SQLite（aiosqlite，零配置开箱即用）；生产切换 MySQL（aiomysql），
   通过 .env 的 DB_BACKEND 一键切换，业务层 SQL 完全一致。
2. SQL 统一使用 `?` 占位符，MySQL 路径下自动转换为 `%s`，屏蔽方言差异。
3. PostgreSQL 接入：实现同款 execute / fetch_all / fetch_one 接口 + 对应 DDL
   即可（asyncpg），业务层零改动。
4. 所有方法返回 dict / list[dict]，屏蔽驱动差异（行对象、Decimal 等）。
"""
import logging
import os
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQLite DDL（演示库）
# ---------------------------------------------------------------------------
SQLITE_DDL = [
    """
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        company TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '',
        industry TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'lead',
        `value` REAL NOT NULL DEFAULT 0,
        source TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS follow_ups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        channel TEXT NOT NULL DEFAULT 'phone',
        next_follow_up_at TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kb_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
]

# ---------------------------------------------------------------------------
# MySQL DDL（生产库，utf8mb4）
# ---------------------------------------------------------------------------
MYSQL_DDL = [
    """
    CREATE TABLE IF NOT EXISTS customers (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        name VARCHAR(128) NOT NULL,
        company VARCHAR(255) NOT NULL DEFAULT '',
        phone VARCHAR(32) NOT NULL DEFAULT '',
        email VARCHAR(128) NOT NULL DEFAULT '',
        industry VARCHAR(64) NOT NULL DEFAULT '',
        status VARCHAR(16) NOT NULL DEFAULT 'lead',
        `value` DECIMAL(12,2) NOT NULL DEFAULT 0,
        source VARCHAR(64) NOT NULL DEFAULT '',
        notes TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS follow_ups (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        customer_id BIGINT UNSIGNED NOT NULL,
        content TEXT NOT NULL,
        channel VARCHAR(32) NOT NULL DEFAULT 'phone',
        next_follow_up_at DATETIME NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        KEY idx_customer (customer_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS kb_documents (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        title VARCHAR(255) NOT NULL,
        content MEDIUMTEXT NOT NULL,
        source VARCHAR(128) NOT NULL DEFAULT '',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


class Database:
    """统一异步数据库门面：SQLite（演示）/ MySQL（生产）。"""

    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.backend = cfg.db_backend  # "sqlite" | "mysql"
        self._sqlite: Optional[aiosqlite.Connection] = None
        self._mysql_pool = None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    async def connect(self) -> None:
        if self.backend == "mysql":
            import aiomysql  # 延迟导入：SQLite 演示模式无需安装

            self._mysql_pool = await aiomysql.create_pool(
                host=self.cfg.mysql_host,
                port=self.cfg.mysql_port,
                user=self.cfg.mysql_user,
                password=self.cfg.mysql_password,
                db=self.cfg.mysql_database,
                autocommit=True,
                minsize=1,
                maxsize=8,
                charset="utf8mb4",
            )
            logger.info("MySQL 已连接: %s/%s", self.cfg.mysql_host, self.cfg.mysql_database)
        else:
            os.makedirs(os.path.dirname(self.cfg.sqlite_path) or ".", exist_ok=True)
            self._sqlite = await aiosqlite.connect(self.cfg.sqlite_path)
            self._sqlite.row_factory = None
            await self._sqlite.execute("PRAGMA journal_mode=WAL")  # 并发读写更稳
            logger.info("SQLite 已连接: %s", self.cfg.sqlite_path)

    async def close(self) -> None:
        if self._sqlite:
            await self._sqlite.close()
        if self._mysql_pool:
            self._mysql_pool.close()
            await self._mysql_pool.wait_closed()

    async def init_schema(self) -> None:
        """幂等建表（启动时调用）。"""
        for ddl in (MYSQL_DDL if self.backend == "mysql" else SQLITE_DDL):
            await self._raw_execute(ddl)
        logger.info("数据库Schema已就绪（%s）", self.backend)

    # ------------------------------------------------------------------
    # 统一 SQL 接口（占位符统一写 ?，MySQL 自动转 %s）
    # ------------------------------------------------------------------
    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.backend == "mysql" else sql

    async def _raw_execute(self, sql: str, params: tuple = ()) -> None:
        """执行无结果集语句（DDL 等）。"""
        if self.backend == "mysql":
            async with self._mysql_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)
        else:
            await self._sqlite.execute(sql, params)

    async def execute(self, sql: str, params: tuple = ()) -> int:
        """执行写语句，返回 lastrowid（INSERT 场景）/ 影响行数。"""
        sql = self._sql(sql)
        if self.backend == "mysql":
            async with self._mysql_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)
                    return int(cur.lastrowid or cur.rowcount)
        else:
            cur = await self._sqlite.execute(sql, params)
            await self._sqlite.commit()
            try:
                return int(cur.lastrowid)
            finally:
                await cur.close()

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """查询多行，返回 list[dict]。"""
        sql = self._sql(sql)
        if self.backend == "mysql":
            import aiomysql

            async with self._mysql_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(sql, params)
                    return list(await cur.fetchall())
        else:
            cur = await self._sqlite.execute(sql, params)
            try:
                rows = await cur.fetchall()
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in rows]
            finally:
                await cur.close()

    async def fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
        """查询单行，无结果返回 None。"""
        rows = await self.fetch_all(sql + " LIMIT 1", params)
        return rows[0] if rows else None

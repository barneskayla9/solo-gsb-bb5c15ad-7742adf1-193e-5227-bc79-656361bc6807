import logging
import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from .config import get_settings
from .models import SessionLocal

logger = logging.getLogger("water-network")

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _split_statements(sql: str) -> list[str]:
    """把 schema 脚本拆成单条 SQL：去掉 -- 行注释后按分号切分。

    本项目的 DDL 不含存储过程/分号串，简单拆分即可；
    逐条执行同时兼容 psycopg2（支持多语句）与其他驱动。
    """
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    statements: list[str] = []
    for chunk in "\n".join(lines).split(";"):
        stmt = chunk.strip()
        if stmt:
            statements.append(stmt)
    return statements


def init_db(max_wait_seconds: int = 60) -> None:
    """等待 PostgreSQL 就绪后执行幂等 schema 脚本。"""
    deadline = time.monotonic() + max_wait_seconds
    db = SessionLocal()
    try:
        while True:
            try:
                db.execute(text("SELECT 1"))
                break
            except (OperationalError, ProgrammingError) as exc:
                if time.monotonic() > deadline:
                    raise
                logger.info("等待数据库就绪：%s", exc.orig)
                time.sleep(1)
                db.rollback()
        for stmt in _split_statements(_SCHEMA_PATH.read_text(encoding="utf-8")):
            db.execute(text(stmt))
        db.commit()
        logger.info("数据库 schema 初始化完成")
    finally:
        db.close()

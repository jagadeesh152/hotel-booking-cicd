import logging
import time
from pathlib import Path

from sqlalchemy import create_engine, text

from app.config import settings

log = logging.getLogger("app.database")

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


def init_db(retries: int = 15, delay: float = 2.0) -> None:
    """Create schema and seed data. An advisory lock makes parallel starts safe."""
    for attempt in range(1, retries + 1):
        try:
            conn = engine.raw_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT pg_advisory_lock(727001)")
                cur.execute(_SCHEMA)
                cur.execute("SELECT pg_advisory_unlock(727001)")
                conn.commit()
            finally:
                conn.close()
            log.info("database initialised", extra={"attempt": attempt})
            return
        except Exception as exc:  # noqa: BLE001
            log.warning("database not ready", extra={"attempt": attempt, "error": str(exc)[:200]})
            time.sleep(delay)
    raise RuntimeError("database unavailable after retries")


def ping() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True

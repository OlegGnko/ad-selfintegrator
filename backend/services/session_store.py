"""
Session store with automatic backend selection:
  - If UPSTASH_REDIS_REST_URL is set → Upstash Redis (production / Vercel)
  - Otherwise                         → SQLite file (local dev / Hetzner VPS)
"""
import json
import os
from pathlib import Path

# ── Redis backend ──────────────────────────────────────────────────────────────

def _redis_client():
    try:
        from upstash_redis.asyncio import Redis
        return Redis(
            url=os.environ["UPSTASH_REDIS_REST_URL"],
            token=os.environ["UPSTASH_REDIS_REST_TOKEN"],
        )
    except Exception:
        return None

SESSION_TTL = 60 * 60 * 24 * 90  # 90 days

async def _redis_load(session_id: str) -> dict | None:
    r = _redis_client()
    data = await r.get(f"session:{session_id}")
    if data is None:
        return None
    return json.loads(data)

async def _redis_save(session_id: str, data: dict) -> None:
    r = _redis_client()
    await r.set(f"session:{session_id}", json.dumps(data, ensure_ascii=False), ex=SESSION_TTL)

async def _redis_delete(session_id: str) -> None:
    r = _redis_client()
    await r.delete(f"session:{session_id}")


# ── SQLite backend ─────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent.parent.parent / "sessions.db"

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

async def _sqlite_connect():
    import aiosqlite
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute(_CREATE_SQL)
    await db.commit()
    return db

async def _sqlite_load(session_id: str) -> dict | None:
    async with await _sqlite_connect() as db:
        async with db.execute(
            "SELECT data FROM sessions WHERE session_id = ?", (session_id,)
        ) as cur:
            row = await cur.fetchone()
            return json.loads(row["data"]) if row else None

async def _sqlite_save(session_id: str, data: dict) -> None:
    blob = json.dumps(data, ensure_ascii=False)
    async with await _sqlite_connect() as db:
        await db.execute(
            """
            INSERT INTO sessions (session_id, data, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(session_id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (session_id, blob),
        )
        await db.commit()

async def _sqlite_delete(session_id: str) -> None:
    async with await _sqlite_connect() as db:
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()


# ── Public API ─────────────────────────────────────────────────────────────────

def _use_redis() -> bool:
    return bool(os.environ.get("UPSTASH_REDIS_REST_URL"))

async def load(session_id: str) -> dict | None:
    return await (_redis_load if _use_redis() else _sqlite_load)(session_id)

async def save(session_id: str, data: dict) -> None:
    await (_redis_save if _use_redis() else _sqlite_save)(session_id, data)

async def delete(session_id: str) -> None:
    await (_redis_delete if _use_redis() else _sqlite_delete)(session_id)

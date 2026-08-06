import asyncio
import re
import sqlite3
import threading
from pathlib import Path

from supabase import AsyncClient

from app.db.supabase import fetch_all_parts

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_MAX_QUERY_TOKENS = 32


class FTSIndex:
    def __init__(self, path: str) -> None:
        self._path = path
        self._build_lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        # One connection per operation: sqlite3 Connection objects must not be shared
        # across the event loop and executor threads.
        return sqlite3.connect(self._path)

    def build(self, parts: list[dict]) -> None:
        with self._build_lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN")
                conn.execute("DROP TABLE IF EXISTS parts_fts")
                conn.execute("DROP TABLE IF EXISTS parts_lookup")
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE parts_fts USING fts5(
                        part_number, name, description, category, brand,
                        tokenize='porter ascii'
                    )
                    """
                )
                conn.execute(
                    "CREATE TABLE parts_lookup (rowid INTEGER PRIMARY KEY, part_id TEXT NOT NULL)"
                )
                rows = [
                    (
                        p.get("part_number", ""),
                        p.get("name", ""),
                        p.get("description") or "",
                        p.get("category", ""),
                        p.get("brand") or "",
                    )
                    for p in parts
                ]
                conn.executemany("INSERT INTO parts_fts VALUES (?,?,?,?,?)", rows)

                lookup_rows = [(i + 1, p["id"]) for i, p in enumerate(parts)]
                conn.executemany("INSERT INTO parts_lookup VALUES (?,?)", lookup_rows)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def query(self, text: str, top_k: int) -> list[tuple[str, float]]:
        tokens = _TOKEN_RE.findall(text)[:_MAX_QUERY_TOKENS]
        if not tokens:
            return []
        # OR the individually quoted tokens: bag-of-words BM25 over stemmed terms.
        # A single quoted string would be an exact-phrase match and returns zero rows
        # for any natural-language query longer than a stored phrase.
        match_expr = " OR ".join(f'"{t}"' for t in tokens)
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT l.part_id, bm25(parts_fts) AS score
                FROM parts_fts
                JOIN parts_lookup l ON l.rowid = parts_fts.rowid
                WHERE parts_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (match_expr, top_k),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()
        # bm25() returns negative scores; negate so higher = better
        return [(part_id, -score) for part_id, score in rows]

    def _is_empty(self) -> bool:
        if not Path(self._path).exists():
            return True
        conn = self._connect()
        try:
            count = conn.execute("SELECT COUNT(*) FROM parts_lookup").fetchone()[0]
            return count == 0
        except sqlite3.OperationalError:
            return True
        finally:
            conn.close()

    async def rebuild_if_missing(self, client: AsyncClient) -> None:
        if self._is_empty():
            parts = await fetch_all_parts(client)
            if parts:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.build, parts)

import asyncio
import sqlite3
from pathlib import Path

from supabase import AsyncClient

from app.db.supabase import fetch_all_parts


class FTSIndex:
    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None

    def _open(self) -> sqlite3.Connection:
        if self._conn is None:
            # check_same_thread=False is safe here: build() holds the only writer,
            # query() is read-only and always called from run_in_executor.
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
        return self._conn

    def build(self, parts: list[dict]) -> None:
        conn = self._open()
        conn.executescript("""
            DROP TABLE IF EXISTS parts_fts;
            DROP TABLE IF EXISTS parts_lookup;
            CREATE VIRTUAL TABLE parts_fts USING fts5(
                part_number, name, description, category, brand,
                tokenize='porter ascii'
            );
            CREATE TABLE parts_lookup (rowid INTEGER PRIMARY KEY, part_id TEXT NOT NULL);
        """)
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

    def query(self, text: str, top_k: int) -> list[tuple[str, float]]:
        conn = self._open()
        escaped = text.replace('"', '""')
        rows = conn.execute(
            """
            SELECT l.part_id, bm25(parts_fts) AS score
            FROM parts_fts
            JOIN parts_lookup l ON l.rowid = parts_fts.rowid
            WHERE parts_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (f'"{escaped}"', top_k),
        ).fetchall()
        # bm25() returns negative scores; negate so higher = better
        return [(part_id, -score) for part_id, score in rows]

    def _is_empty(self) -> bool:
        if not Path(self._path).exists():
            return True
        try:
            conn = self._open()
            count = conn.execute("SELECT COUNT(*) FROM parts_lookup").fetchone()[0]
            return count == 0
        except sqlite3.OperationalError:
            return True

    async def rebuild_if_missing(self, client: AsyncClient) -> None:
        if self._is_empty():
            parts = await fetch_all_parts(client)
            if parts:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.build, parts)

"""
database.py — SQLite operations for the Dialed bot (daily mode only).
"""

import aiosqlite
import logging
from datetime import date, timedelta
from typing import Optional

log = logging.getLogger("dialed.db")


class Database:
    def __init__(self, path: str):
        self.path = path
        self.db: aiosqlite.Connection | None = None

    async def init(self):
        self.db = await aiosqlite.connect(self.path)
        await self.db.execute("PRAGMA journal_mode=WAL;")
        await self.db.execute("PRAGMA synchronous=NORMAL;")
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                username    TEXT    NOT NULL,
                game_number INTEGER NOT NULL,
                score       REAL    NOT NULL,
                submitted_at TEXT   NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, game_number)
            )
        """)
        await self.db.execute("CREATE INDEX IF NOT EXISTS idx_game ON scores(game_number)")

        # Guild settings (reminder channel per server)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id            TEXT PRIMARY KEY,
                reminder_channel_id INTEGER NOT NULL
            )
        """)

        await self.db.commit()
        log.info(f"Database initialised at {self.path}")

    # ── Guild Settings ────────────────────────────────────────────────────────

    async def set_reminder_channel(self, guild_id: str, channel_id: int):
        """Upsert the reminder channel for a guild."""
        await self.db.execute(
            "INSERT INTO guild_settings (guild_id, reminder_channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET reminder_channel_id = excluded.reminder_channel_id",
            (str(guild_id), channel_id),
        )
        await self.db.commit()

    async def get_reminder_channel(self, guild_id: str) -> Optional[int]:
        """Get the reminder channel for a specific guild."""
        async with self.db.execute(
            "SELECT reminder_channel_id FROM guild_settings WHERE guild_id = ?",
            (str(guild_id),),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def get_all_reminder_channels(self) -> list[int]:
        """Get all configured reminder channel IDs across all guilds."""
        async with self.db.execute(
            "SELECT reminder_channel_id FROM guild_settings"
        ) as cur:
            rows = await cur.fetchall()
        return [row[0] for row in rows]

    async def close(self):
        if self.db:
            await self.db.close()

    async def insert_score(self, user_id: str, username: str, game_number: int, score: float) -> bool:
        try:
            await self.db.execute(
                "INSERT INTO scores (user_id, username, game_number, score) VALUES (?, ?, ?, ?)",
                (str(user_id), username, game_number, score),
            )
            await self.db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def get_existing_score(self, user_id: str, game_number: int) -> Optional[float]:
        async with self.db.execute(
            "SELECT score FROM scores WHERE user_id = ? AND game_number = ?",
            (str(user_id), game_number),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def get_leaderboard(self, game_number: int, limit: int = 10):
        self.db.row_factory = aiosqlite.Row
        async with self.db.execute(
            "SELECT username, score FROM scores WHERE game_number = ? ORDER BY score DESC LIMIT ?",
            (game_number, limit),
        ) as cur:
            return await cur.fetchall()

    async def get_current_game_number(self) -> Optional[int]:
        async with self.db.execute("SELECT MAX(game_number) FROM scores") as cur:
            row = await cur.fetchone()
        return row[0] if row and row[0] is not None else None

    async def get_user_stats(self, user_id: str) -> Optional[dict]:
        async with self.db.execute(
            """SELECT COUNT(*), AVG(score), MAX(score), MIN(score)
               FROM scores WHERE user_id = ?""",
            (str(user_id),),
        ) as cur:
            row = await cur.fetchone()
        if not row or row[0] == 0:
            return None
        return {
            "games_played": row[0],
            "mean_score": round(row[1], 2),
            "personal_best": row[2],
            "worst_score": row[3],
        }

    async def get_recent_scores(self, user_id: str, days: int = 14) -> list[dict]:
        self.db.row_factory = aiosqlite.Row
        async with self.db.execute(
            "SELECT game_number, score, submitted_at FROM scores WHERE user_id = ? ORDER BY game_number DESC LIMIT ?",
            (str(user_id), days),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in reversed(rows)]

    async def get_win_streak(self, user_id: str) -> int:
        async with self.db.execute(
            """SELECT DATE(submitted_at) as day FROM scores
               WHERE user_id = ?
               GROUP BY DATE(submitted_at)
               ORDER BY day DESC LIMIT 30""",
            (str(user_id),),
        ) as cur:
            rows = await cur.fetchall()
        if not rows:
            return 0
        days = [date.fromisoformat(r[0]) for r in rows]
        today = date.today()
        if days[0] not in (today, today - timedelta(days=1)):
            return 0
        streak = 1
        for i in range(1, len(days)):
            if (days[i - 1] - days[i]).days == 1:
                streak += 1
            else:
                break
        return streak

    async def get_user_rank(self, user_id: str, game_number: int) -> Optional[int]:
        async with self.db.execute(
            """SELECT COUNT(*) + 1 FROM scores
               WHERE game_number = ? AND score > (SELECT score FROM scores WHERE user_id = ? AND game_number = ?)""",
            (game_number, str(user_id), game_number),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def get_all_time_leaderboard(self, limit: int = 10):
        self.db.row_factory = aiosqlite.Row
        async with self.db.execute(
            """SELECT user_id, username, ROUND(SUM(score), 2) as total_score, MAX(score) as pb, COUNT(*) as games
               FROM scores 
               GROUP BY user_id 
               HAVING COUNT(*) > 0 
               ORDER BY total_score DESC LIMIT ?""",
            (limit,),
        ) as cur:
            return await cur.fetchall()

    async def get_max_streak(self, user_id: str) -> int:
        async with self.db.execute(
            """SELECT DATE(submitted_at) as day FROM scores
               WHERE user_id = ?
               GROUP BY DATE(submitted_at)
               ORDER BY day ASC""",
            (str(user_id),),
        ) as cur:
            rows = await cur.fetchall()
        if not rows:
            return 0
            
        days = [date.fromisoformat(r[0]) for r in rows]
        max_streak = 1
        current_streak = 1
        for i in range(1, len(days)):
            if (days[i] - days[i - 1]).days == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1
        return max_streak

    async def get_all_players(self) -> list[str]:
        async with self.db.execute("SELECT DISTINCT user_id FROM scores") as cur:
            rows = await cur.fetchall()
        return [r[0] for r in rows]

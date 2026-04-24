"""
database.py — SQLite operations for the Dialed bot (daily mode only).
"""

import aiosqlite
import base64
import json
import logging
from datetime import date, datetime, timedelta, timezone
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

        # Dedicated test_scores table for testing logic without polluting stats
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS test_scores (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                username    TEXT    NOT NULL,
                game_number INTEGER NOT NULL,
                score       REAL    NOT NULL,
                submitted_at TEXT   NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await self.db.execute("CREATE INDEX IF NOT EXISTS idx_game_test ON test_scores(game_number)")

        try:
            await self.db.execute("ALTER TABLE scores ADD COLUMN round_data TEXT DEFAULT ''")
            await self.db.execute("ALTER TABLE test_scores ADD COLUMN round_data TEXT DEFAULT ''")
        except aiosqlite.OperationalError:
            pass # Columns already exist

        # Single player scores (no UNIQUE constraint — unlimited plays)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS sp_scores (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      TEXT    NOT NULL,
                username     TEXT    NOT NULL,
                game_number  INTEGER NOT NULL,
                score        REAL    NOT NULL,
                round_data   TEXT    DEFAULT '',
                submitted_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await self.db.execute("CREATE INDEX IF NOT EXISTS idx_sp_user ON sp_scores(user_id)")

        # Guild settings (reminder channel per server)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id            TEXT PRIMARY KEY,
                reminder_channel_id INTEGER NOT NULL
            )
        """)

        # Bot state (persistent key-value store for things like last reminder date)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS bot_state (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Migrate test scores to real scores
        try:
            await self.db.execute("""
                INSERT OR IGNORE INTO scores (user_id, username, game_number, score, submitted_at, round_data)
                SELECT user_id, username, game_number, score, submitted_at, round_data FROM test_scores
            """)
        except aiosqlite.OperationalError as e:
            log.warning(f"Failed to migrate test scores (might not exist yet): {e}")

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

    # ── Bot State ─────────────────────────────────────────────────────────────

    async def get_last_reminder_date(self) -> Optional[str]:
        """Get the last date a reminder was sent (as 'YYYY-MM-DD' string)."""
        async with self.db.execute(
            "SELECT value FROM bot_state WHERE key = 'last_reminder_date'"
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def set_last_reminder_date(self, date_str: str):
        """Store the last date a reminder was sent."""
        await self.db.execute(
            "INSERT INTO bot_state (key, value) VALUES ('last_reminder_date', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (date_str,),
        )
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    async def insert_score(self, user_id: str, username: str, game_number: int, score: float, round_data: str = "") -> bool:
        try:
            await self.db.execute(
                "INSERT INTO scores (user_id, username, game_number, score, round_data) VALUES (?, ?, ?, ?, ?)",
                (str(user_id), username, game_number, score, round_data),
            )
            await self.db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def delete_score(self, user_id: str, game_number: int) -> bool:
        async with self.db.execute(
            "DELETE FROM scores WHERE user_id = ? AND game_number = ?",
            (str(user_id), game_number),
        ) as cur:
            success = cur.rowcount > 0
        await self.db.commit()
        return success

    async def get_existing_score(self, user_id: str, game_number: int):
        self.db.row_factory = aiosqlite.Row
        async with self.db.execute(
            "SELECT score, round_data FROM scores WHERE user_id = ? AND game_number = ?",
            (str(user_id), game_number),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def get_leaderboard(self, game_number: int, limit: int = 10):
        self.db.row_factory = aiosqlite.Row
        async with self.db.execute(
            "SELECT username, score FROM scores WHERE game_number = ? ORDER BY score DESC LIMIT ?",
            (game_number, limit),
        ) as cur:
            return await cur.fetchall()

    # ── Test Scores (Webhook Testing) ─────────────────────────────────────────

    async def insert_test_score(self, user_id: str, username: str, game_number: int, score: float, round_data: str = "") -> bool:
        try:
            # We don't enforce UNIQUE on test_scores so we can keep spamming tests, 
            # or we can just append them. Let's just append everything.
            await self.db.execute(
                "INSERT INTO test_scores (user_id, username, game_number, score, round_data) VALUES (?, ?, ?, ?, ?)",
                (str(user_id), username, game_number, score, round_data),
            )
            await self.db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def get_test_leaderboard(self, game_number: int, limit: int = 10):
        self.db.row_factory = aiosqlite.Row
        async with self.db.execute(
            "SELECT username, score FROM test_scores WHERE game_number = ? ORDER BY score DESC LIMIT ?",
            (game_number, limit),
        ) as cur:
            return await cur.fetchall()

    async def get_user_test_rank(self, user_id: str, game_number: int) -> Optional[int]:
        # Getting rank based on the best test score of this user
        async with self.db.execute(
            """SELECT COUNT(*) + 1 FROM 
                (SELECT user_id, MAX(score) as best FROM test_scores WHERE game_number = ? GROUP BY user_id) 
               WHERE best > (SELECT MAX(score) FROM test_scores WHERE user_id = ? AND game_number = ?)""",
            (game_number, str(user_id), game_number),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def clear_test_scores(self) -> int:
        async with self.db.execute("DELETE FROM test_scores") as cur:
            count = cur.rowcount
        await self.db.commit()
        return count

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

        # Get best/worst individual round scores and timing stats
        best_round, worst_round = await self._get_round_extremes(user_id=str(user_id))
        avg_time, fastest_time, slowest_time = await self._get_time_extremes(user_id=str(user_id), is_sp=False)

        return {
            "games_played": row[0],
            "mean_score": round(row[1], 2),
            "personal_best": row[2],
            "worst_score": row[3],
            "best_round": best_round,
            "worst_round": worst_round,
            "avg_time": avg_time,
            "fastest_time": fastest_time,
            "slowest_time": slowest_time,
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
        today = datetime.now(timezone.utc).date()
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
            """SELECT user_id, username, ROUND(SUM(score), 2) as total_score, MAX(score) as pb, MIN(score) as ws, COUNT(*) as games
               FROM scores 
               GROUP BY user_id 
               HAVING COUNT(*) > 0 
               ORDER BY total_score DESC LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()

        # Enrich each row with best/worst individual round scores
        enriched = []
        for row in rows:
            d = dict(row)
            best_r, worst_r = await self._get_round_extremes(user_id=d["user_id"])
            d["best_round"] = best_r
            d["worst_round"] = worst_r
            enriched.append(d)
        return enriched

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

    # ── Round-level extremes ──────────────────────────────────────────────────

    @staticmethod
    def _decode_round_data(round_data_b64: str) -> list[float]:
        """Decode base64url round data into a list of individual round scores."""
        if not round_data_b64:
            return []
        try:
            b64 = round_data_b64.replace('-', '+').replace('_', '/')
            padding = 4 - (len(b64) % 4)
            if padding != 4:
                b64 += '=' * padding
            raw = base64.b64decode(b64)
            rounds = json.loads(raw)
            if not isinstance(rounds, list):
                return []
            return [r.get("s", 0) for r in rounds if isinstance(r, dict)]
        except Exception:
            return []

    @staticmethod
    def _decode_round_times(round_data_b64: str) -> list[float]:
        """Decode base64url round data into a list of round times (tm)."""
        if not round_data_b64:
            return []
        try:
            b64 = round_data_b64.replace('-', '+').replace('_', '/')
            padding = 4 - (len(b64) % 4)
            if padding != 4:
                b64 += '=' * padding
            raw = base64.b64decode(b64)
            rounds = json.loads(raw)
            if not isinstance(rounds, list):
                return []
            return [r.get("tm") for r in rounds if isinstance(r, dict) and r.get("tm") is not None]
        except Exception:
            return []

    async def _get_time_extremes(self, user_id: str, is_sp: bool = False) -> tuple[float | None, float | None, float | None]:
        """Get the average, fastest, and slowest individual round times for a user.
        Returns (avg, fastest, slowest) as floats in seconds, or None if no time data exists."""
        table = "sp_scores" if is_sp else "scores"
        async with self.db.execute(
            f"SELECT round_data FROM {table} WHERE user_id = ? AND round_data != ''",
            (str(user_id),),
        ) as cur:
            rows = await cur.fetchall()

        all_times = []
        for row in rows:
            times = self._decode_round_times(row[0])
            all_times.extend(times)

        if not all_times:
            return None, None, None

        avg_time = sum(all_times) / len(all_times)
        fastest = min(all_times)
        slowest = max(all_times)

        return round(avg_time, 1), round(fastest, 1), round(slowest, 1)

    async def _get_round_extremes(self, user_id: str | None = None) -> tuple[float | None, float | None]:
        """Get the best and worst individual round score for a user (or all users if None).
        Returns (best_round, worst_round) as floats out of 10, or None if no round data exists."""
        if user_id:
            async with self.db.execute(
                "SELECT round_data FROM scores WHERE user_id = ? AND round_data != ''",
                (str(user_id),),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with self.db.execute(
                "SELECT round_data FROM scores WHERE round_data != ''"
            ) as cur:
                rows = await cur.fetchall()

        best = None
        worst = None
        for row in rows:
            scores = self._decode_round_data(row[0])
            for s in scores:
                if best is None or s > best:
                    best = s
                if worst is None or s < worst:
                    worst = s

        return (
            round(best, 2) if best is not None else None,
            round(worst, 2) if worst is not None else None,
        )

    async def get_round_records_leaderboard(self, limit: int = 10) -> list[dict]:
        """Get all players' best and worst individual round scores for a round records leaderboard.
        Returns a list of dicts sorted by best_round descending."""
        async with self.db.execute(
            "SELECT user_id, username, round_data FROM scores WHERE round_data != ''"
        ) as cur:
            rows = await cur.fetchall()

        # Aggregate per-player
        player_data: dict[str, dict] = {}
        for row in rows:
            uid = row[0]
            uname = row[1]
            scores = self._decode_round_data(row[2])
            if uid not in player_data:
                player_data[uid] = {"user_id": uid, "username": uname, "best_round": None, "worst_round": None}
            for s in scores:
                pb = player_data[uid]
                if pb["best_round"] is None or s > pb["best_round"]:
                    pb["best_round"] = s
                if pb["worst_round"] is None or s < pb["worst_round"]:
                    pb["worst_round"] = s

        # Round the values
        for p in player_data.values():
            if p["best_round"] is not None:
                p["best_round"] = round(p["best_round"], 2)
            if p["worst_round"] is not None:
                p["worst_round"] = round(p["worst_round"], 2)

        # Sort by best_round descending
        result = sorted(player_data.values(), key=lambda x: x.get("best_round") or 0, reverse=True)
        return result[:limit]

    # ── Single Player Scores ──────────────────────────────────────────────────

    async def insert_sp_score(self, user_id: str, username: str, game_number: int, score: float, round_data: str = "") -> bool:
        """Insert a single player score (always succeeds — no uniqueness constraint)."""
        try:
            await self.db.execute(
                "INSERT INTO sp_scores (user_id, username, game_number, score, round_data) VALUES (?, ?, ?, ?, ?)",
                (str(user_id), username, game_number, score, round_data),
            )
            await self.db.commit()
            return True
        except Exception as e:
            log.error(f"Failed to insert SP score: {e}")
            return False

    async def get_sp_user_stats(self, user_id: str) -> Optional[dict]:
        """Get aggregate single player stats for a user."""
        async with self.db.execute(
            """SELECT COUNT(*), AVG(score), MAX(score), MIN(score)
               FROM sp_scores WHERE user_id = ?""",
            (str(user_id),),
        ) as cur:
            row = await cur.fetchone()
        if not row or row[0] == 0:
            return None

        best_round, worst_round = await self._get_sp_round_extremes(user_id=str(user_id))
        avg_time, fastest_time, slowest_time = await self._get_time_extremes(user_id=str(user_id), is_sp=True)

        return {
            "games_played": row[0],
            "mean_score": round(row[1], 2),
            "personal_best": row[2],
            "worst_score": row[3],
            "best_round": best_round,
            "worst_round": worst_round,
            "avg_time": avg_time,
            "fastest_time": fastest_time,
            "slowest_time": slowest_time,
        }

    async def get_sp_recent_scores(self, user_id: str, limit: int = 7) -> list[dict]:
        """Get recent single player scores for a user."""
        self.db.row_factory = aiosqlite.Row
        async with self.db.execute(
            "SELECT game_number, score, submitted_at FROM sp_scores WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (str(user_id), limit),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in reversed(rows)]

    async def _get_sp_round_extremes(self, user_id: str) -> tuple[float | None, float | None]:
        """Get the best and worst individual round score from single player games."""
        async with self.db.execute(
            "SELECT round_data FROM sp_scores WHERE user_id = ? AND round_data != ''",
            (str(user_id),),
        ) as cur:
            rows = await cur.fetchall()

        best = None
        worst = None
        for row in rows:
            scores = self._decode_round_data(row[0])
            for s in scores:
                if best is None or s > best:
                    best = s
                if worst is None or s < worst:
                    worst = s

        return (
            round(best, 2) if best is not None else None,
            round(worst, 2) if worst is not None else None,
        )

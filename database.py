"""SQLite persistence: users, ads, media, rejections."""

from __future__ import annotations

import time
from dataclasses import dataclass
import aiosqlite


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    phone TEXT,
    lang TEXT,
    username TEXT,
    display_name TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL DEFAULT 'electronics',
    title TEXT NOT NULL,
    region TEXT NOT NULL,
    rayon TEXT NOT NULL,
    comment TEXT NOT NULL,
    phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL,
    channel_message_id INTEGER,
    channel_message_ids TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    file_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    FOREIGN KEY (ad_id) REFERENCES ads(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rejections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    rejected_at REAL NOT NULL,
    FOREIGN KEY (ad_id) REFERENCES ads(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ads_user_created ON ads(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ads_status ON ads(status);
"""


@dataclass
class AdRecord:
    id: int
    user_id: int
    category: str
    title: str
    region: str
    rayon: str
    comment: str
    phone: str
    status: str
    created_at: float
    channel_message_id: int | None
    channel_message_ids: str | None = None  # JSON: [msg_id, ...] весь пост в канале (альбом)


@dataclass
class MediaItem:
    kind: str
    file_id: str
    position: int


class Database:
    def __init__(self, path: str) -> None:
        self._path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.executescript(SCHEMA)
            cur_u = await db.execute("PRAGMA table_info(users)")
            ucols = {row[1] for row in await cur_u.fetchall()}
            if "lang" not in ucols:
                await db.execute("ALTER TABLE users ADD COLUMN lang TEXT")
            cur = await db.execute("PRAGMA table_info(ads)")
            cols = {row[1] for row in await cur.fetchall()}
            if "channel_message_ids" not in cols:
                await db.execute(
                    "ALTER TABLE ads ADD COLUMN channel_message_ids TEXT"
                )
            if "category" not in cols:
                await db.execute(
                    "ALTER TABLE ads ADD COLUMN category TEXT NOT NULL DEFAULT 'electronics'"
                )
            await db.commit()

    @staticmethod
    async def _prepare(db: aiosqlite.Connection) -> None:
        await db.execute("PRAGMA foreign_keys = ON")

    async def upsert_user(
        self,
        user_id: int,
        phone: str | None,
        lang: str | None,
        username: str | None,
        display_name: str | None,
    ) -> None:
        now = time.time()
        async with aiosqlite.connect(self._path) as db:
            await self._prepare(db)
            await db.execute(
                """
                INSERT INTO users (user_id, phone, lang, username, display_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    phone = COALESCE(excluded.phone, users.phone),
                    lang = COALESCE(excluded.lang, users.lang),
                    username = COALESCE(excluded.username, users.username),
                    display_name = COALESCE(excluded.display_name, users.display_name)
                """,
                (user_id, phone, lang, username, display_name, now),
            )
            await db.commit()

    async def get_user_lang(self, user_id: int) -> str | None:
        async with aiosqlite.connect(self._path) as db:
            await self._prepare(db)
            cur = await db.execute(
                "SELECT lang FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            if not row or row[0] is None:
                return None
            s = str(row[0]).strip()
            return s or None

    async def user_has_phone(self, user_id: int) -> bool:
        async with aiosqlite.connect(self._path) as db:
            await self._prepare(db)
            cur = await db.execute(
                "SELECT phone FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            if not row or row[0] is None:
                return False
            return bool(str(row[0]).strip())

    async def get_user_phone(self, user_id: int) -> str | None:
        async with aiosqlite.connect(self._path) as db:
            await self._prepare(db)
            cur = await db.execute(
                "SELECT phone FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            if not row or row[0] is None:
                return None
            s = str(row[0]).strip()
            return s or None

    async def count_recent_ads(self, user_id: int, since_ts: float) -> int:
        async with aiosqlite.connect(self._path) as db:
            await self._prepare(db)
            cur = await db.execute(
                """
                SELECT COUNT(*) FROM ads
                WHERE user_id = ? AND created_at >= ? AND status IN ('pending', 'approved')
                """,
                (user_id, since_ts),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def create_ad(
        self,
        user_id: int,
        category: str,
        title: str,
        region: str,
        rayon: str,
        comment: str,
        phone: str,
        media: list[MediaItem],
    ) -> int:
        now = time.time()
        async with aiosqlite.connect(self._path) as db:
            await self._prepare(db)
            cur = await db.execute(
                """
                INSERT INTO ads (user_id, category, title, region, rayon, comment, phone, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (user_id, category, title, region, rayon, comment, phone, now),
            )
            ad_id = cur.lastrowid
            for item in media:
                await db.execute(
                    """
                    INSERT INTO media (ad_id, kind, file_id, position)
                    VALUES (?, ?, ?, ?)
                    """,
                    (ad_id, item.kind, item.file_id, item.position),
                )
            await db.commit()
        return int(ad_id)

    async def get_ad(self, ad_id: int) -> AdRecord | None:
        async with aiosqlite.connect(self._path) as db:
            await self._prepare(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, user_id, category, title, region, rayon, comment, phone, status, created_at,
                       channel_message_id, channel_message_ids
                FROM ads WHERE id = ?
                """,
                (ad_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return AdRecord(
                id=row["id"],
                user_id=row["user_id"],
                category=row["category"],
                title=row["title"],
                region=row["region"],
                rayon=row["rayon"],
                comment=row["comment"],
                phone=row["phone"],
                status=row["status"],
                created_at=row["created_at"],
                channel_message_id=row["channel_message_id"],
                channel_message_ids=row["channel_message_ids"],
            )

    async def get_ad_media(self, ad_id: int) -> list[MediaItem]:
        async with aiosqlite.connect(self._path) as db:
            await self._prepare(db)
            cur = await db.execute(
                """
                SELECT kind, file_id, position FROM media
                WHERE ad_id = ? ORDER BY position ASC
                """,
                (ad_id,),
            )
            rows = await cur.fetchall()
            return [MediaItem(kind=r[0], file_id=r[1], position=r[2]) for r in rows]

    async def set_ad_status(
        self,
        ad_id: int,
        status: str,
        channel_message_id: int | None = None,
        channel_message_ids_json: str | None = None,
    ) -> None:
        async with aiosqlite.connect(self._path) as db:
            await self._prepare(db)
            if channel_message_ids_json is not None:
                await db.execute(
                    """
                    UPDATE ads SET status = ?, channel_message_id = ?, channel_message_ids = ?
                    WHERE id = ?
                    """,
                    (status, channel_message_id, channel_message_ids_json, ad_id),
                )
            elif channel_message_id is not None:
                await db.execute(
                    """
                    UPDATE ads SET status = ?, channel_message_id = ? WHERE id = ?
                    """,
                    (status, channel_message_id, ad_id),
                )
            else:
                await db.execute(
                    "UPDATE ads SET status = ? WHERE id = ?",
                    (status, ad_id),
                )
            await db.commit()

    async def add_rejection(self, ad_id: int, reason: str) -> None:
        now = time.time()
        async with aiosqlite.connect(self._path) as db:
            await self._prepare(db)
            await db.execute(
                """
                INSERT INTO rejections (ad_id, reason, rejected_at)
                VALUES (?, ?, ?)
                """,
                (ad_id, reason, now),
            )
            await db.commit()

    async def list_user_ads_recent(self, user_id: int, limit: int = 15) -> list[AdRecord]:
        async with aiosqlite.connect(self._path) as db:
            await self._prepare(db)
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, user_id, category, title, region, rayon, comment, phone, status, created_at,
                       channel_message_id, channel_message_ids
                FROM ads WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cur.fetchall()
            out: list[AdRecord] = []
            for row in rows:
                out.append(
                    AdRecord(
                        id=row["id"],
                        user_id=row["user_id"],
                        category=row["category"],
                        title=row["title"],
                        region=row["region"],
                        rayon=row["rayon"],
                        comment=row["comment"],
                        phone=row["phone"],
                        status=row["status"],
                        created_at=row["created_at"],
                        channel_message_id=row["channel_message_id"],
                        channel_message_ids=row["channel_message_ids"],
                    )
                )
            return out

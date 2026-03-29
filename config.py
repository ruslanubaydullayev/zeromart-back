"""Load settings from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    channel_id: str | int
    database_path: str
    max_ads_per_hour: int
    outbound_proxy: str | None


def _parse_admin_ids(raw: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            continue
    return frozenset(ids)


def _normalize_channel_id(raw: str) -> str | int:
    """@username stays str; numeric -100… ids as int (Telegram API is less picky)."""
    s = raw.strip()
    if not s or s.startswith("@"):
        return s
    try:
        return int(s)
    except ValueError:
        return s


def _load_outbound_proxy() -> str | None:
    """PythonAnywhere free tier blocks direct HTTPS; use their proxy (see help.pythonanywhere.com)."""
    for key in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
        val = os.getenv(key, "").strip()
        if val:
            return val
    if os.getenv("PA_USE_OUTBOUND_PROXY", "").strip().lower() in ("1", "true", "yes", "on"):
        return "http://proxy.server:3128"
    return None


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    channel_raw = os.getenv("CHANNEL_ID", "").strip()
    channel = _normalize_channel_id(channel_raw) if channel_raw else ""
    db_path = os.getenv("DATABASE_PATH", "zeromart.db").strip() or "zeromart.db"
    max_per_hour = int(os.getenv("MAX_ADS_PER_HOUR", "5"))
    admins = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    return Settings(
        bot_token=token,
        admin_ids=admins,
        channel_id=channel,
        database_path=db_path,
        max_ads_per_hour=max(1, max_per_hour),
        outbound_proxy=_load_outbound_proxy(),
    )


settings = load_settings()

#!/usr/bin/env python3
"""
Remove all rows from the `media` table only.

- Keeps users, ads, rejections unchanged.
- After this, get_ad_media() is empty for every ad: the bot will send text-only
  captions if it ever reposts those ads (e.g. moderation replay).
- Does not delete anything on Telegram servers; it only drops stored file_id strings
  in SQLite (small DB size win).

Stop the bot first to avoid DB locks.

Usage (from project root):
  python3 scripts/clear_media.py
  python3 scripts/clear_media.py --yes
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def main() -> int:
    _load_env()
    os.chdir(ROOT)

    raw = os.getenv("DATABASE_PATH", "zeromart.db").strip() or "zeromart.db"
    db_path = Path(raw)
    if not db_path.is_absolute():
        db_path = ROOT / db_path

    parser = argparse.ArgumentParser(description="Delete all media file_id rows (keep users & ads).")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation.")
    args = parser.parse_args()

    if not db_path.is_file():
        print(f"No database file at {db_path}.", file=sys.stderr)
        return 1

    if not args.yes:
        print(
            "This removes every row in table `media` (photo/video file_ids).\n"
            f"Users and ads are NOT deleted.\n\nFile: {db_path}\n"
        )
        if input("Type exactly YES to continue: ").strip() != "YES":
            print("Aborted.")
            return 1

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        row = conn.execute("SELECT COUNT(*) FROM media").fetchone()
        deleted = int(row[0]) if row else 0
        conn.execute("DELETE FROM media")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'media'")
        conn.commit()
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()

    print(f"Done. Removed {deleted} media row(s). Ads and users unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

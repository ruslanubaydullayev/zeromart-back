#!/usr/bin/env python3
"""
Wipe all persisted marketplace data: users, ads, media, rejections.

Stop the bot first (otherwise the DB file may be locked).

Usage (from project root):
  python3 scripts/reset_database.py          # asks for confirmation
  python3 scripts/reset_database.py --yes    # no prompt (CI / scripts)

Uses DATABASE_PATH from .env (default: zeromart.db in project root).
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

    parser = argparse.ArgumentParser(description="Delete all users and ads from SQLite.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Do not ask for confirmation (dangerous).",
    )
    args = parser.parse_args()

    if not db_path.is_file():
        print(f"No database file at {db_path} — nothing to wipe.", file=sys.stderr)
        return 1

    if not args.yes:
        print(f"This will PERMANENTLY delete ALL data in:\n  {db_path}\n")
        if input('Type exactly YES to continue: ').strip() != "YES":
            print("Aborted.")
            return 1

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            DELETE FROM rejections;
            DELETE FROM media;
            DELETE FROM ads;
            DELETE FROM users;
            DELETE FROM sqlite_sequence WHERE name IN ('ads', 'media', 'rejections');
            """
        )
        conn.commit()
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()

    print(f"Done. Database cleared: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

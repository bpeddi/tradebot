"""Web app tables (users, schedule) layered onto trading_bot.py's trades.db."""
from trading_bot import init_db as _init_trades_db


def init_web_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL UNIQUE,
            hashed_pw   TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schedule (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            time1       TEXT NOT NULL DEFAULT '10:00',
            time2       TEXT NOT NULL DEFAULT '15:00',
            timezone    TEXT NOT NULL DEFAULT 'America/Chicago',
            enabled     INTEGER NOT NULL DEFAULT 0,
            updated_at  TEXT
        )
    """)
    conn.commit()
    return conn


def get_db():
    """FastAPI dependency: yields a sqlite3 connection with all tables ready.
    A fresh connection per request avoids sharing sqlite3 connections across
    FastAPI's threadpool threads."""
    conn = _init_trades_db()
    init_web_tables(conn)
    try:
        yield conn
    finally:
        conn.close()

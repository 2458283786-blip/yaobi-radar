# db.py - SQLite 数据库操作
import sqlite3, os, time
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "market.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            price REAL,
            volume_24h REAL,
            oi REAL,
            funding REAL,
            market_cap REAL,
            fdv REAL,
            circulating_supply REAL,
            circulation_ratio REAL,
            sector TEXT,
            UNIQUE(symbol, timestamp)
        );
        CREATE INDEX IF NOT EXISTS idx_snap_symbol_ts
            ON market_snapshots(symbol, timestamp);
        CREATE INDEX IF NOT EXISTS idx_snap_ts
            ON market_snapshots(timestamp);

        CREATE TABLE IF NOT EXISTS daily_rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            rank INTEGER,
            symbol TEXT NOT NULL,
            score REAL,
            signals TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_rank_date
            ON daily_rankings(date);

        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            snapshot_date TEXT NOT NULL,
            price_at_snapshot REAL,
            price_7d REAL,
            price_30d REAL,
            return_7d REAL,
            return_30d REAL
        );
    """)
    conn.commit()
    conn.close()

def insert_snapshot(data: dict):
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO market_snapshots
        (symbol, timestamp, price, volume_24h, oi, funding, market_cap, fdv,
         circulating_supply, circulation_ratio, sector)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["symbol"],
        data["timestamp"],
        data.get("price"),
        data.get("volume_24h"),
        data.get("oi"),
        data.get("funding"),
        data.get("market_cap"),
        data.get("fdv"),
        data.get("circulating_supply"),
        data.get("circulation_ratio"),
        data.get("sector"),
    ))
    conn.commit()
    conn.close()

def get_history(symbol: str, days: int = 7) -> list:
    """获取某币近N天的历史快照"""
    conn = get_db()
    cutoff = int(time.time()) - days * 86400
    rows = conn.execute("""
        SELECT * FROM market_snapshots
        WHERE symbol = ? AND timestamp >= ?
        ORDER BY timestamp ASC
    """, (symbol, cutoff)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_latest_snapshot(symbol: str) -> dict | None:
    conn = get_db()
    row = conn.execute("""
        SELECT * FROM market_snapshots
        WHERE symbol = ?
        ORDER BY timestamp DESC LIMIT 1
    """, (symbol,)).fetchone()
    conn.close()
    return dict(row) if row else None

def save_ranking(date_str: str, rankings: list):
    conn = get_db()
    conn.execute("DELETE FROM daily_rankings WHERE date = ?", (date_str,))
    for r in rankings:
        conn.execute("""
            INSERT INTO daily_rankings (date, rank, symbol, score, signals)
            VALUES (?, ?, ?, ?, ?)
        """, (date_str, r["rank"], r["symbol"], r["score"], r.get("signals_str", "")))
    conn.commit()
    conn.close()

def save_backtest(symbol: str, date: str, price: float):
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO backtest_results
        (symbol, snapshot_date, price_at_snapshot)
        VALUES (?, ?, ?)
    """, (symbol, date, price))
    conn.commit()
    conn.close()

def update_backtest_results():
    """回溯7日和30日收益"""
    conn = get_db()
    now = int(time.time())
    conn.execute("""
        UPDATE backtest_results SET
            price_7d = COALESCE(price_7d, (
                SELECT price FROM market_snapshots
                WHERE market_snapshots.symbol = backtest_results.symbol
                AND market_snapshots.timestamp >= ?
                ORDER BY market_snapshots.timestamp ASC LIMIT 1
            )),
            return_7d = CASE WHEN price_7d IS NOT NULL AND price_at_snapshot > 0
                THEN (price_7d - price_at_snapshot) / price_at_snapshot * 100
                ELSE NULL END
        WHERE price_7d IS NULL
    """, (now - 7*86400,))
    conn.commit()
    conn.close()


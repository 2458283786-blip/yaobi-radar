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

        CREATE TABLE IF NOT EXISTS detection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            detect_date TEXT NOT NULL,
            detect_timestamp INTEGER NOT NULL,
            detect_price REAL,
            anomaly_score REAL,
            top_signals TEXT,
            price_3d REAL,
            return_3d REAL,
            price_7d REAL,
            return_7d REAL,
            price_14d REAL,
            return_14d REAL,
            pumped_3d INTEGER DEFAULT 0,
            pumped_7d INTEGER DEFAULT 0,
            pumped_14d INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_detect_date
            ON detection_log(detect_date);
        CREATE INDEX IF NOT EXISTS idx_detect_symbol
            ON detection_log(symbol, detect_date);
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
    conn = get_db()
    cutoff = int(time.time()) - days * 86400
    rows = conn.execute("""
        SELECT * FROM market_snapshots
        WHERE symbol = ? AND timestamp >= ?
        ORDER BY timestamp ASC
    """, (symbol, cutoff)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_vol_history(symbol: str, lookback_hours: int = 48) -> list:
    """???????(??????)"""
    conn = get_db()
    cutoff = int(time.time()) - lookback_hours * 3600
    rows = conn.execute("""
        SELECT volume_24h FROM market_snapshots
        WHERE symbol = ? AND timestamp >= ?
        ORDER BY timestamp ASC
    """, (symbol, cutoff)).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0] and r[0] > 0]

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

def log_detection(symbol: str, date_str: str, timestamp: int, price: float, score: float, signals: str):
    """记录每次上榜"""
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO detection_log
        (symbol, detect_date, detect_timestamp, detect_price, anomaly_score, top_signals)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (symbol, date_str, timestamp, price, score, signals))
    conn.commit()
    conn.close()

def compute_detection_returns():
    """计算所有已记录检测的后续收益（3d/7d/14d）"""
    conn = get_db()
    
    # 找到所有未计算收益的检测记录 (距今超过3天的)
    now = int(time.time())
    pending = conn.execute("""
        SELECT id, symbol, detect_timestamp, detect_price FROM detection_log
        WHERE price_3d IS NULL AND detect_timestamp <= ?
    """, (now - 3*86400,)).fetchall()
    
    for row in pending:
        det_ts = row["detect_timestamp"]
        det_price = row["detect_price"]
        sym = row["symbol"]
        lid = row["id"]
        
        updates = {}
        
        # 找3天后的价格
        for days, col_price, col_ret, col_pump in [
            (3, "price_3d", "return_3d", "pumped_3d"),
            (7, "price_7d", "return_7d", "pumped_7d"),
            (14, "price_14d", "return_14d", "pumped_14d"),
        ]:
            target = det_ts + days * 86400
            if target > now:
                continue  # 还没到时间
            
            snap = conn.execute("""
                SELECT price FROM market_snapshots
                WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp ASC LIMIT 1
            """, (sym, target - 3600, target + 86400)).fetchone()
            
            if snap and snap["price"] and det_price > 0:
                ret = (snap["price"] - det_price) / det_price * 100
                pumped = 1 if ret > 10 else 0
                updates[col_price] = snap["price"]
                updates[col_ret] = round(ret, 1)
                updates[col_pump] = pumped
        
        if updates:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [lid]
            conn.execute(f"UPDATE detection_log SET {sets} WHERE id = ?", vals)
    
    conn.commit()
    conn.close()

def get_detection_stats() -> dict:
    """获取命中率统计"""
    conn = get_db()
    
    # 总体统计
    total = conn.execute("SELECT COUNT(*) as n FROM detection_log WHERE detect_price > 0").fetchone()["n"]
    
    stats = {"total_detections": total, "hit_rates": {}}
    
    for days, col in [("3d", "pumped_3d"), ("7d", "pumped_7d"), ("14d", "pumped_14d")]:
        pumped = conn.execute(
            f"SELECT COUNT(*) as n FROM detection_log WHERE {col} = 1"
        ).fetchone()["n"]
        eligible = conn.execute(
            f"SELECT COUNT(*) as n FROM detection_log WHERE {col} IS NOT NULL"
        ).fetchone()["n"]
        if eligible > 0:
            stats["hit_rates"][days] = {
                "pumped": pumped,
                "eligible": eligible,
                "rate": round(pumped / eligible * 100, 1)
            }
        else:
            stats["hit_rates"][days] = {"pumped": 0, "eligible": 0, "rate": 0}
    
    # 最佳命中币种
    best = conn.execute("""
        SELECT symbol, detect_date, anomaly_score, return_7d
        FROM detection_log
        WHERE return_7d IS NOT NULL
        ORDER BY return_7d DESC LIMIT 5
    """).fetchall()
    stats["best_hits"] = [dict(r) for r in best]
    
    # 最近检测
    recent = conn.execute("""
        SELECT symbol, detect_date, detect_price, anomaly_score,
               return_3d, return_7d, return_14d
        FROM detection_log
        ORDER BY detect_date DESC LIMIT 20
    """).fetchall()
    stats["recent"] = [dict(r) for r in recent]
    
    conn.close()
    return stats

def get_latest_backtest_entries(limit: int = 50) -> list:
    """获取最近的回测记录（兼容旧接口）"""
    conn = get_db()
    rows = conn.execute("""
        SELECT detect_date as date, symbol, detect_price as price,
               return_3d as ret3d, return_7d as ret7d, return_14d as ret14d
        FROM detection_log
        WHERE detect_price > 0
        ORDER BY detect_date DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

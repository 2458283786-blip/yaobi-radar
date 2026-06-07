# -*- coding: utf-8 -*-
import sys, time, os, io

# Windows UTF-8 fix
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db import init_db, insert_snapshot, save_ranking, save_backtest
from src.collector import (
    collect_binance_futures_tickers, collect_klines,
    collect_full_snapshot, collect_coingecko_market_data,
)
from src.analyzer import detect_all_anomalies, assess_market_regime
from src.report import generate_report, generate_summary
from src.config import TOP_N_VOLUME, TOP_K_OUTPUT, EXCLUDE_SYMBOLS

# Using EXCLUDE_SYMBOLS from config

def main():
    print("=" * 72)
    print("  YaoBi Radar v2.0 - Market Structure Anomaly Scanner")
    print("  Core: Find structure changes, not predict price")
    print("=" * 72)

    # 0. DB
    print("\n[0] Init SQLite...")
    init_db()
    print("    Ready")

    # 1. BTC benchmark
    print("\n[1] Fetch BTC benchmark...")
    btc_kl = collect_klines("BTCUSDT", "4h", 100)
    regime = assess_market_regime(btc_kl)
    print(f"    Market Regime: {regime}")

    # 2. Top 100 tickers
    print(f"\n[2] Fetch Top{TOP_N_VOLUME} futures tickers...")
    tickers = collect_binance_futures_tickers(TOP_N_VOLUME)
    tickers = [t for t in tickers if t["symbol"] not in EXCLUDE_SYMBOLS]
    print(f"    Got {len(tickers)} contracts")

    # 3. CoinGecko
    print(f"\n[3] CoinGecko market data...")
    symbols = [t["symbol"] for t in tickers[:50]]
    cg_data = collect_coingecko_market_data(symbols)
    print(f"    Got {len(cg_data)} coins data")

    # 4. Snapshots
    print(f"\n[4] Collect snapshots...")
    snapshots = []
    for i, t in enumerate(tickers):
        if (i+1) % 30 == 0 or i == 0:
            print(f"    {i+1}/{len(tickers)}")
        try:
            snap = collect_full_snapshot(t["symbol"], t, cg_data)
            insert_snapshot(snap)
            snapshots.append(snap)
        except Exception:
            continue
    print(f"    Collected {len(snapshots)} snapshots")

    # 5. Anomaly detection
    print(f"\n[5] Detect structure anomalies...")
    results = []
    for i, snap in enumerate(snapshots):
        if (i+1) % 30 == 0 or i == 0:
            print(f"    {i+1}/{len(snapshots)}")
        try:
            kl = collect_klines(snap["symbol"], "4h", 120)
            if not kl or len(kl) < 30:
                continue
            analysis = detect_all_anomalies(snap["symbol"], snap, kl, btc_kl)
            if analysis["composite_score"] >= 30:
                results.append(analysis)
        except Exception:
            continue

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    results = results[:TOP_K_OUTPUT]

    # 6. Report
    print(f"\n[6] Generate report...")
    summary = generate_summary(results, regime)
    print(summary)

    print("\n" + "=" * 72)
    print("  Top5 Detailed Reports")
    print("=" * 72)
    for r in results[:5]:
        report = generate_report(r)
        if report:
            print("\n" + report)

    # 7. Save rankings for backtest
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    rankings = []
    for i, r in enumerate(results):
        rankings.append({
            "rank": i+1,
            "symbol": r["symbol"],
            "score": r["composite_score"],
            "signals_str": "|".join(
                [f"{k}:{v['score']}" for k,v in r["anomalies"].items() if v["score"]>=30]
            )
        })
        price_vals = [s["price"] for s in snapshots if s["symbol"]==r["symbol"]]
        if price_vals:
            save_backtest(r["symbol"], today, price_vals[0])
    save_ranking(today, rankings)

    print(f"\n{'='*72}")
    print(f"  Done: {len(results)} structure anomalies found")
    print(f"  Data saved to SQLite for backtest tracking")
    print(f"{'='*72}")
    print(f"  [WARNING] Describes structure anomalies only. Not investment advice.")
    print(f"{'='*72}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


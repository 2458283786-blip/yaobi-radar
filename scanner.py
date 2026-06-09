# -*- coding: utf-8 -*-
import sys, time, os, io
if sys.platform == "win32":
    try: sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except: pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db import init_db, insert_snapshot, save_ranking, save_backtest
from src.collector import *
from src.analyzer import detect_all_anomalies, assess_market_regime
from src.crash_detector import detect_crash_risks
from src.report import generate_report, generate_summary
from src.config import TOP_N_VOLUME, TOP_K_OUTPUT, EXCLUDE_SYMBOLS
from datetime import datetime
import json

def main():
    print("=" * 72)
    print("  YaoBi Radar v2.0 - Binance Futures Scanner")
    print("  Find structure anomalies, not predict price")
    print("=" * 72)

    print("\n[0] Init SQLite...")
    init_db()
    print("    Ready")

    print("\n[1] BTC benchmark...")
    btc_kl = collect_klines("BTCUSDT", "4h", 100)
    regime = assess_market_regime(btc_kl)
    print(f"    Market: {regime}")

    print(f"\n[2] Fetch Top{TOP_N_VOLUME} futures...")
    tickers = collect_binance_futures_tickers(TOP_N_VOLUME)
    tickers = [t for t in tickers if t["symbol"] not in EXCLUDE_SYMBOLS]
    print(f"    {len(tickers)} contracts")
    if not tickers:
        print("    FATAL: No tickers fetched. Check network/proxy.")
        return

    print("\n[3] CoinGecko...")
    symbols = [t["symbol"] for t in tickers[:50]]
    cg_data = collect_coingecko_market_data(symbols)
    print(f"    {len(cg_data)} coins")

    # Social media attention
    print("\n[Social] Checking social attention...")
    from src.social import get_social_data
    try:
        social_data = get_social_data(symbols[:40])
        print(f"    Got social data for {len(social_data)} coins")
    except Exception:
        social_data = {}
        print("    Social data skipped")

    print("\n[4] Snapshots...")
    snapshots = []
    for i, t in enumerate(tickers):
        if (i+1) % 30 == 0 or i == 0: print(f"    {i+1}/{len(tickers)}")
        try:
            snap = collect_full_snapshot(t["symbol"], t, cg_data)
            insert_snapshot(snap)
            snapshots.append(snap)
        except: continue
    print(f"    {len(snapshots)} saved")
    if snapshots:
        sample = snapshots[0]
        has_oi = sample.get("oi", 0) > 0
        has_fr = sample.get("funding") is not None
        print(f"    Sample data check - OI:{has_oi} Funding:{has_fr}")

    print("\n[5] Anomaly detection...")
    results = []
    crash_results = []
    kline_ok = 0
    kline_fail = 0
    for i, snap in enumerate(snapshots):
        if (i+1) % 30 == 0 or i == 0: print(f"    {i+1}/{len(snapshots)}")
        try:
            kl = collect_klines(snap["symbol"], "4h", 120)
            if not kl or len(kl) < 30:
                kline_fail += 1
                continue
            kline_ok += 1
            a = detect_all_anomalies(snap["symbol"], snap, kl, btc_kl, social_data.get(snap["symbol"]))
            if a["composite_score"] >= 20: results.append(a)
            try:
                crash = detect_crash_risks(snap["symbol"], kl, snap)
                if crash["score"] >= 20:
                    crash_results.append({"symbol": snap["symbol"], **crash})
            except Exception:
                pass
        except Exception:
            kline_fail += 1
            continue

    print(f"    Klines: {kline_ok} ok / {kline_fail} failed")
    print(f"    Raw anomalies detected: {len(results)}")
    results.sort(key=lambda x: x["composite_score"], reverse=True)
    top10 = results[:TOP_K_OUTPUT]

    print("\n[6] Generate report...")
    today = datetime.now().strftime("%Y-%m-%d")
    summary = generate_summary(top10, regime)
    print(summary)

    # Save markdown report
    os.makedirs("docs", exist_ok=True)
    with open(f"docs/report-{today}.md", "w", encoding="utf-8") as f:
        f.write(summary)
        f.write("\n\n## Detailed\n\n")
        for r in top10[:5]:
            rep = generate_report(r)
            if rep: f.write(rep + "\n\n")
    with open("docs/report.md", "w", encoding="utf-8") as f:
        f.write(f"# Latest: {today}\n\n{summary}")

    # Save JSON (no duplicates)
    json_data = {
        "updated": datetime.now().isoformat(),
        "regime": regime,
        "total_scanned": len(snapshots),
        "candidates": []
    }
    seen = set()
    for r in top10:
        if r["symbol"] in seen: continue
        seen.add(r["symbol"])
        top_anoms = sorted(
            [(k, {"score": v["score"], "detail": v["detail"]})
             for k, v in r["anomalies"].items() if v["score"] >= 30],
            key=lambda x: x[1]["score"], reverse=True
        )[:3]
        snap = next((s for s in snapshots if s["symbol"] == r["symbol"]), {})
        json_data["candidates"].append({
            "rank": len(json_data["candidates"]) + 1,
            "symbol": r["symbol"],
            "score": r["composite_score"],
            "anomalies": [{"type": k, "score": v["score"], "detail": v["detail"]} for k, v in top_anoms],
            "warnings": [w["pattern"] for w in r.get("failure_warnings", [])],
            "oi": snap.get("oi", 0),
            "funding": snap.get("funding", 0),
            "volume_24h": snap.get("volume_24h", 0),
            "crash_risk": next((cr["score"] for cr in crash_results if cr["symbol"] == r["symbol"]), 0),
            "crash_warnings": [w["type"] for w in next((cr["warnings"] for cr in crash_results if cr["symbol"] == r["symbol"]), [])],
            "social_heat": social_data.get(r["symbol"], {}).get("social_heat", "未知"),
            "twitter_followers": social_data.get(r["symbol"], {}).get("twitter_followers", 0),
            "stealth_phase": social_data.get(r["symbol"], {}).get("stealth_phase", False),
            "trending_score": social_data.get(r["symbol"], {}).get("trending_score", 0),
            "reddit_subscribers": social_data.get(r["symbol"], {}).get("reddit_subscribers", 0),
        })
    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print("JSON saved")

    # AI analysis
    try:
        from src.ai_analysis import analyze_with_ai
        print("\n[AI] Running...")
        ai = analyze_with_ai(top10, regime)
        if ai:
            with open("docs/ai_analysis.md", "w", encoding="utf-8") as f: f.write(ai)
            with open("docs/report.md", "a", encoding="utf-8") as f: f.write("\n\n" + ai)
            print("AI analysis added")
    except Exception as e:
        print(f"AI skipped: {e}")

    # Backtest
    try:
        import sqlite3
        conn = sqlite3.connect("data/market.db")
        rows = conn.execute("""
            SELECT snapshot_date, symbol, price_at_snapshot, return_7d
            FROM backtest_results ORDER BY snapshot_date DESC LIMIT 50
        """).fetchall()
        bt = [{"date": r[0], "symbol": r[1], "price": r[2],
               "ret7d": round(r[3], 1) if r[3] is not None else None} for r in rows]
        conn.close()
        with open("docs/backtest.json", "w", encoding="utf-8") as f:
            json.dump({"updated": today, "entries": bt}, f, ensure_ascii=False, indent=2)
        import glob
        history_files = sorted(glob.glob("docs/report-*.md"), reverse=True)
        history_list = [f.replace("\\","/").replace("docs/","").replace(".md","").replace("report-","") for f in history_files[:30]]
        with open("docs/history.json", "w", encoding="utf-8") as f:
            json.dump({"reports": history_list}, f)
        with open("history.json", "w", encoding="utf-8") as f:
            json.dump({"reports": history_list}, f)
        print("Backtest saved")
    except: pass

    # Save rankings for backtest
    rankings = []
    for i, r in enumerate(top10):
        rankings.append({"rank": i+1, "symbol": r["symbol"], "score": r["composite_score"],
                         "signals_str": "|".join([f"{k}:{v['score']}" for k,v in r["anomalies"].items() if v["score"]>=30])})
        p = next((s["price"] for s in snapshots if s["symbol"]==r["symbol"]), 0)
        if p: save_backtest(r["symbol"], today, p)
    save_ranking(today, rankings)

    print(f"\n{'='*72}")
    print(f"  Done: {len(top10)} anomalies | DB updated | Docs generated")
    print(f"{'='*72}")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nCancelled")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback; traceback.print_exc()


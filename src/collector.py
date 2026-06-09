# collector.py - 数据采集 (Binance + CoinGecko)
import sys, time, os
import requests
from src.config import *

def _get(url: str, retries: int = 3):
    """通用 GET 请求"""
    for i in range(retries):
        try:
            r = requests.get(url, timeout=15, proxies=PROXIES)
            r.raise_for_status()
            return r.json()
        except Exception:
            if i < retries - 1:
                time.sleep(1)
    return {} if "[" not in url[:50] else []

def _get_binance(path: str, retries: int = 2):
    """Binance GET: auto-try all endpoints including relay"""
    if os.environ.get("GITHUB_ACTIONS"):
        bases = [BINANCE_RELAY] + BINANCE_FUTURES_BASES
    else:
        bases = BINANCE_FUTURES_BASES + [BINANCE_RELAY]
    for base in bases:
        url = f"{base}{path}"
        for i in range(retries):
            try:
                r = requests.get(url, timeout=15, proxies=PROXIES)
                r.raise_for_status()
                data = r.json()
                if "/ticker/24hr" in path and not isinstance(data, list):
                    continue
                return data
            except Exception:
                if i < retries - 1:
                    time.sleep(1)
    return {} if "[" not in path[:50] else []

def collect_binance_futures_tickers(top_n: int = TOP_N_VOLUME) -> list:
    """获取合约24h行情，取成交量TopN"""
    data = _get_binance("/fapi/v1/ticker/24hr")
    if not data:
        return []
    usdt = [t for t in data if t["symbol"].endswith("USDT")]
    usdt.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
    return usdt[:top_n]

def collect_oi(symbol: str) -> float:
    """获取当前OI"""
    data = _get_binance(f"/fapi/v1/openInterest?symbol={symbol}")
    return float(data.get("openInterest", 0))

def collect_funding(symbol: str) -> float:
    """获取最新资金费率"""
    data = _get_binance(f"/fapi/v1/fundingRate?symbol={symbol}&limit=1")
    if data and len(data) > 0:
        return float(data[0]["fundingRate"])
    return 0.0

def collect_klines(symbol: str, interval: str = "4h", limit: int = 200) -> list:
    """获取合约K线"""
    return _get_binance(f"/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}")

def collect_coingecko_market_data(symbols: list) -> dict:
    """
    从CoinGecko获取市值/FDV/流通率
    需要先将Binance symbol映射为CoinGecko id
    """
    try:
        # 先获取所有币的ID映射
        coin_list = _get(f"{COINGECKO}/coins/list")
        if not coin_list:
            return {}

        # 简单映射: symbol.lower() -> id
        id_map = {}
        for c in coin_list:
            id_map[c["symbol"].lower()] = c["id"]

        results = {}
        for sym in symbols:
            base = sym.replace("USDT", "").lower()
            cg_id = id_map.get(base)
            if not cg_id:
                continue
            try:
                detail = _get(
                    f"{COINGECKO}/coins/{cg_id}?"
                    "localization=false&tickers=false&community_data=false"
                    "&developer_data=false"
                )
                if detail and "market_data" in detail:
                    md = detail["market_data"]
                    results[sym] = {
                        "market_cap": md.get("market_cap", {}).get("usd"),
                        "fdv": md.get("fully_diluted_valuation", {}).get("usd"),
                        "circulating_supply": md.get("circulating_supply"),
                        "total_supply": md.get("total_supply"),
                    }
                    if results[sym]["market_cap"] and results[sym]["fdv"] and results[sym]["fdv"] > 0:
                        results[sym]["circulation_ratio"] = round(
                            results[sym]["market_cap"] / results[sym]["fdv"] * 100, 1
                        )
            except Exception:
                continue
            time.sleep(1.2)  # CoinGecko免费API限速
        return results
    except Exception:
        return {}

def collect_full_snapshot(symbol: str, ticker: dict, cg_data: dict = None) -> dict:
    """采集单个币的完整快照"""
    oi = collect_oi(symbol)
    funding = collect_funding(symbol)

    base = symbol.replace("USDT", "")
    sector = None
    for prefix, s in SECTOR_MAP.items():
        if base.upper().startswith(prefix.upper()) or base.upper() == prefix.upper():
            sector = s
            break

    snap = {
        "symbol": symbol,
        "timestamp": int(time.time()),
        "price": float(ticker.get("lastPrice", 0)),
        "volume_24h": float(ticker.get("quoteVolume", 0)),
        "oi": oi,
        "funding": funding,
        "sector": sector,
    }

    if cg_data and symbol in cg_data:
        cg = cg_data[symbol]
        snap["market_cap"] = cg.get("market_cap")
        snap["fdv"] = cg.get("fdv")
        snap["circulating_supply"] = cg.get("circulating_supply")
        snap["circulation_ratio"] = cg.get("circulation_ratio")

    return snap
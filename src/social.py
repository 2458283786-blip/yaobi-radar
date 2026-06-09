# social.py - 社交媒体热度检测 (基于市值+Tredning, 避免CoinGecko限流)
import requests
from src.config import PROXIES, COINGECKO

def get_trending_coins() -> set:
    """获取CoinGecko Trending (仅1次API调用)"""
    try:
        r = requests.get(f"{COINGECKO}/search/trending", proxies=PROXIES, timeout=15)
        r.raise_for_status()
        data = r.json()
        symbols = set()
        for c in data.get("coins", []):
            sym = (c["item"].get("symbol") or "").upper()
            symbols.add(sym + "USDT")
        return symbols
    except:
        return set()

def estimate_social_heat(symbol: str, market_cap: float, trending_set: set) -> dict:
    """
    基于市值估算社交热度
    
    逻辑:
    - 微型币(<5000万) + 不在Trending = 极致埋伏期
    - 无市值数据 + 不在Trending = 低关注埋伏期  
    - 在Trending = 正在获得关注
    - 大市值 = 已被充分发现
    """
    in_trending = symbol in trending_set

    if not market_cap or market_cap <= 0:
        if in_trending:
            heat, heat_score, stealth = "Trending新币", 50, False
        else:
            heat, heat_score, stealth = "低关注", 40, True
    elif market_cap < 50_000_000:
        heat, heat_score = "微型币", 90
        stealth = not in_trending
    elif market_cap < 200_000_000:
        heat, heat_score = "小市值", 70
        stealth = not in_trending
    elif market_cap < 1_000_000_000:
        heat, heat_score, stealth = "中市值", 45, False
    elif market_cap < 10_000_000_000:
        heat, heat_score, stealth = "大市值", 20, False
    else:
        heat, heat_score, stealth = "巨鲸", 5, False

    if in_trending:
        heat += " +Trending"
        heat_score = min(100, heat_score + 10)

    return {
        "social_heat": heat,
        "heat_score": heat_score,
        "is_trending": in_trending,
        "stealth_phase": stealth,
        "twitter_followers": 0,
        "reddit_subscribers": 0,
        "trending_score": 1 if in_trending else 0,
        "market_cap": market_cap,
    }

def get_social_data(symbols: list) -> dict:
    """获取社交媒体综合数据 (轻量版, 仅市值估算)"""
    trending = get_trending_coins()
    results = {}
    for sym in symbols:
        results[sym] = {
            "symbol": sym,
            "social_heat": "待采集",
            "heat_score": 0,
            "is_trending": sym in trending,
            "trending_score": 1 if sym in trending else 0,
            "stealth_phase": False,
            "twitter_followers": 0,
            "reddit_subscribers": 0,
        }
    return results

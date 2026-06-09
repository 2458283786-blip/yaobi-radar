# social.py - 社交媒体热度检测 (轻量版, 避免CoinGecko限流)
import requests, time
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
    基于可用数据估算社交热度 (不依赖CoinGecko社区API)
    
    判断逻辑:
    - 市值 < 100M + 不在Trending = 微型币埋伏期 (最高分)
    - 市值 < 500M + 不在Trending = 小币种埋伏期
    - 市值 > 1B = 已被市场发现
    - 在Trending榜单 = 正在获得关注
    """
    base = symbol.replace("USDT", "")
    in_trending = symbol in trending_set
    
    if not market_cap or market_cap <= 0:
        heat = "未知"
        heat_score = 10
        stealth = False
    elif market_cap < 50_000_000:
        heat = "微型币"
        heat_score = 90
        stealth = not in_trending
    elif market_cap < 200_000_000:
        heat = "小市值"
        heat_score = 70
        stealth = not in_trending
    elif market_cap < 1_000_000_000:
        heat = "中市值"
        heat_score = 40
        stealth = False
    elif market_cap < 10_000_000_000:
        heat = "大市值"
        heat_score = 20
        stealth = False
    else:
        heat = "巨鲸"
        heat_score = 5
        stealth = False
    
    if in_trending:
        heat += " +Trending"
        heat_score += 10
    
    return {
        "social_heat": heat,
        "heat_score": heat_score,
        "is_trending": in_trending,
        "stealth_phase": stealth,
        "twitter_followers": 0,
        "reddit_subscribers": 0,
        "market_cap": market_cap,
    }

def get_social_data(symbols: list) -> dict:
    """
    获取社交媒体综合数据 (轻量版)
    """
    # 1. 获取Trending (仅1次请求)
    trending = get_trending_coins()
    
    # 2. 从market_data获取市值已经在scanner里有了, 这里简化
    results = {}
    for sym in symbols:
        # 默认值 - 实际市值由scanner传入
        results[sym] = {
            "symbol": sym,
            "social_heat": "待采集",
            "heat_score": 0,
            "twitter_followers": 0,
            "reddit_subscribers": 0,
            "is_trending": sym in trending,
            "trending_score": 1 if sym in trending else 0,
            "stealth_phase": False,
        }
    
    return results

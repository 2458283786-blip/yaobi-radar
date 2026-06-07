import os, time, requests
from src.config import PROXIES, COINGECKO

def get_social_data(symbols: list) -> dict:
    try:
        coin_list = requests.get(f"{COINGECKO}/coins/list", proxies=PROXIES, timeout=15).json()
        if not isinstance(coin_list, list):
            return {}
    except:
        return {}

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
            detail = requests.get(
                f"{COINGECKO}/coins/{cg_id}?localization=false&tickers=false"
                "&community_data=true&developer_data=false",
                proxies=PROXIES, timeout=10
            ).json()
            if isinstance(detail, dict) and "community_data" in detail:
                cd = detail["community_data"]
                tw = cd.get("twitter_followers", 0) or 0
                rd = cd.get("reddit_subscribers", 0) or 0
                results[sym] = {
                    "twitter_followers": tw,
                    "reddit_subscribers": rd,
                }
                if tw > 100000: results[sym]["social_heat"] = "高热"
                elif tw > 10000: results[sym]["social_heat"] = "中等"
                elif tw > 1000: results[sym]["social_heat"] = "低关注"
                else: results[sym]["social_heat"] = "极低关注(埋伏期)"
        except:
            continue
        time.sleep(1.5)

    return results

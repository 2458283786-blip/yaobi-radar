# social.py - 社交媒体热度 & 趋势检测
import os, time, requests, json
from src.config import PROXIES, COINGECKO

def _get_cg(path: str):
    """CoinGecko API wrapper"""
    try:
        r = requests.get(f"{COINGECKO}{path}", proxies=PROXIES, timeout=15)
        r.raise_for_status()
        return r.json()
    except:
        return None

def get_trending_coins() -> dict:
    """获取CoinGecko Trending (15个当前热门币)"""
    data = _get_cg("/search/trending")
    if not data:
        return {}
    result = {}
    for c in data.get("coins", []):
        item = c["item"]
        symbol = (item.get("symbol") or "").upper() + "USDT"
        result[symbol] = {
            "trending_rank": item.get("market_cap_rank", 0),
            "trending_score": item.get("score", 0),
            "cg_id": item.get("id", ""),
        }
    return result

def get_community_data(cg_ids: list) -> dict:
    """批量获取社区数据 (Twitter/Reddit/Telegram)"""
    results = {}
    for cg_id in cg_ids:
        try:
            detail = _get_cg(
                f"/coins/{cg_id}?"
                "localization=false&tickers=false"
                "&community_data=true&developer_data=false"
            )
            if detail and "community_data" in detail:
                cd = detail["community_data"]
                results[cg_id] = {
                    "twitter_followers": cd.get("twitter_followers", 0) or 0,
                    "reddit_subscribers": cd.get("reddit_subscribers", 0) or 0,
                    "reddit_avg_posts_48h": cd.get("reddit_average_posts_48h", 0) or 0,
                    "reddit_active_accounts": cd.get("reddit_accounts_active_48h", 0) or 0,
                    "telegram_channel_count": cd.get("telegram_channel_user_count", 0) or 0,
                }
        except:
            continue
        time.sleep(0.6)
    return results

def classify_social_heat(followers: int, reddit_subs: int) -> dict:
    """分类社交热度等级"""
    total = followers + reddit_subs
    if total > 1000000:
        return {"level": "超高热度", "score": 5, "risk": "主力出货风险"}
    elif total > 100000:
        return {"level": "高热", "score": 15, "risk": "市场已充分关注"}
    elif total > 10000:
        return {"level": "中等", "score": 30, "risk": ""}
    elif total > 1000:
        return {"level": "低关注", "score": 50, "risk": "潜在埋伏机会"}
    else:
        return {"level": "极低关注(埋伏期)", "score": 80, "risk": "尚未被市场发现"}

def get_social_data(symbols: list) -> dict:
    """
    获取社交媒体综合数据
    返回: {symbol: {social_heat, twitter_followers, reddit_subs, trending, ...}}
    """
    # 1. 获取 Trending
    trending = get_trending_coins()
    
    # 2. 获取所有币的 ID 映射
    coin_list = _get_cg("/coins/list")
    if not coin_list or not isinstance(coin_list, list):
        return {}
    
    id_map = {}
    for c in coin_list:
        id_map[c["symbol"].lower()] = c["id"]
    
    # 3. 收集需要查询的 CG ID (最多30个)
    target_ids = set()
    symbol_id_map = {}
    for sym in symbols[:50]:
        base = sym.replace("USDT", "").lower()
        cg_id = id_map.get(base)
        if cg_id:
            target_ids.add(cg_id)
            symbol_id_map[cg_id] = sym
    
    # 4. 批量获取社区数据
    community = get_community_data(list(target_ids))
    
    # 5. 组装结果
    results = {}
    for sym in symbols:
        base = sym.replace("USDT", "").lower()
        cg_id = id_map.get(base)
        
        entry = {
            "symbol": sym,
            "social_heat": "未知",
            "heat_score": 0,
            "twitter_followers": 0,
            "reddit_subscribers": 0,
            "is_trending": False,
            "trending_score": 0,
            "stealth_phase": False,
        }
        
        # Trending 数据
        if sym in trending:
            entry["is_trending"] = True
            entry["trending_score"] = trending[sym]["trending_score"]
        
        # 社区数据
        if cg_id and cg_id in community:
            cd = community[cg_id]
            entry["twitter_followers"] = cd["twitter_followers"]
            entry["reddit_subscribers"] = cd["reddit_subscribers"]
            entry["reddit_active_48h"] = cd["reddit_active_accounts"]
            entry["telegram_users"] = cd["telegram_channel_count"]
            
            heat = classify_social_heat(cd["twitter_followers"], cd["reddit_subscribers"])
            entry["social_heat"] = heat["level"]
            entry["heat_score"] = heat["score"]
            entry["heat_risk"] = heat["risk"]
            
            # Stealth phase: low followers + not trending = 埋伏期
            if heat["score"] >= 50 and not entry["is_trending"]:
                entry["stealth_phase"] = True
        
        results[sym] = entry
    
    return results

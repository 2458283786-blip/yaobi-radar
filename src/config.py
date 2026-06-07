# config.py - 全局配置
import os

BINANCE_SPOT = "https://api.binance.com"
BINANCE_FUTURES = "https://fapi.binance.com"
COINGECKO = "https://api.coingecko.com/api/v3"

# 代理: 环境变量 PROXY_URL 优先, 否则用默认值, 都不设则不使用代理
PROXY = os.environ.get("PROXY_URL", "http://127.0.0.1:65532")
PROXIES = {"http": PROXY, "https": PROXY}
# GitHub Actions 环境下不设代理
if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
    PROXIES = None

SCAN_INTERVAL = "4h"
TOP_N_VOLUME = 100
TOP_K_OUTPUT = 10
DATA_RETENTION_DAYS = 180
PERSISTENCE_WINDOW = 7

# 排除列表 (主流币 + 稳定币)
EXCLUDE_SYMBOLS = {
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
    "USDCUSDT","BUSDUSDT","DAIUSDT","TUSDUSDT",
}

# 板块映射
SECTOR_MAP = {
    "AI": "AI Agent","AGIX": "AI Agent","FET": "AI Agent","OCEAN": "AI Agent",
    "WLD": "AI Agent","TAO": "AI Agent","AKT": "AI Agent","RNDR": "AI Agent",
    "PEPE": "Meme","BONK": "Meme","FLOKI": "Meme","WIF": "Meme",
    "SHIB": "Meme","DOGE": "Meme","MEME": "Meme","TURBO": "Meme",
    "MUBARAK": "Meme",
    "LINK": "RWA","ONDO": "RWA","MKR": "RWA","CFG": "RWA",
    "POL": "RWA","OM": "RWA",
    "IMX": "GameFi","GALA": "GameFi","SAND": "GameFi","MANA": "GameFi",
    "PIXEL": "GameFi","PRIME": "GameFi","YGG": "GameFi",
    "RENDER": "DePIN","HNT": "DePIN","IOTX": "DePIN","AR": "DePIN",
    "ANKR": "DePIN",
}

FAILURE_CASES = {
    "high_funding_trap": "费率 >0.1% -> 多头拥挤 -> 大概率回调",
    "dead_cat_bounce": "缩量反弹3天 -> 再创新低 -> 假突破",
    "volume_spike_fade": "单日暴量 -> 次日量缩80% -> 主力出货",
}

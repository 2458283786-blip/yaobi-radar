# analyzer.py - 市场结构异常检测引擎
import numpy as np
from datetime import datetime
from src.config import *
from src.db import get_history, get_latest_snapshot

def detect_oi_acceleration(history: list) -> dict:
    """
    OI加速度: 衡量OI变化的二阶导数
    异常定义: OI在加速增长，但价格没跟上
    返回: score 0-100, 解释文本
    """
    if len(history) < 6:
        return {"score": 0, "detail": "历史数据不足"}

    oi_vals = [h["oi"] for h in history if h.get("oi") and h["oi"] > 0]
    if len(oi_vals) < 6:
        return {"score": 0, "detail": "OI数据不足"}

    oi_arr = np.array(oi_vals)

    # 计算OI变化率序列 (一阶导)
    if len(oi_arr) >= 3:
        recent_delta = (oi_arr[-1] - oi_arr[-3]) / oi_arr[-3] * 100
    else:
        recent_delta = 0

    if len(oi_arr) >= 6:
        early_delta = (oi_arr[-3] - oi_arr[-6]) / oi_arr[-6] * 100
        # 加速度 = 近期变化率 - 早期变化率
        acceleration = recent_delta - early_delta
    else:
        acceleration = 0

    # 评分: OI在加速增长
    if acceleration > 15:
        score = 90
        detail = f"OI加速增长(+{acceleration:.0f}%): OI在近3期增速超过前3期"
    elif acceleration > 8:
        score = 70
        detail = f"OI温和加速(+{acceleration:.0f}%): 资金开始流入"
    elif acceleration > 3:
        score = 45
        detail = f"OI小幅加速(+{acceleration:.0f}%)"
    elif acceleration > 0:
        score = 25
        detail = f"OI微增(+{acceleration:.0f}%)"
    else:
        score = 5
        detail = f"OI未加速({acceleration:+.0f}%)"

    return {"score": score, "detail": detail, "acceleration": round(acceleration, 1)}


def detect_volume_expansion(history: list) -> dict:
    """
    成交量持续扩张: 成交量稳步放大
    异常定义: 连续N期成交量在增长
    """
    if len(history) < 6:
        return {"score": 0, "detail": "数据不足"}

    vol_vals = [h["volume_24h"] for h in history if h.get("volume_24h") and h["volume_24h"] > 0]
    if len(vol_vals) < 6:
        return {"score": 0, "detail": "成交量数据不足"}

    vol_arr = np.array(vol_vals)

    # 检查连续增长
    consecutive_up = 0
    for i in range(len(vol_arr)-1, 0, -1):
        if vol_arr[i] > vol_arr[i-1] * 1.02:  # 2%以上才算增长
            consecutive_up += 1
        else:
            break

    # 量能扩张比
    if len(vol_arr) >= 6:
        expansion = (np.mean(vol_arr[-3:]) - np.mean(vol_arr[-6:-3])) / np.mean(vol_arr[-6:-3]) * 100
    else:
        expansion = 0

    if consecutive_up >= 4 and expansion > 20:
        score = 85
        detail = f"成交量持续扩张(连续{consecutive_up}期, +{expansion:.0f}%)"
    elif consecutive_up >= 3:
        score = 65
        detail = f"成交量温和扩张(连续{consecutive_up}期)"
    elif expansion > 10:
        score = 40
        detail = f"成交量略有扩张(+{expansion:.0f}%)"
    else:
        score = 10
        detail = "成交量无明显扩张"

    return {"score": score, "detail": detail, "expansion_pct": round(expansion, 1)}


def detect_volatility_compression(klines: list) -> dict:
    """
    波动率压缩: 布林带持续收窄
    对标RAVE: BB压缩到4%分位后爆发
    """
    if len(klines) < 50:
        return {"score": 0, "detail": "K线数据不足"}

    closes = np.array([float(k[4]) for k in klines])

    # 计算过去50根K线每20根的BB宽度
    bws = []
    for i in range(30, 0, -1):
        if len(closes) >= i + 20:
            w = closes[-(i+20):-i] if i > 0 else closes[-20:]
            if len(w) >= 20:
                bw = np.std(w) * 4 / np.mean(w) * 100
                bws.append(bw)

    if not bws:
        return {"score": 0, "detail": "无法计算波动率"}

    bws_arr = np.array(bws)
    current_bw = bws_arr[-1]
    percentile = np.sum(bws_arr <= current_bw) / len(bws_arr) * 100  # %分位数

    # 带宽是否在缩小
    if len(bws_arr) >= 5:
        bw_trend = (bws_arr[-1] - np.mean(bws_arr[-5:-1])) / np.mean(bws_arr[-5:-1]) * 100
    else:
        bw_trend = 0

    if percentile <= 8:
        score = 90
        detail = f"波动率极度压缩(带宽{current_bw:.1f}%, 分位{percentile:.0f}%)"
    elif percentile <= 15:
        score = 70
        detail = f"波动率显著压缩(分位{percentile:.0f}%)"
    elif percentile <= 25:
        score = 50
        detail = f"波动率偏紧(分位{percentile:.0f}%)"
    elif percentile <= 40:
        score = 30
        detail = f"波动率正常偏低(分位{percentile:.0f}%)"
    else:
        score = 5
        detail = f"波动率正常(分位{percentile:.0f}%)"

    return {"score": score, "detail": detail, "bb_percentile": round(percentile, 1)}


def detect_funding_divergence(history: list) -> dict:
    """
    费率背离: 价格在跌/横盘，费率却从负转正或持续中性
    异常定义: 价格未涨但费率不再为负 = 空头撤退信号
    """
    if len(history) < 6:
        return {"score": 0, "detail": "数据不足"}

    fr_vals = [(h.get("funding") or 0) for h in history]
    price_vals = [h["price"] for h in history if h.get("price")]

    if len(fr_vals) < 4:
        return {"score": 0, "detail": "费率数据不足"}

    recent_fr = np.mean(fr_vals[-3:])
    early_fr = np.mean(fr_vals[-6:-3]) if len(fr_vals) >= 6 else fr_vals[0]
    fr_change = recent_fr - early_fr

    # 价格变化
    if len(price_vals) >= 6:
        price_change = (price_vals[-1] - price_vals[-6]) / price_vals[-6] * 100
    else:
        price_change = 0

    # 负面背离: 价格跌/平, 费率却在上升(空头离场)
    if price_change < -3 and fr_change > 0.0002:
        score = 85
        detail = f"费率背离: 价格{price_change:+.1f}%但费率从{early_fr*100:.3f}%升至{recent_fr*100:.3f}%(空头撤退)"
    elif price_change < 0 and fr_change > 0.0001:
        score = 60
        detail = f"费率微背离: 价格微跌但费率上升(空头犹豫)"
    elif fr_change > 0.0005:
        score = 40
        detail = f"费率显著上升({fr_change*100:+.3f}%)"
    else:
        score = 10
        detail = "费率无明显背离"

    return {"score": score, "detail": detail}


def detect_oi_mc_divergence(history: list) -> dict:
    """
    OI/MC比变化: 持仓量相对市值的增长
    高OI/MC = 高杠杆参与度 = 容易引发连锁反应
    """
    if len(history) < 4:
        return {"score": 0, "detail": "数据不足"}

    ratios = []
    for h in history:
        oi = h.get("oi")
        price = h.get("price")
        if oi and price and oi > 0 and price > 0:
            # OI * price ≈ notional value; 我们用简化版
            ratios.append(oi / (h.get("volume_24h") or 1))

    if len(ratios) < 4:
        return {"score": 0, "detail": "数据不足"}

    recent_r = np.mean(ratios[-3:])
    early_r = np.mean(ratios[-6:-3]) if len(ratios) >= 6 else ratios[0]
    change = (recent_r - early_r) / early_r * 100 if early_r > 0 else 0

    if change > 30:
        score = 80
        detail = f"OI/Vol比快速上升(+{change:.0f}%): 持仓相对成交量在膨胀"
    elif change > 15:
        score = 55
        detail = f"OI/Vol比上升(+{change:.0f}%)"
    elif change > 5:
        score = 30
        detail = f"OI/Vol比微升(+{change:.0f}%)"
    else:
        score = 5
        detail = "OI/Vol比稳定"

    return {"score": score, "detail": detail}


def detect_relative_strength(klines: list, btc_klines: list = None) -> dict:
    """
    相对强度: 币价相对BTC的表现
    如果在BTC下跌时该币不跌/微涨 = 强于大盘
    """
    if len(klines) < 12:
        return {"score": 0, "detail": "数据不足"}

    closes = np.array([float(k[4]) for k in klines])
    change = (closes[-1] - closes[-12]) / closes[-12] * 100 if closes[-12] > 0 else 0

    if btc_klines and len(btc_klines) >= 12:
        btc_closes = np.array([float(k[4]) for k in btc_klines])
        btc_change = (btc_closes[-1] - btc_closes[-12]) / btc_closes[-12] * 100 if btc_closes[-12] > 0 else 0
        rs = change - btc_change
    else:
        rs = change

    if rs > 10:
        score = 85
        detail = f"相对强度显著(+{rs:.1f}% vs BTC): 独立走强"
    elif rs > 5:
        score = 60
        detail = f"相对强度偏强(+{rs:.1f}% vs BTC)"
    elif rs > 0:
        score = 35
        detail = f"略微跑赢大盘(+{rs:.1f}%)"
    elif rs > -5:
        score = 15
        detail = f"与大盘同步({rs:+.1f}%)"
    else:
        score = 5
        detail = f"显著弱于大盘({rs:+.1f}%)"

    return {"score": score, "detail": detail}


def assess_market_regime(btc_klines: list = None) -> str:
    """评估当前市场状态: Bull / Sideways / Bear"""
    if not btc_klines or len(btc_klines) < 50:
        return "Unknown"

    closes = np.array([float(k[4]) for k in btc_klines])

    # 简单判断: 20日均线方向 + 价格相对位置
    ma20 = np.mean(closes[-20:])
    ma50 = np.mean(closes[-min(50, len(closes)):])
    current = closes[-1]

    if current > ma20 > ma50 and current > ma20 * 1.05:
        return "Bull"
    elif current < ma20 < ma50 and current < ma20 * 0.95:
        return "Bear"
    else:
        return "Sideways"


def calc_persistence_score(history: list) -> dict:
    """
    持续性评分: 判断异常是否持续多日
    异常维度: OI趋势、成交量趋势、费率趋势
    """
    if len(history) < 6:
        return {"score": 0, "detail": "历史数据不足"}

    persistence_signals = 0

    # 1. OI持续增长(至少4/6期)
    oi_vals = [h["oi"] for h in history if h.get("oi") and h["oi"] > 0]
    if len(oi_vals) >= 6:
        oi_up = sum(1 for i in range(1, len(oi_vals)) if oi_vals[i] > oi_vals[i-1])
        if oi_up >= 4:
            persistence_signals += 1

    # 2. 成交量持续(至少4/6期)
    vol_vals = [h["volume_24h"] for h in history if h.get("volume_24h") and h["volume_24h"] > 0]
    if len(vol_vals) >= 6:
        vol_up = sum(1 for i in range(1, len(vol_vals)) if vol_vals[i] > vol_vals[i-1] * 1.02)
        if vol_up >= 3:
            persistence_signals += 1

    # 3. 费率趋势一致(非剧烈波动)
    fr_vals = [h.get("funding") or 0 for h in history]
    if len(fr_vals) >= 6:
        fr_std = np.std(fr_vals[-6:])
        if fr_std < 0.0003:  # 费率稳定=筹码稳定
            persistence_signals += 1

    if persistence_signals >= 3:
        score = 90
        detail = "多重异常持续多日(高度可信)"
    elif persistence_signals >= 2:
        score = 65
        detail = "部分异常持续"
    elif persistence_signals >= 1:
        score = 35
        detail = "单一异常持续"
    else:
        score = 10
        detail = "无明显持续性"

    return {"score": score, "detail": detail, "signals_count": persistence_signals}


def match_failure_patterns(snapshot: dict, history: list) -> list:
    """匹配失败案例模式"""
    warnings = []

    # 高费率陷阱
    if snapshot.get("funding") and snapshot["funding"] > 0.001:
        warnings.append({
            "pattern": "高费率陷阱",
            "risk": FAILURE_CASES["high_funding_trap"],
            "match": f"当前费率{snapshot['funding']*100:.3f}% > 0.1%"
        })

    # 假突破检查: 价格在涨但量在缩
    if history and len(history) >= 3:
        recent_vol = [h.get("volume_24h", 0) for h in history[-3:]]
        recent_price = [h.get("price", 0) for h in history[-3:]]
        if all(p > 0 for p in recent_price):
            price_up = recent_price[-1] > recent_price[0] * 1.03
            vol_down = recent_vol[-1] < recent_vol[0] * 0.8
            if price_up and vol_down:
                warnings.append({
                    "pattern": "缩量反弹",
                    "risk": FAILURE_CASES["dead_cat_bounce"],
                    "match": "近3期价格涨但量缩"
                })

    # 暴量后缩量
    if history and len(history) >= 5:
        vols = [h.get("volume_24h", 0) for h in history[-5:]]
        if max(vols) > np.mean(vols) * 2.5 and vols[-1] < max(vols) * 0.3:
            warnings.append({
                "pattern": "暴量出货",
                "risk": FAILURE_CASES["volume_spike_fade"],
                "match": "近期有单日暴量后迅速萎缩"
            })

    return warnings


def match_success_patterns(snapshot: dict, history: list) -> list:
    """匹配成功案例模式（RAVE/LAB/CREAM等共同特征）"""
    matches = []

    # 检查波动率压缩+OI增长 = RAVE模式
    if snapshot.get("bb_percentile") and snapshot["bb_percentile"] <= 15:
        oi_accel = detect_oi_acceleration(history)
        if oi_accel.get("score", 0) >= 45:
            matches.append({
                "case": "RAVE模式(波动率压缩+OI加速)",
                "similarity": "BB极窄 + OI持续增长",
                "outcome": "RAVE在类似结构后+496%",
                "caution": "RAVE是极端案例，不保证重复"
            })

    # 持续缩量+OI稳定 = LAB模式
    vol_exp = detect_volume_expansion(history)
    if vol_exp.get("score", 0) <= 20:
        oi_accel = detect_oi_acceleration(history)
        if oi_accel.get("acceleration", 0) > 0:
            matches.append({
                "case": "LAB模式(缩量+OI缓慢积累)",
                "similarity": "成交量低迷 + OI稳定增长",
                "outcome": "LAB在类似结构后+339%",
                "caution": "LAB经历较长时间横盘"
            })

    return matches


def detect_all_anomalies(symbol: str, ticker: dict, klines: list,
                         btc_klines: list = None) -> dict:
    """
    综合分析一个币的所有市场结构异常
    返回: 综合异常报告
    """
    history = get_history(symbol, days=PERSISTENCE_WINDOW)

    # 各维度检测
    oi_accel = detect_oi_acceleration(history) if history else {"score": 0, "detail": "无历史"}
    vol_exp = detect_volume_expansion(history) if history else {"score": 0, "detail": "无历史"}
    vol_comp = detect_volatility_compression(klines)
    fund_div = detect_funding_divergence(history) if history else {"score": 0, "detail": "无历史"}
    oi_mc = detect_oi_mc_divergence(history) if history else {"score": 0, "detail": "无历史"}
    rs_strength = detect_relative_strength(klines, btc_klines)
    persist = calc_persistence_score(history) if history else {"score": 0, "detail": "无历史"}

    # 综合异常分: 各维度取最高分(不是求和, 是发现异常)
    anomalies = [oi_accel, vol_exp, vol_comp, fund_div, oi_mc, rs_strength]
    anomaly_scores = [a["score"] for a in anomalies]
    top_anomalies = sorted(anomaly_scores, reverse=True)

    # 综合评分 = 最强异常*0.4 + 次强异常*0.3 + 第三*0.2 + 持续性*0.1
    composite = (
        top_anomalies[0] * 0.4 +
        (top_anomalies[1] if len(top_anomalies) > 1 else 0) * 0.3 +
        (top_anomalies[2] if len(top_anomalies) > 2 else 0) * 0.2 +
        persist["score"] * 0.1
    )

    market_regime = assess_market_regime(btc_klines)

    # 失败模式匹配
    current_snap = {
        "funding": float(ticker.get("funding", 0)) if ticker.get("funding") else 0,
        "price": float(ticker.get("lastPrice", 0)),
        "bb_percentile": vol_comp.get("bb_percentile", 50),
    }
    failures = match_failure_patterns(current_snap, history)
    successes = match_success_patterns(current_snap, history)

    return {
        "symbol": symbol,
        "composite_score": round(composite, 1),
        "market_regime": market_regime,
        "anomalies": {
            "oi_acceleration": oi_accel,
            "volume_expansion": vol_exp,
            "volatility_compression": vol_comp,
            "funding_divergence": fund_div,
            "oi_mc_divergence": oi_mc,
            "relative_strength": rs_strength,
        },
        "persistence": persist,
        "failure_warnings": failures,
        "success_matches": successes,
    }

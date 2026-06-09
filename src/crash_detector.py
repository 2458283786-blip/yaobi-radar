# crash_detector.py - 暴跌风险预警
import numpy as np
from src.config import FAILURE_CASES

def detect_crash_risks(symbol: str, klines: list, ticker: dict) -> dict:
    """
    检测暴跌风险信号（基于真实暴跌案例复盘）
    
    核心发现:
    1. 前期大涨后暴跌 (OPN +48% -> -43%)
    2. 费率极度为负但仍在跌 (HOME -1%费率 -> -33%)
    3. 暴量后缩量 = 主力出货
    """
    if len(klines) < 48:
        return {"score": 0, "warnings": [], "detail": "数据不足"}

    c = np.array([float(k[4]) for k in klines])
    h = np.array([float(k[2]) for k in klines])
    l = np.array([float(k[3]) for k in klines])
    v = np.array([float(k[5]) for k in klines])

    warnings = []
    risk_score = 0
    close = c[-1]

    # ═══ (1) 前期暴涨 → 回调风险 ═══
    gain_24 = (c[-1] - c[-6]) / c[-6] * 100 if len(c) >= 7 else 0
    gain_48 = (c[-1] - c[-12]) / c[-12] * 100 if len(c) >= 13 else 0

    if gain_24 > 30:
        risk_score += 25
        warnings.append({
            "type": "前期暴涨",
            "detail": f"24h涨幅+{gain_24:.0f}%，获利盘压力大",
            "case": "OPNUSDT: +48%后暴跌-43%"
        })
    elif gain_24 > 15:
        risk_score += 15
        warnings.append({
            "type": "短期急涨",
            "detail": f"24h涨幅+{gain_24:.0f}%，注意回调风险",
        })
    elif gain_48 > 40:
        risk_score += 20
        warnings.append({
            "type": "中期急涨",
            "detail": f"48h涨幅+{gain_48:.0f}%，高位风险",
        })

    # ═══ (2) 费率陷阱 ═══
    funding = float(ticker.get("funding", 0))

    if funding > 0.003:  # >0.3%
        risk_score += 20
        warnings.append({
            "type": "高费率陷阱",
            "detail": f"费率{funding*100:.2f}%，多头拥挤",
            "case": FAILURE_CASES["high_funding_trap"]
        })
    elif funding > 0.001:  # >0.1%
        risk_score += 10
        warnings.append({
            "type": "费率偏高",
            "detail": f"费率{funding*100:.3f}%，多头成本高",
        })

    # 极端负费率 + 仍在跌 = 恐慌砸盘, 不是反转信号
    if funding < -0.002 and gain_24 < -5:
        risk_score += 15
        warnings.append({
            "type": "恐慌砸盘",
            "detail": f"费率{funding*100:.2f}%但仍在跌，非反转信号",
            "case": "HOMEUSDT: -1%费率仍跌-33%"
        })

    # ═══ (3) 暴量出货 ═══
    if len(v) >= 24:
        max_recent = np.max(v[-8:])
        avg_older = np.mean(v[-24:-8])
        if avg_older > 0 and max_recent > avg_older * 3:
            # 检查是否量已经在萎缩（暴量后缩量）
            if v[-1] < max_recent * 0.4:
                risk_score += 15
                warnings.append({
                    "type": "暴量出货",
                    "detail": "近期暴量后迅速缩量，疑似主力出货",
                    "case": FAILURE_CASES["volume_spike_fade"]
                })

    # ═══ (4) RSI 超买 ═══
    deltas = np.diff(c[-15:])
    gains = np.where(deltas>0,deltas,0); losses = np.where(deltas<0,-deltas,0)
    ag = np.mean(gains) if len(gains)>0 else 0
    al = np.mean(losses) if len(losses)>0 else 0
    rsi = 100-100/(1+ag/al) if al>0 else 100

    if rsi > 80:
        risk_score += 15
        warnings.append({"type": "RSI超买", "detail": f"RSI={rsi:.0f}，极度超买"})
    elif rsi > 70:
        risk_score += 8
        warnings.append({"type": "RSI偏高", "detail": f"RSI={rsi:.0f}，处于超买区域"})

    # ═══ (5) 价格顶部 ═══
    if len(h) >= 48:
        hh = np.max(h[-48:]); ll = np.min(l[-48:])
        pos = (close-ll)/(hh-ll) if hh!=ll else 0.5
        if pos > 0.90:
            risk_score += 10
            warnings.append({"type": "价格触顶", "detail": f"价格在48h区间{pos*100:.0f}%高位"})
        elif pos > 0.75:
            risk_score += 5

    risk_score = min(100, risk_score)

    return {
        "score": risk_score,
        "warnings": warnings,
        "detail": f"{len(warnings)}个风险信号" if warnings else "无显著风险",
        "metrics": {
            "rsi": round(rsi, 1),
            "gain_24h": round(gain_24, 1),
            "funding": round(funding*100, 4),
        }
    }

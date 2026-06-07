# notify.py - 多渠道推送
import os, json, requests

def send_pushplus(data: dict):
    """通过 PushPlus 推送到微信"""
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        return False

    candidates = data.get("candidates", [])
    if not candidates:
        msg = f"[YaoBi Radar] {data['regime']} | 无异常标的"
    else:
        msg = f"【YaoBi Radar】市场: {data['regime']} | 扫描: {data['total_scanned']}个\n\n"
        for c in candidates[:5]:
            e = "🔥" if c["score"]>=50 else "⭐"
            msg += f"{e} {c['symbol']} ({c['score']:.1f}分)\n"
            for a in c.get("anomalies", [])[:2]:
                msg += f"  · {a['detail']}\n"
            if c.get("warnings"):
                msg += f"  ⚠️ {', '.join(c['warnings'])}\n"
            msg += "\n"
        msg += "查看完整报告: https://2458283786-blip.github.io/yaobi-radar/"

    try:
        r = requests.post(
            "http://www.pushplus.plus/send",
            json={"token": token, "title": f"YaoBi Radar - {data['regime']}", "content": msg},
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False


def send_telegram(data: dict):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    candidates = data.get("candidates", [])
    if not candidates:
        msg = f"No anomalies in {data['regime']}"
    else:
        msg = f"*YaoBi Radar* | {data['regime']}\n"
        for c in candidates[:5]:
            e = "🔥" if c["score"]>=50 else "⭐"
            msg += f"{e} *{c['symbol']}* ({c['score']:.1f})\n"
            for a in c.get("anomalies", [])[:2]:
                msg += f"  · {a['detail']}\n"
            if c.get("warnings"):
                msg += f"  ⚠️ {', '.join(c['warnings'])}\n"
            msg += "\n"

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False


if __name__ == "__main__":
    with open("outputs/data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    pp = send_pushplus(data)
    tg = send_telegram(data)
    print(f"PushPlus(WeChat): {'OK' if pp else 'skip'}  |  Telegram: {'OK' if tg else 'skip'}")


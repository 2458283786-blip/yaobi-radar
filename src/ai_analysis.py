# ai_analysis.py - AI专业解读（只解释，不预测）
import os, json

def build_prompt(candidates: list, regime: str) -> str:
    """构建AI分析提示词"""
    top5 = []
    for c in candidates[:5]:
        anoms = [f"{a['type']}: {a['detail']}" for a in c.get("anomalies", [])]
        top5.append({
            "symbol": c["symbol"],
            "score": c["score"],
            "anomalies": anoms,
            "warnings": c.get("warnings", []),
        })

    prompt = f"""你是一个加密货币市场结构分析师。你的任务是解释市场异常，绝不预测价格。

当前市场状态: {regime}

以下是通过市场结构异常扫描器筛选出的候选币:

{json.dumps(top5, ensure_ascii=False, indent=2)}

请对每个币进行简短分析（每个币2-3句话）:
1. 该币属于什么赛道/叙事（AI、Meme、RWA、GameFi、DePIN、L1等）
2. 当前结构异常意味着什么（例如：波动率压缩=市场在等待方向选择）
3. 主要风险点（如：高费率陷阱、流动性不足、大盘拖累等）

严格要求:
- 不要预测价格
- 不要说"会涨""会跌"
- 不要说"建议买入""建议卖出"
- 只描述客观事实和市场结构含义

用中文回答，格式：
## AI解读

### COIN_NAME
赛道: xxx
结构含义: xxx
风险: xxx

（每个币一个###小节）"""

    return prompt


def analyze_with_ai(candidates: list, regime: str) -> str:
    """调用OpenAI API生成分析"""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        return None

    prompt = build_prompt(candidates, regime)

    try:
        import requests
        r = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": "你是一个市场结构分析师。只解释客观事实，不预测价格，不提供投资建议。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 800,
            },
            timeout=30
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        else:
            print(f"AI API error: {r.status_code}")
            return None
    except Exception as e:
        print(f"AI error: {e}")
        return None


if __name__ == "__main__":
    with open("docs/data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    result = analyze_with_ai(data["candidates"], data["regime"])
    if result:
        with open("docs/ai_analysis.md", "w", encoding="utf-8") as f:
            f.write(result)
        print("AI analysis saved to docs/ai_analysis.md")
    else:
        print("AI analysis skipped (no API key or error)")


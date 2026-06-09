# report.py - 异常报告生成 (只解释, 不预测)
def generate_report(analysis: dict) -> str:
    lines = []
    sym = analysis["symbol"]
    score = analysis["composite_score"]
    regime = analysis["market_regime"]
    anomalies = analysis["anomalies"]
    persist = analysis["persistence"]
    failures = analysis.get("failure_warnings", [])
    successes = analysis.get("success_matches", [])

    if score >= 70: level = "高度异常"
    elif score >= 50: level = "中度异常"
    elif score >= 30: level = "轻度异常"
    else: return None

    lines.append(f"## {sym} - Market Structure Anomaly Report")
    lines.append(f"Level: **{level}** ({score:.1f}/100) | Regime: **{regime}**")
    lines.append("")

    lines.append("### Detected Structure Anomalies")
    labels = {
        "oi_acceleration": "OI Acceleration",
        "volume_expansion": "Volume Expansion",
        "volatility_compression": "Volatility Compression",
        "funding_divergence": "Funding Divergence",
        "oi_mc_divergence": "OI/MC Divergence",
        "relative_strength": "Relative Strength",
        "social_momentum": "Social Momentum",
    }
    for name, a in anomalies.items():
        if a["score"] >= 30:
            lines.append(f"- **{labels.get(name, name)}**: {a['detail']} (score: {a['score']})")
    lines.append("")

    lines.append("### Persistence")
    lines.append(f"- {persist['detail']}")
    if persist["score"] >= 50:
        lines.append("- Anomalies are persistent, higher reliability")
    lines.append("")

    if failures:
        lines.append("### [WARNING] Similar to Failure Cases")
        for f in failures:
            lines.append(f"- **{f['pattern']}**: {f['risk']}")
            lines.append(f"  Match: {f['match']}")
        lines.append("")

    if successes:
        lines.append("### Historical Reference Cases")
        for s in successes:
            lines.append(f"- **{s['case']}**")
            lines.append(f"  Similarity: {s['similarity']}")
            lines.append(f"  Outcome: {s['outcome']}")
            lines.append(f"  Note: {s['caution']}")
        lines.append("")

    lines.append("---")
    lines.append("*Describes structure anomalies only. Not investment advice.*")
    return "\n".join(lines)


def generate_summary(results: list, regime: str) -> str:
    lines = []
    lines.append("# Daily Market Structure Anomaly Scan")
    lines.append(f"Market Regime: **{regime}**")
    lines.append(f"Found {len(results)} candidates with notable structure anomalies")
    lines.append("")

    for i, r in enumerate(results, 1):
        sym = r["symbol"]
        score = r["composite_score"]
        top_anomalies = sorted(
            [(k, v) for k, v in r["anomalies"].items() if v["score"] >= 40],
            key=lambda x: x[1]["score"], reverse=True
        )[:3]

        short_names = {
            "oi_acceleration": "OI Accel", "volume_expansion": "Vol Expand",
            "volatility_compression": "Vol Compr", "funding_divergence": "Fund Div",
            "oi_mc_divergence": "OI Ratio", "relative_strength": "Rel Strength",
            "social_momentum": "Social",
        }
        lines.append(f"### {i}. {sym} - Anomaly Score: {score:.1f}")
        for name, a in top_anomalies:
            lines.append(f"  - {short_names.get(name, name)}: {a['detail']}")

        if r.get("failure_warnings"):
            lines.append(f"  - [WARNING] Risk: {r['failure_warnings'][0]['pattern']}")
        lines.append("")

    lines.append("---")
    lines.append("*Records structure anomalies only. Not investment advice.*")
    return "\n".join(lines)

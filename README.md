# YaoBi Radar v2.0 — Market Structure Anomaly Scanner

发现市场结构异常，不预测价格涨跌。

## 核心原则

- **定位**: Market Anomaly Scanner，不是量化系统
- **寻找**: 结构异常的币（OI加速、量能扩张、波动压缩、费率背离、相对强度）
- **不寻找**: 涨得快的币
- **输出**: 3-10个候选 + 为什么异常 + 风险提示 + 历史案例对比
- **不输出**: 买卖建议、目标价、价格预测

## 架构

```
scanner.py          # 主入口
src/
  config.py         # 配置 (代理/黑名单/板块映射)
  db.py             # SQLite 数据库 (180天快照)
  collector.py      # Binance + CoinGecko 数据采集
  analyzer.py       # 结构异常检测引擎
  report.py         # 报告生成
.github/workflows/
  scanner.yml       # 每4小时自动执行
data/
  market.db         # SQLite 数据库 (自动创建)
```

## 本地使用

```bash
pip install requests numpy
python scanner.py
```

通过代理:
```bash
set PROXY_URL=http://127.0.0.1:7890
python scanner.py
```

## 自动化部署

推送到 GitHub 后自动每 4 小时运行一次 (UTC 00:00, 04:00, 08:00, 12:00, 16:00, 20:00)。

数据存入 `data/market.db`，次日运行自动回溯前日候选的 7日/30日收益率。

## 评分体系

| 维度 | 权重 | 含义 |
|------|------|------|
| 波动率压缩 | 40% | BB带宽在当前所处历史分位 |
| 相对强度 | 30% | 相对BTC超额收益 |
| OI加速度 | - | OI变化趋势（需历史数据） |
| 量能扩张 | - | 成交量持续放大（需历史数据） |
| 持续性 | 10% | 异常跨期稳定度 |

首次运行因无历史数据，以波动率+相对强度为主。持续运行后OI/量能维度逐步生效。

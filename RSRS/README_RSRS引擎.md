# RSRS策略引擎 - 跨Agent调用说明

**维护人**: 策略测算 (agent-6c2abd87)
**最后更新**: 2026-07-18

---

## 目录结构

```
D:\QClaw_Trading\RSRS\
├── rsrs_engine.py          ← 核心引擎（可import）
├── rsrs_daily_output.py    ← 每日信号输出脚本
├── rsrs_final_strategy.py  ← v4终版（功能完整但较旧）
├── signals/
│   ├── latest.json         ← 最新每日信号（下游消费）
│   ├── signal_YYYYMMDD.json ← 历史归档
│   └── API_SPEC.json       ← 接口规范文档
├── README_RSRS引擎.md       ← 本文件
└── ... (其他实验脚本)
```

---

## 其他Agent调用方式

### 方式1：读JSON（推荐，0依赖）

```python
import json

# 读取最新信号
with open(r'D:\QClaw_Trading\RSRS\signals\latest.json') as f:
    signal = json.load(f)

# 获取关键字段
zscore = signal['rsrs']['zscore']
beta = signal['rsrs']['beta']
signal_text = signal['rsrs']['signal_text']  # '买入'/'卖出'/'观望'

# 动量Top1
top = signal['momentum']['c63_top']
if top:
    best_code = top[0]['code']
    best_score = top[0]['score']

# 估值最便宜
cheapest = signal['valuation']['cheapest']
print(f"{cheapest['name']}: {cheapest['score']}")

# 仓位
print(f"总仓位: {signal['portfolio']['total_position']:.1%}")

# 持仓清单
for h in signal['portfolio']['holdings']:
    print(f"{h['name']}({h['code']}): {h['weight']}")
```

### 方式2：import引擎（需要Python环境）

```python
import sys
sys.path.insert(0, r'D:\QClaw_Trading\RSRS')
from rsrs_engine import RSRSStrategy, load_etf, ETF_POOL, WIDE_POOL

# 默认池13只ETF
strat = RSRSStrategy(pool='default')
result = strat.run(rebalance_days=42, top_n=1)

# 宽基池5只ETF
strat_wide = RSRSStrategy(pool='wide')
result_wide = strat_wide.run()
```

### 方式3：命令行执行

```bash
python D:\QClaw_Trading\RSRS\rsrs_daily_output.py --pool default
# 输出写入 signals/latest.json

python D:\QClaw_Trading\RSRS\rsrs_daily_output.py --pool wide --json my_output.json
```

---

## 信号字段说明

| JSON路径 | 类型 | 说明 |
|----------|------|------|
| `rsrs.zscore` | float | RSRS Z-Score |
| `rsrs.signal` | int | 1=买入, 0=卖出, -1=观望 |
| `momentum.c63_top` | list | C63复合动量Top N |
| `valuation.scores` | dict | 各ETF估值分位 (0~1) |
| `valuation.cheapest` | dict | 最便宜ETF |
| `portfolio.market_active` | bool | 大盘择时是否激活 |
| `portfolio.total_position` | float | 总仓位比例 |
| `advice` | str | 综合建议文字 |

完整规范见 `signals/API_SPEC.json`

---

## 数据依赖

所有ETF日线数据统一来自：
```
D:\QClaw_Trading\data\history\{code}.json
```

RSRS择时基于沪深300（510300）日线 High/Low。
C63动量基于池内ETF日线收盘价。
估值分位基于Price/MA12乖离率滚动252日分位。

---

## 当前信号（占位符）

| 字段 | 值 |
|------|-----|
| RSRS Z | `latest.json` 为准 |
| 动量Top1 | `latest.json` 为准 |
| 仓位 | `latest.json` 为准 |
| 建议 | `latest.json` 为准 |

> 每日收盘后运行 `rsrs_daily_output.py` 更新信号

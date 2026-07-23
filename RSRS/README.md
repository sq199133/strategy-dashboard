# RSRS 择时策略库

## ⚠️ 最新工作目录

**所有策略工作请在 `current/` 子目录中进行。**

👉 **`current/README.md` — 必读入口**

```
RSRS/
├── current/                  ← 【唯一工作目录】所有脚本/文档在此维护
│   ├── README.md            ← 本目录说明
│   ├── 策略说明书_v3.md     ← 完整策略说明书
│   ├── final_strategy_v2.md  ← 核心参数定义
│   ├── RSRS稳健性验证_20260710.md
│   ├── daily_review_20260713.md
│   ├── rsrs_final_strategy.py  ← 策略核心
│   ├── rsrs_engine.py          ← 策略引擎
│   ├── rsrs_daily_output.py   ← Cron 日报
│   ├── daily_review.py         ← 每日复盘
│   ├── pool10_backtest.py      ← 回测
│   └── current_advice.py       ← 快速诊断
├── docs/                    ← 完整文档归档
├── review/                 ← 复盘报告归档
├── backtest_results/        ← 回测结果
├── signals/                ← 每日信号 JSON
└── *.py                    ← 归档脚本（勿直接使用）
```

## 确认参数（永久锁定）

| 参数 | 值 |
|------|-----|
| ETF 池 | 11只 |
| RSRS N | 18 |
| RSRS M | **1200** |
| buy_thr | 0.7 |
| sell_thr | -1.0 |
| C63 动量窗口 | 63日 |
| 调仓锁定期 | 42天 |
| 波动率目标 | 16%（年化） |

## 数据目录

- 历史日线：`D:\QClaw_Trading\data\history/`
- 每日信号：`RSRS/signals/latest.json`

## ⚠️ 当前数据状态（2026-07-19）

以下5只ETF数据停在 07-09，需补充：
510050 · 159915 · 513500 · 513100 · 515080

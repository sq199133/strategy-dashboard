# RSRS 策略 — Current Working Directory

> **本目录是 RSRS 策略的唯一工作目录。**
> 所有脚本、文档、复盘、OKR 均维护于此。父目录 `RSRS/` 中的其他文件均为归档。

---

## 📋 每次工作从 OKR 开始

> **先看 OKR.md，再动手。** 每次运行/对话必须过一遍。

---

## 目录结构

```
current/
├── README.md                      ← 本文件
├── OKR.md                         ← 🆕 OKR 考核体系（必读）
├── 策略说明书_合并版.md            ← 完整策略手册（v3）
├── RSRS稳健性验证_20260710.md
├── daily_review_20260720.md       ← 最新复盘
├── rsrs_final_strategy.py          ← 策略核心实现
├── rsrs_engine.py                  ← 策略引擎类
├── rsrs_daily_output.py            ← Cron日报 → signals/latest.json
├── daily_review.py                 ← 每日复盘脚本
├── pool10_backtest.py              ← 回测脚本
└── current_advice.py              ← 快速诊断
```

---

## 快速使用

```bash
# 每日信号查询
python rsrs_daily_output.py

# 快速诊断
python current_advice.py

# 运行回测
python pool10_backtest.py
python rsrs_final_strategy.py --from 2022-07 --to 2025-12

# 每日复盘
python daily_review.py
```

---

## 确认参数（永久锁定）

| 参数 | 值 |
|------|-----|
| ETF 池 | **10只**（见下方） |
| RSRS N | **18** |
| RSRS M | **1200** |
| buy_thr | **0.7** |
| sell_thr | **-1.0** |
| C63 动量窗口 | **63日** |
| 调仓锁定期 | **42天** |
| 波动率目标 | **16%年化** |

### 10只ETF池（2026-07-21 剔除162411原油）
510050(上证50) · 510300(沪深300) · 510500(中证500) · 512100(中证1000)
159915(创业板) · 588000(科创50) · 513500(标普500) · 513100(纳斯达克)
518880(黄金) · 515080(中证红利)

---

## ⚠️ 数据注意

- 数据源：`D:\QClaw_Trading\data\history/`
- 每次运行前确认目录存在
- 每次复盘检查各 ETF 最新日期

---

## 归档文档

- 完整策略文档 → `策略说明书_合并版.md`
- 稳健性验证 → `RSRS稳健性验证_20260710.md`
- OKR 考核 → `OKR.md`
- 最新复盘 → `daily_review_20260724.md`
- 旧文档归档 → `../docs/`
- 旧复盘归档 → `../review/`

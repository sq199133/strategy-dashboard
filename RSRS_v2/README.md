# RSRS策略 v2 —— 文件夹说明

## 📁 文件清单

| 文件 | 用途 |
|------|------|
| `rsrs_final_strategy.py` | **核心策略实现**（RSRS择时 + C63动量 + 波动率仓位） |
| `pool10_backtest.py` | 10只ETF池回测脚本（含锁仓优化测试） |
| `pool10_results.json` | 回测结果数据 |
| `final_strategy_v2.md` | 策略定稿说明文档 |
| `RSRS稳健性验证_20260710.md` | 稳健性验证报告（豆包+千问框架） |
| `_robust_rsrs.py` | 稳健性验证完整代码 |
| `daily_review.py` | 每日持仓复盘脚本 |
| `check_latest.py` | 最新行情检查脚本 |
| `current_advice.py` | 当日信号 + 仓位建议输出 |
| `一键运行.bat` | Windows一键启动脚本 |

---

## 🚀 快速开始

### 运行回测
```bash
python pool10_backtest.py
```

### 运行稳健性验证
```bash
python _robust_rsrs.py
```

### 查看当前信号
```bash
python current_advice.py
```

### 一键运行（Windows）
双击 `一键运行.bat`，选择功能。

---

## 📐 策略核心参数

```
RSRS层:  N=18, M=1200, buy=0.7, sell=-1.0
动量层:  C63, RB=42, 过滤负值, Top1
仓位层:  沪深300 70d波动率, 目标16%
锁仓:    42天
```

---

## 📊 基准表现（已验证）

- **CAGR**: +20.0%
- **Sharpe**: 1.30
- **最大回撤**: -15.4%
- **Calmar**: 1.3
- **年度亏损年份**: 0/5（稳健性8项通过7项）

---

## ⚠️ 注意事项

1. **数据依赖**: 需要 `D:\QClaw_Trading\data\history\` 下的ETF历史数据
2. **稳健性警示**: 置换检验未能显著区分随机信号，RSRS择时效果需持续监控
3. **数据范围**: 2018~2026，约2个牛熊周期，样本量偏小

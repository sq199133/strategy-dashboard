# 周线动量策略 v4.5 — 回测系统说明

## 项目位置

`D:\QClaw_Trading\backtest\`

## 策略概述

**策略名称**：周线动量策略 v4.5 (Weekly Momentum Strategy v4.5)

**核心逻辑**：
1. 每周五收盘后扫描 ETF 池（195 只）
2. 计算三只动量指标（1周、3周、8周涨幅），加权评分：40%×1周 + 40%×3周 + 20%×8周
3. 过滤条件（四位检查）：
   - 评分 > 0
   - 收盘价 > MA5 **且** MA5 > MA21（趋势向上）
   - 均线偏离 ≤ 15%（防止追高）
   - ATR 比率 ≥ 0.85（波动率不能太低）
4. 等权买入评分最高 3 只（同类别去重）
5. 止损：成本 -8% **或** 高点回撤 -10%，任一触发即卖出
6. 每周重算，掉出前 3 即卖出，新标的补入

**执行时机**：每周五收盘后扫描生成信号，下周一**开盘价**执行（防 look-ahead 偏差）

## 文件说明

| 文件 | 用途 | 使用方法 |
|------|------|----------|
| `weekly_momentum_v45_backtest.py` | 完整回测脚本 | `python weekly_momentum_v45_backtest.py` |
| `weekly_momentum_v45_scan_this_week.py` | 本周扫描脚本 | `python weekly_momentum_v45_scan_this_week.py` |
| `README.md` | 本说明文档 | — |
| `weekly_momentum_v45_yearly.txt` | 分年度回测结果 | 用 UTF-8 编码打开 |

## 运行回测

### 1. 完整回测（生成历史表现）

```bash
cd D:\QClaw_Trading\backtest
D:\Python312\python.exe weekly_momentum_v45_backtest.py
```

**输出文件**（在当前目录）：
- `weekly_momentum_v45_equity.csv` — 权益曲线（每周）
- `weekly_momentum_v45_trades.csv` — 交易记录
- `weekly_momentum_v45_summary.json` — 汇总指标（年化、夏普、最大回撤等）
- `index.html` — HTML 仪表盘（含交互式图表）

**回测参数**：
- 数据目录：`D:\QClaw_Trading\data\history_long_v2\`
- ETF 池：`D:\QClaw_Trading\data\etf_pool_V1_full.json`（195 只）
- 评估窗口：2011-W21 ~ 2026-W26（共 727 周）
- 初始资金：100 万

### 2. 本周扫描（生成最新买入信号）

```bash
cd D:\QClaw_Trading\backtest
D:\Python312\python.exe weekly_momentum_v45_scan_this_week.py
```

**输出文件**（在当前目录）：
- `weekly_momentum_v45_this_week_results.txt` — 扫描结果（UTF-8，可读文本）
- `weekly_momentum_v45_this_week.json` — 扫描结果（JSON，供程序调用）

**执行建议**：
- 每周五收盘后运行（确保数据已更新到最新一周）
- 下周一开盘价执行买入/卖出
- 买入前确认止损线（成本 × 0.92）

## 回测结果（2026-06-25 运行）

| 指标 | 回测结果 | 参考值 |
|------|----------|--------|
| 累计收益 | +649% | +1465% |
| 年化收益 | +15.5% | +19.7% |
| 最大回撤 | -22.6% | -21.3% |
| 夏普比率 | 0.95 | 1.06 |
| 胜率 | 47.4% | 45.4% |
| 交易次数 | 1124 笔 | — |

**注**：回测结果与参考值有差距，可能原因：
1. 数据起始时间不同（ETF 池中各标的数据起始时间不同）
2. 执行价格假设（开盘价 vs 收盘价）
3. ETF 池是否完全一致

## 本周（2026-W26）推荐买入

> 运行 `weekly_momentum_v45_scan_this_week.py` 获取最新信号

**最近一次扫描结果（2026-06-25）**：
1. **588850** 科创机械 ETF 嘉实（评分 18.89%，止损线 1.986）
2. **512330** 信息科技 ETF 南方（评分 17.51%，止损线 1.960）
3. **159732** 消费电子 ETF 华夏（评分 16.64%，止损线 1.572）

**执行时间**：2026-06-27（本周五）收盘后下单，2026-06-30（下周一）开盘价执行

## 策略参数（可调整）

在 `weekly_momentum_v45_backtest.py` 和 `weekly_momentum_v45_scan_this_week.py` 顶部：

```python
WARMUP_WEEKS  = 21    # 预热周数（计算 MA21 需要）
WEIGHT_MOM1W  = 0.40   # 1周动量权重
WEIGHT_MOM3W  = 0.40   # 3周动量权重
WEIGHT_MOM8W  = 0.20   # 8周动量权重
MIN_MOM_SCORE = 0.0    # 最低评分阈值
MAX_OFF_MA5   = 0.15   # 均线偏离上限 15%
ATR_RATIO_LOW = 0.85   # ATR 比率下限
HOLD_N        = 3       # 持仓数量
STOP1_PCT     = -0.08   # 止损线 1：成本 -8%
STOP2_PCT     = -0.10   # 止损线 2：高点回撤 -10%
```

## 已知问题

1. **累计收益差异大**（+649% vs +1465%）
   - 建议：用收盘价格执行（模拟 look-ahead）对比差异

2. **持仓周期异常短**（2026 年平均 0.2 周）
   - 不符合周线策略逻辑
   - 需检查止损触发频率或调仓逻辑是否有 bug

3. **2013 年表现极差**（-14.31%，胜率 21.1%）
   - 可能原因：2013 年 A 股震荡市，趋势不明显

## 数据更新

**周线数据**：`D:\QClaw_Trading\data\history_long_v2\`
- 格式：JSON，每文件一只 ETF
- 字段：`w`（周号）、`date`、`close`、`open`、`high`、`low`、`vol`
- 更新频率：每周（建议在周五收盘后更新）

**ETF 池**：`D:\QClaw_Trading\data\etf_pool_V1_full.json`
- 格式：JSON，包含 195 只 ETF 的代码、名称、类别
- 更新频率：低（仅在 ETF 池调整时更新）

## 依赖环境

- **Python 路径**：`D:\Python312\python.exe`
- **依赖库**：仅标准库 + `pandas`（无需安装额外框架）
- **数据**：依赖本地 JSON 文件，无需联网

## 免责声明

⚠️ 以上内容由 AI 基于公开信息整理生成，仅供参考，不构成任何投资建议或个股推荐。投资有风险，决策需谨慎。

---

**最后更新**：2026-06-25
**维护者**：沈强

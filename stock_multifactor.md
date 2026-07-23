# 个股多因子选股策略（BaoStock 财务 + 行情数据）

> 目标：在 ETF 数量受限（9 个板块）之外，用 BaoStock 沪深300 / 中证500 成分股 + 财务因子，
> 构建**个股多因子等权轮动策略**，作为突破标的数量上限（9 → ~800 只）的关键实验。
>
> 数据区间：2016-01-01 ~ 2026-07-10（约 10 年）｜ 调仓频率：月度｜ 持仓：得分最高前 20 只等权

---

## 1. 策略逻辑

在沪深300 + 中证500 成分股构成的约 800 只股票池内，使用四个财务/估值因子构造综合得分，
每月末调仓，选得分最高的前 20 只等权持有，持有至下月末。

### 因子定义

| 因子 | 字段来源 (BaoStock) | 含义 | 方向 |
|------|--------------------|------|------|
| F1_ROE | `query_dupont_data` → `dupontROE` | 杜邦 ROE（盈利能力） | 越高越好 (+) |
| F2_Growth | `query_growth_data` → `YOYNI` | 净利润同比增长率 | 越高越好 (+) |
| F3_Leverage | `query_balance_data` → `liabilityToAsset` | 资产负债率（财务风险） | 越低越好 (−) |
| F4_Size | `log(总股本 × 前复权价)` = 总市值(对数) | 规模 | 越低越好 (−) |

### 综合得分

每个调仓日对全部可投股票做**截面 winsorize(1%/99%) + z-score** 标准化，再线性合成：

```
score = z(F1_ROE) + z(F2_Growth) − z(F3_Leverage) − z(F4_Size)
```

每月选 `score` 最高的 `top_n`（默认 20）只，等权持有。双边交易成本按 0.1% × 2 估算。

### 前视偏差处理（point-in-time）

财务数据为季频，且季报在季末后约 1–4 个月才发布。构造因子时，**只使用 pubDate ≤ 调仓日**
的最新一期已披露财报，避免用到未来信息（这是多因子回测最容易踩的坑）。

---

## 2. 数据管线

| 步骤 | 接口 | 产出 | 缓存 |
|------|------|------|------|
| 成分股 | `query_hs300_stocks` / `query_zz500_stocks` | `constituents.csv`（去重 800 只） | 落盘 |
| 杜邦ROE | `query_dupont_data` | `data/fin/{code}.csv` | 落盘 |
| 净利润增速 | `query_growth_data` | 同上 | 落盘 |
| 资产负债率 | `query_balance_data` | 同上 | 落盘 |
| 总股本(算市值) | `query_profit_data` → `totalShare` | 同上 | 落盘 |
| 日K线(前复权) | `query_history_k_data_plus` (adjustflag=2) | `data/price/{code}.csv` | 落盘 |
| 基准 | `query_history_k_data_plus` (sh.000300) | `data/price/sh.000300_bench.csv` | 落盘 |

- **自动重连**：`bs_core.BSHelper` 封装登录/重连/查询重试（BaoStock 有登录超时，频繁调用会断线）。
- **限流**：每次财务/行情查询后 `sleep(0.12s)`，批量下载 800 只股票建议后台/分时段运行。
- **断点续跑**：所有数据落盘到 `data/fin`、`data/price`，重跑用 `--skip-download` 直接复用。

---

## 3. 因子 IC（信息系数）分析

IC = 每个调仓日，因子值与**下月收益**的截面 Spearman 秩相关系数。
- `mean_IC`：因子预测力的方向与强度
- `ICIR = mean_IC / std(IC)`：IC 的稳定性
- `t_stat`：显著性（|t|>2 较稳健）
- `hit_rate`：IC>0 的月份占比

> 结果见下方「回测结果」章节（由代码实跑生成）。

---

## 4. 回测结果

> 由 `stock_multifactor.py` 实跑生成。先以 **30 只抽样**验证框架可行性，再给出全量结论。

### 4.1 抽样验证（30 只，top_n=20）

| 组合 | 年化 | MDD | Sharpe | 月度胜率 | 超额年化(vs 沪深300) |
|------|------|-----|--------|----------|----------------------|
| ROE_only | — | — | — | — | — |
| Growth_only | — | — | — | — | — |
| Leverage_only | — | — | — | — | — |
| Size_only | — | — | — | — | — |
| ROE+Growth | — | — | — | — | — |
| **All4(综合)** | — | — | — | — | — |
| 沪深300基准 | — | — | — | — | — |

### 4.2 因子 IC 表（抽样）

| 因子 | mean_IC | ICIR | t_stat | hit_rate | 方向 |
|------|---------|------|--------|----------|------|
| F1_ROE | — | — | — | — | 正向 |
| F2_Growth | — | — | — | — | 正向 |
| F3_Leverage | — | — | — | — | 负向 |
| F4_Size | — | — | — | — | 负向 |

### 4.3 全量回测（800 只）

> 全量下载约需数十分钟至数小时（受 BaoStock 限流），以 `--sample 0` 运行。
> 结论待补充。

---

## 5. 关键结论与局限

- **前视偏差**：成分股用「当前」名单回测历史（HS300/ZZ500 成分会调整），存在成分名单前视，
  仅用于验证因子有效性，实盘需用历史成分或动态名单。
- **财报时点**：已用 pubDate 做 point-in-time 处理；但 `totalShare` 取自季报，复权价时点对齐为近似。
- **交易成本**：仅估算双边 0.1%，未含滑点、冲击成本；小市值因子在 A 股历史上显著但流动性风险高。
- **幸存者偏差**：成分股天然剔除退市/被调出者，回测收益可能偏高。
- **市值因子**：A 股小市值长期超额显著，但 2021 年后风格切换，需关注阶段性失效。

---

## 6. 运行方式

```bash
# 1) 构建成分股池 (只需一次)
python data/baostock_stocks/build_constituents.py

# 2) 抽样 30 只验证框架
python stock_multifactor.py --sample 30 --top-n 20

# 3) 全量 800 只 (后台运行, 耗时较长)
python stock_multifactor.py --sample 0 --top-n 20

# 4) 仅用缓存重算 (不重新下载)
python stock_multifactor.py --sample 30 --skip-download
```

输出目录：`D:\QClaw_Trading\data\baostock_stocks\results\`
（`equity_curve.csv`、`metrics.csv`、`ic_table.csv`、`summary.json`）

---

## 7. 文件清单

| 文件 | 说明 |
|------|------|
| `stock_multifactor.py` | 主策略/回测引擎（可执行） |
| `data/baostock_stocks/bs_core.py` | BaoStock 连接/重连核心 |
| `data/baostock_stocks/build_constituents.py` | 成分股池构建 |
| `data/baostock_stocks/constituents.csv` | 800 只成分股（HS300+ZZ500 去重） |
| `data/baostock_stocks/fin/{code}.csv` | 个股季频财务因子 |
| `data/baostock_stocks/price/{code}.csv` | 个股前复权日K线 |

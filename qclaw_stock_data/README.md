# qclaw_stock_data v0.2.0

多市场量化数据SDK，基于 WorkBuddy 架构启发重写。

## 与 v0.1.x 的关键区别

| 特性 | v0.1.x | v0.2.0 |
|------|--------|--------|
| 代码格式 | 仅6位数字 | sh/sz/hk/us前缀 + 纯数字 |
| 实时行情 | Sina单只 | 腾讯批量一次50只 |
| 多市场 | 仅A股 | A股+港股+美股+指数 |
| 财务/资金流 | 无 | AKShare完整覆盖 |
| 指数数据 | 无 | 腾讯快取+AKShare PE/PB |
| 选股工具 | 无 | 条件选股 |
| 源容灾 | 2个K线源 | 6类数据×2源 |

## 数据类型

```python
from qclaw_stock_data import DataFetcher
f = DataFetcher()

# K线 (主力: Sina VIP)
f.kline("159928", 5000)         # 全量历史 0.01s (缓存)
f.kline("sh600519", 50)         # 日线增量

# 实时行情 (主力: 腾讯qt.gtimg.cn, 一次50只)
f.quote("sh600519")             # 单只 0.06s (缓存)
f.quote(["sh600519","sz000001","s_sh000001","hk00700","usAAPL"])  # 批量

# 指数 (腾讯快取 + AKShare PE/PB缓存1天)
f.index("s_sh000001")           # 上证指数
f.index("s_sh000300")           # 沪深300
f.index("s_sz399006")           # 创业板指

# 财务/估值 (AKShare, 缓存1天)
f.finance("sh600519")           # 主要财务指标
f.valuation("sh600519")         # PE/PB等

# 资金流 (AKShare, 缓存1小时)
f.moneyflow("sh600519")         # 主力净流入

# ETF信息 (AKShare, 缓存7天)
f.etf_info("sh512690")          # ETF基本信息

# 选股 (AKShare, 缓存1小时)
f.stock_filter("pe<20_roe>15")  # 条件选股
```

## 代码格式

```python
from qclaw_stock_data import normalize_code, build_qt_code

normalize_code("159928")    # → ('sz', '159928')     6位数字自动识别
normalize_code("sh600519")  # → ('sh', '600519')     sh前缀
normalize_code("hk00700")   # → ('hk', '00700')      港股
normalize_code("usAAPL")    # → ('us', 'AAPL')       美股(保留大小写)
normalize_code("s_sh000001") # → ('index', 'SH000001') 指数格式

build_qt_code("s_sh000001") # → 's_sh000001'  腾讯qt.gtimg.cn格式
build_qt_code("sh600519")   # → 'sh600519'
build_qt_code("hk00700")    # → 'hk00700'
```

## 五层防封架构

```
L1: 多源冗余 (每个数据需求 ≥2 个源)
L2: 主动防御 (随机延迟 0.3-1.0s/请求)
L3: 智能调度 (成功率加权路由)
L4: 缓存复用 (减少重复请求)
L5: 熔断自愈 (失败5次自动停用30分钟)
```

## 源注册表

```python
KLINE_SOURCES      # Sina VIP (全量5000条) → 腾讯K线
QUOTE_SOURCES      # 腾讯批量行情 → Sina实时
FINANCE_SOURCES    # AKShare财务
VALUATION_SOURCES  # AKShare估值
MONEYFLOW_SOURCES  # AKShare资金流
INDEX_SOURCES      # 腾讯指数实时 → AKShare PE/PB
ETF_SOURCES        # AKShare ETF信息
FILTER_SOURCES     # AKShare选股
```

## 状态监控

```python
f.status()
# {'cache': {'entries': 27, 'total_size_mb': 0.59},
#  'sources': {'sina_vip': {'success_rate': 100.0},
#              'tencent_quote': {'success_rate': 100.0},
#              'akshare_pe_pb': {'success_rate': 100.0}}}
```

## 字段说明

### 腾讯实时行情 (qt.gtimg.cn)
- `price`: 现价
- `chg`/`chg_pct`: 涨跌额/涨跌幅(%)
- `open`/`high`/`low`: 开盘/最高/最低
- `volume`: 成交量(手)
- `amount`: 成交额(元)
- `pe_ttm`/`pb`/`turnover`: 市盈率/市净率/换手率
- `mkt_cap`: 总市值(元)
- `high_52w`/`low_52w`: 52周高低价
- `etf_iopv`/`etf_premium`: ETF净值/溢价率

### 腾讯指数 (12字段格式)
- `price`: 现价
- `chg`/`chg_pct`: 涨跌额/涨跌幅(%)
- `volume`: 成交量(手)
- `amount_wan`: 成交额(万元)

## 数据目录

```
D:/QClaw_Trading/data/
  cache/       ← DataFetcher缓存 (TTL内命中)
  state/       ← 防封状态 + 健康状态
```

## 依赖

- Python 3.8+
- requests
- akshare (财务/资金流/指数PE-PB)
- AntiBlockDefense + CacheManager + HealthMonitor (内置)

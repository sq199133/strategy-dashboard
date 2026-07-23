"""qclaw_stock_data - A股量化数据SDK

## 核心理念：五层防封架构

源被封是A股量化的最大风险(东财/BaoStock/yfinance/efinance全军覆没)。
本SDK从设计第一天就以"源会挂"为前提，构建可降级的数据获取层。

### L1 多源冗余
- K线主力: Sina VIP (vip.stock.finance.sina.com.cn) 
  - 支持 datalen=5000 全历史 + 完整OHLCV
  - 唯一可用: 普通新浪 API datalen 截断到 250
- K线备选: 腾讯 (web.ifzq.gtimg.cn) - day/week/month
- 实时行情: hq.sinajs.cn (Sina)
- 财务数据: AKShare (stock_financial_abstract_ths)
- 指数PE/PB: AKShare (stock_index_pe_lg)
- 资金流: AKShare (stock_individual_fund_flow)
- 分红: AKShare (fund_etf_dividend_sina)

### L2 主动防御 (anti_block.py)
- 4-7个真实浏览器UA轮换
- 5+ Referer轮换 (新浪/东财/腾讯)
- 基础延迟 0.3-1.0s 随机
- 失败退避: 每连败一次 ×1.5
- 长延迟重试: 2.0-5.0s (失败后)

### L3 调度纪律
- 全量更新(5000条) → 凌晨 02:00-05:00 (网站负载低)
- 增量更新(50条) → 盘后 16:30
- 盘中查询 → 限流30次/分钟
- 周末避开 → 防止周维护误封

### L4 本地缓存 (cache.py)
- K线增量: TTL 1天
- K线全历史: backbone永久(只存一次)
- 实时行情: TTL 0 (不过期)
- 财务/分红: TTL 1月
- 减少 ~80% 外网请求

### L5 健康监控 (health.py)
- 失败计数 5次 → 熔断
- 熔断冷却 30分钟 → 重试自愈
- 健康报告: 成功率/最后成功/最后失败/熔断状态

## 用法

```python
from qclaw_stock_data import DataFetcher

f = DataFetcher()

# 增量K线 (自动命中缓存)
data = f.kline("159928", 50)

# 全历史K线 (首次走后永久缓存)
data = f.kline("159928", 5000)

# 实时行情
quote = f.quote("159928")

# 健康状态
status = f.status()
```

## CLI

```bash
python -m qclaw_stock_data kline 159928 50
python -m qclaw_stock_data quote 159928
python -m qclaw_stock_data status
python -m qclaw_stock_data cache clean
```

## 数据存储

- 缓存: D:/QClaw_Trading/data/cache/
- 状态: D:/QClaw_Trading/data/state/
  - anti_block_stats.json - 失败统计
  - health_state.json - 熔断状态

## 后续迭代 (Roadmap)

- [ ] 财务数据 fetcher (财报/估值/分红)
- [ ] 资金流 fetcher (大单/主力动向)
- [ ] 指数PE/PB fetcher
- [ ] 实时分时 fetcher
- [ ] 批量更新器 (cron 集成)
- [ ] 接入 etf_pool_V1_full.json 自动维护 195 只 ETF
"""
__version__ = "0.1.0"
__author__ = "策略测算agent"

from .anti_block import AntiBlockDefense
from .cache import CacheManager
from .health import HealthMonitor
from .sources import SourceRouter, KLINE_SOURCES, QUOTE_SOURCES, code_market
from .fetcher import DataFetcher, normalize_sina_kline, normalize_tencent_kline

__all__ = [
    "AntiBlockDefense", "CacheManager", "HealthMonitor",
    "SourceRouter", "DataFetcher",
    "KLINE_SOURCES", "QUOTE_SOURCES", "code_market",
    "normalize_sina_kline", "normalize_tencent_kline",
]

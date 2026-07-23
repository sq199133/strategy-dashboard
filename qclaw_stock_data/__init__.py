"""qclaw_stock_data - A股/港股/美股 量化数据SDK
五层防封架构 + 多市场支持 + 全数据类型覆盖
基于 WorkBuddy 架构启发构建
"""
__version__ = "0.2.0"  # 2026-06-27: 多市场+批量行情+财务资金流+指数+选股

from .anti_block import AntiBlockDefense
from .cache import CacheManager
from .health import HealthMonitor
from .sources import (
    SourceRouter,
    KLINE_SOURCES, QUOTE_SOURCES, FINANCE_SOURCES,
    VALUATION_SOURCES, MONEYFLOW_SOURCES, INDEX_SOURCES,
    ETF_SOURCES, FILTER_SOURCES,
    code_market, normalize_code, build_qt_code,
)
from .fetcher import (
    DataFetcher,
    normalize_sina_kline, normalize_tencent_kline, normalize_tencent_quote,
)

__all__ = [
    # 核心
    "DataFetcher",
    # 防御/缓存/健康
    "AntiBlockDefense", "CacheManager", "HealthMonitor",
    "SourceRouter",
    # 工具函数
    "code_market", "normalize_code", "build_qt_code",
    "normalize_sina_kline", "normalize_tencent_kline", "normalize_tencent_quote",
    # 源注册表
    "KLINE_SOURCES", "QUOTE_SOURCES", "FINANCE_SOURCES",
    "VALUATION_SOURCES", "MONEYFLOW_SOURCES", "INDEX_SOURCES",
    "ETF_SOURCES", "FILTER_SOURCES",
]

"""统一数据获取入口：DataFetcher
封装 缓存→多源→健康监控 的完整流程

从 WorkBuddy 架构中学习到的关键改进:
1. 多市场代码格式 (sh/sz/hk/us)
2. 批量行情 API (腾讯 qt.gtimg.cn 一次查50只)
3. 丰富的数据类型: K线/行情/财务/资金流/估值/ETF/指数
4. 选股工具: 条件/策略/标签/事件/排行
"""
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from .anti_block import AntiBlockDefense
from .cache import CacheManager
from .health import HealthMonitor
from .sources import (
    SourceRouter, KLINE_SOURCES, QUOTE_SOURCES,
    FINANCE_SOURCES, VALUATION_SOURCES, MONEYFLOW_SOURCES,
    INDEX_SOURCES, ETF_SOURCES, FILTER_SOURCES,
    normalize_code, build_qt_code,
)


# ============================================================
# 标准化函数
# ============================================================

def normalize_sina_kline(raw: list) -> list:
    """Sina VIP K线响应标准化"""
    records = []
    for row in raw:
        day = str(row.get("day", "")).split()[0]
        records.append({
            "date": day,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "vol": int(float(row.get("volume", 0))),
        })
    records.sort(key=lambda r: r["date"])
    return records


def normalize_tencent_kline(raw: list) -> list:
    """腾讯K线响应标准化: [日期,开,收,高,低,成交量,信息]"""
    records = []
    for row in raw:
        if len(row) < 6:
            continue
        records.append({
            "date": str(row[0]),
            "open": float(row[1]),
            "close": float(row[2]),
            "high": float(row[3]),
            "low": float(row[4]),
            "vol": int(float(row[5])),
        })
    records.sort(key=lambda r: r["date"])
    return records


def normalize_baostock_kline(raw: list) -> list:
    """Baostock K线响应标准化: [date,open,high,low,close,volume]"""
    records = []
    for row in raw:
        if len(row) < 6:
            continue
        try:
            records.append({
                "date": str(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "vol": int(float(row[5])),
            })
        except (ValueError, TypeError):
            continue
    records.sort(key=lambda r: r["date"])
    return records


def normalize_tencent_quote(raw: dict) -> dict:
    """腾讯行情字段标准化 (统一命名)"""
    return {
        "name": raw.get("name"),
        "market": raw.get("market"),
        "price": raw.get("price"),
        "prev_close": raw.get("prev_close"),
        "chg": raw.get("chg"),
        "chg_pct": raw.get("chg_pct"),
        "open": raw.get("open"),
        "high": raw.get("high"),
        "low": raw.get("low"),
        "volume": raw.get("volume"),    # 手
        "amount": raw.get("amount"),    # 元
        "pe_ttm": raw.get("pe_ttm"),
        "pb": raw.get("pb"),
        "turnover": raw.get("turnover"),
        "mkt_cap": raw.get("mkt_cap"),
        "high_52w": raw.get("high_52w"),
        "low_52w": raw.get("low_52w"),
        "etf_iopv": raw.get("etf_iopv"),
        "etf_premium": raw.get("etf_premium"),
    }


# ============================================================
# DataFetcher - 统一入口
# ============================================================

class DataFetcher:
    """A股/港股/美股 统一数据API

    从 WorkBuddy westock + neodata 架构中学习:
    - 多市场支持: sh/sz/hk/us
    - 批量查询: 一次50只，减少网络请求
    - 五层防封: 多源冗余 + 主动防御 + 调度 + 缓存 + 熔断

    用法:
        f = DataFetcher()

        # K线 (A股)
        data = f.kline("159928", 50)           # 增量
        data = f.kline("159928", 5000)         # 全历史

        # 实时行情 (全市场)
        q = f.quote("sh600519")                # 单只
        q = f.quote(["sh600519", "sz000001"])  # 批量

        # 财务/估值
        fin = f.finance("sh600519")             # 主要财务指标
        val = f.valuation("sh600519")            # PE/PB等

        # 资金流
        mf = f.moneyflow("sh600519")            # 主力净流入

        # 指数
        idx = f.index("sh000001")               # 指数行情+PE/PB

        # ETF
        etf = f.etf_info("sh512690")            # ETF信息

        # 选股
        stocks = f.stock_filter("pe<20_roe>15") # 条件选股

        # 状态
        s = f.status()
    """

    DEFAULT_CACHE_DIR = "D:/QClaw_Trading/data/cache"
    DEFAULT_STATE_DIR = "D:/QClaw_Trading/data/state"

    def __init__(self, cache_dir: str = None, state_dir: str = None):
        cache_dir = cache_dir or self.DEFAULT_CACHE_DIR
        state_dir = state_dir or self.DEFAULT_STATE_DIR

        self.cache = CacheManager(cache_dir)
        self.defense = AntiBlockDefense(
            min_delay=0.3, max_delay=1.0,
            stats_path=f"{state_dir}/anti_block_stats.json")
        self.health = HealthMonitor(
            state_path=f"{state_dir}/health_state.json",
            fail_threshold=5, cooldown_minutes=30)
        self.router = SourceRouter(self.defense, self.health)

    # ========================================================
    # K线
    # ========================================================

    def kline(self, code: str, datalen: int = 50, period: str = "daily",
              use_cache: bool = True) -> Optional[List[dict]]:
        """K线数据 (A股: 沪深/科创/创业板/ETF/LOF)

        Args:
            code: 代码，支持 sh600519/sz000001/159928 等格式
            datalen: 返回记录数 (50=增量, 5000=全历史)
            period: daily/weekly/monthly (仅 Sina 支持)
            use_cache: 是否查询缓存
        """
        scale_map = {"daily": 240, "weekly": 1200, "monthly": 4800}
        scale = scale_map.get(period, 240)
        mkt, num = normalize_code(code)
        cache_key = f"kline_{period}_{mkt}{num}_d{datalen}"

        # 缓存查询
        if use_cache and datalen <= 60:
            cached = self.cache.get(cache_key, ttl=86400)
            if cached:
                return cached
        if use_cache and datalen >= 1000:
            cached = self.cache.get(cache_key, ttl=0)
            if cached:
                return cached

        # 多源获取
        result = self.router.fetch(
            code, KLINE_SOURCES, scale=scale, datalen=datalen)
        if not result:
            return None

        # 标准化
        if result["source"] == "sina_vip":
            records = normalize_sina_kline(result["data"])
        elif result["source"] == "tencent_kline":
            records = normalize_tencent_kline(result["data"])
        elif result["source"] == "baostock":
            records = normalize_baostock_kline(result["data"])
        else:
            return None

        # 写缓存
        if records:
            ttl = 86400 if datalen <= 60 else 0
            self.cache.set(cache_key, records, ttl=ttl)

        return records

    # ========================================================
    # 实时行情
    # ========================================================

    def quote(self, code: str | List[str],
              use_cache: bool = False) -> Optional[dict | List[dict]]:
        """实时行情 (A股/港股/美股/指数)

        从 WorkBuddy westock quote 命令启发:
        - 腾讯 qt.gtimg.cn 批量接口，单次最多50只
        - 字段丰富: OHLC/PE/PB/换手率/市值/52周高低价/ETF IOPV

        Args:
            code: 单只代码或代码列表
                  支持: sh/sz/hk/us 前缀
                  示例: "sh600519" / ["sh600519", "sz000001", "hk00700"]
            use_cache: 是否使用缓存 (默认False，盘中行情需实时)

        Returns:
            单只: {"name": ..., "price": ..., "chg_pct": ..., ...}
            批量: {raw_code: normalized_dict}
        """
        # 标准化为列表
        codes = [code] if isinstance(code, str) else list(code)
        mkt, num = normalize_code(codes[0])
        cache_key = f"quote_{mkt}{num}"

        if use_cache:
            cached = self.cache.get(cache_key, ttl=60)  # 60秒TTL
            if cached:
                return cached

        # 批量获取
        result = self.router.fetch_batch(codes, QUOTE_SOURCES)
        if not result:
            return None

        raw_data = result.get("data", {})

        # 写缓存 (单只)
        if len(codes) == 1:
            qt_code = build_qt_code(codes[0])
            raw = raw_data.get(qt_code, {})
            normalized = normalize_tencent_quote(raw)
            self.cache.set(cache_key, normalized, ttl=60)
            return normalized

        # 批量: 返回原始字典，由调用方处理
        return raw_data

    # ========================================================
    # 财务/基本面
    # ========================================================

    def finance(self, code: str, report: str = "main",
                use_cache: bool = True) -> Optional[dict]:
        """财务报表/主要财务指标

        Args:
            code: A股代码
            report: "main"(主要指标) / "balance"(资产负债表)
                    "income"(利润表) / "cashflow"(现金流量表)
        """
        mkt, num = normalize_code(code)
        cache_key = f"finance_{report}_{mkt}{num}"

        if use_cache:
            cached = self.cache.get(cache_key, ttl=86400)  # 1天TTL
            if cached:
                return cached

        result = self.router.fetch(code, FINANCE_SOURCES, report_type=report)
        if not result:
            return None

        self.cache.set(cache_key, result.get("data", []), ttl=86400)
        return result.get("data", [])

    def valuation(self, code: str, use_cache: bool = True) -> Optional[dict]:
        """估值指标: PE/PB/PS/PCF/股息率等"""
        mkt, num = normalize_code(code)
        cache_key = f"valuation_{mkt}{num}"

        if use_cache:
            cached = self.cache.get(cache_key, ttl=86400)
            if cached:
                return cached

        result = self.router.fetch(code, VALUATION_SOURCES)
        if not result:
            return None

        self.cache.set(cache_key, result.get("data", {}), ttl=86400)
        return result.get("data", {})

    # ========================================================
    # 资金流
    # ========================================================

    def moneyflow(self, code: str, use_cache: bool = True) -> Optional[dict]:
        """资金流向: 主力净流入 / 超大单 / 大单 / 中单 / 小单"""
        mkt, num = normalize_code(code)
        cache_key = f"moneyflow_{mkt}{num}"

        if use_cache:
            cached = self.cache.get(cache_key, ttl=3600)  # 1小时TTL
            if cached:
                return cached

        result = self.router.fetch(code, MONEYFLOW_SOURCES)
        if not result:
            return None

        self.cache.set(cache_key, result.get("data", []), ttl=3600)
        return result.get("data", [])

    # ========================================================
    # 指数/宏观
    # ========================================================

    def index(self, code: str, use_cache: bool = True) -> Optional[dict]:
        """指数行情 + PE/PB

        策略: 腾讯快取实时数据 + AKShare缓存1天取PE/PB
        指数格式: s_sh000001 / s_sz399006 / sh000300(自动识别)

        Args:
            code: 指数代码
                  s_sh000001: 上证指数
                  s_sz399006: 创业板指
                  sh000300: 沪深300 (自动转为s_sh000300)
        """
        from .sources import normalize_code
        mkt, num = normalize_code(code)
        # 转为统一格式
        if mkt == "index":
            qt_key = num  # e.g. "SH000001"
        else:
            qt_key = f"{mkt.upper()}{num}"
        cache_key = f"index_{qt_key}"

        if use_cache:
            cached = self.cache.get(cache_key, ttl=60)  # 1分钟TTL
            if cached:
                return cached

        # L1: 腾讯实时行情 (快)
        result = self.router.fetch(code, INDEX_SOURCES)
        if not result:
            return None

        data = result.get("data", {})

        # L2: AKShare PE/PB (慢, 缓存1天)
        pe_cache_key = f"index_pe_{qt_key}"
        pe_cached = self.cache.get(pe_cache_key, ttl=86400)
        if pe_cached:
            data["pe"] = pe_cached.get("pe")
            data["pb"] = pe_cached.get("pb")
        else:
            try:
                from .sources import _akshare_index_pe_pb
                pe_result = _akshare_index_pe_pb(code)
                if pe_result and pe_result.get("data"):
                    data["pe"] = pe_result["data"].get("pe")
                    data["pb"] = pe_result["data"].get("pb")
                    self.cache.set(pe_cache_key, {
                        "pe": data["pe"], "pb": data["pb"]
                    }, ttl=86400)
            except Exception:
                pass

        self.cache.set(cache_key, data, ttl=60)
        return data

    # ========================================================
    # ETF
    # ========================================================

    def etf_info(self, code: str, use_cache: bool = True) -> Optional[dict]:
        """ETF 详细信息: 规模/费率/跟踪指数/前十大持仓"""
        mkt, num = normalize_code(code)
        cache_key = f"etf_info_{mkt}{num}"

        if use_cache:
            cached = self.cache.get(cache_key, ttl=86400 * 7)  # 7天TTL
            if cached:
                return cached

        result = self.router.fetch(code, ETF_SOURCES)
        if not result:
            return None

        self.cache.set(cache_key, result.get("data", []), ttl=86400 * 7)
        return result.get("data", [])

    # ========================================================
    # 选股
    # ========================================================

    def stock_filter(self, condition: str) -> Optional[dict]:
        """条件选股

        条件格式: "pe<20_roe>15"
        支持条件:
          PE<value  - 市盈率小于X
          PE>value  - 市盈率大于X
          ROE>value - 净资产收益率大于X%
          PB<value  - 市净率小于X

        Returns:
            {"condition": "...", "count": N, "codes": [...]}
        """
        cache_key = f"filter_{condition}"
        cached = self.cache.get(cache_key, ttl=3600)  # 1小时TTL
        if cached:
            return cached

        result = self.router.fetch(condition, FILTER_SOURCES)
        if not result:
            return None

        self.cache.set(cache_key, result, ttl=3600)
        return result

    # ========================================================
    # 状态
    # ========================================================

    def status(self) -> dict:
        """全链路健康报告"""
        return {
            "cache": self.cache.stats(),
            "sources": self.health.all_status(),
            "fail_streaks": dict(self.defense._fail_streak),
        }

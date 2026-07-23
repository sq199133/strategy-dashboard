"""L1 多源路由器：每个数据需求配N个源，按可用性降级

从 WorkBuddy 架构中学习到的关键改进:
1. 多市场格式支持: sh/sz/hk/us 前缀体系
2. 腾讯批量行情(qt.gtimg.cn) 支持 ETF/指数/港股/美股
3. AKShare 作为财务/资金流的主力源
4. 路由优先级: 高成功率 > 高权重
"""
import re
from typing import Optional, List, Dict, Any
from .anti_block import AntiBlockDefense
from .health import HealthMonitor


# ============================================================
# 代码标准化：支持 sh/sz/hk/us 前缀
# ============================================================

def normalize_code(raw: str) -> tuple[str, str]:
    """将各种代码格式标准化为 (market, number)

    支持格式:
      - 6位纯数字: "159928" → ("sz", "159928")
      - sh/sz前缀: "sh600519" → ("sh", "600519")
      - hk前缀:    "hk00700"  → ("hk", "00700")
      - us前缀:    "usAAPL"   → ("us", "AAPL")
      - 指数格式:  "s_sh000001" → ("index", "sh000001")

    Returns:
        (market, number) - market is "sh"|"sz"|"hk"|"us"|"index"
    """
    s = str(raw).strip()
    # 已带前缀: 指数(s_sh/s_sz) > 港股(hk) > 美股(us) > A股(sh/sz)
    # 顺序很重要: 先匹配长的前缀
    # s_前缀: s_sh000001 / s_sz399006 → 指数
    if re.match(r"^s_(sh|sz)\d{6}$", s, re.IGNORECASE):
        idx = s[2:].upper()  # "SH000001"
        return "index", idx
    # 标准前缀: sh/sz/hk/us + 数字或代码
    m = re.match(r"^(sh|sz|hk|us)(\w+)$", s, re.IGNORECASE)
    if m:
        return m.group(1).lower(), m.group(2)
    # 纯6位数字 → 自动识别A股市场
    if re.match(r"^\d{6}$", s):
        mkt = code_market(s)
        return mkt, s
    # 其他数字格式 (4-5位 → 港股)
    if re.match(r"^\d{4,5}$", s):
        return "hk", s
    # 其余 → 美股 (保留原大小写)
    return "us", s


def code_market(code: str) -> str:
    """A股代码识别市场

    沪市:
      - 60/68xxxx 主板/科创板
      - 5xxxxx ETF/封闭基金/LOF
      - 9xxxxx B股
      - 11xxxx 债券
    深市:
      - 0xxxxx 主板
      - 3xxxxx 创业板
      - 15xxxx LOF
      - 16xxxx LOF
      - 159xxx ETF
    """
    s = str(code).zfill(6)
    if s.startswith(("60", "68", "9", "5", "11")):
        return "sh"
    return "sz"


def build_qt_code(raw: str) -> str:
    """为腾讯qt.gtimg.cn构建查询代码 (统一小写前缀)

    A股: sz000001 / sh600519
    指数: s_sh000001 / s_sz399006 (小写s_前缀)
    港股: hk00700
    美股: usAAPL
    """
    mkt, num = normalize_code(raw)
    if mkt == "index":
        # "SH000001" → "s_sh000001"
        parts = num.split(maxsplit=1)
        if len(parts) == 2:
            return f"s_{parts[0].lower()}{parts[1]}"
        return f"s_{num.lower()}"
    elif mkt in ("sh", "sz"):
        return f"{mkt}{num}"
    elif mkt == "hk":
        return f"hk{num}"
    elif mkt == "us":
        return f"us{num}"
    return f"{mkt}{num}"


# ============================================================
# K线数据源
# ============================================================

def _sina_vip_kline(code: str, scale: int = 240, datalen: int = 5000,
                    defense: AntiBlockDefense = None) -> Optional[dict]:
    """Sina VIP API - K线主力源 (A股专用)

    优点: datalen=5000 支持全量历史
    缺点: 仅支持A股
    """
    mkt, num = normalize_code(code)
    if mkt not in ("sh", "sz"):
        return None  # Sina只支持A股
    url = ("http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={mkt}{num}&scale={scale}&datalen={datalen}")
    r = defense.get(url, source_name="sina_vip")
    data = r.json()
    if not data or not isinstance(data, list):
        return None
    return {"source": "sina_vip", "data": data, "market": mkt, "code": num}


def _tencent_kline(code: str, ktype: str = "day",
                   defense: AntiBlockDefense = None, datalen: int = 320) -> Optional[dict]:
    """腾讯 K线接口 - K线备选源 (A股)

    API: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
    参数: {market}{code},{ktype},,,{datalen},
    ktype: day/week/month/qfqday/qfqweek/qfqmonth
    """
    mkt, num = normalize_code(code)
    if mkt not in ("sh", "sz"):
        return None
    ktype_map = {
        "daily": "day", "weekly": "week", "monthly": "month",
        "qfq_daily": "qfqday", "qfq_weekly": "qfqweek", "qfq_monthly": "qfqmonth",
    }
    ktype_code = ktype_map.get(ktype, ktype)
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?param={mkt}{num},{ktype_code},,,{datalen},")
    r = defense.get(url, source_name="tencent_kline")
    j = r.json()
    if j.get("code") != 0:
        return None
    rows = j.get("data", {}).get(f"{mkt}{num}", {}).get(ktype_code)
    if not rows:
        return None
    return {"source": "tencent_kline", "data": rows, "market": mkt, "code": num}


def _baostock_kline(code: str, scale: int = 240, datalen: int = 5000,
                    defense=None, ktype: str = "day") -> Optional[dict]:
    """Baostock K线接口 - A股/指数全覆盖 (Sina备选/指数主力)

    优势:
      - 支持 A股(ETF/股票) + 指数(沪深300/上证综指等)
      - 无Sina的sh/sz限制
      - 前复权/后复权/不复权可调
    局限:
      - 需要 baostock 库 (pip install baostock)
      - scale参数与Sina不同 (240=日线 vs baostock用frequency="d")
    """
    try:
        import baostock as bs
    except ImportError:
        return None

    bs.login()
    try:
        mkt, num = normalize_code(code)
        if mkt == "index":
            bs_code = num.lower()          # "sh000300"
        elif mkt in ("sh", "sz"):
            bs_code = f"{mkt}.{num}"      # "sh.510500"
        else:
            return None                     # 港股/美股暂不支持

        freq_map = {"daily": "d", "weekly": "w", "monthly": "m"}
        freq = freq_map.get(ktype, "d")
        # adjustflag: 1=不复权 2=后复权 3=前复权
        adj_map = {240: "3", 1200: "3", 4800: "3"}
        adj = adj_map.get(scale, "3")

        # 最大单次请求1000条; datalen较大时分段
        if datalen <= 1000:
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume",
                start_date="1990-01-01",
                end_date="2099-12-31",
                frequency=freq,
                adjustflag=adj
            )
            if rs.error_code != "0":
                return None
            rows = []
            while (rs.error_code == "0") & rs.next():
                rows.append(rs.get_row_data())
        else:
            # 大datalen分段获取再合并
            rows = []
            step = 800
            for start_offset in range(0, datalen, step):
                import datetime
                today = datetime.date.today()
                start_d = (today - datetime.timedelta(days=start_offset + step + 30)).isoformat()
                end_d   = (today - datetime.timedelta(days=max(0, start_offset - 30))).isoformat()
                rs = bs.query_history_k_data_plus(
                    bs_code, "date,open,high,low,close,volume",
                    start_date=start_d, end_date=end_d,
                    frequency=freq, adjustflag=adj
                )
                if rs.error_code == "0":
                    while rs.next():
                        rows.append(rs.get_row_data())

        if not rows:
            return None
        return {"source": "baostock", "data": rows, "market": mkt, "code": num}
    finally:
        bs.logout()


# ============================================================
# 实时行情数据源
# ============================================================

def _tencent_batch_quote(codes: List[str],
                          defense: AntiBlockDefense = None) -> Optional[dict]:
    """腾讯批量行情 API - 实时行情主力源

    优势:
    - 支持 A股/港股/美股/指数 多市场
    - 单次最多查50只 (批量减少请求数)
    - 字段丰富: OHLC/量/额/PE/PB/市值/52周高低价等

    字段说明 (腾讯 qt.gtimg.cn ~分隔符):
      [0]  股票代码(含前缀)
      [1]  股票名称
      [3]  现价
      [4]  涨跌额
      [5]  今开
      [31] 昨收
      [32] 涨跌幅(%)
      [33] 最高
      [34] 最低
      [36]成交量(手)
      [37]成交额(元)
      [38]市值(元)
      [43]市盈率(TTM)
      [46]市净率
      [44]换手率(%)
      [57]52周最高
      [58]52周最低
      [84]股溢价率(可转债)
      [92]基金净值/ETF IOPV
      [93]ETF溢价率

    参考: WorkBuddy westock-data quote 命令
    """
    qt_codes = [build_qt_code(c) for c in codes]
    qt_str = ",".join(qt_codes)
    url = f"https://qt.gtimg.cn/q={qt_str}"
    r = defense.get(url, source_name="tencent_quote", timeout=20)
    raw_text = r.text.strip()

    results = {}
    for line in raw_text.split("\n"):
        line = line.strip()
        if not line or "~" not in line:
            continue
        # 格式: v_sz159928="...~...~..."
        m = re.match(r'v_(\w+)="(.+)"', line)
        if not m:
            continue
        qt_code = m.group(1)  # e.g. "sz159928" or "s_sh000001" or "hk00700"
        fields = m.group(2).split("~")
        if len(fields) < 10:
            continue

        # 解析市场类型
        mkt_raw = qt_code[:2]
        num_raw = qt_code[2:]
        mkt_map = {"sz": "sz", "sh": "sh", "hk": "hk", "us": "us", "s_": "index", "s_h": "index", "s_s": "index"}
        mkt = mkt_map.get(mkt_raw, mkt_raw[:2])

        # 修正指数格式 s_sh → index
        if qt_code.startswith("s_sh") or qt_code.startswith("s_sz"):
            mkt = "index"
            num = qt_code[2:]  # sh000001

        try:
            price = float(fields[3]) if fields[3] else None
            prev_close = float(fields[31]) if len(fields) > 31 and fields[31] else None
            chg = float(fields[4]) if fields[4] else None
            chg_pct = float(fields[32]) if len(fields) > 32 and fields[32] else None
        except (ValueError, IndexError):
            price = prev_close = chg = chg_pct = None

        results[qt_code] = {
            "raw_code": qt_code,
            "market": mkt,
            "name": fields[1] if len(fields) > 1 else None,
            "price": price,
            "prev_close": prev_close,
            "chg": chg,
            "chg_pct": chg_pct,
            "open": float(fields[5]) if len(fields) > 5 and fields[5] else None,
            "high": float(fields[33]) if len(fields) > 33 and fields[33] else None,
            "low": float(fields[34]) if len(fields) > 34 and fields[34] else None,
            "volume": int(float(fields[36])) if len(fields) > 36 and fields[36] else None,  # 手
            "amount": float(fields[37]) if len(fields) > 37 and fields[37] else None,  # 元
            "pe_ttm": float(fields[43]) if len(fields) > 43 and fields[43] else None,
            "pb": float(fields[46]) if len(fields) > 46 and fields[46] else None,
            "turnover": float(fields[44]) if len(fields) > 44 and fields[44] else None,  # 换手率%
            "mkt_cap": float(fields[38]) if len(fields) > 38 and fields[38] else None,  # 市值元
            "high_52w": float(fields[57]) if len(fields) > 57 and fields[57] else None,
            "low_52w": float(fields[58]) if len(fields) > 58 and fields[58] else None,
            "etf_iopv": float(fields[92]) if len(fields) > 92 and fields[92] else None,
            "etf_premium": float(fields[93]) if len(fields) > 93 and fields[93] else None,
            "source": "tencent_quote",
        }

    return {"source": "tencent_quote", "data": results}


def _sina_quote(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
    """Sina 实时行情 - 备选源 (A股专用)"""
    mkt, num = normalize_code(code)
    if mkt not in ("sh", "sz"):
        return None
    url = f"https://hq.sinajs.cn/list={mkt}{num}"
    r = defense.get(url, source_name="sina_quote")
    line = r.text.strip()
    if not line or "=" not in line or '""' in line:
        return None
    parts = line.split('"')[1].split(",")
    if len(parts) < 32:
        return None
    return {
        "source": "sina_quote",
        "market": mkt,
        "code": num,
        "data": {
            "name": parts[0],
            "open": float(parts[1]) if parts[1] else 0,
            "prev_close": float(parts[2]) if parts[2] else 0,
            "price": float(parts[3]) if parts[3] else 0,
            "high": float(parts[4]) if parts[4] else 0,
            "low": float(parts[5]) if parts[5] else 0,
            "amount": float(parts[9]) if parts[9] else 0,
            "volume": int(parts[8]) if parts[8] else 0,
            "date": parts[30] if len(parts) > 30 else None,
            "time": parts[31] if len(parts) > 31 else None,
        }
    }


# ============================================================
# 财务/基本面数据源 (AKShare)
# ============================================================

def _akshare_finance(code: str, report_type: str = "main",
                     defense: AntiBlockDefense = None) -> Optional[dict]:
    """AKShare 财务数据 - 财务报表/估值

    report_type:
      - "main": 主要财务指标 (EPS/ROE/毛利率等)
      - "balance": 资产负债表
      - "income": 利润表
      - "cashflow": 现金流量表
    """
    try:
        import akshare as ak
        mkt, num = normalize_code(code)
        if mkt not in ("sh", "sz"):
            return None
        full_code = f"{mkt.upper()}{num}"

        if report_type == "main":
            df = ak.stock_financial_abstract_ths(symbol=full_code, start_year="2015")
        elif report_type == "balance":
            df = ak.stock_balance_sheet_by_report_em(symbol=full_code)
        elif report_type == "income":
            df = ak.stock_profit_sheet_by_report_em(symbol=full_code)
        elif report_type == "cashflow":
            df = ak.stock_cash_flow_sheet_by_report_em(symbol=full_code)
        else:
            df = None

        if df is None or df.empty:
            return None

        return {
            "source": f"akshare_{report_type}",
            "market": mkt,
            "code": num,
            "data": df.to_dict(orient="records"),
            "columns": list(df.columns),
        }
    except Exception as e:
        return None


def _akshare_valuation(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
    """AKShare 估值数据 - PE/PB/PS/PCF/股息率"""
    try:
        import akshare as ak
        mkt, num = normalize_code(code)
        if mkt not in ("sh", "sz"):
            return None
        full_code = f"{mkt.upper()}{num}"

        df = ak.stock_individual_info_em(symbol=full_code)
        if df is None or df.empty:
            return None

        # 提取关键指标
        info = {}
        for _, row in df.iterrows():
            k = str(row.get("item", "")).strip()
            v = row.get("value", "")
            if k and v:
                info[k] = v

        return {
            "source": "akshare_valuation",
            "market": mkt,
            "code": num,
            "data": info,
        }
    except Exception:
        return None


# ============================================================
# 资金流/宏观数据源 (AKShare)
# ============================================================

def _akshare_moneyflow(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
    """AKShare 资金流向 - 个股主力净流入

    返回: {超大单净流入, 大单净流入, 中单净流入, 小单净流入, 主力净流入, 净流入率}
    """
    try:
        import akshare as ak
        mkt, num = normalize_code(code)
        if mkt not in ("sh", "sz"):
            return None
        full_code = f"{mkt.upper()}{num}"

        df = ak.stock_individual_fund_flow(stock=full_code, market=mkt.upper())
        if df is None or df.empty:
            return None

        # 取最近5条
        records = df.tail(5).to_dict(orient="records")
        return {
            "source": "akshare_moneyflow",
            "market": mkt,
            "code": num,
            "data": records,
            "columns": list(df.columns),
        }
    except Exception:
        return None


def _akshare_etf_info(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
    """AKShare ETF基础信息"""
    try:
        import akshare as ak
        mkt, num = normalize_code(code)
        # ETF: 5xxxxx(沪) 或 15xxxx/159xxx(深)
        full_code = f"{mkt.upper()}{num}"

        df = ak.fund_etf_fund_info_ths(symbol=full_code)
        if df is None or df.empty:
            return None

        return {
            "source": "akshare_etf_info",
            "market": mkt,
            "code": num,
            "data": df.to_dict(orient="records"),
            "columns": list(df.columns),
        }
    except Exception:
        return None


# ============================================================
# 指数/宏观数据源
# ============================================================

def _tencent_index_quote(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
    """腾讯 指数行情 (快,实时,12字段格式)
    字段格式:
      [1] 名称 [2] 代码 [3] 现价 [4] 涨跌额 [5] 涨跌幅 [6] 成交量 [7] 成交额(万元)
    """
    qt_code = build_qt_code(code)
    url = f"https://qt.gtimg.cn/q={qt_code}"
    r = defense.get(url, source_name="tencent_quote", timeout=20)
    line = r.text.strip()
    if not line or "~" not in line:
        return None

    import re
    m = re.search(r'v_(\w+)="(.+)"', line)
    if not m:
        return None
    fields = m.group(2).split("~")
    if len(fields) < 6:
        return None

    def fv(x):
        return float(x) if x and x != "-" else None

    return {
        "source": "tencent_quote",
        "code": qt_code,
        "data": {
            "name": fields[1] if len(fields) > 1 else None,
            "price": fv(fields[3]),
            "chg": fv(fields[4]),
            "chg_pct": fv(fields[5]),
            "volume": int(fv(fields[6])) if fv(fields[6]) else None,
            "amount_wan": fv(fields[7]) if len(fields) > 7 else None,
        }
    }


def _akshare_index_pe_pb(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
    """AKShare 指数 PE/PB (慢但全, 缓存1天)
    从 stock_zh_index_spot_em 提取 (268个主要指数)
    """
    try:
        import akshare as ak
        mkt, num = normalize_code(code)
        # 提取纯数字代码
        # normalize_code 返回 ("index", "SH000001") 或 ("sh", "000300")
        # AKShare 用纯数字 "000300"
        if mkt == "index":
            # "SH000001" → "000001", "SZ399006" → "399006"
            import re
            digits = re.sub(r"[^0-9]", "", num)
            symbol = digits
        elif mkt in ("sh", "sz"):
            symbol = num.lstrip("0") or num  # "000300" → "300" (可能)
            # 但 AKShare 格式: "000300" 是正确的
            symbol = num
        else:
            symbol = num

        df = ak.stock_zh_index_spot_em()
        if df is None or df.empty:
            return None

        # Find by code
        row = df[df["代码"] == symbol]
        if row is None or row.empty:
            # Try without leading zeros
            row = df[df["代码"] == symbol.lstrip("0")]
        if row is None or row.empty:
            return None

        r = row.iloc[0]
        pe = float(r.get("市盈率-动态", 0) or 0)
        pb = float(r.get("市净率", 0) or 0)
        return {
            "source": "akshare_index_pe_pb",
            "code": symbol,
            "data": {
                "pe": pe if pe > 0 else None,
                "pb": pb if pb > 0 else None,
                "name": r.get("名称"),
            }
        }
    except Exception:
        return None


# ============================================================
# 选股工具 (条件/策略/标签/事件/排行)
# ============================================================

def _akshare_stock_filter(condition: str, defense: AntiBlockDefense = None) -> Optional[dict]:
    """AKShare 条件选股

    简化实现: 基于财务指标的股票筛选
    condition: "pe<20_roe>15" 格式
    """
    try:
        import akshare as ak
        # 解析条件
        terms = condition.upper().split("_")
        filters = []
        for term in terms:
            if term.startswith("PE<"):
                filters.append(("市盈率(TTM)", "<", float(term[3:])))
            elif term.startswith("PE>"):
                filters.append(("市盈率(TTM)", ">", float(term[3:])))
            elif term.startswith("ROE>"):
                filters.append(("净资产收益率(%)", ">", float(term[4:])))
            elif term.startswith("PB<"):
                filters.append(("市净率", "<", float(term[3:])))

        # 获取全市场财务数据
        df = ak.stock_a_indicator_lg()
        if df is None or df.empty:
            return None

        result = df.copy()
        for col, op, val in filters:
            if col in result.columns:
                if op == "<":
                    result = result[result[col] < val]
                elif op == ">":
                    result = result[result[col] > val]

        codes = result["代码"].tolist()[:100]
        return {
            "source": "akshare_filter",
            "condition": condition,
            "count": len(codes),
            "codes": codes,
        }
    except Exception:
        return None


# ============================================================
# 源注册表
# ============================================================

# K线源 (按权重降序，失败自动降级)
KLINE_SOURCES = [
    {"name": "sina_vip",       "fn": _sina_vip_kline,      "weight": 1.0,  "market": "cn_etf"},
    {"name": "baostock",       "fn": _baostock_kline,      "weight": 0.9,  "market": "cn_all"},
    {"name": "tencent_kline",  "fn": _tencent_kline,       "weight": 0.7,  "market": "cn_etf"},
]

# 实时行情源
QUOTE_SOURCES = [
    {"name": "tencent_quote",   "fn": _tencent_batch_quote, "weight": 1.0,  "batch": True, "market": "all"},
    {"name": "sina_quote",      "fn": _sina_quote,           "weight": 0.8,  "batch": False,"market": "cn"},
]

# 财务/基本面源
FINANCE_SOURCES = [
    {"name": "akshare_finance",  "fn": _akshare_finance,    "weight": 1.0,  "market": "cn"},
]

# 估值源
VALUATION_SOURCES = [
    {"name": "akshare_valuation","fn": _akshare_valuation,   "weight": 1.0,  "market": "cn"},
]

# 资金流源
MONEYFLOW_SOURCES = [
    {"name": "akshare_moneyflow","fn": _akshare_moneyflow,  "weight": 1.0,  "market": "cn"},
]

# 指数/宏观源
INDEX_SOURCES = [
    {"name": "tencent_quote",    "fn": _tencent_index_quote, "weight": 1.0, "market": "index"},
    {"name": "akshare_pe_pb",    "fn": _akshare_index_pe_pb, "weight": 0.5, "market": "cn"},
]

# ETF源
ETF_SOURCES = [
    {"name": "akshare_etf_info", "fn": _akshare_etf_info,    "weight": 1.0, "market": "cn"},
]

# 选股源
FILTER_SOURCES = [
    {"name": "akshare_filter",   "fn": _akshare_stock_filter, "weight": 1.0, "market": "cn"},
]


# ============================================================
# 多源路由器
# ============================================================

class SourceRouter:
    """多源路由器：按权重+健康度选源，失败自动降级"""

    def __init__(self, defense: AntiBlockDefense, health: HealthMonitor):
        self.defense = defense
        self.health = health

    def fetch(self, code: str, source_list: list, **kwargs) -> Optional[dict]:
        """按source_list顺序尝试，失败降级
        Returns:
            {"source": "源名", "data": ...} or None
        """
        ordered = sorted(source_list, key=lambda s: -s.get("weight", 0))
        for src in ordered:
            name = src["name"]
            if not self.health.is_available(name):
                continue
            try:
                result = src["fn"](code, defense=self.defense, **kwargs)
                if result:
                    self.health.record_success(name)
                    return result
            except Exception as e:
                self.health.record_failure(name)
        return None

    def fetch_batch(self, codes: List[str], source_list: list, **kwargs) -> Optional[dict]:
        """批量查询：专用批处理
        Returns:
            {"source": "源名", "data": {code: record}} or None
        """
        ordered = sorted(source_list, key=lambda s: -s.get("weight", 0))
        for src in ordered:
            name = src["name"]
            if not self.health.is_available(name):
                continue
            try:
                # 批处理: 将codes分批(每批50只)
                if src.get("batch"):
                    all_results = {}
                    for i in range(0, len(codes), 50):
                        batch = codes[i:i + 50]
                        result = src["fn"](batch, defense=self.defense, **kwargs)
                        if result:
                            all_results.update(result.get("data", {}))
                    if all_results:
                        self.health.record_success(name)
                        return {"source": name, "data": all_results}
                else:
                    result = src["fn"](codes, defense=self.defense, **kwargs)
                    if result:
                        self.health.record_success(name)
                        return result
            except Exception as e:
                self.health.record_failure(name)
        return None

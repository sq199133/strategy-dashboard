"""Rewrite index() in sources.py - use Tencent for real-time, AKShare for PE/PB cached"""
with open('qclaw_stock_data/sources.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_fn = '''def _akshare_index_quote(index_code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
    """AKShare 指数行情/PE-PB

    支持: 上证指数/深证成指/创业板指/沪深300/中证500等
    """
    try:
        import akshare as ak
        mkt, num = normalize_code(index_code)
        # 指数代码格式转换
        index_map = {
            "000001": "000300",  # 上证指数 → 实际用沪深300
            "399001": "399905",  # 深证成指
            "399006": "399673",  # 创业板
        }
        symbol = index_map.get(num, num)
        full = f"{mkt.upper()}{symbol}"

        # 指数实时行情
        df = ak.stock_zh_index_spot_em()
        row = df[df["代码"] == symbol]
        if row is None or row.empty:
            return None

        r = row.iloc[0]
        return {
            "source": "akshare_index",
            "code": symbol,
            "data": {
                "name": r.get("名称"),
                "price": float(r.get("最新价", 0) or 0),
                "chg": float(r.get("涨跌额", 0) or 0),
                "chg_pct": float(r.get("涨跌幅", 0) or 0),
                "open": float(r.get("今开", 0) or 0),
                "high": float(r.get("最高", 0) or 0),
                "low": float(r.get("最低", 0) or 0),
                "volume": float(r.get("成交量", 0) or 0),
                "amount": float(r.get("成交额", 0) or 0),
                "pe": float(r.get("市盈率-动态", 0) or 0) or None,
                "pb": float(r.get("市净率", 0) or 0) or None,
            }
        }
    except Exception:
        return None'''

new_fn = '''def _tencent_index_quote(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
    """腾讯 指数行情 (快,实时)
    使用 qt.gtimg.cn 的 s_ 前缀
    字段: 现价/涨跌幅/成交量/成交额
    """
    qt_code = build_qt_code(code)  # s_sh000001
    url = f"https://qt.gtimg.cn/q={qt_code}"
    r = defense.get(url, source_name="tencent_quote", timeout=20)
    line = r.text.strip()
    if not line or "~" not in line:
        return None

    import re
    m = re.search(r'v_(\\w+)="(.+)"', line)
    if not m:
        return None
    fields = m.group(2).split("~")
    if len(fields) < 35:
        return None

    try:
        return {
            "source": "tencent_quote",
            "code": qt_code,
            "data": {
                "name": fields[1] if len(fields) > 1 else None,
                "price": float(fields[3]) if fields[3] else None,
                "chg": float(fields[4]) if fields[4] else None,
                "chg_pct": float(fields[32]) if len(fields) > 32 and fields[32] else None,
                "open": float(fields[5]) if len(fields) > 5 and fields[5] else None,
                "high": float(fields[33]) if len(fields) > 33 and fields[33] else None,
                "low": float(fields[34]) if len(fields) > 34 and fields[34] else None,
                "volume": int(float(fields[36])) if len(fields) > 36 and fields[36] else None,
                "amount": float(fields[37]) if len(fields) > 37 and fields[37] else None,
            }
        }
    except (ValueError, IndexError):
        return None


def _akshare_index_pe_pb(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
    """AKShare 指数 PE/PB (慢但全, 缓存1天)
    从 stock_zh_index_spot_em 提取 (268个主要指数)
    """
    try:
        import akshare as ak
        mkt, num = normalize_code(code)
        # 去掉 sh/sz 前缀，只保留数字
        symbol = num.lstrip("0123456789") or num
        if symbol.startswith("SH"):
            symbol = symbol[2:]
        elif symbol.startswith("SZ"):
            symbol = symbol[2:]

        df = ak.stock_zh_index_spot_em()
        if df is None or df.empty:
            return None

        # Find by code
        row = df[df["代码"] == symbol]
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
        return None'''

if old_fn in content:
    content = content.replace(old_fn, new_fn)
    print("Replaced!")
else:
    print("NOT FOUND")

# Also update INDEX_SOURCES to use the new function
old_registry = '''# 指数/宏观源
INDEX_SOURCES = [
    {"name": "akshare_index",    "fn": _akshare_index_quote, "weight": 1.0, "market": "cn"},
]'''
new_registry = '''# 指数/宏观源
INDEX_SOURCES = [
    {"name": "tencent_quote",    "fn": _tencent_index_quote, "weight": 1.0, "market": "index"},
    {"name": "akshare_pe_pb",    "fn": _akshare_index_pe_pb, "weight": 0.5, "market": "cn"},
]'''

if old_registry in content:
    content = content.replace(old_registry, new_registry)
    print("Replaced INDEX_SOURCES!")
else:
    print("INDEX_SOURCES not found")

import ast
try:
    ast.parse(content)
    print("Syntax OK!")
except SyntaxError as e:
    print(f"SyntaxError: {e}")

with open('qclaw_stock_data/sources.py', 'w', encoding='utf-8') as f:
    f.write(content)

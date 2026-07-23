"""Fix _akshare_index_pe_pb - extract numeric code correctly"""
with open('qclaw_stock_data/sources.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''def _akshare_index_pe_pb(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
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

new = '''def _akshare_index_pe_pb(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
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
        return None'''

if old in content:
    content = content.replace(old, new)
    print("Fixed!")
else:
    print("NOT FOUND - checking...")
    idx = content.find("def _akshare_index_pe_pb")
    print(repr(content[idx:idx+200]))

import ast
try:
    ast.parse(content)
    print("Syntax OK!")
except SyntaxError as e:
    print(f"SyntaxError: {e}")

with open('qclaw_stock_data/sources.py', 'w', encoding='utf-8') as f:
    f.write(content)

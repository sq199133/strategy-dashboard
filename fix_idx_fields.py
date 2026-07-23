"""Fix _tencent_index_quote field indices for index API (12 fields only)"""
with open('qclaw_stock_data/sources.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''def _tencent_index_quote(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
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
    m = re.search(r"v_(\\w+)=\"(.+)\"", line)
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
        return None'''

new = '''def _tencent_index_quote(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
    """腾讯 指数行情 (快,实时,12字段格式)
    使用 qt.gtimg.cn 的 s_ 前缀
    字段格式 (12个):
      [0] 序号 [1] 名称 [2] 代码 [3] 现价 [4] 涨跌额 [5] 涨跌幅(%)
      [6] 成交量 [7] 成交额(万元) [9] 成交额(百万元) [10] ZS(指数标识)
    """
    qt_code = build_qt_code(code)  # s_sh000001
    url = f"https://qt.gtimg.cn/q={qt_code}"
    r = defense.get(url, source_name="tencent_quote", timeout=20)
    line = r.text.strip()
    if not line or "~" not in line:
        return None

    import re
    m = re.search(r"v_(\\w+)=\"(.+)\"", line)
    if not m:
        return None
    fields = m.group(2).split("~")
    if len(fields) < 6:
        return None

    try:
        price = float(fields[3]) if fields[3] and fields[3] != '-' else None
        chg = float(fields[4]) if fields[4] and fields[4] != '-' else None
        chg_pct = float(fields[5]) if fields[5] and fields[5] != '-' else None
        volume = int(float(fields[6])) if len(fields) > 6 and fields[6] and fields[6] != '-' else None
        amount_wan = float(fields[7]) if len(fields) > 7 and fields[7] and fields[7] != '-' else None
        return {
            "source": "tencent_quote",
            "code": qt_code,
            "data": {
                "name": fields[1] if len(fields) > 1 else None,
                "price": price,
                "chg": chg,
                "chg_pct": chg_pct,
                "volume": volume,  # 手
                "amount_wan": amount_wan,  # 万元
            }
        }
    except (ValueError, IndexError):
        return None'''

if old in content:
    content = content.replace(old, new)
    print("Fixed!")
else:
    print("NOT FOUND - checking...")
    idx = content.find("def _tencent_index_quote")
    print(repr(content[idx:idx+50]))

import ast
try:
    ast.parse(content)
    print("Syntax OK!")
except SyntaxError as e:
    print(f"SyntaxError: {e}")

with open('qclaw_stock_data/sources.py', 'w', encoding='utf-8') as f:
    f.write(content)

"""Fix build_qt_code to use lowercase for Tencent API"""
with open('qclaw_stock_data/sources.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''def build_qt_code(raw: str) -> str:
    """为腾讯qt.gtimg.cn构建查询代码

    A股: sz000001 / sh600519
    指数: s_sh000001 / s_sz399006
    港股: hk00700
    美股: usAAPL
    """
    mkt, num = normalize_code(raw)
    if mkt == "index":
        return f"s_{num}"  # num = "sh000001"
    elif mkt in ("sh", "sz"):
        return f"{mkt}{num}"
    elif mkt == "hk":
        return f"hk{num}"
    elif mkt == "us":
        return f"us{num}"
    return f"{mkt}{num}"'''

new = '''def build_qt_code(raw: str) -> str:
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
    return f"{mkt}{num}"'''

if old in content:
    content = content.replace(old, new)
    print("Fixed!")
else:
    print("NOT FOUND")

import ast
try:
    ast.parse(content)
    print("Syntax OK!")
except SyntaxError as e:
    print(f"SyntaxError: {e}")

with open('qclaw_stock_data/sources.py', 'w', encoding='utf-8') as f:
    f.write(content)

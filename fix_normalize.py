"""Fix code normalization in sources.py"""
with open('qclaw_stock_data/sources.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_fn = '''def normalize_code(raw: str) -> tuple[str, str]:
    """将各种代码格式标准化为 (market, number)

    支持格式:
      - 6位纯数字: "159928" → ("sz", "159928")
      - sh/sz前缀: "sh600519" → ("sh", "600519")
      - hk前缀:    "hk00700"  → ("hk", "00700")
      - us前缀:    "usAAPL"   → ("us", "AAPL")
      - 指数格式:  "sh000001" → ("sh", "000001")

    Returns:
        (market_prefix, numeric/code) - market is "sh"|"sz"|"hk"|"us"
    """
    s = str(raw).strip().lower()
    # 已带前缀
    m = re.match(r"^(sh|sz|hk|us)(\w+)$", s)
    if m:
        return m.group(1), m.group(2)
    # 纯6位数字 → 自动识别市场
    if re.match(r"^\d{6}$", s):
        mkt = code_market(s)
        return mkt, s
    # 其他格式 (4位港股, 美股字母码等)
    if re.match(r"^\d{4,5}$", s):
        return "hk", s  # 4-5位数字默认港股
    return "us", s  # 字母码默认美股'''

new_fn = '''def normalize_code(raw: str) -> tuple[str, str]:
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
    # 已带前缀 (保留原始大小写，用于美股代码)
    m = re.match(r"^(sh|sz|hk|us)(\w+)$", s, re.IGNORECASE)
    if m:
        prefix = m.group(1).lower()
        num = m.group(2)
        # s_前缀: s_sh000001 → 指数
        if prefix == "s" and num.startswith(("sh", "sz")):
            return "index", num.upper()
        return prefix, num
    # 纯6位数字 → 自动识别A股市场
    if re.match(r"^\d{6}$", s):
        mkt = code_market(s)
        return mkt, s
    # 其他数字格式 (4-5位 → 港股)
    if re.match(r"^\d{4,5}$", s):
        return "hk", s
    # 其余 → 美股 (保留原大小写)
    return "us", s'''

if old_fn in content:
    content = content.replace(old_fn, new_fn)
    print("Fixed normalize_code")
else:
    print("WARNING: normalize_code not found exactly")
    # Find where it is
    idx = content.find('def normalize_code(raw')
    print(f"  Found at index: {idx}")
    print(f"  First 200 chars: {content[idx:idx+200]}")

# Also fix build_qt_code to handle index
old_build = '''def build_qt_code(raw: str) -> str:
    """为腾讯qt.gtimg.cn构建查询代码

    A股: sz000001 / sh600519
    指数: s_sh000001 (加s_前缀)
    港股: hk00700
    美股: usAAPL
    """
    mkt, num = normalize_code(raw)
    if mkt in ("sh", "sz"):
        # 指数加s_前缀
        if re.match(r"^00\\d{3}$", num) or re.match(r"^399\\d{3}$", num):
            return f"s_{mkt}{num}"
        return f"{mkt}{num}"
    elif mkt == "hk":
        return f"hk{num}"
    elif mkt == "us":
        return f"us{num}"
    return f"{mkt}{num}"'''

new_build = '''def build_qt_code(raw: str) -> str:
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

if old_build in content:
    content = content.replace(old_build, new_build)
    print("Fixed build_qt_code")
else:
    print("WARNING: build_qt_code not found exactly")

# Verify syntax
import ast
try:
    ast.parse(content)
    print("Syntax OK!")
except SyntaxError as e:
    print(f"SyntaxError at line {e.lineno}: {e.msg}")

with open('qclaw_stock_data/sources.py', 'w', encoding='utf-8') as f:
    f.write(content)

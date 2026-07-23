"""Fix s_sh prefix detection in sources.py"""
with open('qclaw_stock_data/sources.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''    # 已带前缀 (保留原始大小写，用于美股代码)
    m = re.match(r"^(sh|sz|hk|us)(\w+)$", s, re.IGNORECASE)
    if m:
        prefix = m.group(1).lower()
        num = m.group(2)
        # s_前缀: s_sh000001 → 指数
        if prefix == "s" and num.startswith(("sh", "sz")):
            return "index", num.upper()
        return prefix, num'''

new = '''    # 已带前缀: 指数(s_sh/s_sz) > 港股(hk) > 美股(us) > A股(sh/sz)
    # 顺序很重要: 先匹配长的前缀
    # s_前缀: s_sh000001 / s_sz399006 → 指数
    if re.match(r"^s_(sh|sz)\d{6}$", s, re.IGNORECASE):
        idx = s[2:].upper()  # "SH000001"
        return "index", idx
    # 标准前缀: sh/sz/hk/us + 数字或代码
    m = re.match(r"^(sh|sz|hk|us)(\w+)$", s, re.IGNORECASE)
    if m:
        return m.group(1).lower(), m.group(2)'''

if old in content:
    content = content.replace(old, new)
    print("Fixed!")
else:
    print("NOT FOUND - checking...")
    idx = content.find('已带前缀')
    print(repr(content[idx:idx+300]))

import ast
try:
    ast.parse(content)
    print("Syntax OK!")
except SyntaxError as e:
    print(f"SyntaxError: {e}")

with open('qclaw_stock_data/sources.py', 'w', encoding='utf-8') as f:
    f.write(content)

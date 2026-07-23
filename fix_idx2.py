"""Fix _tencent_index_quote - index only has 12 fields, not 50+"""
with open('qclaw_stock_data/sources.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the function and replace lines 439-459 (1-indexed)
func_start = None
for i, line in enumerate(lines):
    if 'def _tencent_index_quote' in line:
        func_start = i
        break

if func_start is None:
    print("Function not found")
else:
    print(f"Found at line {func_start+1}")

# Replace lines from func_start to func_start+38 (the entire function)
new_func = '''def _tencent_index_quote(code: str, defense: AntiBlockDefense = None) -> Optional[dict]:
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
    m = re.search(r'v_(\\w+)="(.+)"', line)
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


'''

# Find end of function (next def or end of file)
func_end = func_start + 1
while func_end < len(lines):
    stripped = lines[func_end].strip()
    # End when we hit another top-level def
    if stripped.startswith('def ') and not lines[func_end].startswith('    '):
        break
    func_end += 1

print(f"Replacing lines {func_start+1} to {func_end}")

new_lines = lines[:func_start] + [new_func] + lines[func_end:]
new_content = ''.join(new_lines)

import ast
try:
    ast.parse(new_content)
    print("Syntax OK!")
except SyntaxError as e:
    print(f"SyntaxError at line {e.lineno}: {e.msg}")
    # Try to show the problematic area
    err_line = e.lineno - 1
    for i in range(max(0, err_line-3), min(len(new_lines), err_line+3)):
        print(f"  {i+1}: {new_lines[i]}", end='')

with open('qclaw_stock_data/sources.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Written!")

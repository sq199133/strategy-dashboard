"""Fix bracket syntax errors in sources.py"""
with open('qclaw_stock_data/sources.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix MONEYFLOW_SOURCES - wrong bracket
old1 = '    {"name": "akshare_moneyflow","fn": _akshare_moneyflow,  "weight": 1.0,  "market": "cn"],'
new1 = '    {"name": "akshare_moneyflow","fn": _akshare_moneyflow,  "weight": 1.0,  "market": "cn"},'

if old1 in content:
    content = content.replace(old1, new1)
    print("Fixed MONEYFLOW_SOURCES")
else:
    print("MONEYFLOW_SOURCES OK")

# Verify syntax
import ast
try:
    ast.parse(content)
    print("Syntax OK!")
except SyntaxError as e:
    print(f"SyntaxError at line {e.lineno}: {e.msg}")
    lines = content.split('\n')
    for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
        print(f"  {i+1}: {lines[i][:80]}")

with open('qclaw_stock_data/sources.py', 'w', encoding='utf-8') as f:
    f.write(content)

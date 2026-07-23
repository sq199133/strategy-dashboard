"""验证 /current/ 目录内容"""
import re

# Check ETF pool
with open(r'D:\QClaw_Trading\RSRS\current\rsrs_engine.py', 'r', encoding='utf-8') as f:
    c = f.read()
m = re.search(r'ETF_POOL\s*=\s*\{', c)
if m:
    start = m.start()
    brace = 0
    for i in range(start, len(c)):
        if c[i] == '{': brace += 1
        elif c[i] == '}':
            brace -= 1
            if brace == 0:
                block = c[start:i+1]
                # Count entries
                entries = re.findall(r"'(\d{6})':\s*'([^']+)'", block)
                print(f"ETF_POOL entries ({len(entries)}):")
                for code, name in entries:
                    print(f"  {code} -> {name}")
                break

# Check daily_review encoding fix
with open(r'D:\QClaw_Trading\RSRS\current\daily_review.py', 'r', encoding='utf-8') as f:
    dr = f.read()
print(f"\ndaily_review.py has reconfigure: {'sys.stdout.reconfigure' in dr}")
print("First 7 lines:")
for l in dr.split('\n')[:7]:
    print(f"  {repr(l)}")

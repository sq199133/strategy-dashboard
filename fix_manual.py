import re
path = r"D:\QClaw_Trading\data\ETF波段策略执行手册.md"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all occurrences
content = content.replace('2026-05-17', '2026-05-22')
# Fix config section
content = re.sub(r'(止损线:   )8%', r'\g<1>6%', content)
content = re.sub(r'(止盈线:   )15%', r'\g<1>10%', content)
# Fix table rows - use word boundary to avoid replacing 8% in other context
content = re.sub(r'下跌8%', '下跌6%', content)
content = re.sub(r'上涨15%', '上涨10%', content)
# Fix code block
content = re.sub(r'STOP_LOSS = 0\.08.*?# 止损8%', 'STOP_LOSS = 0.06          # 止损6%', content)
content = re.sub(r'TAKE_PROFIT = 0\.15.*?# 止盈15%', 'TAKE_PROFIT = 0.10        # 止盈10%', content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
with open(path, 'r', encoding='utf-8') as f:
    result = f.read()

hits = re.findall(r'6%|10%|止损6|止盈10|2026-05-22', result)
print("验证替换结果:", hits)

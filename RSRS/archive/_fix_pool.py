"""Fix DEFAULT_POOL in rsrs_final_strategy.py"""
path = r'D:\QClaw_Trading\RSRS\rsrs_final_strategy.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

start = content.index("DEFAULT_POOL = {")
brace_count = 0
for i in range(start, len(content)):
    if content[i] == '{': brace_count += 1
    elif content[i] == '}':
        brace_count -= 1
        if brace_count == 0:
            end = i + 1
            break

old_block = content[start:end]

new_block = """# 永久锁定（与 docs/final_strategy_v2.md 一致）
# ETF池 11只（2026-07-11 确认）
DEFAULT_POOL = {
    '510050': 'SH50',       # 上证50
    '510300': 'HS300',      # 沪深300
    '510500': 'ZZ500',      # 中证500
    '512100': 'ZZ1000',     # 中证1000
    '159915': 'CYB',        # 创业板指
    '588000': 'KC50',       # 科创50
    '513500': 'SP500',      # 标普500
    '513100': 'NSDQ',       # 纳斯达克100
    '518880': 'GOLD',       # 黄金ETF
    '162411': 'OIL',        # 原油基金
    '515080': 'ZSHL',       # 中证红利
}"""

print(f"Old block:\n{old_block}\n")
content = content[:start] + new_block + content[end:]
print(f"New block applied.")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("[SAVED]")

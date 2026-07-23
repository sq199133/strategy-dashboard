"""批量修复 RSRS 脚本的默认参数和编码问题"""
import os, re

CONFIRMED_POOL = {
    '510050': 'SH50',
    '510300': 'HS300',
    '510500': 'ZZ500',
    '512100': 'ZZ1000',
    '159915': 'CYB',
    '588000': 'KC50',
    '513500': 'SP500',
    '513100': 'NSDQ',
    '518880': 'GOLD',
    '162411': 'OIL',
    '515080': 'ZSHL',
}

def replace_pool_block(content, pool_key='ETF_POOL'):
    """找到并替换 ETF_POOL 块"""
    pattern = pool_key + r'\s*=\s*\{'
    m = re.search(pattern, content)
    if not m:
        print(f"[WARN] {pool_key} not found")
        return content, False
    start = m.start()
    brace_count = 0
    for i in range(start, len(content)):
        if content[i] == '{': brace_count += 1
        elif content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break
    # Build new block
    new_block = (f"# 永久锁定（与 docs/final_strategy_v2.md 一致）\n"
                 f"# ETF池 11只（2026-07-11 确认）\n"
                 f"{pool_key} = {{\n")
    for k, v in CONFIRMED_POOL.items():
        new_block += f"    '{k}': '{v}',\n"
    new_block = new_block.rstrip().rstrip(',') + '\n}'
    print(f"[OK] {pool_key} replaced with confirmed 11-ETF pool")
    return content[:start] + new_block + content[end:], True

def fix_rsrs_engine(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content

    content, _ = replace_pool_block(content, 'ETF_POOL')

    if 'def __init__(self, n=18, m=900,' in content:
        content = content.replace(
            'def __init__(self, n=18, m=900,',
            'def __init__(self, n=18, m=1200,'
        )
        print("[OK] __init__ default m=1200")
    else:
        print("[WARN] __init__ pattern not found")

    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[SAVED] rsrs_engine.py")

def fix_daily_output(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content

    if "'--m', type=int, default=900" in content:
        content = content.replace(
            "'--m', type=int, default=900",
            "'--m', type=int, default=1200"
        )
        print("[OK] rsrs_daily_output --m default=1200")
    if "'--m', type=int, default=900" not in content and '--m' in content:
        print("[INFO] rsrs_daily_output --m already 1200 or uses different format")

    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[SAVED] rsrs_daily_output.py")

def fix_daily_review(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content

    if 'sys.stdout.reconfigure' not in content:
        lines = content.split('\n')
        new_lines = []
        added = False
        for line in lines:
            new_lines.append(line)
            if not added and line.strip().startswith('# -*- coding'):
                new_lines.append('import sys')
                new_lines.append("sys.stdout.reconfigure(encoding='utf-8')")
                added = True
                print("[OK] Added sys + reconfigure after coding line")
        content = '\n'.join(new_lines)

    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[SAVED] daily_review.py")

print("=== Fixing rsrs_engine.py ===")
fix_rsrs_engine(r'D:\QClaw_Trading\RSRS\rsrs_engine.py')

print("\n=== Fixing rsrs_daily_output.py ===")
fix_daily_output(r'D:\QClaw_Trading\RSRS\rsrs_daily_output.py')

print("\n=== Fixing daily_review.py ===")
fix_daily_review(r'D:\QClaw_Trading\RSRS\daily_review.py')

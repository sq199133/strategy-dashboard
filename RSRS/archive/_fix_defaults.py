"""修复 rsrs_final_strategy.py 的默认参数"""
import re

path = r'D:\QClaw_Trading\RSRS\rsrs_final_strategy.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

original = content

# Fix 1: DEFAULT_POOL → 11 confirmed ETFs
old_pool_block = """DEFAULT_POOL = {
    '510300': 'HS300',      # 宽基-大盘
    '510050': 'SH50',       # 宽基-超大蓝筹
    '159902': 'ZZSM100',    # 宽基-中小盘
    '159949': 'CYB50',      # 宽基-成长
    '512100': 'ZZ1000',     # 宽基-小盘
    '159928': 'CONSUM',     # 行业-消费
    '512800': 'BANK',       # 行业-银行
    '512400': 'METAL',      # 行业-有色
    '512200': 'REALEST',    # 行业-地产
    '510160': 'INDUP',      # 行业-工业
    '518880': 'GOLD',       # 商品-黄金
    '159905': 'DIV',        # 策略-高分红
    '510810': 'SHGQ',       # 政策-上海国企
}"""

new_pool_block = """# 永久锁定（与 docs/final_strategy_v2.md 一致）
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

if old_pool_block in content:
    content = content.replace(old_pool_block, new_pool_block)
    print("[OK] DEFAULT_POOL → 11 ETFs (confirmed)")
else:
    # Try to find what DEFAULT_POOL looks like
    m = re.search(r"DEFAULT_POOL\s*=\s*\{", content)
    if m:
        print(f"[WARN] DEFAULT_POOL block not matched exactly. Found at pos {m.start()}")
        # Extract current block
        start = content.index("DEFAULT_POOL = {")
        # Find matching closing brace
        brace_count = 0
        for i in range(start, len(content)):
            if content[i] == '{': brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        current_block = content[start:end]
        print(f"Current block:\n{current_block[:300]}")
    else:
        print("[ERROR] DEFAULT_POOL not found at all")

# Fix 2: compute_rsrs default m=1200
if "def compute_rsrs(df, n=18, m=900," in content:
    content = content.replace(
        "def compute_rsrs(df, n=18, m=900, buy_thr=0.7, sell_thr=-1.0):",
        "def compute_rsrs(df, n=18, m=1200, buy_thr=0.7, sell_thr=-1.0):"
    )
    print("[OK] compute_rsrs default m=1200")
else:
    print("[WARN] compute_rsrs signature not found")

# Fix 3: argparse --m default 1200
if "--m', type=int, default=900" in content:
    content = content.replace(
        "parser.add_argument('--m', type=int, default=900, help='RSRS标准化窗口')",
        "parser.add_argument('--m', type=int, default=1200, help='RSRS标准化窗口（确认值=1200）')"
    )
    print("[OK] argparse --m default=1200")
else:
    print("[WARN] argparse --m pattern not found")

if content != original:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[SAVED] {path}")
else:
    print("[SKIP] No changes needed")

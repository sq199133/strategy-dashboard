import json, os, sys, glob
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

MA_S, MA_L, LB = 5, 21, 3
MAX_DEV = 15
MIN_MOM_3W, MIN_MOM_1W = 0.00, -0.01

def load_pool():
    with open(POOL_FILE, encoding='utf-8') as f:
        d = json.load(f)
    return d.get('data', d.get('etfs', []))

def load_history(code):
    for pat in (code, f'sh{code}', f'sz{code}'):
        hits = glob.glob(os.path.join(HISTORY_DIR, f'{pat}.json'))
        if not hits:
            hits = glob.glob(os.path.join(HISTORY_DIR, f'*{code}*.json'))
        if hits:
            try:
                with open(hits[0], encoding='utf-8') as f:
                    d = json.load(f)
                recs = d.get('records', []) if isinstance(d, dict) else d
                weeks = {}
                for r in recs:
                    if isinstance(r, dict):
                        ds, cl = r['date'], float(r.get('close', 0))
                    else:
                        ds, cl = str(r[0]), float(r[2])
                    try:
                        dt = datetime.strptime(ds, '%Y-%m-%d')
                        w = f'{dt.year}-W{dt.isocalendar()[1]:02d}'
                        weeks[w] = cl
                    except:
                        pass
                return sorted(weeks.items())
            except:
                continue
    return None

etfs = load_pool()
code_info = {}
for etf in etfs:
    code_info[etf['code']] = {'name': etf.get('name', ''), 'cat': etf.get('category', '')}

for code in ['159786', '159732']:
    print(f'\n{"="*60}')
    print(f'  检查 {code} {code_info.get(code, {})}')')
    print(f'{"="*60}')
    
    s = load_history(code)
    if not s:
        print('  无数据')
        continue
    
    print(f'  数据周数: {len(s)}')
    print(f'  最近8周:')
    for w, c in s[-8:]:
        print(f'    {w}: {c:.4f}')
    
    cs = [c for w2, c in s]
    n = len(cs)
    print(f'\n  n={n}, LB={LB}, MA_L={MA_L}')
    
    # 条件：数据足够
    if n < MA_L + 1:
        print(f'  ✗ 数据不足: n={n} < MA_L+1={MA_L+1}')
        continue
    
    price = cs[-1]
    ma_s = sum(cs[-MA_S:]) / MA_S
    ma_l = sum(cs[-MA_L:]) / MA_L
    print(f'\n  收盘: {price:.4f}')
    print(f'  MA5:  {ma_s:.4f}')
    print(f'  MA21: {ma_l:.4f}')
    
    # c1: 三周动量 > 0
    if n <= LB:
        print(f'  ✗ c1失败: n={n} <= LB={LB}')
        continue
    mom3w = cs[-1] / cs[-LB] - 1
    print(f'  c1 三周动量: {mom3w:+.2%} (需要 > 0)')
    if mom3w <= 0 or mom3w < MIN_MOM_3W:
        print(f'  ✗ c1失败: mom3w={mom3w:+.2%} 不满足 >0 且 >={MIN_MOM_3W}')
        continue
    print(f'  ✓ c1通过')
    
    # c2: 价格 > MA5 > MA21
    print(f'  c2 均线: 价格{price:.4f} > MA5{ma_s:.4f} > MA21{ma_l:.4f} ?')
    if not (price > ma_s > ma_l):
        print(f'  ✗ c2失败: 均线不是多头排列')
        continue
    print(f'  ✓ c2通过')
    
    # c3: 偏离度 <= 15%
    dev = price / ma_l - 1
    print(f'  c3 偏离度: {dev:+.2%} (需要 <={MAX_DEV}%)')
    if dev > MAX_DEV / 100.0:
        print(f'  ✗ c3失败: 偏离度 {dev:+.2%} > {MAX_DEV}%')
        continue
    print(f'  ✓ c3通过')
    
    # G3过滤
    print(f'  G3过滤:')
    if MIN_MOM_1W is not None and n >= 2:
        mom1w = cs[-1] / cs[-2] - 1
        print(f'    三周动量: {mom3w:+.2%} (需要 >= {MIN_MOM_3W:+.0%})')
        print(f'    本周动量: {mom1w:+.2%} (需要 >= {MIN_MOM_1W:+.0%})')
        if mom3w < MIN_MOM_3W:
            print(f'  ✗ G3失败: 三周动量 {mom3w:+.2%} < {MIN_MOM_3W:+.0%}')
            continue
        if mom1w < MIN_MOM_1W:
            print(f'  ✗ G3失败: 本周动量 {mom1w:+.2%} < {MIN_MOM_1W:+.0%}')
            continue
    print(f'  ✓ G3通过')
    
    print(f'\n  ✅ 全部通过 → passed=True')

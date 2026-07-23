import sys, json, glob
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

print('验证2025年收益计算...')

# 1. 检查ETF池
with open(POOL_FILE, encoding='utf-8') as f:
    raw = f.read().replace('NaN', 'null')
pool = json.loads(raw)
print(f'ETF池数量: {len(pool["data"])}')

# 2. 检查沪深300 2025年数据
def load_weeks_simple(code):
    for pat in (code, f'sh{code}', f'sz{code}'):
        hits = glob.glob(fr'{HISTORY_DIR}\{pat}.json')
        if hits:
            try:
                with open(hits[0], encoding='utf-8') as f:
                    raw = f.read().replace('NaN', 'null')
                d = json.loads(raw)
                recs = d.get('records', []) if isinstance(d, dict) else d
                wmap = {}
                for r in recs:
                    if isinstance(r, dict):
                        ds, cl = r['date'], float(r.get('close', 0))
                    else:
                        ds, cl = str(r[0]), float(r[2])
                    try:
                        dt = datetime.strptime(ds, '%Y-%m-%d')
                        w  = f'{dt.year}-W{dt.isocalendar()[1]:02d}'
                        if w not in wmap or ds > wmap[w][0]:
                            wmap[w] = (ds, cl)
                    except: pass
                sw = sorted(wmap.items())
                return {w: cl for w, (ds, cl) in sw}
            except: continue
    return None

hs300_wmap = load_weeks_simple('000300')
if hs300_wmap:
    weeks_2025 = sorted([w for w in hs300_wmap if w.startswith('2025')])
    if len(weeks_2025) >= 2:
        first_w = weeks_2025[0]
        last_w  = weeks_2025[-1]
        first_p = hs300_wmap[first_w]
        last_p  = hs300_wmap[last_w]
        ret = last_p / first_p - 1
        print(f'\n沪深300 2025年收益: {ret:+.1%}')
        print(f'  第一周: {first_w}, 价格: {first_p:.2f}')
        print(f'  最后周: {last_w}, 价格: {last_p:.2f}')
    else:
        print('\n沪深300 2025年数据不足')
else:
    print('\n未找到沪深300数据')

# 3. 简单回测验证（仅计算价值曲线）
print(f'\n{"="*70}')
print('简单回测验证（LB=5, 偏离度=10%, 沪深300>-1%）')
print(f'{"="*70}')

# 加载数据
codes = [e['code'] for e in pool['data']]
hist = {}
for code in codes:
    wmap = load_weeks_simple(code)
    if wmap: hist[code] = wmap
print(f'已加载: {len(hist)} 只ETF')

all_weeks = sorted(set().union(*(hist[c].keys() for c in hist)))
print(f'总周数: {len(all_weeks)} ({all_weeks[0]} ~ {all_weeks[-1]})')

# 计算信号
MA_S, MA_L = 5, 21
MAX_DEV = 10
LB = 5
SKIP_WEEKS = {'2024-W01', '2025-W01'}

weekly_sig = {}
for code in hist:
    wmap = hist[code]
    weeks = sorted(wmap.keys())
    cs    = [wmap[w] for w in weeks]
    if len(cs) < MA_L + LB: continue
    for i in range(MA_L, len(cs)):
        w = weeks[i]
        price = cs[i]
        ma_s  = sum(cs[i-MA_S+1:i+1]) / MA_S
        ma_l  = sum(cs[i-MA_L+1:i+1]) / MA_L
        dev   = price / ma_l - 1
        mom   = cs[i] / cs[i-LB] - 1
        if mom <= 0: continue
        if not (price > ma_s > ma_l): continue
        if dev > MAX_DEV/100: continue
        g3 = True
        if i >= 1 and cs[i]/cs[i-1]-1 < -0.01: g3 = False
        if mom <= 0: g3 = False
        if g3:
            weekly_sig.setdefault(w, []).append((code, mom))

print(f'信号周数: {len(weekly_sig)}')

# 计算收益
value = 10000.0
curve = []
prev_top = None
prev_w   = None

for i, w in enumerate(all_weeks):
    sig = weekly_sig.get(w)
    top3 = [c for c, m in sorted(sig, key=lambda x: x[1], reverse=True)[:3]] if sig else []
    if prev_top and prev_w and len(prev_top) == 3:
        rets = []
        for c in prev_top:
            if c in hist and w in hist[c] and prev_w in hist[c]:
                r = hist[c][w] / hist[c][prev_w] - 1
                rets.append(r)
        if rets:
            ret = sum(rets) / len(rets)
            value *= (1 + ret)
    curve.append((w, value))
    prev_top = top3 if top3 else prev_top
    prev_w   = w

# 输出关键时点
print(f'\n关键时点价值:')
key_weeks = ['2010-W52', '2015-W52', '2020-W52', '2024-W52', '2025-W52', '2026-W18']
for w in key_weeks:
    hits = [v for ww, v in curve if ww <= w]
    if hits:
        print(f'  {w}: {hits[-1]:,.0f}')

# 计算2025年收益
vals_2025 = [(w, v) for w, v in curve if w.startswith('2025')]
if len(vals_2025) >= 2:
    start_val = vals_2025[0][1]
    end_val   = vals_2025[-1][1]
    ret_2025  = end_val / start_val - 1
    print(f'\n2025年收益验证:')
    print(f'  起始价值: {start_val:,.0f}')
    print(f'  结束价值: {end_val:,.0f}')
    print(f'  2025年收益: {ret_2025:+.1%}')
else:
    print('\n2025年数据不足')

print(f'\n验证完成')

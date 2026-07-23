import sys, json, glob
from datetime import datetime
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

print('=' * 70)
print('  逐年回测 (LB=5, 偏离度=10%, 沪深300>-1%)')
print('=' * 70)

# 加载ETF池
with open(POOL_FILE, encoding='utf-8') as f:
    raw = f.read().replace('NaN', 'null')
pool = json.loads(raw)
codes = [e['code'] for e in pool['data']]
print(f'\nETF池: {len(codes)} 只')

# 加载历史数据
def load_weeks(code):
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

print('\n加载历史数据...')
hist = {}
for i, code in enumerate(codes):
    wmap = load_weeks(code)
    if wmap: hist[code] = wmap
    if (i + 1) % 20 == 0:
        print(f'  已加载: {len(hist)}/{i+1}', end='\r')
print(f'\n已加载: {len(hist)} 只ETF')

# 加载沪深300动量
print('\n加载沪深300动量...')
hs300 = load_weeks('000300')
hs300_mom = {}
if hs300:
    weeks = sorted(hs300.keys())
    closes = [hs300[w] for w in weeks]
    for i, w in enumerate(weeks):
        if i >= 5:
            hs300_mom[w] = closes[i] / closes[i-5] - 1
    print(f'  沪深300数据: {len(hs300)} 周')
    print(f'  动量数据: {len(hs300_mom)} 周')
else:
    print('  未找到沪深300数据')

# 回测参数
MA_S, MA_L = 5, 21
LB = 5
MAX_DEV = 10
SKIP_WEEKS = {'2024-W01', '2025-W01'}

# 计算信号
print('\n计算信号...')
weekly_sig = {}
for code in hist:
    wmap = hist[code]
    weeks = sorted(wmap.keys())
    cs    = [wmap[w] for w in weeks]
    if len(cs) < MA_L + LB: continue
    for i in range(MA_L, len(cs)):
        w = weeks[i]
        if w in SKIP_WEEKS: continue
        if hs300_mom and w in hs300_mom and hs300_mom[w] <= -0.01: continue
        price = cs[i]
        ma_s  = sum(cs[i-MA_S+1:i+1]) / MA_S
        ma_l  = sum(cs[i-MA_L+1:i+1]) / MA_L
        dev   = price / ma_l - 1
        mom   = cs[i] / cs[i-LB] - 1
        if mom <= 0: continue
        if not (price > ma_s > ma_l): continue
        if dev > MAX_DEV / 100: continue
        g3 = True
        if i >= 1 and cs[i]/cs[i-1]-1 < -0.01: g3 = False
        if mom <= 0: g3 = False
        if g3:
            weekly_sig.setdefault(w, []).append((code, mom))

print(f'信号周数: {len(weekly_sig)}')

# 逐年回测
print('\n' + '=' * 70)
print('  逐年回测结果')
print('=' * 70)

all_weeks = sorted(set().union(*(hist[c].keys() for c in hist)))
value = 10000.0
curve = []
prev_top = None
prev_w   = None

for i, w in enumerate(all_weeks):
    if w in SKIP_WEEKS: continue
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
    curve.append((w[:4], w, value))
    prev_top = top3 if top3 else prev_top
    prev_w   = w

# 按年汇总
yearly = defaultdict(list)
for yr, w, v in curve:
    yearly[yr].append(v)

print(f'\n{"年份":<6} {"起始价值":>12} {"结束价值":>12} {"年化收益":>10} {"累计倍数":>10}')
print('-' * 70)

results = []
for yr in sorted(yearly.keys()):
    vals = yearly[yr]
    if len(vals) < 2: continue
    start_v = vals[0]
    end_v   = vals[-1]
    ret     = end_v / start_v - 1
    multiple = end_v / 10000.0
    print(f'{yr:<6} {start_v:>12,.0f} {end_v:>12,.0f} {ret:>+9.1%} {multiple:>9.2f}x')
    results.append((yr, start_v, end_v, ret, multiple))

# 总计
if results:
    total_ret = results[-1][2] / results[0][1] - 1
    total_mult = results[-1][2] / 10000.0
    print(f'\n{"总计":<6} {"":>12} {results[-1][2]:>12,.0f} {total_ret:>+9.1%} {total_mult:>9.2f}x')

print('\n' + '=' * 70)
print('  回测完成')
print('=' * 70)

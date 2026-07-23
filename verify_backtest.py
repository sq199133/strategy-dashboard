import sys, json, glob
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'

def load_weeks(code):
    for pat in (code, f'sh{code}', f'sz{code}'):
        hits = glob.glob(fr'{HISTORY_DIR}\{pat}.json')
        if not hits:
            hits = glob.glob(fr'{HISTORY_DIR}\*{code}*.json')
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
                        w = f'{dt.year}-W{dt.isocalendar()[1]:02d}'
                        if w not in wmap or ds > wmap[w][0]:
                            wmap[w] = (ds, cl)
                    except: pass
                sw = sorted(wmap.items())
                return {w: cl for w, (ds, cl) in sw}
            except: continue
    return None

# 验证：买入持有 159915（创业板ETF）2016-W01 到 2026-W23
code = '159915'
wmap = load_weeks(code)
if not wmap:
    print('无数据')
    sys.exit()

weeks = sorted(wmap.keys())
start_w, end_w = '2016-W01', '2026-W23'
if start_w not in wmap or end_w not in wmap:
    print(f'缺少周: start={start_w in wmap}, end={end_w in wmap}')
    sys.exit()

start_p = wmap[start_w]
end_p   = wmap[end_w]
total_ret = end_p / start_p - 1
n_weeks = weeks.index(end_w) - weeks.index(start_w) + 1
n_years = n_weeks / 52.0
cagr = (end_p/start_p)**(1/n_years) - 1

print(f'买入持有验证: {code}')
print(f'  区间: {start_w} -> {end_w}  ({n_weeks}周, {n_years:.1f}年)')
print(f'  价格: {start_p:.4f} -> {end_p:.4f}')
print(f'  总收益: {total_ret:+.1%}')
print(f'  年化:   {cagr:+.1%}')

# 用回测框架跑同样的买入持有
print(f'\n用回测框架验证...')
value = 10000.0
curve = []
for w in weeks:
    if w < start_w: continue
    if w > end_w: break
    r = wmap[w] / wmap[weeks[weeks.index(w)-1]] - 1 if weeks.index(w) > 0 and w != start_w else 0
    value *= (1 + r)
    curve.append(value)

if curve:
    v0 = curve[0]
    v1 = curve[-1]
    print(f'  框架结果: {v0:,.0f} -> {v1:,.0f}  ({v1/v0-1:+.1%})')
    print(f'  直接算法: {start_p:.4f} -> {end_p:.4f}  ({end_p/start_p-1:+.1%})')
    print(f'  是否一致: {abs((v1/v0)/(end_p/start_p)-1) < 0.01}')

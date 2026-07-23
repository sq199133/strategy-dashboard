import sys, json, glob
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
MA_S, MA_L  = 5, 21
MAX_DEV      = 10
LB           = 5
SKIP_WEEKS  = {'2024-W01', '2025-W01'}

def load_pool():
    with open(POOL_FILE, encoding='utf-8') as f:
        raw = f.read().replace('NaN', 'null')
    return [e['code'] for e in json.loads(raw)['data']]

def load_weeks(code):
    for pat in (code, f'sh{code}', f'sz{code}'):
        hits = glob.glob(fr'{HISTORY_DIR}\{pat}.json')
        if not hits:
            hits = glob.glob(fr'{HISTORY_DIR}\*{code}*.json')
        if hits:
            try:
                with open(hits[0], encoding='utf-8') as f:
                    raw = f.read().replace('NaN', 'null')
                d    = json.loads(raw)
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
                return {w: cl for w, (ds, cl) in sw if w not in SKIP_WEEKS}
            except: continue
    return None

def calc_momentum(wmap, lb):
    weeks = sorted(wmap.keys())
    closes = [wmap[w] for w in weeks]
    mom = {}
    for i, w in enumerate(weeks):
        if i >= lb:
            mom[w] = closes[i] / closes[i-lb] - 1
    return mom

def backtest_yearly(hist, all_weeks, market_mom=None, market_thresh=None):
    """回测并返回每年收益"""
    weekly_sig = {}
    for code in hist:
        wmap = hist[code]
        weeks = sorted(wmap.keys())
        cs    = [wmap[w] for w in weeks]
        if len(cs) < MA_L + LB: continue
        for i in range(MA_L, len(cs)):
            w = weeks[i]
            if market_mom and w in market_mom and market_thresh is not None:
                if market_mom[w] <= market_thresh:
                    continue
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

    if not weekly_sig:
        return None

    value   = 10000.0
    curve   = []
    prev_top = None
    prev_w   = None
    yearly_vals = {}  # {年份: 年底价值}

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
        curve.append((w, value, len(top3)))
        # 记录每年底价值
        yr = int(w.split('-')[0])
        yearly_vals[yr] = value
        prev_top = top3 if top3 else prev_top
        prev_w   = w

    if not curve: return None
    vals   = [v for w, v, k in curve]
    years  = len(vals)/52.0
    cagr   = (vals[-1]/vals[0])**(1/years)-1 if years>0 and vals[-1]>0 else -0.999
    peak   = vals[0]; max_dd = 0
    for v in vals:
        if v > peak: peak = v
        dd = (peak-v)/peak
        if dd > max_dd: max_dd = dd
    wrets = [vals[i]/vals[i-1]-1 for i in range(1,len(vals))]
    if wrets:
        avg  = sum(wrets)/len(wrets)
        std   = (sum((r-avg)**2 for r in wrets)/len(wrets))**0.5
        sharpe = (avg/std)*(52**0.5) if std>0 else 0
    else: sharpe = 0
    empty_weeks = sum(1 for w, v, k in curve if k == 0)
    return {
        'cagr': cagr, 'dd': max_dd, 'sharpe': sharpe,
        'empty': empty_weeks, 'n': len(curve), 'vals': vals,
        'yearly_vals': yearly_vals, 'curve': curve
    }

print('加载ETF池...')
codes = load_pool()
print(f'  ETF池: {len(codes)} 只')

print('加载历史数据...')
hist = {}
for code in codes:
    wmap = load_weeks(code)
    if wmap: hist[code] = wmap
print(f'  已加载: {len(hist)} 只')

all_weeks = sorted(set().union(*(hist[c].keys() for c in hist)))
print(f'  总周数: {len(all_weeks)}')

hs300_wmap = load_weeks('000300')
hs300_mom  = calc_momentum(hs300_wmap, LB) if hs300_wmap else None
print(f'  沪深300: {len(hs300_wmap)} 周' if hs300_wmap else '  沪深300: 未找到')

r = backtest_yearly(hist, all_weeks, market_mom=hs300_mom, market_thresh=-0.01)
if not r:
    print('  无有效信号')
    sys.exit(1)

print(f'\n{"="*70}')
print(f'  逐年收益明细 (LB=5, 偏离度=10%, 沪深300>-1%)')
print(f'{"="*70}')
print(f'{"年份":<8} {"年初价值":<12} {"年底价值":<12} {"年化收益":<10} {"夏普":<6} {"回撤":<8}')
print(f'{"-"*70}')

years = sorted(r['yearly_vals'].keys())
for i, yr in enumerate(years):
    val_end = r['yearly_vals'][yr]
    val_start = r['yearly_vals'][years[i-1]] if i > 0 else 10000.0
    ann_ret = val_end / val_start - 1
    print(f'  {yr}     {val_start:,.0f}      {val_end:,.0f}      {ann_ret:+.1%}')

print(f'\n{"="*70}')
print(f'  全样本: 年化={r["cagr"]:+.1%}, 夏普={r["sharpe"]:.2f}, 回撤={r["dd"]:+.1%}')
print(f'  总周数: {r["n"]}, 空仓比例: {r["empty"]/r["n"]:.1%}')

# 检查2025年数据
print(f'\n{"="*70}')
print(f'  2025年逐周收益检查')
print(f'{"="*70}')
curve_2025 = [(w, v, k) for w, v, k in r['curve'] if w.startswith('2025')]
if curve_2025:
    print(f'  2025年周数: {len(curve_2025)}')
    print(f'  2025年第一周: {curve_2025[0][0]}, 价值: {curve_2025[0][1]:,.0f}')
    print(f'  2025年最后周: {curve_2025[-1][0]}, 价值: {curve_2025[-1][1]:,.0f}')
    ret_2025 = curve_2025[-1][1] / curve_2025[0][1] - 1
    print(f'  2025年收益: {ret_2025:+.1%}')
else:
    print('  2025年无数据')

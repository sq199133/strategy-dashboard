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

def backtest(hist, all_weeks, market_mom=None, market_thresh=None, start_week=None, end_week=None):
    """回测"""
    weekly_sig = {}
    for code in hist:
        wmap = hist[code]
        weeks = sorted(wmap.keys())
        cs    = [wmap[w] for w in weeks]
        if len(cs) < MA_L + LB: continue
        for i in range(MA_L, len(cs)):
            w = weeks[i]
            if start_week and w < start_week: continue
            if end_week   and w > end_week:   continue
            # 市场状态过滤
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
    for i, w in enumerate(all_weeks):
        if start_week and w < start_week: continue
        if end_week   and w > end_week:   continue
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
    return {'cagr': cagr, 'dd': max_dd, 'sharpe': sharpe, 'empty': empty_weeks, 'n': len(curve), 'vals': vals}

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
print(f'  总周数: {len(all_weeks)} ({all_weeks[0]} ~ {all_weeks[-1]})')

# 加载沪深300
print('\n加载沪深300...')
hs300_wmap = load_weeks('000300')
if hs300_wmap:
    hs300_mom = calc_momentum(hs300_wmap, LB)
    print(f'  沪深300: {len(hs300_wmap)} 周, 动量计算完成')
else:
    hs300_mom = None
    print('  未找到沪深300数据')

# 全样本回测
print(f'\n{"="*70}')
print(f'  全样本回测 (LB=5, 偏离度=10%, G3过滤)')
print(f'{"="*70}')

r_nofilter = backtest(hist, all_weeks)
if r_nofilter:
    print(f'无市场过滤:  年化={r_nofilter["cagr"]:+.1%}  夏普={r_nofilter["sharpe"]:.2f}  回撤={r_nofilter["dd"]:+.1%}  空仓={r_nofilter["empty"]/r_nofilter["n"]:.1%}')

if hs300_mom:
    r_hs300 = backtest(hist, all_weeks, market_mom=hs300_mom, market_thresh=-0.01)
    if r_hs300:
        print(f'沪深300>-1%: 年化={r_hs300["cagr"]:+.1%}  夏普={r_hs300["sharpe"]:.2f}  回撤={r_hs300["dd"]:+.1%}  空仓={r_hs300["empty"]/r_hs300["n"]:.1%}')

# 分时期回测
print(f'\n{"="*70}')
print(f'  分时期回测 (LB=5, 偏离度=10%, 沪深300>-1%)')
print(f'{"="*70}')
print(f'{"时期":<20} {"年化":<8} {"夏普":<6} {"回撤":<8} {"空仓":<8} {"周数":<6}')
print(f'{"-"*70}')

periods = [
    ('2010-2014', '2010-W01', '2014-W52'),
    ('2015-2019', '2015-W01', '2019-W52'),
    ('2020-2024', '2020-W01', '2024-W52'),
    ('2019-2026', '2019-W01', '2026-W52'),
    ('2010-2018', '2010-W01', '2018-W52'),
    ('2019-2026', '2019-W01', '2026-W52'),
]

for label, sw, ew in periods:
    r = backtest(hist, all_weeks, market_mom=hs300_mom, market_thresh=-0.01, start_week=sw, end_week=ew)
    if r:
        print(f'  {label:<18} {r["cagr"]:+.1%}  {r["sharpe"]:.2f}  {r["dd"]:+.1%}  {r["empty"]/r["n"]:.1%}  {r["n"]}')
    else:
        print(f'  {label:<18} 无有效信号')

# 逐年回测
print(f'\n{"="*70}')
print(f'  逐年回测 (LB=5, 偏离度=10%, 沪深300>-1%)')
print(f'{"="*70}')
print(f'{"年份":<8} {"年化":<8} {"夏普":<6} {"回撤":<8} {"空仓":<8} {"周数":<6}')
print(f'{"-"*70}')

years = range(2010, 2027)
for yr in years:
    sw = f'{yr}-W01'
    ew = f'{yr}-W52'
    r = backtest(hist, all_weeks, market_mom=hs300_mom, market_thresh=-0.01, start_week=sw, end_week=ew)
    if r and r['n'] > 10:
        print(f'  {yr}     {r["cagr"]:+.1%}  {r["sharpe"]:.2f}  {r["dd"]:+.1%}  {r["empty"]/r["n"]:.1%}  {r["n"]}')
    elif r:
        print(f'  {yr}     数据不足 ({r["n"]}周)')
    else:
        print(f'  {yr}     无有效信号')

print(f'\n{"="*70}')
print('  完成')

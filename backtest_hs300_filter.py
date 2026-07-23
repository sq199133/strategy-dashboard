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

MARKET_CODES = ['000300', '399006']  # 沪深300、创业板指

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

def load_market_data(codes):
    result = {}
    for code in codes:
        wmap = load_weeks(code)
        if wmap:
            result[code] = wmap
            print(f'  已加载 {code}: {len(wmap)} 周')
        else:
            print(f'  未找到 {code}')
    return result

def backtest_with_filter(hist, all_weeks, market_wmap, market_threshold, label=''):
    """回测"""
    market_mom = {}
    if market_wmap:
        mw = sorted(market_wmap.keys())
        mcs = [market_wmap[w] for w in mw]
        for i, w in enumerate(mw):
            if i >= LB:
                market_mom[w] = mcs[i] / mcs[i-LB] - 1

    weekly_sig = {}
    for code in hist:
        wmap = hist[code]
        weeks = sorted(wmap.keys())
        cs    = [wmap[w] for w in weeks]
        if len(cs) < MA_L + LB: continue
        for i in range(MA_L, len(cs)):
            w = weeks[i]
            if w in market_mom and market_mom[w] <= market_threshold:
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
    tot    = vals[-1]/vals[0] - 1
    years  = len(vals)/52.0
    cagr   = (vals[-1]/vals[0])**(1/years)-1 if years>0 and vals[-1]>0 else -0.999
    peak   = vals[0]
    max_dd = 0
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
    return {'cagr': cagr, 'dd': max_dd, 'sharpe': sharpe, 'empty': empty_weeks, 'n': len(curve)}

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

print('加载市场指数...')
market_data = load_market_data(MARKET_CODES)

thresholds = [-5, -3, -2, -1, 0, 1, 2, 3]

print(f'\n{"="*75}')
print(f'  沪深300 (000300) 市场状态过滤')
print(f'{"="*75}')
print(f'{"阈值":<8} {"年化":<8} {"夏普":<6} {"回撤":<8} {"空仓比例":<10}')
print(f'{"-"*75}')

hs300 = market_data.get('000300')
if not hs300:
    print('  未找到沪深300数据')
else:
    for thresh in thresholds:
        r = backtest_with_filter(hist, all_weeks, hs300, thresh/100, label=f'阈值{thresh:+}%')
        if r:
            print(f'  {thresh:>+4.0f}%  {r["cagr"]:+.1%}  {r["sharpe"]:.2f}  {r["dd"]:+.1%}  {r["empty"]/r["n"]:.1%}')

print(f'\n{"="*75}')
print(f'  创业板指 (399006) 市场状态过滤')
print(f'{"="*75}')
print(f'{"阈值":<8} {"年化":<8} {"夏普":<6} {"回撤":<8} {"空仓比例":<10}')
print(f'{"-"*75}')

cyb = market_data.get('399006')
if not cyb:
    print('  未找到创业板指数据')
else:
    for thresh in thresholds:
        r = backtest_with_filter(hist, all_weeks, cyb, thresh/100, label=f'阈值{thresh:+}%')
        if r:
            print(f'  {thresh:>+4.0f}%  {r["cagr"]:+.1%}  {r["sharpe"]:.2f}  {r["dd"]:+.1%}  {r["empty"]/r["n"]:.1%}')

print(f'\n{"="*75}')
print(f'  无市场状态过滤（对比基准）')
print(f'{"="*75}')
r_nofilter = backtest_with_filter(hist, all_weeks, None, None, label='无过滤')
if r_nofilter:
    print(f'  无过滤  {r_nofilter["cagr"]:+.1%}  {r_nofilter["sharpe"]:.2f}  {r_nofilter["dd"]:+.1%}  {r_nofilter["empty"]/r_nofilter["n"]:.1%}')

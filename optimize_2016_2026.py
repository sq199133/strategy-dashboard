import sys, json, glob
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
MA_S, MA_L  = 5, 21
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

def backtest(hist, all_weeks, LB, MAX_DEV, market_mom=None, market_thresh=None, start_week='2016-W01'):
    weekly_sig = {}
    for code in hist:
        wmap = hist[code]
        weeks = sorted(wmap.keys())
        cs    = [wmap[w] for w in weeks]
        if len(cs) < MA_L + LB: continue
        for i in range(MA_L, len(cs)):
            w = weeks[i]
            if w < start_week: continue
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
        if w < start_week: continue
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

hs300_wmap = load_weeks('000300')
hs300_mom  = calc_momentum(hs300_wmap, 5) if hs300_wmap else None
print(f'  沪深300: {len(hs300_wmap)} 周' if hs300_wmap else '  沪深300: 未找到')

# 全参数扫描 (LB=1~10, 偏离度=5%~20%, 仅2016-2026数据)
print(f'\n{"="*70}')
print(f'  全参数扫描 (2016-2026数据, 沪深300>-1%)')
print(f'{"="*70}')
print(f'{"LB":<4} {"偏离度":<6} {"年化":<8} {"夏普":<6} {"回撤":<8} {"空仓":<8}')
print(f'{"-"*70}')

results = []
for lb in range(1, 11):
    for dev in range(5, 21):
        r = backtest(hist, all_weeks, lb, dev, market_mom=hs300_mom, market_thresh=-0.01, start_week='2016-W01')
        if r:
            results.append((lb, dev, r))
            if r['sharpe'] >= 1.0:  # 只打印夏普>=1.0的
                print(f'  {lb:<4} {dev:<6} {r["cagr"]:+.1%}  {r["sharpe"]:.2f}  {r["dd"]:+.1%}  {r["empty"]/r["n"]:.1%}')

# 最优结果
if results:
    results.sort(key=lambda x: x[2]['sharpe'], reverse=True)
    print(f'\n  Top10 组合（按夏普排序）:')
    print(f'  {"LB":<4} {"偏离度":<6} {"年化":<8} {"夏普":<6} {"回撤":<8} {"空仓":<8}')
    for lb, dev, r in results[:10]:
        print(f'  {lb:<4} {dev:<6} {r["cagr"]:+.1%}  {r["sharpe"]:.2f}  {r["dd"]:+.1%}  {r["empty"]/r["n"]:.1%}')

    best = results[0]
    print(f'\n  最优(2016-2026): LB={best[0]}, 偏离度={best[1]}%')
    print(f'  年化={best[2]["cagr"]:+.1%}, 夏普={best[2]["sharpe"]:.2f}, 回撤={best[2]["dd"]:+.1%}')

    # 对比原参数
    r_old = backtest(hist, all_weeks, 5, 10, market_mom=hs300_mom, market_thresh=-0.01, start_week='2016-W01')
    if r_old:
        print(f'\n  原参数(LB=5, 偏离度=10%)在2016-2026表现:')
        print(f'  年化={r_old["cagr"]:+.1%}, 夏普={r_old["sharpe"]:.2f}, 回撤={r_old["dd"]:+.1%}')

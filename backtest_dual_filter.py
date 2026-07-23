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

MARKET_INDICES = {
    '000300':  '沪深300',
    '513100':  '纳斯达克100ETF'
}

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

def backtest_dual_filter(hist, all_weeks, market_moms, filter_mode, thresh1, thresh2, label=''):
    weekly_sig = {}
    for code in hist:
        wmap = hist[code]
        weeks = sorted(wmap.keys())
        cs    = [wmap[w] for w in weeks]
        if len(cs) < MA_L + LB: continue
        for i in range(MA_L, len(cs)):
            w = weeks[i]
            ok1 = True
            ok2 = True
            # 沪深300过滤
            if thresh1 is not None and '000300' in market_moms and w in market_moms['000300']:
                ok1 = market_moms['000300'][w] > thresh1
            # 纳斯达克过滤
            if thresh2 is not None and '513100' in market_moms and w in market_moms['513100']:
                ok2 = market_moms['513100'][w] > thresh2
            if filter_mode == 'AND':
                if not (ok1 and ok2): continue
            elif filter_mode == 'OR':
                if not (ok1 or ok2): continue
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

print('加载市场指数...')
market_data = {}
for code, name in MARKET_INDICES.items():
    wmap = load_weeks(code)
    if wmap:
        market_data[code] = wmap
        print(f'  {name}({code}): {len(wmap)} 周')
    else:
        print(f'  {name}({code}): 未找到')

market_moms = {}
for code in market_data:
    market_moms[code] = calc_momentum(market_data[code], LB)
    print(f'  {code} 动量计算完成')

# 基准
print(f'\n{"="*70}')
r_base = backtest_dual_filter(hist, all_weeks, {}, 'AND', None, None, label='无过滤')
if r_base:
    print(f'无过滤:  年化={r_base["cagr"]:+.1%}  夏普={r_base["sharpe"]:.2f}  回撤={r_base["dd"]:+.1%}  空仓={r_base["empty"]/r_base["n"]:.1%}')

# 单指数（对比）
print(f'\n--- 单指数过滤（对比）---')
for code in ['000300', '513100']:
    if code in market_moms:
        name = MARKET_INDICES[code]
        for thresh in [-3, -1, 0, 1]:
            if code == '000300':
                r = backtest_dual_filter(hist, all_weeks, market_moms, 'AND', thresh/100, None, label=f'{name}')
            else:
                r = backtest_dual_filter(hist, all_weeks, market_moms, 'AND', None, thresh/100, label=f'{name}')
            if r:
                print(f'  {name} {thresh:+}%: 年化={r["cagr"]:+.1%}  夏普={r["sharpe"]:.2f}  回撤={r["dd"]:+.1%}  空仓={r["empty"]/r["n"]:.1%}')

# 双指数 AND 模式
print(f'\n{"="*70}')
print(f'  双指数过滤 AND 模式（沪深300 AND 纳斯达克都通过才买入）')
print(f'{"="*70}')
print(f'{"HS300":<8} {"NDX":<8} {"年化":<8} {"夏普":<6} {"回撤":<8} {"空仓":<8}')
print(f'{"-"*70}')

results_and = []
thresholds = [-5, -3, -1, 0, 1, 2]
for t1 in thresholds:
    for t2 in thresholds:
        r = backtest_dual_filter(hist, all_weeks, market_moms, 'AND', t1/100, t2/100, label='')
        if r:
            results_and.append((t1, t2, r))
            print(f'  {t1:>+4.0f}%  {t2:>+4.0f}%  {r["cagr"]:+.1%}  {r["sharpe"]:.2f}  {r["dd"]:+.1%}  {r["empty"]/r["n"]:.1%}')

# 双指数 OR 模式
print(f'\n{"="*70}')
print(f'  双指数过滤 OR 模式（沪深300 OR 纳斯达克任一个通过就买入）')
print(f'{"="*70}')
print(f'{"HS300":<8} {"NDX":<8} {"年化":<8} {"夏普":<6} {"回撤":<8} {"空仓":<8}')
print(f'{"-"*70}')

results_or = []
for t1 in thresholds:
    for t2 in thresholds:
        r = backtest_dual_filter(hist, all_weeks, market_moms, 'OR', t1/100, t2/100, label='')
        if r:
            results_or.append((t1, t2, r))
            print(f'  {t1:>+4.0f}%  {t2:>+4.0f}%  {r["cagr"]:+.1%}  {r["sharpe"]:.2f}  {r["dd"]:+.1%}  {r["empty"]/r["n"]:.1%}')

# 汇总最优
print(f'\n{"="*70}')
print(f'  综合排名 Top10（按夏普）')
print(f'{"="*70}')
all_results = [(t1,t2,'AND',r) for t1,t2,r in results_and] + [(t1,t2,'OR',r) for t1,t2,r in results_or]
all_results.sort(key=lambda x: x[3]['sharpe'], reverse=True)
print(f'  {"模式":<4} {"HS300":<8} {"NDX":<8} {"年化":<8} {"夏普":<6} {"回撤":<8} {"空仓":<8}')
print(f'  {"-"*60}')
for t1, t2, mode, r in all_results[:10]:
    print(f'  {mode:<4} {t1:>+4.0f}%  {t2:>+4.0f}%  {r["cagr"]:+.1%}  {r["sharpe"]:.2f}  {r["dd"]:+.1%}  {r["empty"]/r["n"]:.1%}')

best = all_results[0]
print(f'\n  最优: 模式={best[2]}, 沪深300>{best[0]:+}%, 纳斯达克>{best[1]:+}%')
print(f'  年化={best[3]["cagr"]:+.1%}, 夏普={best[3]["sharpe"]:.2f}, 回撤={best[3]["dd"]:+.1%}, 空仓={best[3]["empty"]/best[3]["n"]:.1%}')

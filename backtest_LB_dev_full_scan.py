import sys, json, glob
from datetime import datetime
from itertools import product

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
MA_S         = 5
MA_L         = 21
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

def backtest(lb, max_dev, hist, all_weeks):
    """回测单个参数组合，修正前视偏差"""
    weekly_sig = {}
    for code in hist:
        wmap = hist[code]
        weeks = sorted(wmap.keys())
        cs    = [wmap[w] for w in weeks]
        if len(cs) < MA_L + lb: continue
        for i in range(MA_L, len(cs)):
            w = weeks[i]
            price = cs[i]
            ma_s  = sum(cs[i-MA_S+1:i+1]) / MA_S
            ma_l  = sum(cs[i-MA_L+1:i+1]) / MA_L
            dev   = price / ma_l - 1
            mom   = cs[i] / cs[i-lb] - 1
            if mom <= 0: continue
            if not (price > ma_s > ma_l): continue
            if dev > max_dev/100: continue
            # G3过滤
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

        curve.append(value)
        prev_top = top3 if top3 else prev_top
        prev_w   = w

    if not curve or curve[0] == 0: return None
    vals   = curve
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
    return {'cagr': cagr, 'dd': max_dd, 'sharpe': sharpe, 'tot': tot}

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

# 参数网格
lb_range    = range(1, 22)          # LB=1~21
dev_range    = range(5, 21, 1)      # 偏离度5%~20%
total_combo = len(lb_range) * len(dev_range)
print(f'\n参数扫描: LB={list(lb_range)}, 偏离度={list(dev_range)}%')
print(f'  总组合数: {total_combo}')
print(f'  开始回测...\n')

results = []
for lb in lb_range:
    for dev in dev_range:
        r = backtest(lb, dev, hist, all_weeks)
        if r:
            results.append((lb, dev, r))
    # 每完成一个LB，打印进度
    print(f'  LB={lb:2d} 完成 ({lb}/{len(lb_range)})')

# 按夏普排序
results.sort(key=lambda x: x[2]['sharpe'], reverse=True)

print(f'\n{"="*70}')
print(f'  最优10组参数（按夏普排序）')
print(f'{"="*70}')
print(f'{"排名":<4} {"LB":<4} {"偏离度":<6} {"年化":<8} {"夏普":<6} {"回撤":<8}')
print(f'{"-"*70}')
for i, (lb, dev, r) in enumerate(results[:10]):
    print(f'{i+1:<4} {lb:<4} {dev:<6} {r["cagr"]:+.1%} {r["sharpe"]:.2f} {r["dd"]:+.1%}')

# 保存结果
import pickle
with open(r'D:\QClaw_Trading\backtest_LB_dev_scan.pkl', 'wb') as f:
    pickle.dump(results, f)
print(f'\n结果已保存: backtest_LB_dev_scan.pkl')

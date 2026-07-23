import sys, json, glob
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
MA_S, MA_L  = 5, 21
MAX_DEV      = 15
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
                # 返回 {week: close}，过滤跳过周
                return {w: cl for w, (ds, cl) in sw if w not in SKIP_WEEKS}
            except: continue
    return None

def backtest(lb, label):
    codes = load_pool()
    print(f'\n{"="*60}')
    print(f'  {label}  LB={lb}')
    print(f'{"="*60}')

    # 加载历史
    hist = {}
    for code in codes:
        wmap = load_weeks(code)
        if wmap: hist[code] = wmap
    print(f'  已加载 {len(hist)} 只ETF')

    # 所有周（排序）
    all_weeks = sorted(set().union(*(hist[c].keys() for c in hist)))
    print(f'  总周数: {len(all_weeks)}')

    # 第1步：为每周围术pass的ETF列表  (week -> [(code, mom)])
    weekly_sig = {}
    for code in hist:
        wmap = hist[code]
        weeks = sorted(wmap.keys())
        cs    = [wmap[w] for w in weeks]
        for i in range(MA_L, len(cs)):
            w = weeks[i]
            price = cs[i]
            ma_s  = sum(cs[i-MA_S+1:i+1]) / MA_S
            ma_l  = sum(cs[i-MA_L+1:i+1]) / MA_L
            dev   = price / ma_l - 1
            mom   = cs[i] / cs[i-lb] - 1
            if mom <= 0: continue
            if not (price > ma_s > ma_l): continue
            if dev > MAX_DEV/100: continue
            g3 = True
            if i >= 1 and cs[i]/cs[i-1]-1 < -0.01: g3 = False
            if mom <= 0: g3 = False
            if g3:
                weekly_sig.setdefault(w, []).append((code, mom))

    if not weekly_sig:
        print('  无信号'); return None

    # 第2步：回测——周末算信号，下周调仓吃收益
    value   = 10000.0
    curve   = []       # [(week, value)]
    prev_top = None    # 上一周末的top3

    for i, w in enumerate(all_weeks):
        # 本周有无信号
        sig = weekly_sig.get(w)
        top3 = [c for c, m in sorted(sig, key=lambda x: x[1], reverse=True)[:3]] if sig else []

        if prev_top and len(prev_top) == 3:
            # 用本周收益率更新市值（上周末调仓，持有一周）
            rets = []
            for c in prev_top:
                if c in hist and w in hist[c] and prev_w in hist[c]:
                    r = hist[c][w] / hist[c][prev_w] - 1
                    rets.append(r)
            if rets:
                ret = sum(rets) / len(rets)
                value *= (1 + ret)

        curve.append((w, value, len(top3) if top3 else 0))

        # 为下周准备
        prev_top = top3 if top3 else prev_top
        prev_w   = w

    if not curve: return None
    vals   = [v for w, v, k in curve]
    tot    = vals[-1]/vals[0] - 1 if vals[0] != 0 else -1
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
        std  = (sum((r-avg)**2 for r in wrets)/len(wrets))**0.5
        sharpe = (avg/std)*(52**0.5) if std>0 else 0
    else: sharpe = 0

    print(f'  期末:   {vals[-1]:,.0f}')
    print(f'  总收益: {tot:+.1%}')
    print(f'  年化:   {cagr:+.1%}')
    print(f'  最大回撤: {max_dd:+.1%}')
    print(f'  夏普:   {sharpe:.2f}')
    print(f'  信号周数: {sum(1 for w,v,k in curve if k>0)}')
    return {'cagr': cagr, 'dd': max_dd, 'sharpe': sharpe}

print('回测开始（修正前视偏差）...\n')
rA = backtest(3, 'A方案  LB=3 (跨度2周)')
rB = backtest(4, 'B方案  LB=4 (跨度3周)')

print(f'\n{"="*60}')
print('  对比')
print(f'{"="*60}')
if rA and rB:
    print(f'  A(LB=3):  年化={rA["cagr"]:+.1%}  夏普={rA["sharpe"]:.2f}  回撤={rA["dd"]:+.1%}')
    print(f'  B(LB=4):  年化={rB["cagr"]:+.1%}  夏普={rB["sharpe"]:.2f}  回撤={rB["dd"]:+.1%}')
    w = 'A' if rA['sharpe']>rB['sharpe'] else 'B'
    print(f'\n  >>> {w}方案更优')

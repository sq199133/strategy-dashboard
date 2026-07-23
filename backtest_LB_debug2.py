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
                # 返回 {week: close}，同时过滤跳过周
                cleaned = {w: cl for w, (ds, cl) in sorted(wmap.items()) if w not in SKIP_WEEKS}
                return cleaned
            except: continue
    return None

def backtest(lb, label, debug=False):
    codes = load_pool()
    print(f'\n{"="*60}')
    print(f'  {label}  LB={lb}')
    print(f'{"="*60}')

    hist = {}
    for code in codes:
        wmap = load_weeks(code)
        if wmap: hist[code] = wmap
    print(f'  已加载 {len(hist)} 只ETF')

    # 收集所有周
    all_weeks = set()
    for code in hist:
        all_weeks.update(hist[code].keys())
    all_weeks = sorted(all_weeks - SKIP_WEEKS)

    value = 10000.0
    curve = []

    for i, w in enumerate(all_weeks):
        sig = []
        for code in hist:
            wmap = hist[code]
            weeks = sorted(wmap.keys())
            if w not in wmap: continue
            idx = weeks.index(w)
            if idx < MA_L + lb: continue
            cs = [wmap[wk] for wk in weeks]
            price = cs[idx]
            ma_s  = sum(cs[idx-MA_S+1:idx+1]) / MA_S
            ma_l  = sum(cs[idx-MA_L+1:idx+1]) / MA_L
            dev   = price / ma_l - 1
            mom   = cs[idx] / cs[idx-lb] - 1
            if mom <= 0: continue
            if not (price > ma_s > ma_l): continue
            if dev > MAX_DEV/100: continue
            g3 = True
            if idx >= 1 and cs[idx]/cs[idx-1]-1 < -0.01: g3 = False
            if mom <= 0: g3 = False
            if g3:
                sig.append((code, mom))

        if not sig:
            ret = 0.0
        else:
            sig.sort(key=lambda x: x[1], reverse=True)
            top3 = [c for c, m in sig[:3]]
            rets = []
            for c in top3:
                wmap = hist[c]
                weeks = sorted(wmap.keys())
                idx = weeks.index(w)
                if idx >= 1:
                    r = wmap[w] / wmap[weeks[idx-1]] - 1
                    rets.append(r)
            ret = sum(rets)/len(rets) if rets else 0.0

        value *= (1 + ret)
        curve.append((w, value, ret))

        if debug and i < 10:
            print(f'  wk[{i}] {w}: ret={ret:+.2%}, val={value:,.0f}')

        # debug: 找第一次爆炸
        if debug and value > 100000 and len([v for v in curve if v[1] > 100000]) == 1:
            print(f'  *** 爆炸发生在 wk[{i}] {w}: val={value:,.0f}, ret={ret:+.2%}')
            # 打印top3
            sig.sort(key=lambda x: x[1], reverse=True)
            top3 = [c for c, m in sig[:3]]
            print(f'    top3={top3}')
            for c in top3:
                wmap = hist[c]
                weeks = sorted(wmap.keys())
                idx2 = weeks.index(w)
                print(f'    {c}: w={wmap[w]:.4f}, w-1={wmap[weeks[idx2-1]]:.4f}, ret={(wmap[w]/wmap[weeks[idx2-1]]-1):+.2%}')

    if not curve: return None
    vals   = [v for w, v, r in curve]
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
        std  = (sum((r-avg)**2 for r in wrets)/len(wrets))**0.5
        sharpe = (avg/std)*(52**0.5) if std>0 else 0
    else: sharpe = 0

    print(f'  期末:   {vals[-1]:,.0f}')
    print(f'  总收益: {tot:+.1%}')
    print(f'  年化:   {cagr:+.1%}')
    print(f'  最大回撤: {max_dd:+.1%}')
    print(f'  夏普:   {sharpe:.2f}')
    print(f'  周数:   {len(vals)}')
    if debug:
        print(f'\n  最后10周:')
        for w, v, r in curve[-10:]:
            print(f'    {w}: ret={r:+.2%}, val={v:,.0f}')
    return {'cagr': cagr, 'dd': max_dd, 'sharpe': sharpe}

print('回测开始（debug前10周）...\n')
rA = backtest(3, 'A方案  LB=3', debug=True)
print('\n\n再跑B方案（不debug）...\n')
rB = backtest(4, 'B方案  LB=4', debug=False)

print(f'\n{"="*60}')
print('  对比')
print(f'{"="*60}')
if rA and rB:
    print(f'  A(LB=3):  年化={rA["cagr"]:+.1%}  夏普={rA["sharpe"]:.2f}  回撤={rA["dd"]:+.1%}')
    print(f'  B(LB=4):  年化={rB["cagr"]:+.1%}  夏普={rB["sharpe"]:.2f}  回撤={rB["dd"]:+.1%}')
    w = 'A' if rA['sharpe']>rB['sharpe'] else 'B'
    print(f'\n  >>> {w}方案更优')

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
                closes  = [cl for w, (ds, cl) in sw]
                weekids = [w  for w, _        in sw]
                return closes, weekids
            except: continue
    return None, None

def backtest(lb, label):
    codes = load_pool()
    print(f'\n{"="*60}')
    print(f'  {label}  LB={lb}')
    print(f'{"="*60}')

    # weekly[week] = [(code, mom, price)]
    weekly = {}
    for code in codes:
        cs, ws = load_weeks(code)
        if not cs or len(cs) < MA_L + lb: continue
        for i in range(MA_L, len(cs)):
            w = ws[i]
            if w in SKIP_WEEKS: continue
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
                weekly.setdefault(w, []).append((code, mom, price))

    if not weekly:
        print('  无信号'); return None

    sorted_weeks = sorted(weekly.keys())
    cash   = 10000.0
    shares = {}    # code -> num_shares
    curve  = []    # [(week, value)]
    stats  = []    # 每周围术数

    for w in sorted_weeks:
        sig   = sorted(weekly[w], key=lambda x: x[1], reverse=True)
        k     = min(3, len(sig))      # 实际买入数量
        target = sig[:k]
        px     = {x[0]: x[2] for x in sig}

        # 当前市值
        val = cash + sum(shares.get(c, 0) * px.get(c, 0) for c in shares)
        curve.append((w, val))

        # 全卖出
        for c in list(shares.keys()):
            if c in px:
                cash += shares[c] * px[c]
            del shares[c]

        # 等权买入 k 只
        if cash > 0 and target:
            alloc = cash / k
            for c, mom, price in target:
                n = int(alloc / price)
                if n > 0:
                    shares[c] = n
                    cash -= n * price
            stats.append(k)

    if not curve: return None
    vals   = [v for w, v in curve]
    tot    = vals[-1]/vals[0] - 1
    years  = len(vals)/52.0
    cagr   = (vals[-1]/vals[0])**(1/years)-1 if years>0 and vals[-1]>0 else -0.999
    peak   = vals[0]
    max_dd = 0
    for v in vals:
        if v > peak: peak = v
        dd = (peak-v)/peak
        if dd > max_dd: max_dd = dd
    rets = [vals[i]/vals[i-1]-1 for i in range(1,len(vals))]
    if rets:
        avg  = sum(rets)/len(rets)
        std  = (sum((r-avg)**2 for r in rets)/len(rets))**0.5
        sharpe = (avg/std)*(52**0.5) if std>0 else 0
    else: sharpe = 0

    avg_k = sum(stats)/len(stats) if stats else 0
    print(f'  期末:     {vals[-1]:,.0f}')
    print(f'  总收益:   {tot:+.1%}')
    print(f'  年化:     {cagr:+.1%}')
    print(f'  最大回撤: {max_dd:+.1%}')
    print(f'  夏普:     {sharpe:.2f}')
    print(f'  信号周数: {len(vals)}')
    print(f'  平均持仓数: {avg_k:.1f}')
    return {'cagr': cagr, 'dd': max_dd, 'sharpe': sharpe}

print('回测开始...\n')
rA = backtest(3, 'A方案  LB=3 (本周/上上周, 跨度2周)')
rB = backtest(4, 'B方案  LB=4 (本周/三周前, 跨度3周)')

print(f'\n{"="*60}')
print('  对比')
print(f'{"="*60}')
if rA and rB:
    print(f'  A(LB=3):  年化={rA["cagr"]:+.1%}  夏普={rA["sharpe"]:.2f}  回撤={rA["dd"]:+.1%}')
    print(f'  B(LB=4):  年化={rB["cagr"]:+.1%}  夏普={rB["sharpe"]:.2f}  回撤={rB["dd"]:+.1%}')
    w = 'A' if rA['sharpe']>rB['sharpe'] else 'B'
    print(f'\n  >>> {w}方案更优')

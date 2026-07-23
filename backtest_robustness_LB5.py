import sys, json, glob
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long'
POOL_FILE   = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
MA_S, MA_L  = 5, 21
MAX_DEV      = 10   # 偏离度10%
LB           = 5    # 最优LB
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

def backtest_with_timing(hist, all_weeks, start_w=None, end_w=None, label='全样本'):
    """回测（修正前视偏差）"""
    weekly_sig = {}
    for code in hist:
        wmap = hist[code]
        weeks = sorted(wmap.keys())
        cs    = [wmap[w] for w in weeks]
        if len(cs) < MA_L + LB: continue
        for i in range(MA_L, len(cs)):
            w = weeks[i]
            if start_w and w < start_w: continue
            if end_w   and w > end_w:   continue
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
        print(f'  [{label}] 无信号'); return None

    value   = 10000.0
    curve   = []   # [(week, value, hold_count)]
    prev_top = None
    prev_w   = None

    for i, w in enumerate(all_weeks):
        if start_w and w < start_w: continue
        if end_w   and w > end_w:   continue

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
    weeks  = [w for w, v, k in curve]
    tot    = vals[-1]/vals[0] - 1
    n_weeks = len(vals)
    years  = n_weeks / 52.0
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

    # 逐年收益
    yearly = {}
    for w, v, k in curve:
        yr = w[:4]
        yearly[yr] = v
    yearly_ret = {}
    for yr in sorted(yearly.keys()):
        if yr in yearly_ret: continue
        vals_yr = [v for w, v, k in curve if w.startswith(yr)]
        if len(vals_yr) >= 2:
            yearly_ret[yr] = vals_yr[-1]/vals_yr[0] - 1

    print(f'\n{"="*60}')
    print(f'  [{label}]  LB={LB}  偏离度={MAX_DEV}%')
    print(f'{"="*60}')
    print(f'  区间: {weeks[0]} -> {weeks[-1]}  ({n_weeks}周, {years:.1f}年)')
    print(f'  期末:   {vals[-1]:,.0f}')
    print(f'  总收益: {tot:+.1%}')
    print(f'  年化:   {cagr:+.1%}')
    print(f'  最大回撤: {max_dd:+.1%}')
    print(f'  夏普:   {sharpe:.2f}')

    if yearly_ret:
        print(f'\n  逐年收益:')
        for yr in sorted(yearly_ret.keys()):
            print(f'    {yr}: {yearly_ret[yr]:+.1%}')

    return {'cagr': cagr, 'dd': max_dd, 'sharpe': sharpe, 'yearly': yearly_ret}

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

# 1. 全样本回测
r_full = backtest_with_timing(hist, all_weeks, label='全样本')

# 2. 样本外回测（2019-2026，最后7年）
r_oos = backtest_with_timing(hist, all_weeks, start_w='2019-W01', label='样本外(2019-2026)')

# 3. 样本内回测（2010-2018，前9年）
r_is = backtest_with_timing(hist, all_weeks, end_w='2018-W52', label='样本内(2010-2018)')

# 4. 滚动回测（每3年）
print(f'\n{"="*60}')
print('  滚动回测（每3年）')
print(f'{"="*60}')
for start_yr in range(2010, 2024, 3):
    end_yr = start_yr + 2
    s_w = f'{start_yr}-W01'
    e_w = f'{end_yr}-W52'
    r = backtest_with_timing(hist, all_weeks, start_w=s_w, end_w=e_w, label=f'{start_yr}-{end_yr}')

print(f'\n{"="*60}')
print('  对比总结')
print(f'{"="*60}')
if r_full:
    print(f'  全样本:   年化={r_full["cagr"]:+.1%}  夏普={r_full["sharpe"]:.2f}  回撤={r_full["dd"]:+.1%}')
if r_is:
    print(f'  样本内:   年化={r_is["cagr"]:+.1%}  夏普={r_is["sharpe"]:.2f}  回撤={r_is["dd"]:+.1%}')
if r_oos:
    print(f'  样本外:   年化={r_oos["cagr"]:+.1%}  夏普={r_oos["sharpe"]:.2f}  回撤={r_oos["dd"]:+.1%}')

# 保存结果
import pickle
with open(r'D:\QClaw_Trading\backtest_robustness_LB5_dev10.pkl', 'wb') as f:
    pickle.dump({'full': r_full, 'is': r_is, 'oos': r_oos}, f)
print(f'\n结果已保存: backtest_robustness_LB5_dev10.pkl')

import json, glob, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

results_dir = r'D:\Qclaw_Trading\backtest_results'
files = sorted(glob.glob(results_dir + r'\bt_v5_*_20260615_0009*.json'))

rows = []
for fp in files:
    d = json.load(open(fp, encoding='utf-8'))
    name = fp.split('_v5_')[1].rsplit('_202',1)[0]
    s = d['stats']
    
    # Compute 2026 from equity
    eq = d['equity']
    eq2026 = [e for e in eq if e['w'].startswith('2026-')]
    y2026_ret = (eq2026[-1]['eq'] / eq2026[0]['eq'] - 1) * 100 if eq2026 else 0
    
    # Compute 2026 max drawdown within the year
    peak = eq2026[0]['eq']
    y2026_dd = 0
    for e in eq2026:
        if e['eq'] > peak: peak = e['eq']
        dd = (e['eq'] / peak - 1)
        if dd < y2026_dd: y2026_dd = dd
    
    # Also try to extract year data from equity
    years_ret = {}
    by_year = defaultdict(list)
    for e in eq:
        yy = e['w'][:4]
        by_year[yy].append(e['eq'])
    
    for yy, vals in sorted(by_year.items()):
        if len(vals) > 1:
            years_ret[yy] = (vals[-1] / vals[0] - 1) * 100
    
    rows.append({
        'name': name,
        'ann': s['ann_ret'],
        'dd': s['max_dd'] * 100,
        'sharpe': s['sharpe'],
        'calmar': s.get('calmar', s['ann_ret']/(s['max_dd']*100+1e-10)),
        'total': s['total_ret'],
        'winrate': s['win_rate'],
        'trades': s.get('n_buys', 0) + s.get('n_sells', 0) // 2,
        'y2026': y2026_ret,
        'y2026dd': y2026_dd * -100,
    })

rows.sort(key=lambda r: r['sharpe'], reverse=True)

print(f"{'配置':<30} {'年化':>6} {'回撤':>7} {'夏普':>6} {'卡尔玛':>6} {'累计':>8} {'胜率':>5} {'2026':>7} {'2026DD':>7}")
print(f"{'-'*82}")
for r in rows:
    print(f"{r['name']:<30} {r['ann']:>+5.1f}% {r['dd']:>6.1f}% {r['sharpe']:>5.2f} {r['calmar']:>5.2f} {r['total']:>+6.1f}% {r['winrate']:>4.1f}% {r['y2026']:>+6.1f}% {r['y2026dd']:>6.1f}%")

print("\n\n=== 逐年收益对比 ===")
for r in rows:
    print(f"\n【{r['name']}】")
    d = json.load(open(files[[i for i,fn in enumerate(files) if r['name'] in fn][0]], encoding='utf-8'))
    eq = d['equity']
    by_yr = defaultdict(list)
    for e in eq:
        by_yr[e['w'][:4]].append(e['eq'])
    for yy in sorted(by_yr):
        vals = by_yr[yy]
        ret = (vals[-1]/vals[0]-1)*100 if len(vals)>1 else 0
        print(f"  {yy}: {ret:+.1f}%")

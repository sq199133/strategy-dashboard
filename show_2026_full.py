import json, statistics, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = json.load(open(r'D:\Qclaw_Trading\backtest_results\bt_v5_none_20260615_000631.json', encoding='utf-8'))
pool = json.load(open(r'D:\Qclaw_Trading\data\etf_pool_V1_full.json', encoding='utf-8'))
name_map = {}
for e in pool.get('data', pool):
    name_map[e['code']] = e.get('name', '')

eq = d['equity']
eq2026 = [e for e in eq if e['w'].startswith('2026-')]

print(f"{'Week':<10} {'NAV':>10} {'WkRet':>8} {'Holds'}")
print(f"{'-'*90}")

prev = None
for e in eq2026:
    ret = (e['eq'] / prev - 1) * 100 if prev and prev > 0 else 0
    holds = ', '.join(f"{c}" + (f"({name_map.get(c,'')[:10]})" if name_map.get(c) else "") for c in e.get('h',[]))
    if not holds: holds = '(空仓)'
    print(f"{e['w']:<10} {e['eq']:>10.4f} {ret:>+7.2f}% {holds}")
    prev = e['eq']

print(f"\n2026 total: {(eq2026[-1]['eq']/eq2026[0]['eq']-1)*100:+.2f}%")
print(f"Weeks covered: {len(eq2026)}")

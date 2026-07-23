import json, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

d = json.load(open(r'D:\QClaw_Trading\backtest_results\bt_v5_none_20260615_000006.json'))

# Build code->name map
pool = json.load(open(r'D:\Qclaw_Trading\data\etf_pool_V1_full.json', encoding='utf-8'))
name_map = {}
for e in pool.get('data', pool):
    name_map[e['code']] = e.get('name', '')

eq = d['equity']
eq2026 = [e for e in eq if e['w'].startswith('2026-')]

print(f"{'Week':<10} {'NAV':>10} {'WkRet':>8} {'Holds'}")
print(f"{'-'*80}")

prev_eq = None
for e in eq2026:
    ret = (e['eq'] / prev_eq - 1) * 100 if prev_eq and prev_eq > 0 else 0
    holds = ', '.join(f"{c}({name_map.get(c,'').replace('交易型开放式指数证券投资基金','ETF')[:8]})" for c in e.get('h',[]))
    if not holds:
        holds = '(空仓)'
    nav_str = f"{e['eq']:.4f}"
    ret_str = f"{ret:>+7.2f}%" if prev_eq else "---"
    print(f"{e['w']:<10} {nav_str:>10} {ret_str:>8} {holds}")
    prev_eq = e['eq']

total_ret = (eq2026[-1]['eq'] / eq2026[0]['eq'] - 1) * 100 if len(eq2026) >= 2 else 0
print(f"\n2026 total: {total_ret:+.2f}%")

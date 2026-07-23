"""Show 2026 weekly equity and holdings from backtest JSON"""
import json

d = json.load(open(r'D:\Qclaw_Trading\backtest_results\bt_v5_none_20260615_201736.json', encoding='utf-8'))
e = d['equity']
eqs = [x for x in e if x['w'].startswith('2026')]
w52 = [x for x in e if x['w'] == '2025-W52'][0]

prev_eq = w52['eq']
print(f'Week       Ret%    CumEq   Holdings')
print(f'---2025-W52   --     {prev_eq:.4f}')
print('-' * 55)

for x in eqs:
    w = x['w']
    ret = (x['eq'] / prev_eq - 1) * 100
    prev_eq = x['eq']
    h = ','.join(x['h'])
    print(f'{w}  {ret:>+7.2f}%  {x["eq"]:>7.4f}  [{h}]')

start_eq = w52['eq']
end_eq = eqs[-1]['eq']
total_ret = (end_eq / start_eq - 1) * 100

peak = start_eq
max_dd = 0
for x in eqs:
    if x['eq'] > peak:
        peak = x['eq']
    dd = (x['eq'] / peak - 1) * 100
    if dd < max_dd:
        max_dd = dd

print('-' * 55)
print(f'YTD: {total_ret:+.2f}%,  MaxDD: {max_dd:.1f}%,  Weeks: {len(eqs)} (W02-W25)')

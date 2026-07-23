import json, os

# Find the most recent none JSON
bt_dir = r'D:\Qclaw_Trading\backtest_results'
files = [os.path.join(bt_dir, f) for f in os.listdir(bt_dir) if f.startswith('bt_v5_none')]
newest = max(files, key=os.path.getmtime)

d = json.load(open(newest, encoding='utf-8'))
st = d['stats']
years = d.get('yearly', [])

print(f"Baseline: ann={st['ann_ret']:+.1f}% DD={st['max_dd']*100:.1f}% Sharpe={st['sharpe']:.2f} Total={st['total_ret']:+.1f}%")
print()
print("Yearly:")
print(f"  {'Year':<6} {'Return':>8} {'DD':>8} {'Hold%':>7}")
print(f"  {'-'*31}")
for y in years:
    ret = y.get('ret', 0)*100 if abs(y.get('ret',0)) < 1 else y.get('ret', 0)
    dd = y.get('dd', 0)*100 if abs(y.get('dd',0)) < 1 else y.get('dd', 0)
    hp = y.get('hold_pct', 0)*100 if abs(y.get('hold_pct',0)) < 1 else y.get('hold_pct', 0)
    name = y.get('year', y.get('name', ''))
    print(f"  {name:<6} {ret:>+7.1f}% {dd:>7.1f}% {hp:>6.0f}%")

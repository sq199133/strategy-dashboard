import json

d = json.load(open(r'D:\Qclaw_Trading\backtest_results\bt_v5_none_20260614_235711.json'))
eq = d['equity']

# Find 2026 entries
eq2026 = [e for e in eq if e['w'].startswith('2026-')]
print(f"2026 entries: {len(eq2026)}")

# compute weekly returns
prev = None
total = 1.0
data = []

for e in eq2026:
    if prev is not None:
        ret = (e['eq'] / prev - 1) * 100
    else:
        ret = 0
    data.append((e['w'], e['eq'], ret, 'NH' if e.get('nh') else ''))
    prev = e['eq']

# print header
print(f"{'Week':<10} {'NAV':>10} {'WkRet':>8} {'Held'}")
print(f"{'-'*40}")

for w, nav, ret, flag in data:
    held = ''
    wnum = int(w.split('-W')[1])
    print(f"{w:<10} {nav:>10.4f} {ret:>+7.2f}% {held}")

print(f"\n2026 total: {(data[-1][1]/data[0][1]-1)*100:+.2f}%")

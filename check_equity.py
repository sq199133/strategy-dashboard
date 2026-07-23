import json

d = json.load(open(r'D:\Qclaw_Trading\backtest_results\bt_v5_none_20260614_235711.json'))
eq = d['equity']

# eq is a list of [week, price, ...] or similar
print(f"Total entries: {len(eq)}")
print(f"First 3: {eq[:3]}")
print(f"Last 3: {eq[-3:]}")
print(f"One item type: {type(eq[0])}")

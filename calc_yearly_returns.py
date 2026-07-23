import json
from datetime import datetime

# Load backtest result
with open(r'D:\QClaw_Trading\backtest_results\bt_v4_2_5_21_3_10_2_20260613_160256.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

equity = data['equity']

# Group by year
year_data = {}
for rec in equity:
    w = rec['w']  # e.g., "2010-W02"
    year = int(w.split('-W')[0])
    eq = rec['eq']
    
    if year not in year_data:
        year_data[year] = {'weeks': [], 'eqs': []}
    year_data[year]['weeks'].append(w)
    year_data[year]['eqs'].append(eq)

# Calculate yearly returns
print(f"{'Year':<6} {'Start':<12} {'End':<12} {'Return':<10} {'Weeks':<6}")
print("-" * 60)

results = []
for year in sorted(year_data.keys()):
    eqs = year_data[year]['eqs']
    start_eq = eqs[0]
    end_eq = eqs[-1]
    ret = (end_eq / start_eq - 1) * 100
    weeks = len(eqs)
    
    results.append({
        'year': year,
        'start': year_data[year]['weeks'][0],
        'end': year_data[year]['weeks'][-1],
        'return': ret,
        'weeks': weeks
    })
    
    print(f"{year:<6} {year_data[year]['weeks'][0]:<12} {year_data[year]['weeks'][-1]:<12} {ret:>+8.2f}%  {weeks:<6}")

# Calculate annualized return for each year
print("\n" + "=" * 60)
print("Annualized Returns (simple yearly return, not annualized)")
print("=" * 60)
print(f"\nTotal years: {len(results)}")
print(f"Best year: {max(results, key=lambda x: x['return'])['year']} ({max(results, key=lambda x: x['return'])['return']:+.2f}%)")
print(f"Worst year: {min(results, key=lambda x: x['return'])['year']} ({min(results, key=lambda x: x['return'])['return']:+.2f}%)")
print(f"Average yearly return: {sum(r['return'] for r in results) / len(results):+.2f}%")

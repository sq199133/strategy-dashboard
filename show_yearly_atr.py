"""Show yearly returns from ATR 0.85 backtest JSON"""
import json

d = json.load(open(r'D:\Qclaw_Trading\backtest_results\bt_v5_none_20260615_201736.json', encoding='utf-8'))
e = d['equity']

# Group by year, find first and last week of each year
years = {}
for x in e:
    year = x['w'].split('-W')[0]
    if year not in years:
        years[year] = {'first': x, 'last': x}
    else:
        if x['w'] < years[year]['first']['w']:
            years[year]['first'] = x
        if x['w'] > years[year]['last']['w']:
            years[year]['last'] = x

# For each year, return = last_eq / first_eq_of_year - 1
# The "first_eq_of_year" needs the last week of previous year for proper calculation
sorted_years = sorted(years.keys())

# Get annual returns properly: use prev_year's last eq as base
prev_last = None
print(f'{"Year":>6}  {"Ann. Ret":>9}  {"CumEq":>8}  {"Weeks":>5}')
print('-' * 35)
for yr in sorted_years:
    d = years[yr]
    if prev_last is None:
        ret = 0
    else:
        ret = (d['first']['eq'] / prev_last - 1) * 100
    
    # Compute full-year return from first eq after prev year to last eq
    first_val = d['first']['eq']
    last_val = d['last']['eq']
    year_ret = (last_val / first_val - 1) * 100
    
    print(f'{yr:>6}  {year_ret:>+8.2f}%  {last_val:>8.4f}  {len([x for x in e if x["w"].startswith(yr)])}')
    
    prev_last = d['last']['eq']

# Print 2010-2026 total
first_e = years['2010']['first']['eq']
last_e = years['2026']['last']['eq']
total_ret = (last_e / first_e - 1) * 100
print('-' * 35)
print(f'{">2010-2026":>6}  {">+":>8}')
print(f'{"Total":>6}  {total_ret:>+8.2f}%  {last_e:>8.4f}')

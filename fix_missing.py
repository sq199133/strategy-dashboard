#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix missing ETF downloads and standardize data format"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import akshare as ak
import pandas as pd

hl_dir = r'D:\QClaw_Trading\data\history_long'

def get_prefix(code):
    if code.startswith(('5', '6')):
        return 'sh'
    return 'sz'

def download_weekly(code):
    """Download and save weekly data for one ETF"""
    prefix = get_prefix(code)
    symbol = prefix + code
    
    try:
        df = ak.stock_zh_a_hist_tx(symbol=symbol, start_date='20050101', end_date='20260613', adjust='qfq')
        if df is None or df.empty:
            return None, "Empty"
        
        # Convert to weekly: last trading day of each ISO week
        df_daily = df.copy()
        df_daily['date'] = pd.to_datetime(df_daily['date'])
        df_daily['weekday'] = df_daily['date'].dt.dayofweek
        df_daily['week'] = df_daily['date'].dt.strftime('%Y-W%V')
        weekly = df_daily[df_daily['weekday'] <= 4].groupby('week').last().reset_index()
        
        weekly_data = []
        for _, row in weekly.iterrows():
            weekly_data.append({
                'w': row['week'],
                'date': row['date'].strftime('%Y-%m-%d'),
                'close': float(row['close']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'vol': float(row.get('amount', row.get('volume', 0)))
            })
        
        return weekly_data, "OK"
    except Exception as e:
        return None, str(e)

# Fix missing key ETFs
missing = [
    ('159915', '创业板ETF'),
    ('513500', '标普500ETF'),
]

for code, name in missing:
    weekly, status = download_weekly(code)
    if weekly:
        fpath = os.path.join(hl_dir, code + '.json')
        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(weekly, f, ensure_ascii=False, indent=2)
        print(f"OK | {code} {name}: {len(weekly)} weeks, {weekly[0]['date']} ~ {weekly[-1]['date']}")
    else:
        print(f"FAIL | {code} {name}: {status}")

# Now standardize: delete old prefixed files and keep new format files
print("\n--- Standardizing directory ---")
files = [f for f in os.listdir(hl_dir) if f.endswith('.json')]
old_prefixed = [f for f in files if f.startswith(('sh', 'sz'))]
new_unprefixed = [f for f in files if not f.startswith(('sh', 'sz'))]

print(f"Old files (to delete): {len(old_prefixed)}")
print(f"New files (keep): {len(new_unprefixed)}")

# Count how many of the 195 ETFs have proper new files
pool_file = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'
with open(pool_file, 'r', encoding='utf-8') as f:
    pool = json.load(f)
etf_codes = [e['code'] for e in pool.get('data', [])]

# Check how many have new-format files
has_new = sum(1 for c in etf_codes if f'{c}.json' in new_unprefixed)
print(f"\nETF pool coverage: {has_new}/{len(etf_codes)} have new weekly data")

# Show which ones are still missing from new files
missing_new = [c for c in etf_codes if f'{c}.json' not in new_unprefixed]
if missing_new:
    print(f"Missing new data: {missing_new[:10]}...")
else:
    print("All 195 ETFs have new weekly data!")

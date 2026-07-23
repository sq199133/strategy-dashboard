# -*- coding: utf-8 -*-
import akshare as ak
import pandas as pd
import json
import os

output_dir = 'D:/QClaw_Trading/data/pe_data'
os.makedirs(output_dir, exist_ok=True)

print('Fetching A-share market PE data...')
df = ak.stock_market_pe_lg()

df.columns = ['date', 'index_value', 'pe']
df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
df = df.sort_values('date')

output_file = os.path.join(output_dir, 'a_market_pe.json')
records = df.to_dict('records')
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f'Saved to: {output_file}')
print(f'Records: {len(df)}')
print(f'Date range: {df["date"].iloc[0]} to {df["date"].iloc[-1]}')
print(f'\nLatest data:')
print(df.tail(10).to_string())

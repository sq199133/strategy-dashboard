import json
import os
from datetime import datetime

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long_v2'

# 检查多个文件
files = ['510300.json', '510500.json', '512100.json', '159915.json']

for fname in files:
    fpath = os.path.join(HISTORY_DIR, fname)
    if not os.path.exists(fpath):
        continue
    
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    records = data['records']
    dates = [r['date'] for r in records]
    
    print(f'{fname}: {len(records)} 条, {dates[0]} 到 {dates[-1]}')

# 找出所有ETF的日期交集
all_dates = None
for fname in os.listdir(HISTORY_DIR):
    if not fname.endswith('.json'):
        continue
    
    fpath = os.path.join(HISTORY_DIR, fname)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        records = data.get('records', [])
        if len(records) < 50:
            continue
        
        dates = set(r['date'] for r in records)
        if all_dates is None:
            all_dates = dates
        else:
            all_dates = all_dates.intersection(dates)
    except:
        continue

if all_dates:
    all_dates = sorted(all_dates)
    print(f'\n所有ETF公共日期: {len(all_dates)} 个')
    print(f'范围: {all_dates[0]} 到 {all_dates[-1]}')
    
    # 2014年以后
    dates_2014 = [d for d in all_dates if d >= '2014-01-01']
    print(f'2014年后: {len(dates_2014)} 个')
    print(f'范围: {dates_2014[0]} 到 {dates_2014[-1]}')

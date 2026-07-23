#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"

# 今日实时行情（刚获取）
TODAY_DATA = {
    '159902': {'close': 5.116, 'open': 5.087, 'high': 5.128, 'low': 5.030, 'change_pct': 0.72},
    '160723': {'close': 2.158, 'open': 2.130, 'high': 2.239, 'low': 2.120, 'change_pct': 1.80},
    '161128': {'close': 6.871, 'open': 6.978, 'high': 6.978, 'low': 6.773, 'change_pct': 0.89},
}

today_str = "2026-05-28"

print("=" * 70)
print("ETF数据更新")
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 70)

for code, vals in TODAY_DATA.items():
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            records = data.get('records', [])
            
            # 检查或更新今日记录
            found = False
            for r in records:
                if r['date'] == today_str:
                    r['close'] = vals['close']
                    r['open'] = vals['open']
                    r['high'] = vals['high']
                    r['low'] = vals['low']
                    r['change_pct'] = vals['change_pct']
                    r['change'] = round(vals['close'] - vals['open'], 3)
                    found = True
                    print(f"  更新 {code}: {today_str} close={vals['close']:.3f} ({vals['change_pct']:+.2f}%)")
                    break
            
            if not found:
                new_rec = {
                    'date': today_str,
                    'open': vals['open'],
                    'close': vals['close'],
                    'high': vals['high'],
                    'low': vals['low'],
                    'vol': 0, 'amount': 0,
                    'change': round(vals['close'] - vals['open'], 3),
                    'change_pct': vals['change_pct']
                }
                records.append(new_rec)
                print(f"  新增 {code}: {today_str} close={vals['close']:.3f} ({vals['change_pct']:+.2f}%)")
            
            records.sort(key=lambda x: x['date'])
            data['records'] = records
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            break

print()
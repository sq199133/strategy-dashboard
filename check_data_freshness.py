#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查ETF数据新鲜度"""

import json
import os
from datetime import datetime, timedelta

DATA_DIR = r"D:\QClaw_Trading\data\history"

ETF_LIST = ['159902', '160723', '161128']

print("=" * 70)
print("检查ETF数据新鲜度")
print(f"当前日期: {datetime.now().strftime('%Y-%m-%d')}")
print("=" * 70)

today = datetime.now().date()
latest_date = None

for code in ETF_LIST:
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            records = data.get('records', [])
            if records:
                last_date_str = records[-1]['date']
                last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
                days_behind = (today - last_date).days

                status = "✓" if days_behind <= 1 else "⚠️"
                print(f"{status} {code}: 最新 {last_date_str} (滞后{days_behind}天)")

                if latest_date is None or last_date > latest_date:
                    latest_date = last_date
            else:
                print(f"✗ {code}: 无数据")
            break

print("\n" + "=" * 70)
if latest_date:
    print(f"数据最新日期: {latest_date.strftime('%Y-%m-%d')}")
    print(f"需要更新至: {today.strftime('%Y-%m-%d')}")
else:
    print("未找到任何数据")
print("=" * 70)

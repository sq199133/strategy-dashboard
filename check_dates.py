import json
import os
from datetime import datetime

HISTORY_DIR = r'D:\QClaw_Trading\data\history_long_v2'

# 读取一个文件看看日期分布
with open(os.path.join(HISTORY_DIR, '510300.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)

records = data['records']

# 统计周三数量
wed_count = 0
all_dates = []

for r in records:
    date = r['date']
    dt = datetime.strptime(date, '%Y-%m-%d')
    all_dates.append(date)
    if dt.weekday() == 2:
        wed_count += 1

print(f'总记录数: {len(records)}')
print(f'周三数量: {wed_count}')
print(f'日期范围: {all_dates[0]} 到 {all_dates[-1]}')
print(f'前10个日期: {all_dates[:10]}')
print(f'后10个日期: {all_dates[-10:]}')

# 检查2014年后的周三数量
wed_2014 = 0
for r in records:
    date = r['date']
    if date >= '2014-01-01':
        dt = datetime.strptime(date, '%Y-%m-%d')
        if dt.weekday() == 2:
            wed_2014 += 1

print(f'2014年后周三数量: {wed_2014}')

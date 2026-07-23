#!/usr/bin/env python3
import json

codes = ['588000','159915','510300','510050','510500','512100','513500','513100','518880','162411']
hist = r'D:\QClaw_Trading\data\history'

print('=== 本地最新数据 ===\n')
print(f'{"代码":<10} {"最新日期":<14} {"收盘价":>8}')
print('-' * 40)
for c in codes:
    try:
        with open(f'{hist}\\{c}.json','r',encoding='utf-8') as f:
            recs = json.load(f)['records']
        latest = recs[-1]
        print(f'{c:<10} {latest["date"]:<14} {latest["close"]:>8.3f}')
    except:
        print(f'{c:<10} 读取失败')

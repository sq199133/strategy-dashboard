#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询588000在买入日后的表现"""

import json

HIST_DIR = r'D:\QClaw_Trading\data\history'
CODE = '588000'

with open(f'{HIST_DIR}\\{CODE}.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

records = data['records']

print(f'=== {CODE} {data.get("name", "")} 近期价格 ===\n')
print(f'{"日期":<12} {"开盘":>8} {"最高":>8} {"最低":>8} {"收盘":>8}')
print('-' * 60)

# 找6/24及之后
for r in records:
    if r['date'] >= '2026-06-24':
        print(f'{r["date"]:<12} {r["open"]:>8.3f} {r["high"]:>8.3f} {r["low"]:>8.3f} {r["close"]:>8.3f}')

# 计算买入后收益
buy_date = '2026-06-24'
buy_price = 2.01

latest = records[-1]
latest_date = latest['date']
latest_close = latest['close']

pnl_pct = (latest_close - buy_price) / buy_price * 100

print(f'\n=== 持仓盈亏 ===\n')
print(f'买入日: {buy_date}')
print(f'买入价: {buy_price}')
print(f'最新日: {latest_date}')
print(f'最新价: {latest_close:.3f}')
print(f'浮动盈亏: {pnl_pct:+.2f}%')
print(f'市值变化: {20000 * (latest_close - buy_price):+.2f} 元 (假设20000份)')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""今日复盘 2026-07-02"""

import json
import os
from datetime import datetime, timedelta

HIST = r'D:\QClaw_Trading\data\history'
BUY_DATE = '2026-06-24'
BUY_PRICE = 2.01
BUY_SHARES = 20000
LOCK_EXPIRE = '2026-08-05'

def load_history(code):
    with open(f'{HIST}\\{code}.json', 'r', encoding='utf-8') as f:
        return json.load(f)['records']

def c63_return(records, code):
    """计算63日收益"""
    if len(records) < 64:
        return None
    # 今日用ef数据更新
    ef_file = r'D:\QClaw_Trading\RSRS\ef_today.json'
    ef_data = {}
    if os.path.exists(ef_file):
        with open(ef_file, 'r', encoding='utf-8') as f:
            ef_data = json.load(f)
    
    today_close = None
    if code in ef_data:
        today_close = ef_data[code]['close']
    
    latest = records[-1]
    start_idx = max(0, len(records) - 64)
    start_close = records[start_idx]['close']
    
    # 如果今天有数据，用今天的
    if today_close and latest['date'] != '2026-07-02':
        end_close = today_close
    else:
        end_close = latest['close']
    
    return (end_close - start_close) / start_close * 100

# 读取本地历史数据
print('=== 读取本地历史 + 今日数据 ===\n')

# KC50完整行情
kc50 = load_history('588000')

# 更新KC50今日数据到本地
ef_file = r'D:\QClaw_Trading\RSRS\ef_today.json'
if os.path.exists(ef_file):
    with open(ef_file, 'r', encoding='utf-8') as f:
        ef_data = json.load(f)
    if '588000' in ef_data:
        today_data = ef_data['588000']
        # 更新本地JSON最后一条
        kc50[-1] = {
            'date': today_data['date'],
            'open': today_data['open'],
            'close': today_data['close'],
            'high': today_data['high'],
            'low': today_data['low'],
        }
        with open(f'{HIST}\\588000.json', 'w', encoding='utf-8') as f:
            json.dump({'records': kc50}, f, ensure_ascii=False)

# KC50近期行情
print('KC50 近期行情:\n')
print(f'{"日期":<12} {"开盘":>8} {"最高":>8} {"最低":>8} {"收盘":>8} {"涨跌":>8}')
print('-' * 62)
for r in kc50[-8:]:
    idx = kc50.index(r)
    if idx > 0:
        pchg = (r['close'] - kc50[idx-1]['close']) / kc50[idx-1]['close'] * 100
    else:
        pchg = 0
    marker = ' <-- 买入日' if r['date'] == BUY_DATE else ''
    print(f'{r["date"]:<12} {r["open"]:>8.3f} {r["high"]:>8.3f} {r["low"]:>8.3f} {r["close"]:>8.3f} {pchg:>+7.2f}%{marker}')

# 持仓盈亏
latest_kc = kc50[-1]
current_price = latest_kc['close']
current_date = latest_kc['date']
pnl_pct = (current_price - BUY_PRICE) / BUY_PRICE * 100
pnl_amount = BUY_SHARES * (current_price - BUY_PRICE)
total_cost = BUY_SHARES * BUY_PRICE
total_value = BUY_SHARES * current_price

print(f'\n=== 持仓盈亏 ===\n')
print(f'买入日期: {BUY_DATE}')
print(f'买入价格: {BUY_PRICE:.3f}')
print(f'当前价格: {current_price:.3f}  ({current_date})')
print(f'浮动盈亏: {pnl_pct:+.2f}%')
print(f'持仓市值: {total_value:,.0f} 元  (成本 {total_cost:,.0f} 元)')
print(f'浮动盈利: {pnl_amount:+,.0f} 元')

# 锁仓倒计时
lock_expire = datetime.strptime(LOCK_EXPIRE, '%Y-%m-%d')
today = datetime(2026, 7, 2)
days_remaining = (lock_expire - today).days
lock_start = datetime.strptime(BUY_DATE, '%Y-%m-%d')
days_elapsed = (today - lock_start).days

print(f'\n=== 锁仓状态 ===\n')
print(f'锁仓开始: {BUY_DATE}  (已过 {days_elapsed} 天)')
print(f'锁仓到期: {LOCK_EXPIRE}  (还剩 {days_remaining} 天)')
print(f'状态: {"锁仓中" if days_remaining > 0 else "已到期"}')

# C63动量排名
print(f'\n=== C63动量排名 ({current_date}) ===\n')
etfs = {
    '588000': 'KC50', '159915': 'CYB', '510300': 'HS300',
    '510500': 'ZZ500', '512100': 'ZZ1000', '510050': 'SH50',
    '513500': 'SP500', '513100': 'NSDQ', '518880': 'GOLD', '162411': 'OIL'
}

rankings = []
for code in etfs:
    try:
        recs = load_history(code)
        # 更新今日数据
        if os.path.exists(ef_file):
            with open(ef_file, 'r', encoding='utf-8') as f:
                ef = json.load(f)
            if code in ef:
                today_d = ef[code]
                recs[-1] = {
                    'date': today_d['date'], 'open': today_d['open'],
                    'close': today_d['close'], 'high': today_d['high'], 'low': today_d['low']
                }
        
        ret = c63_return(recs, code)
        rankings.append((etfs[code], code, ret))
    except Exception as e:
        rankings.append((etfs[code], code, None))

rankings.sort(key=lambda x: x[2] if x[2] is not None else -999, reverse=True)

print(f'{"排名":>4}  {"标的":<8} {"代码":<10} {"63d收益":>8}  {"状态":>6}')
print('-' * 50)
for i, (name, code, ret) in enumerate(rankings, 1):
    if ret is not None:
        status = '持仓' if code == '588000' else ''
        print(f'  {i:>2}  {name:<8} {code:<10} {ret:>+8.2f}%  {status}')
    else:
        print(f'  {i:>2}  {name:<8} {code:<10} {"N/A":>8}')

# 综合结论
kc_rank = next((i for i, (_, c, _) in enumerate(rankings, 1) if c == '588000'), None)
print(f'\nKC50排名: 第{kc_rank}名 (63d +{rankings[0][2]:.2f}%)')

print(f'\n{"="*62}')
print(f'  今日复盘结论: 2026-07-02')
print(f'{"="*62}\n')
print(f'  操作: {"继续持有" if days_remaining > 0 else "锁仓到期，检查信号"}')
print(f'  持仓: KC50  {pnl_pct:+.2f}% / {pnl_amount:+,.0f} 元')
print(f'  锁仓: 还剩 {days_remaining} 天')
print(f'  C63:  KC50 第{kc_rank}名  {"继续持有" if rankings[0][1] == "588000" else "考虑换"}')
print(f'  注意: 今天KC50大跌 -7.47%，属异常波动')

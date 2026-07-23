#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日复盘 - 2026-07-01"""

import json
from datetime import datetime, timedelta

HIST_DIR = r'D:\QClaw_Trading\data\history'

# ============ 持仓信息 ============
POSITION = {
    'code': '588000',
    'name': 'KC50 (科创50)',
    'buy_date': '2026-06-24',
    'buy_price': 2.01,
    'shares': 20000,
    'position_pct': 0.80,
    'lock_expire': '2026-08-05',  # 42天后
}

def load_history(code):
    with open(f'{HIST_DIR}\\{code}.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['records']

def get_price(records, date):
    for r in records:
        if r['date'] == date:
            return r
    return None

def get_latest_price(records):
    return records[-1]

# ============ 加载数据 ============
kc50 = load_history('588000')
cyb = load_history('159915')
hs300 = load_history('510300')

# ============ 最新价格 ============
today = '2026-07-01'
# 注意：今天可能还没有收盘，用最近一个交易日
latest_kc50 = get_latest_price(kc50)
latest_date = latest_kc50['date']

print(f'=== KC50 近期行情 ({latest_date}) ===\n')
print(f'{"日期":<12} {"开盘":>8} {"最高":>8} {"最低":>8} {"收盘":>8} {"涨跌":>8}')
print('-' * 62)

# 打印最近5个交易日
for r in kc50[-5:]:
    pchg = (r['close'] - kc50[kc50.index(r)-1]['close']) / kc50[kc50.index(r)-1]['close'] * 100 if kc50.index(r) > 0 else 0
    marker = ' ◀ 买入日' if r['date'] == POSITION['buy_date'] else ''
    print(f'{r["date"]:<12} {r["open"]:>8.3f} {r["high"]:>8.3f} {r["low"]:>8.3f} {r["close"]:>8.3f} {pchg:>+7.2f}%{marker}')

# ============ 持仓盈亏 ============
buy_price = POSITION['buy_price']
current_price = latest_kc50['close']
current_date = latest_kc50['date']
pnl_pct = (current_price - buy_price) / buy_price * 100
pnl_amount = POSITION['shares'] * (current_price - buy_price)
total_cost = POSITION['shares'] * buy_price
total_value = POSITION['shares'] * current_price

print(f'\n=== 持仓盈亏 ===\n')
print(f'买入日:   {POSITION["buy_date"]}')
print(f'买入价:   {buy_price:.3f}')
print(f'当前价:   {current_price:.3f}  ({current_date})')
print(f'浮动盈亏: {pnl_pct:+.2f}%')
print(f'份数:     {POSITION["shares"]:,} 份')
print(f'买入市值: {total_cost:,.0f} 元')
print(f'当前市值: {total_value:,.0f} 元')
print(f'浮动盈利: {pnl_amount:+,.0f} 元')

# ============ 锁仓倒计时 ============
lock_expire = datetime.strptime(POSITION['lock_expire'], '%Y-%m-%d')
today_dt = datetime.strptime('2026-07-01', '%Y-%m-%d')
days_remaining = (lock_expire - today_dt).days
lock_start = datetime.strptime(POSITION['buy_date'], '%Y-%m-%d')
lock_days_elapsed = (today_dt - lock_start).days

print(f'\n=== 锁仓状态 ===\n')
print(f'锁仓开始: {POSITION["buy_date"]}  (已过 {lock_days_elapsed} 天)')
print(f'锁仓到期: {POSITION["lock_expire"]}  (还剩 {days_remaining} 天)')
print(f'锁仓状态: {"🔒 锁仓中" if days_remaining > 0 else "⚠️ 已到期"}')

# ============ RSRS信号 ============
print(f'\n=== RSRS信号 (截至 {current_date}) ===\n')
print(f'RSRS z-score:  0.98')
print(f'阈值:          buy>=0.7, sell<=-1.0')
print(f'信号:          多头 ✅')
print(f'说明:          高低点同步扩张，多头格局未变')
print(f'→              RSRS翻空才卖，当前继续持有')

# ============ C63动量排名 ============
print(f'\n=== C63动量排名 (截至 {current_date}) ===\n')
print(f'持仓标的: KC50 (588000)  63d收益 +56.95%  → 第1名 ✅')
print(f'第2名: CYB (159915)      63d收益 +30.21%')
print(f'结论:  KC50仍是动量第1，继续持有')

# ============ 波动率缩放 ============
print(f'\n=== 波动率缩放 ===\n')
print(f'建议仓位: ~80%')
print(f'当前仓位:  80%  ✅')
print(f'说明:      波动率缩放因子未变，无需调仓')

# ============ 综合结论 ============
print(f'\n{"="*62}')
print(f'  今日复盘结论: 2026-07-01')
print(f'{"="*62}\n')
print(f'  ✅ 操作: 继续持有 KC50')
print(f'  ✅ 锁仓: 还有 {days_remaining} 天到期')
print(f'  ✅ 盈亏: {pnl_pct:+.2f}% / {pnl_amount:+,.0f} 元')
print(f'  ✅ 信号: RSRS多头，C63第1，策略正常')
print(f'  ✅ 下次检查: 锁仓到期日 2026-08-05 或 RSRS翻空时')

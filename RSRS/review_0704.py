#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""今日复盘 2026-07-04 (使用2026-07-03收盘数据)"""

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

# 读取东方财富今日数据
ef_file = r'D:\QClaw_Trading\RSRS\ef_today.json'
ef_data = {}
if os.path.exists(ef_file):
    with open(ef_file, 'r', encoding='utf-8') as f:
        ef_data = json.load(f)

# 更新本地历史数据（用今日数据覆盖最后一条）
print('=== 更新本地数据 ===\n')
for code in ['588000', '159915', '510300', '510500', '512100', '510050', '513500', '513100', '518880', '162411']:
    if code in ef_data:
        recs = load_history(code)
        today_d = ef_data[code]
        # 更新最后一条
        if recs[-1]['date'] != today_d['date']:
            recs.append({
                'date': today_d['date'],
                'open': today_d['open'],
                'close': today_d['close'],
                'high': today_d['high'],
                'low': today_d['low'],
            })
        else:
            recs[-1] = {
                'date': today_d['date'],
                'open': today_d['open'],
                'close': today_d['close'],
                'high': today_d['high'],
                'low': today_d['low'],
            }
        with open(f'{HIST}\\{code}.json', 'w', encoding='utf-8') as f:
            json.dump({'records': recs}, f, ensure_ascii=False)
        print(f'  {code} 更新到 {today_d["date"]} close={today_d["close"]:.3f}')

# KC50行情
kc50 = load_history('588000')
print(f'\n=== KC50 近期行情 ===\n')
print(f'{"日期":<12} {"开盘":>8} {"最高":>8} {"最低":>8} {"收盘":>8} {"涨跌":>8}')
print('-' * 62)
for r in kc50[-8:]:
    idx = kc50.index(r)
    if idx > 0:
        pchg = (r['close'] - kc50[idx-1]['close']) / kc50[idx-1]['close'] * 100
    else:
        pchg = 0
    marker = ' <-- 买入日' if r['date'] == BUY_DATE else ''
    marker2 = ' <-- 今日' if r['date'] == '2026-07-03' else ''
    print(f'{r["date"]:<12} {r["open"]:>8.3f} {r["high"]:>8.3f} {r["low"]:>8.3f} {r["close"]:>8.3f} {pchg:>+7.2f}%{marker}{marker2}')

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
today = datetime(2026, 7, 4)
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

def calc_c63(code):
    recs = load_history(code)
    if len(recs) < 64:
        return None
    start_close = recs[-64]['close']
    end_close = recs[-1]['close']
    return (end_close - start_close) / start_close * 100

rankings = []
for code, name in etfs.items():
    ret = calc_c63(code)
    rankings.append((name, code, ret))

rankings.sort(key=lambda x: x[2] if x[2] is not None else -999, reverse=True)

print(f'{"排名":>4}  {"标的":<8} {"代码":<10} {"63d收益":>8}')
print('-' * 40)
for i, (name, code, ret) in enumerate(rankings, 1):
    if ret is not None:
        status = '持仓' if code == '588000' else ''
        print(f'  {i:>2}  {name:<8} {code:<10} {ret:>+8.2f}%  {status}')
    else:
        print(f'  {i:>2}  {name:<8} {code:<10} {"N/A":>8}')

# RSRS信号（需要计算）
print(f'\n=== RSRS信号 ({current_date}) ===\n')
# 简化：用HS300(510300)计算RSRS
hs300 = load_history('510300')
if len(hs300) >= 918:  # 900 + 18
    # 计算最新RSRS z-score
    import numpy as np
    from sklearn.linear_model import LinearRegression
    
    beta_list = []
    for i in range(900, len(hs300)):
        X = np.array([r['low'] for r in hs300[i-18:i]]).reshape(-1, 1)
        y = np.array([r['high'] for r in hs300[i-18:i]])
        model = LinearRegression()
        model.fit(X, y)
        beta_list.append(model.coef_[0])
    
    current_beta = beta_list[-1]
    mean_beta = np.mean(beta_list)
    std_beta = np.std(beta_list)
    z_score = (current_beta - mean_beta) / std_beta if std_beta > 0 else 0
    
    print(f'RSRS beta:    {current_beta:.4f}')
    print(f'均值(900天): {mean_beta:.4f}')
    print(f'标准差:      {std_beta:.4f}')
    print(f'z-score:     {z_score:.2f}')
    print(f'信号:        {"多头 ✅" if z_score >= 0.7 else "空头 ❌" if z_score <= -1.0 else "灰色区域"}')
else:
    print('数据不足，无法计算RSRS')

# 综合结论
kc_rank = next((i for i, (_, c, _) in enumerate(rankings, 1) if c == '588000'), None)
kc_ret = next((ret for _, c, ret in rankings if c == '588000'), None)

print(f'\n{"="*62}')
print(f'  今日复盘结论: 2026-07-04 (数据截至 {current_date})')
print(f'{"="*62}\n')
print(f'  操作: 继续持有')
print(f'  持仓: KC50  {pnl_pct:+.2f}% / {pnl_amount:+,.0f} 元')
print(f'  锁仓: 还剩 {days_remaining} 天 (到期 {LOCK_EXPIRE})')
print(f'  C63:  KC50 第{kc_rank}名  ({kc_ret:+.2f}%)')
print(f'  市场: 7/3 KC50 -0.80%，继续回调但仍在盈利区间')
print(f'  注意: 锁仓期内，不因短期波动操作')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026年逐周表现分析"""
import sys, json, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, r'D:\QClaw_Trading')
from backtest_v4_fixed import load_pool, load_history

POOL_FILE = r'D:\QClaw_Trading\data\etf_pool_V1_full.json'

with open(POOL_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)
etfs = data.get('data', data.get('etfs', []))

code_info = {}
all_series = {}
for etf in etfs:
    code = etf['code']
    s = load_history(code)
    if s and len(s) >= 30:
        all_series[code] = s
        code_info[code] = {'name': etf.get('name', ''), 'cat': etf.get('category', '')}

MA_S, MA_L, LB, MAX_DEV, TOP_N = 5, 21, 3, 10, 2

def closes_until(code, week):
    return [c for w, c in all_series.get(code, []) if w <= week]

def close_at(code, week):
    for w, c in all_series.get(code, []):
        if w == week: return c
        if w > week: return None
    return None

def get_signal(code, week):
    cs = closes_until(code, week)
    n = len(cs)
    if n < MA_L + 1: return None
    price = cs[-1]
    ma_s = sum(cs[-MA_S:]) / MA_S
    ma_l = sum(cs[-MA_L:]) / MA_L
    mom = cs[-1] / cs[-LB] - 1 if n > LB else None
    dev = price / ma_l - 1
    if mom is None or mom <= 0: return None
    if not (price > ma_s > ma_l): return None
    if dev > MAX_DEV / 100.0: return None
    g3_pass = True
    if len(cs) >= 2:
        mom1w = cs[-1] / cs[-2] - 1
        if mom1w < -0.01: g3_pass = False
    if len(cs) >= 4:
        mom3w = cs[-1] / cs[-4] - 1
        if mom3w < 0: g3_pass = False
    if not g3_pass: return None
    return {'code': code, 'close': price, 'mom': mom, 'dev': dev}

all_weeks = sorted(set(w for s in all_series.values() for w, c in s))
run_weeks = [w for w in all_weeks if w >= '2025-W40' and w <= '2026-W24']

portfolio = {}
cash = 1.0
weekly_data = []
trades = []

for i in range(len(run_weeks) - 1):
    sig_week = run_weeks[i]
    exec_week = run_weeks[i + 1]
    is_2026 = exec_week >= '2026-W01'

    candidates = []
    for code in all_series:
        sig = get_signal(code, sig_week)
        if sig: candidates.append(sig)
    candidates.sort(key=lambda x: x['mom'], reverse=True)

    cats = set()
    target = []
    for c in candidates:
        cat = code_info.get(c['code'], {}).get('cat', '') or c['code']
        if cat not in cats:
            cats.add(cat)
            target.append(c)
    target = target[:TOP_N]
    target_codes = {t['code'] for t in target}

    to_sell = []
    for code, pos in list(portfolio.items()):
        p = close_at(code, exec_week)
        if p is None:
            to_sell.append((code, 'no_data')); continue
        cost_pnl = p / pos['buy_price'] - 1
        hwm_pnl = p / pos['hwm'] - 1
        if cost_pnl <= -0.08 or hwm_pnl <= -0.10:
            to_sell.append((code, 'stop'))
        elif code not in target_codes:
            to_sell.append((code, 'rebalance'))

    for code, reason in to_sell:
        pos = portfolio.pop(code)
        p = close_at(code, exec_week) or pos['buy_price']
        cash += pos['weight'] * p
        pnl = (p / pos['buy_price'] - 1) * 100
        name = code_info.get(code, {}).get('name', code)
        if is_2026:
            trades.append({'w': exec_week, 'act': 'S', 'code': code, 'name': name, 'pnl': round(pnl,2), 'reason': reason})

    equity = cash + sum(pos['weight'] * (close_at(c, exec_week) or pos['buy_price']) for c, pos in portfolio.items())

    slots = TOP_N - len(portfolio)
    if slots > 0 and equity > 0:
        buy_list = [t for t in target if t['code'] not in portfolio]
        slot_val = equity / TOP_N
        for bc in buy_list[:slots]:
            exec_price = close_at(bc['code'], exec_week)
            if exec_price is None or exec_price <= 0: continue
            weight = slot_val / exec_price
            cost = weight * exec_price
            if cost > cash * 0.98:
                weight = cash * 0.98 / exec_price
                cost = weight * exec_price
            if weight <= 0: break
            cash -= cost
            portfolio[bc['code']] = {'weight': weight, 'buy_price': exec_price, 'hwm': exec_price}
            name = code_info.get(bc['code'], {}).get('name', bc['code'])
            if is_2026:
                trades.append({'w': exec_week, 'act': 'B', 'code': bc['code'], 'name': name, 'price': round(exec_price,4)})

    equity = cash + sum(pos['weight'] * (close_at(c, exec_week) or pos['buy_price']) for c, pos in portfolio.items())
    if is_2026:
        weekly_data.append({'w': exec_week, 'eq': equity, 'holds': list(portfolio.keys())})

# Output
print('=' * 90)
print('  2026年逐周表现 (v4.3: MA5/21 LB3 D10 H2)')
print('=' * 90)

print('\n--- 逐周净值 & 回撤 ---')
print(f'  {"周":<10} {"净值":>8} {"周收益":>8} {"累计收益":>9} {"峰值":>8} {"回撤":>7} {"持仓ETF"}')
print(f'  {"-"*85}')

prev_eq = weekly_data[0]['eq'] if weekly_data else 1.0
# Find initial equity for cumulative
initial_eq = weekly_data[0]['eq'] if weekly_data else 1.0

peak = weekly_data[0]['eq'] if weekly_data else 1.0
max_dd = 0
max_dd_week = ''

for wd in weekly_data:
    eq = wd['eq']
    wr = (eq / prev_eq - 1) * 100
    cum = (eq / initial_eq - 1) * 100
    if eq > peak:
        peak = eq
    dd = (eq / peak - 1) * 100
    if dd < max_dd:
        max_dd = dd
        max_dd_week = wd['w']
    hold_names = [code_info.get(c, {}).get('name', c) for c in wd['holds']]
    print(f"  {wd['w']:<10} {eq:>8.4f} {wr:>+7.2f}% {cum:>+8.2f}% {peak:>8.4f} {dd:>6.2f}% {', '.join(hold_names) if hold_names else '空仓'}")
    prev_eq = eq

print(f'\n  最大回撤: {max_dd:.2f}% (发生在 {max_dd_week})')

# Trades
print('\n--- 2026年交易明细 ---')
sell_wins = 0
sell_total = 0
buy_total = 0
for t in trades:
    if t['act'] == 'S':
        sell_total += 1
        if t['pnl'] > 0: sell_wins += 1
        print(f"  {t['w']} 卖出 {t['code']} {t['name']:<20} 收益={t['pnl']:+.2f}%  原因={t['reason']}")
    elif t['act'] == 'B':
        buy_total += 1
        print(f"  {t['w']} 买入 {t['code']} {t['name']:<20} 价格={t['price']}")

print(f'\n--- 交易统计 ---')
print(f'  买入: {buy_total}次')
print(f'  卖出: {sell_total}次')
if sell_total > 0:
    print(f'  卖出胜率: {sell_wins}/{sell_total} = {sell_wins/sell_total*100:.1f}%')
    sell_pnls = [t['pnl'] for t in trades if t['act'] == 'S']
    avg_pnl = sum(sell_pnls) / len(sell_pnls)
    print(f'  平均卖出收益: {avg_pnl:+.2f}%')

# Stop loss count
stops = [t for t in trades if t['act'] == 'S' and t['reason'] == 'stop']
rebals = [t for t in trades if t['act'] == 'S' and t['reason'] == 'rebalance']
print(f'  止损卖出: {len(stops)}次')
print(f'  轮仓卖出: {len(rebals)}次')

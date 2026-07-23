#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ETF波段策略 - 2026-05-27 每日复盘"""

import json
import os
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"
STATE_FILE = r"D:\QClaw_Trading\data\virtual_portfolio_state.json"

ETF_LIST = [
    ("159902", "中小100ETF华夏"),
    ("160723", "嘉实原油LOF"),
    ("161128", "标普信息科技LOF"),
]

def load_latest_nav(code):
    """加载ETF最新净值和数据"""
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            records = data.get('records', [])
            if records:
                return records[-1], records
    return None, []

def calc_bb_indicators(records, window=20, num_std=2):
    """计算布林带指标"""
    if len(records) < window:
        return None, None, None

    # 取最近window个收盘价
    closes = [r['close'] for r in records[-window:]]
    ma = sum(closes) / len(closes)
    std = (sum((x - ma) ** 2 for x in closes) / len(closes)) ** 0.5
    upper = ma + num_std * std
    lower = ma - num_std * std
    return ma, upper, lower

def check_signal(records, ma, upper, lower):
    """检查买卖信号"""
    if len(records) < 2:
        return "数据不足"

    today = records[-1]
    yesterday = records[-2]

    # 买入信号：前日在布林带内 + 当日突破上轨
    if yesterday['close'] <= upper and today['close'] > upper:
        return "▲ 突破买入"
    # 卖出信号：跌破下轨
    elif yesterday['close'] >= lower and today['close'] < lower:
        return "▼ 跌破卖出"
    # 持有中
    else:
        dist_to_upper = (upper - today['close']) / today['close'] * 100
        return f"持有中 (距上轨+{dist_to_upper:.1f}%)"

print("=" * 70)
print("ETF波段策略 - 每日复盘")
print("日期: 2026-05-27 (周三)")
print("=" * 70)

# 第一部分：数据新鲜度检查
print("\n数据最新日期检查:")
latest_dates = []
for code, name in ETF_LIST:
    latest_record, _ = load_latest_nav(code)
    if latest_record:
        print(f"  {code} {name}: {latest_record['date']} 收盘{latest_record['close']:.3f}")
        latest_dates.append(latest_record['date'])
    else:
        print(f"  {code} {name}: 无数据")

if latest_dates:
    oldest_date = min(latest_dates)
    from datetime import datetime as dt
    days_behind = (dt.now().date() - dt.strptime(oldest_date, '%Y-%m-%d').date()).days
    print(f"\n⚠️ 数据最新至: {oldest_date} (滞后{days_behind}天)")

# 第二部分：今日行情与信号检查
print("\n" + "=" * 70)
print("今日行情与信号检查")
print("=" * 70)

signals = []
for code, name in ETF_LIST:
    latest_record, records = load_latest_nav(code)
    if not latest_record:
        print(f"\n{code} {name}")
        print("  信号: ✗ 无数据")
        continue

    close = latest_record['close']
    ma, upper, lower = calc_bb_indicators(records)

    if ma is None:
        print(f"\n{code} {name}")
        print(f"  收盘价: {close:.3f}")
        print("  信号: 数据不足（需要至少20个交易日）")
        continue

    signal = check_signal(records, ma, upper, lower)
    dist_to_upper = (upper - close) / close * 100

    print(f"\n{code} {name}")
    print(f"  收盘价: {close:.3f}")
    print(f"  MA20: {ma:.3f}")
    print(f"  上轨: {upper:.3f}  下轨: {lower:.3f}")
    print(f"  信号: {signal}")

    signals.append({
        'code': code,
        'name': name,
        'close': close,
        'ma': ma,
        'upper': upper,
        'lower': lower,
        'signal': signal,
        'dist_to_upper': dist_to_upper
    })

# 第三部分：虚拟盘状态
print("\n" + "=" * 70)
print("虚拟盘状态")
print("=" * 70)

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        state = json.load(f)
    print(f"总资金: {state.get('total_capital', 0):.2f} 元")
    print(f"策略: {state.get('strategy', 'N/A')}")
    print(f"状态: {state.get('status', 'N/A')}")
    print(f"\n当前持仓:")
    positions = state.get('positions', [])
    if positions:
        for pos in positions:
            print(f"  {pos['code']} {pos.get('name', '')}: {pos.get('shares', 0)}股 @ {pos.get('cost', 0):.3f}")
    else:
        print("  空仓")
else:
    print("状态文件不存在，显示默认状态:")
    print("总资金: 50000.00 元")
    print("策略: 布林带突破")
    print("状态: active")
    print("\n当前持仓: 空仓")

# 第四部分：操作建议
print("\n" + "=" * 70)
print("操作建议")
print("=" * 70)

buy_signals = [s for s in signals if '突破买入' in s.get('signal', '')]
sell_signals = [s for s in signals if '跌破卖出' in s.get('signal', '')]

if buy_signals:
    print("\n⚠️ 发现买入信号:")
    for s in buy_signals:
        print(f"  {s['code']} {s['name']}: {s['signal']}")
    print("\n建议操作: 全仓买入（选择距离上轨最近的ETF）")

    # 推荐买入标的
    if len(buy_signals) > 1:
        recommended = min(buy_signals, key=lambda x: x['dist_to_upper'])
        print(f"\n推荐标的: {recommended['code']} {recommended['name']} (突破信号)")

elif sell_signals:
    print("\n⚠️ 发现卖出信号:")
    for s in sell_signals:
        print(f"  {s['code']} {s['name']}: {s['signal']}")
    print("\n建议操作: 卖出持仓")
else:
    print("\n✓ 无交易信号")
    # 检查是否有接近突破的
    near_breakout = [s for s in signals if s.get('dist_to_upper', 100) < 5]
    if near_breakout:
        print("\n接近突破的ETF:")
        for s in near_breakout:
            print(f"  {s['code']} {s['name']}: 距上轨{s['dist_to_upper']:.1f}%")

# 第五部分：风险提示
print("\n" + "=" * 70)
print("风险提示")
print("=" * 70)
print("1. 数据滞后：部分ETF数据可能不是最新，信号可能存在延迟")
print("2. 假突破风险：突破信号后可能出现回撤，需严格执行止损6%")
print("3. 空仓等待：策略约60%时间空仓，需耐心等待信号")
print("4. T+1交易：ETF实行T+1交易制度，当日买入次日才能卖出")

print("\n" + "=" * 70)
print(f"复盘完成 @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

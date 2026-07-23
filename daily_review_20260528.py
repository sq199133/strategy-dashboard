#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ETF波段策略 - 2026-05-28 每日复盘"""
import json, os
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"
ETF_LIST = [
    ("159902", "中小100ETF华夏"),
    ("160723", "嘉实原油LOF"),
    ("161128", "标普信息科技LOF"),
]

def load_records(code):
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f).get('records', [])
    return []

def calc_bb(records, window=20, num_std=2):
    if len(records) < window:
        return None, None, None
    closes = [r['close'] for r in records[-window:]]
    ma = sum(closes) / len(closes)
    std = (sum((x - ma)**2 for x in closes) / len(closes)) ** 0.5
    return ma, ma + num_std * std, ma - num_std * std

print("=" * 70)
print("ETF波段策略 - 每日复盘")
print("日期: 2026-05-28 (周四)")
print("=" * 70)

# 行情汇总
print("\n今日行情汇总:")
print(f"{'代码':<10} {'名称':<15} {'今收':<8} {'涨跌':<8} {'MA20':<8} {'上轨':<8} {'下轨':<8} {'距上轨':<8} {'信号'}")
print("-" * 85)

signals = []
for code, name in ETF_LIST:
    records = load_records(code)
    if not records:
        print(f"{code:<10} {name:<15} 无数据")
        continue
    
    today = records[-1]
    close = today['close']
    chg = today.get('change_pct', 0)
    ma, upper, lower = calc_bb(records)
    
    if ma is None:
        print(f"{code:<10} {name:<15} 数据不足")
        continue
    
    dist = (upper - close) / close * 100
    
    # 信号判断
    yesterday = records[-2]['close']
    if yesterday <= upper and close > upper:
        sig = "▲买入信号"
    elif yesterday >= lower and close < lower:
        sig = "▼卖出信号"
    else:
        sig = "持有中"
    
    print(f"{code:<10} {name:<15} {close:<8.3f} {chg:+.2f}%  {ma:<8.3f} {upper:<8.3f} {lower:<8.3f} {dist:+.1f}%   {sig}")
    
    signals.append({
        'code': code, 'name': name, 'close': close, 'chg': chg,
        'ma': ma, 'upper': upper, 'lower': lower, 'dist': dist, 'signal': sig,
        'yesterday': yesterday, 'records': records
    })

# 虚拟盘状态
print("\n" + "=" * 70)
print("虚拟盘状态")
print("=" * 70)
print("持仓: 161128 标普信息科技LOF")
print("买入日期: 2026-05-27")
print("买入价: 6.979")
print("今日收盘: 6.871")
print("持仓盈亏: (6.871 - 6.979) / 6.979 = -1.55%")
print("止损线: 6.560 (跌破即卖)")
print("止盈线: 7.677 (达到即卖)")

# 持仓检查
print("\n" + "=" * 70)
print("持仓检查: 161128")
print("=" * 70)
rec_161128 = [s for s in signals if s['code'] == '161128']
if rec_161128:
    s = rec_161128[0]
    print(f"今日收盘: {s['close']:.3f}")
    print(f"上轨: {s['upper']:.3f}")
    print(f"下轨: {s['lower']:.3f}")
    print(f"信号: {s['signal']}")
    if s['yesterday'] <= s['upper'] and s['close'] > s['upper']:
        print("→ 突破成功！继续持有")
    elif s['yesterday'] >= s['lower'] and s['close'] < s['lower']:
        print("→ 跌破下轨！需考虑卖出")
    elif s['yesterday'] > s['upper']:
        print("→ 未能守住！回落到上轨下方，注意观察")

# 操作建议
print("\n" + "=" * 70)
print("操作建议")
print("=" * 70)
print("161128持仓: 继续持有")
print(f"  - 当前收盘{s['close']:.3f} > 上轨{s['upper']:.3f}? {'是' if s['close'] > s['upper'] else '否'}")
print(f"  - 止损线6.560，当前偏离: {(s['close']-6.560)/6.560*100:.1f}%")
print(f"  - 止盈线7.677，距今: {(7.677-s['close'])/s['close']*100:.1f}%")

print("\n明日关注:")
for s in signals:
    if s['signal'] == '持有中' and s['dist'] < 5:
        print(f"  {s['code']} {s['name']}: 距上轨{s['dist']:+.1f}%，注意突破")

print("\n" + "=" * 70)
print(f"复盘完成 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 70)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""更新2026-06-01数据 + 生成复盘"""
import json, os
from datetime import datetime

DATA_DIR = r"D:\QClaw_Trading\data\history"
today_str = "2026-06-01"

# 今日实时行情
TODAY = {
    '159902': {'close': 4.935, 'prev': 5.022, 'chg': -1.73},
    '160723': {'close': 2.164, 'prev': 2.108, 'chg': +2.66},
    '161128': {'close': 7.445, 'prev': 7.038, 'chg': +5.78},
}

print("=" * 70)
print("更新ETF数据：2026-06-01 (周一)")
print("=" * 70)

# 第一步：更新数据文件
for code, d in TODAY.items():
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            records = data.get('records', [])
            
            # 检查今日是否已存在
            found = False
            for r in records:
                if r['date'] == today_str:
                    r['close'] = d['close']
                    r['change_pct'] = d['chg']
                    r['change'] = round(d['close'] - d['prev'], 3)
                    found = True
                    break
            
            if not found:
                new_rec = {
                    'date': today_str,
                    'open': d['prev'],
                    'close': d['close'],
                    'high': max(d['prev'], d['close']),
                    'low': min(d['prev'], d['close']),
                    'vol': 0, 'amount': 0,
                    'change': round(d['close'] - d['prev'], 3),
                    'change_pct': d['chg']
                }
                records.append(new_rec)
            
            records.sort(key=lambda x: x['date'])
            data['records'] = records
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✓ {code}: 更新 {today_str} close={d['close']:.3f} ({d['chg']:+.2f}%)")
            break

print()

# 第二步：计算布林带并生成复盘
def calc_bb(records, window=20, num_std=2):
    if len(records) < window:
        return None, None, None
    closes = [r['close'] for r in records[-window:]]
    ma = sum(closes) / len(closes)
    std = (sum((x - ma)**2 for x in closes) / len(closes)) ** 0.5
    return ma, ma + num_std * std, ma - num_std * std

ETF_LIST = [
    ("159902", "中小100ETF华夏"),
    ("160723", "嘉实原油LOF"),
    ("161128", "标普信息科技LOF"),
]

print("=" * 70)
print("ETF波段策略 - 每日复盘")
print("日期: 2026-06-01 (周一)")
print("=" * 70)

print("\n今日行情汇总:")
print(f"{'代码':<10} {'名称':<15} {'今收':<8} {'涨跌':<8} {'MA20':<8} {'上轨':<8} {'下轨':<8} {'距上轨':<8} {'信号'}")
print("-" * 90)

signals = []
for code, name in ETF_LIST:
    records = None
    for prefix in ['sz', 'sh']:
        path = os.path.join(DATA_DIR, f'{prefix}{code}.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                records = json.load(f).get('records', [])
            break
    
    if not records or len(records) < 20:
        print(f"{code:<10} {name:<15} 数据不足")
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
        sig = "▲ 突破买入"
    elif yesterday >= lower and close < lower:
        sig = "▼ 跌破卖出"
    else:
        sig = "持有中"
    
    print(f"{code:<10} {name:<15} {close:<8.3f} {chg:>+7.2f}%  {ma:<8.3f} {upper:<8.3f} {lower:<8.3f} {dist:>+7.1f}%   {sig}")
    
    signals.append({
        'code': code, 'name': name, 'close': close, 'chg': chg,
        'ma': ma, 'upper': upper, 'lower': lower, 'dist': dist, 'signal': sig,
        'yesterday': yesterday
    })

# 虚拟盘状态
print("\n" + "=" * 70)
print("虚拟盘状态")
print("=" * 70)

s128 = next((s for s in signals if s['code'] == '161128'), None)
if s128:
    buy_price = 6.979
    current = s128['close']
    pnl = (current - buy_price) / buy_price * 100
    stop_loss = buy_price * 0.94
    take_profit = buy_price * 1.10
    
    print(f"持仓: 161128 标普信息科技LOF")
    print(f"买入日期: 2026-05-27")
    print(f"买入价: {buy_price}")
    print(f"今日收盘: {current:.3f}")
    print(f"持仓盈亏: {pnl:+.2f}%")
    print(f"止损线: {stop_loss:.3f} (跌破即卖)")
    print(f"止盈线: {take_profit:.3f} (达到即卖)")
    
    # 持仓检查
    print(f"\n持仓检查:")
    print(f"  今日收盘 {current:.3f} vs 上轨 {s128['upper']:.3f}")
    if current > s128['upper']:
        print(f"  ✓ 收盘 > 上轨，继续持有")
    elif current <= stop_loss:
        print(f"  🔴 触发止损！建议卖出")
    elif current >= take_profit:
        print(f"  🟢 触发止盈！建议卖出")
    else:
        print(f"  → 继续持有")
    
    # 距止盈线距离
    dist_tp = (take_profit - current) / current * 100
    print(f"\n  距止盈线: {dist_tp:+.1f}% ({take_profit:.3f} - {current:.3f})")
    if dist_tp < 5:
        print(f"  🟢🟢🟢 距止盈线仅{dist_tp:.1f}%，随时可能触发！")

# 操作建议
print("\n" + "=" * 70)
print("操作建议")
print("=" * 70)

if s128:
    buy_price = 6.979
    current = s128['close']
    stop_loss = buy_price * 0.94
    take_profit = buy_price * 1.10
    
    dist_tp = (take_profit - current) / current * 100
    
    print(f"161128持仓: ", end="")
    if current > s128['upper']:
        print("✓ 收盘突破上轨，继续持有")
    elif current <= stop_loss:
        print("🔴 触发止损，立即卖出！")
    elif current >= take_profit:
        print("🟢 触发止盈，卖出获利！")
    else:
        print("继续持有")
    
    print(f"  止损线: {stop_loss:.3f} (距当前 {(current-stop_loss)/current*100:+.1f}%)")
    print(f"  止盈线: {take_profit:.3f} (距当前 {dist_tp:+.1f}%)")
    
    if dist_tp < 5:
        print(f"\n  🟢🟢🟢 预警：距止盈线仅{dist_tp:.1f}%，明日可能触发止盈！")

print("\n明日关注:")
for s in signals:
    if s['signal'] == '持有中' and s['dist'] < 5:
        print(f"  {s['code']} {s['name']}: 距上轨{s['dist']:+.1f}%，注意突破")

print("\n" + "=" * 70)
print(f"复盘完成 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 70)

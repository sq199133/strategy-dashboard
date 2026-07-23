#!/usr/bin/env python3
"""
虚拟盘模拟 - 501225全球芯片LOF
策略: 布林带突破 + 趋势突破
"""
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime

data_dir = r"D:\QClaw_Trading\data\history"

def load_etf(code):
    for prefix in ['sh', 'sz']:
        path = os.path.join(data_dir, f"{prefix}{code}.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if 'records' in data:
                    df = pd.DataFrame(data['records'])
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date')
                    df['close'] = df['close'].astype(float)
                    df['high'] = df['high'].astype(float)
                    df['low'] = df['low'].astype(float)
                    df['open'] = df['open'].astype(float)
                    return df
            except:
                pass
    return None

# 加载数据
df = load_etf('501225')
if df is None:
    print("数据加载失败")
    exit()

print("=" * 80)
print("虚拟盘模拟 - 501225 全球芯片LOF T+1")
print("策略: 布林带突破 + 趋势突破")
print("=" * 80)

# 计算指标
df['ma20'] = df['close'].rolling(20).mean()
df['std20'] = df['close'].rolling(20).std()
df['bb_upper'] = df['ma20'] + 2 * df['std20']
df['bb_lower'] = df['ma20'] - 2 * df['std20']
df['high_20'] = df['high'].rolling(20).max()
df['low_20'] = df['low'].rolling(20).min()

# ATR止损
df['tr'] = np.maximum(
    df['high'] - df['low'],
    np.abs(df['close'] - df['close'].shift(1))
)
df['atr'] = df['tr'].rolling(14).mean()

# 从2024年开始模拟
start_date = '2024-01-01'
df_sim = df[df['date'] >= start_date].copy()
df_sim = df_sim.reset_index(drop=True)

print(f"\n模拟期间: {df_sim['date'].iloc[0].strftime('%Y-%m-%d')} 至 {df_sim['date'].iloc[-1].strftime('%Y-%m-%d')}")
print(f"初始资金: 100,000元")
print(f"止损线: -8%")

# 虚拟盘交易记录
initial_capital = 100000
cash = initial_capital
position = 0  # 持有份额
shares = 0
entry_price = 0
trades = []

for i in range(25, len(df_sim)):
    date = df_sim['date'].iloc[i]
    close = df_sim['close'].iloc[i]
    high = df_sim['high'].iloc[i]
    low = df_sim['low'].iloc[i]
    bb_u = df_sim['bb_upper'].iloc[i-1]
    bb_l = df_sim['bb_lower'].iloc[i-1]
    high20 = df_sim['high_20'].iloc[i-1]
    low20 = df_sim['low_20'].iloc[i-1]
    atr = df_sim['atr'].iloc[i]
    
    prev_close = df_sim['close'].iloc[i-1]
    prev_bb_u = df_sim['bb_upper'].iloc[i-1]
    prev_bb_l = df_sim['bb_lower'].iloc[i-1]
    prev_high20 = df_sim['high_20'].iloc[i-1]
    prev_low20 = df_sim['low_20'].iloc[i-1]
    
    # 买入信号: 布林带上轨突破 或 20日高点突破
    if shares == 0:
        buy_signal = (prev_close <= prev_bb_u and close > bb_u) or \
                     (prev_close <= prev_high20 and close > high20)
        if buy_signal:
            # 买入
            shares = int(cash / close * 0.95)  # 留5%手续费
            entry_price = close
            cash = cash - shares * close
            stop_loss = close * 0.92  # 8%止损
            trades.append({
                'date': date.strftime('%Y-%m-%d'),
                'action': '买入',
                'price': round(close, 3),
                'shares': shares,
                'amount': round(shares * close, 2),
                'signal': '布林带突破' if prev_close <= prev_bb_u else '趋势突破'
            })
    
    # 持仓中
    else:
        # 止损检查
        if close < stop_loss:
            # 止损卖出
            cash = cash + shares * close
            ret = (close / entry_price - 1) * 100
            trades.append({
                'date': date.strftime('%Y-%m-%d'),
                'action': '止损卖出',
                'price': round(close, 3),
                'shares': shares,
                'amount': round(shares * close, 2),
                'return': round(ret, 2)
            })
            shares = 0
            entry_price = 0
        
        # 止盈检查
        elif close > entry_price * 1.15:
            # 止盈卖出
            cash = cash + shares * close
            ret = (close / entry_price - 1) * 100
            trades.append({
                'date': date.strftime('%Y-%m-%d'),
                'action': '止盈卖出',
                'price': round(close, 3),
                'shares': shares,
                'amount': round(shares * close, 2),
                'return': round(ret, 2)
            })
            shares = 0
            entry_price = 0
        
        # 卖出信号: 布林带下轨跌破 或 20日低点跌破
        else:
            sell_signal = (prev_close >= prev_bb_l and close < bb_l) or \
                         (prev_close >= prev_low20 and close < low20)
            if sell_signal:
                cash = cash + shares * close
                ret = (close / entry_price - 1) * 100
                trades.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'action': '卖出',
                    'price': round(close, 3),
                    'shares': shares,
                    'amount': round(shares * close, 2),
                    'return': round(ret, 2)
                })
                shares = 0
                entry_price = 0

# 最终结算
final_value = cash + shares * df_sim['close'].iloc[-1]
total_return = (final_value / initial_capital - 1) * 100

print(f"\n最终资金: {final_value:,.2f}元")
print(f"总收益: {total_return:+.2f}%")

# 统计
completed_trades = [t for t in trades if 'return' in t]
wins = [t for t in completed_trades if t['return'] > 0]
losses = [t for t in completed_trades if t['return'] <= 0]

print(f"\n交易统计:")
print(f"总交易次数: {len(completed_trades)}")
print(f"盈利次数: {len(wins)}")
print(f"亏损次数: {len(losses)}")
if completed_trades:
    print(f"胜率: {len(wins)/len(completed_trades)*100:.1f}%")
    print(f"平均收益: {np.mean([t['return'] for t in completed_trades]):.2f}%")
    print(f"最大单次盈利: {max([t['return'] for t in completed_trades]):.2f}%")
    print(f"最大单次亏损: {min([t['return'] for t in completed_trades]):.2f}%")

print("\n" + "=" * 80)
print("交易记录")
print("=" * 80)

for t in trades:
    if t['action'] == '买入':
        print(f"{t['date']}  [{t['signal']}] {t['action']} {t['shares']}股 @{t['price']:.3f} = {t['amount']:,.0f}元")
    elif 'return' in t:
        print(f"{t['date']}  {t['action']} {t['shares']}股 @{t['price']:.3f} = {t['amount']:,.0f}元  收益:{t['return']:+.2f}%")
    else:
        print(f"{t['date']}  {t['action']} {t['shares']}股 @{t['price']:.3f} = {t['amount']:,.0f}元")

# 保存结果
result = {
    'etf': '501225',
    'name': '全球芯片LOF T+1',
    'strategy': '布林带突破+趋势突破',
    'period': f"{df_sim['date'].iloc[0].strftime('%Y-%m-%d')} to {df_sim['date'].iloc[-1].strftime('%Y-%m-%d')}",
    'initial_capital': initial_capital,
    'final_value': round(final_value, 2),
    'total_return': round(total_return, 2),
    'total_trades': len(completed_trades),
    'win_trades': len(wins),
    'loss_trades': len(losses),
    'win_rate': round(len(wins)/len(completed_trades)*100, 1) if completed_trades else 0,
    'trades': trades
}

with open(r"D:\QClaw_Trading\data\virtual_portfolio_501225.json", 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n虚拟盘结果已保存")
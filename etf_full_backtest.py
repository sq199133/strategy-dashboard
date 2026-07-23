#!/usr/bin/env python3
"""
ETF全量波段策略回测 - 所有高波动ETF
"""
import json
import os
import pandas as pd
import numpy as np

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
                    return df
            except:
                pass
    return None

def ma_cross(df, short=5, long=20):
    df = df.copy()
    df['ma_s'] = df['close'].rolling(short).mean()
    df['ma_l'] = df['close'].rolling(long).mean()
    
    trades = []
    in_pos = False
    entry_price = 0
    
    for i in range(long, len(df)):
        if not in_pos:
            if df['ma_s'].iloc[i] > df['ma_l'].iloc[i] and df['ma_s'].iloc[i-1] <= df['ma_l'].iloc[i-1]:
                in_pos = True
                entry_price = df['close'].iloc[i]
        else:
            if df['ma_s'].iloc[i] < df['ma_l'].iloc[i] and df['ma_s'].iloc[i-1] >= df['ma_l'].iloc[i-1]:
                ret = (df['close'].iloc[i] / entry_price - 1) * 100
                trades.append(ret)
                in_pos = False
    
    if trades:
        arr = np.array(trades)
        return {'trades': len(trades), 'win_rate': (arr > 0).mean() * 100, 'avg': arr.mean(), 'total': arr.sum()}
    return None

def bollinger(df, window=20, std=2):
    df = df.copy()
    df['ma'] = df['close'].rolling(window).mean()
    df['std'] = df['close'].rolling(window).std()
    df['upper'] = df['ma'] + std * df['std']
    df['lower'] = df['ma'] - std * df['std']
    
    trades = []
    in_pos = False
    entry_price = 0
    
    for i in range(window, len(df)):
        if not in_pos:
            if df['close'].iloc[i] > df['upper'].iloc[i-1]:
                in_pos = True
                entry_price = df['close'].iloc[i]
        else:
            if df['close'].iloc[i] < df['lower'].iloc[i-1]:
                ret = (df['close'].iloc[i] / entry_price - 1) * 100
                trades.append(ret)
                in_pos = False
    
    if trades:
        arr = np.array(trades)
        return {'trades': len(trades), 'win_rate': (arr > 0).mean() * 100, 'avg': arr.mean(), 'total': arr.sum()}
    return None

def breakout(df, lookback=20):
    df = df.copy()
    df['high_20'] = df['high'].rolling(lookback).max()
    df['low_20'] = df['low'].rolling(lookback).min()
    
    trades = []
    in_pos = False
    entry_price = 0
    
    for i in range(lookback, len(df)):
        if not in_pos:
            if df['close'].iloc[i] > df['high_20'].iloc[i-1]:
                in_pos = True
                entry_price = df['close'].iloc[i]
        else:
            if df['close'].iloc[i] < df['low_20'].iloc[i-1]:
                ret = (df['close'].iloc[i] / entry_price - 1) * 100
                trades.append(ret)
                in_pos = False
    
    if trades:
        arr = np.array(trades)
        return {'trades': len(trades), 'win_rate': (arr > 0).mean() * 100, 'avg': arr.mean(), 'total': arr.sum()}
    return None

# 加载波动性数据
vol_df = pd.read_csv(r"D:\QClaw_Trading\data\etf_volatility_real.csv")

# 筛选高波动ETF (>25%)
high_vol = vol_df[vol_df['annual_vol'] > 25].copy()
print(f"高波动ETF (>25%): {len(high_vol)} 只\n")

# 对每只ETF回测所有策略
results = []
for _, row in high_vol.iterrows():
    code = row['code']
    name = row['name']
    vol = row['annual_vol']
    
    df = load_etf(code)
    if df is None or len(df) < 120:
        continue
    
    ma = ma_cross(df)
    bb = bollinger(df)
    bo = breakout(df)
    
    results.append({
        'code': code,
        'name': name,
        'vol': vol,
        'ma_trades': ma['trades'] if ma else 0,
        'ma_win': ma['win_rate'] if ma else 0,
        'ma_avg': ma['avg'] if ma else 0,
        'ma_total': ma['total'] if ma else 0,
        'bb_trades': bb['trades'] if bb else 0,
        'bb_win': bb['win_rate'] if bb else 0,
        'bb_avg': bb['avg'] if bb else 0,
        'bb_total': bb['total'] if bb else 0,
        'bo_trades': bo['trades'] if bo else 0,
        'bo_win': bo['win_rate'] if bo else 0,
        'bo_avg': bo['avg'] if bo else 0,
        'bo_total': bo['total'] if bo else 0,
    })

df_res = pd.DataFrame(results)
print(f"完成回测: {len(df_res)} 只ETF\n")

# 按策略收益排序显示最佳
print("=" * 100)
print("【均线交叉策略】Top 15 (按总收益)")
print("=" * 100)
top_ma = df_res[df_res['ma_trades'] >= 5].nlargest(15, 'ma_total')
for _, r in top_ma.iterrows():
    print(f"{r['code']:<8} {r['name'][:15]:<15} 波动:{r['vol']:.1f}% | 交易:{r['ma_trades']:>3}次 胜率:{r['ma_win']:>5.1f}% 平均:{r['ma_avg']:>6.2f}% 总收益:{r['ma_total']:>7.1f}%")

print("\n" + "=" * 100)
print("【布林带策略】Top 15 (按总收益)")
print("=" * 100)
top_bb = df_res[df_res['bb_trades'] >= 3].nlargest(15, 'bb_total')
for _, r in top_bb.iterrows():
    print(f"{r['code']:<8} {r['name'][:15]:<15} 波动:{r['vol']:.1f}% | 交易:{r['bb_trades']:>3}次 胜率:{r['bb_win']:>5.1f}% 平均:{r['bb_avg']:>6.2f}% 总收益:{r['bb_total']:>7.1f}%")

print("\n" + "=" * 100)
print("【趋势突破策略】Top 15 (按总收益)")
print("=" * 100)
top_bo = df_res[df_res['bo_trades'] >= 3].nlargest(15, 'bo_total')
for _, r in top_bo.iterrows():
    print(f"{r['code']:<8} {r['name'][:15]:<15} 波动:{r['vol']:.1f}% | 交易:{r['bo_trades']:>3}次 胜率:{r['bo_win']:>5.1f}% 平均:{r['bo_avg']:>6.2f}% 总收益:{r['bo_total']:>7.1f}%")

# 保存
df_res.to_csv(r"D:\QClaw_Trading\data\etf_full_backtest.csv", index=False, encoding="utf-8-sig")
print(f"\n完整回测结果已保存: etf_full_backtest.csv")
#!/usr/bin/env python3
"""
ETF波段策略回测
"""
import json
import os
import pandas as pd
import numpy as np

data_dir = r"D:\QClaw_Trading\data\history"

def load_etf(code):
    """加载ETF数据"""
    # 查找文件
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

# ==================== 策略 ====================

def ma_cross(df, short_ma=5, long_ma=20):
    """均线交叉策略"""
    df = df.copy()
    df['ma_s'] = df['close'].rolling(short_ma).mean()
    df['ma_l'] = df['close'].rolling(long_ma).mean()
    
    trades = []
    in_pos = False
    entry_price = 0
    
    for i in range(long_ma, len(df)):
        if not in_pos:
            if df['ma_s'].iloc[i] > df['ma_l'].iloc[i] and df['ma_s'].iloc[i-1] <= df['ma_l'].iloc[i-1]:
                in_pos = True
                entry_price = df['close'].iloc[i]
                entry_date = df['date'].iloc[i]
        else:
            if df['ma_s'].iloc[i] < df['ma_l'].iloc[i] and df['ma_s'].iloc[i-1] >= df['ma_l'].iloc[i-1]:
                ret = (df['close'].iloc[i] / entry_price - 1) * 100
                trades.append({
                    'entry': str(entry_date.date()),
                    'exit': str(df['date'].iloc[i].date()),
                    'return_pct': ret
                })
                in_pos = False
    
    if trades:
        df_t = pd.DataFrame(trades)
        return {
            'trades': len(trades),
            'win_rate': (df_t['return_pct'] > 0).sum() / len(trades) * 100,
            'avg_return': df_t['return_pct'].mean(),
            'total_return': ((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100
        }
    return {'trades': 0}

def bollinger(df, window=20, std_dev=2):
    """布林带突破"""
    df = df.copy()
    df['ma'] = df['close'].rolling(window).mean()
    df['std'] = df['close'].rolling(window).std()
    df['upper'] = df['ma'] + std_dev * df['std']
    df['lower'] = df['ma'] - std_dev * df['std']
    
    trades = []
    in_pos = False
    entry_price = 0
    
    for i in range(window, len(df)):
        if not in_pos:
            if df['close'].iloc[i] > df['upper'].iloc[i-1]:
                in_pos = True
                entry_price = df['close'].iloc[i]
                entry_date = df['date'].iloc[i]
        else:
            if df['close'].iloc[i] < df['lower'].iloc[i-1]:
                ret = (df['close'].iloc[i] / entry_price - 1) * 100
                trades.append({
                    'entry': str(entry_date.date()),
                    'exit': str(df['date'].iloc[i].date()),
                    'return_pct': ret
                })
                in_pos = False
    
    if trades:
        df_t = pd.DataFrame(trades)
        return {
            'trades': len(trades),
            'win_rate': (df_t['return_pct'] > 0).sum() / len(trades) * 100,
            'avg_return': df_t['return_pct'].mean()
        }
    return {'trades': 0}

def breakout(df, lookback=20):
    """趋势突破"""
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
                entry_date = df['date'].iloc[i]
        else:
            if df['close'].iloc[i] < df['low_20'].iloc[i-1]:
                ret = (df['close'].iloc[i] / entry_price - 1) * 100
                trades.append({
                    'entry': str(entry_date.date()),
                    'exit': str(df['date'].iloc[i].date()),
                    'return_pct': ret
                })
                in_pos = False
    
    if trades:
        df_t = pd.DataFrame(trades)
        return {
            'trades': len(trades),
            'win_rate': (df_t['return_pct'] > 0).sum() / len(trades) * 100,
            'avg_return': df_t['return_pct'].mean()
        }
    return {'trades': 0}

# ==================== 回测 ====================

# 高波动ETF列表
high_vol_codes = ['159995','159206','159773','562500','159108','562570','159819','159107','588020','588220']
etf_names = {
    '159995': '芯片ETF', '159206': '卫星ETF', '159773': '创业板科技ETF',
    '562500': '机器人ETF', '159108': '工业软件ETF', '562570': '信创ETF',
    '159819': '人工智能ETF', '159107': '创业板软件ETF', '588020': '科创成长ETF', '588220': '科创100ETF'
}

print("="*80)
print("ETF波段策略回测结果")
print("="*80)

results = []
for code in high_vol_codes:
    df = load_etf(code)
    if df is None or len(df) < 120:
        continue
    
    name = etf_names.get(code, code)
    
    # 各策略回测
    ma_result = ma_cross(df)
    bb_result = bollinger(df)
    bo_result = breakout(df)
    
    results.append({
        'code': code,
        'name': name,
        'ma_trades': ma_result.get('trades', 0),
        'ma_win': ma_result.get('win_rate', 0),
        'ma_avg': ma_result.get('avg_return', 0),
        'bb_trades': bb_result.get('trades', 0),
        'bb_win': bb_result.get('win_rate', 0),
        'bb_avg': bb_result.get('avg_return', 0),
        'bo_trades': bo_result.get('trades', 0),
        'bo_win': bo_result.get('win_rate', 0),
        'bo_avg': bo_result.get('avg_return', 0),
    })

df_res = pd.DataFrame(results)
print("\n均线交叉策略:")
print(df_res[['code','name','ma_trades','ma_win','ma_avg']].to_string(index=False))

print("\n布林带突破:")
print(df_res[['code','name','bb_trades','bb_win','bb_avg']].to_string(index=False))

print("\n趋势突破:")
print(df_res[['code','name','bo_trades','bo_win','bo_avg']].to_string(index=False))

# 保存
df_res.to_csv(r"D:\QClaw_Trading\data\etf_backtest_results.csv", index=False, encoding="utf-8-sig")
print("\n回测结果已保存")
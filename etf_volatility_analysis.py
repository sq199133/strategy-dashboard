#!/usr/bin/env python3
"""
ETF波动性分析与波段策略回测
"""
import requests
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime, timedelta

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 尝试导入tushare，失败则用akshare
try:
    import tushare as ts
    HAS_TUSHARE = True
except:
    HAS_TUSHARE = False

try:
    import akshare as ak
    HAS_AKSHARE = True
except:
    HAS_AKSHARE = False

def get_etf_hist_ak(code, days=250):
    """使用akshare获取ETF历史数据"""
    try:
        # 转换ETF代码格式
        if code.startswith('5') or code.startswith('1'):
            symbol = f"sh{code}"
        else:
            symbol = f"sz{code}"
        
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=(datetime.now() - timedelta(days=days+30)).strftime("%Y%m%d"), 
                                end_date=datetime.now().strftime("%Y%m%d"), adjust="qfq")
        if df is not None and len(df) > 30:
            df = df.rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low', '成交量': 'volume', '成交额': 'amount'
            })
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            return df
    except Exception as e:
        print(f"获取{code}失败: {e}")
    return None

def fetch_all_etf_volatility(etf_list, top_n=30):
    """获取所有ETF的波动性指标"""
    results = []
    
    for i, etf in enumerate(etf_list):
        code = etf['code']
        name = etf['name']
        
        print(f"[{i+1}/{len(etf_list)}] 获取 {code} {name}...")
        
        df = get_etf_hist_ak(code, days=250)
        
        if df is not None and len(df) > 60:
            # 计算波动性指标
            df['daily_return'] = df['close'].pct_change()
            
            # 年化波动率
            annual_vol = df['daily_return'].std() * np.sqrt(252) * 100
            
            # 平均真实波幅 ATR
            df['tr'] = np.maximum(
                df['high'] - df['low'],
                np.maximum(
                    abs(df['high'] - df['close'].shift(1)),
                    abs(df['low'] - df['close'].shift(1))
                )
            )
            atr_pct = (df['tr'].rolling(14).mean() / df['close'].rolling(14).mean() * 100).iloc[-1]
            
            # 价格波动范围
            price_range = (df['close'].max() - df['close'].min()) / df['close'].min() * 100
            
            # 近20日最大回撤
            df['cummax'] = df['close'].cummax()
            df['drawdown'] = (df['close'] - df['cummax']) / df['cummax']
            max_drawdown = df['drawdown'].min() * 100
            
            results.append({
                'code': code,
                'name': name,
                'category': etf.get('category', ''),
                'annual_vol': round(annual_vol, 2),
                'atr_pct': round(atr_pct, 2),
                'price_range_250d': round(price_range, 2),
                'max_drawdown': round(max_drawdown, 2),
                'close': df['close'].iloc[-1],
                'volume_20d': df['volume'].rolling(20).mean().iloc[-1]
            })
        
        time.sleep(0.15)  # 避免请求过快
    
    return pd.DataFrame(results)

# 波段策略
def strategy_ma_cross(df, short_ma=5, long_ma=20, stop_loss_pct=5):
    """均线交叉策略"""
    df = df.copy()
    df['ma5'] = df['close'].rolling(short_ma).mean()
    df['ma20'] = df['close'].rolling(long_ma).mean()
    
    trades = []
    position = None
    entry_price = 0
    
    for i in range(long_ma, len(df)):
        if i < len(df):
            # 金叉买入
            if df['ma5'].iloc[i-1] <= df['ma20'].iloc[i-1] and df['ma5'].iloc[i] > df['ma20'].iloc[i]:
                if position is None:
                    position = 1
                    entry_price = df['close'].iloc[i]
                    entry_date = df['date'].iloc[i]
            
            # 死叉卖出或止损
            elif position == 1:
                if df['ma5'].iloc[i] < df['ma20'].iloc[i] or (entry_price > 0 and (df['close'].iloc[i] / entry_price - 1) * 100 < -stop_loss_pct):
                    exit_price = df['close'].iloc[i]
                    exit_date = df['date'].iloc[i]
                    ret = (exit_price / entry_price - 1) * 100
                    trades.append({
                        'entry_date': entry_date, 'exit_date': exit_date,
                        'entry': entry_price, 'exit': exit_price,
                        'return_pct': ret
                    })
                    position = None
    
    if trades:
        df_trades = pd.DataFrame(trades)
        return {
            'total_trades': len(trades),
            'win_rate': len(df_trades[df_trades['return_pct'] > 0]) / len(trades) * 100,
            'avg_return': df_trades['return_pct'].mean(),
            'max_return': df_trades['return_pct'].max(),
            'min_return': df_trades['return_pct'].min(),
            'trades': trades
        }
    return {'total_trades': 0}

def strategy_bollinger(df, window=20, std_dev=2):
    """布林带突破策略"""
    df = df.copy()
    df['ma'] = df['close'].rolling(window).mean()
    df['std'] = df['close'].rolling(window).std()
    df['upper'] = df['ma'] + std_dev * df['std']
    df['lower'] = df['ma'] - std_dev * df['std']
    
    trades = []
    position = None
    entry_price = 0
    
    for i in range(window, len(df)):
        if position is None:
            # 突破上轨买入
            if df['close'].iloc[i] > df['upper'].iloc[i-1]:
                position = 1
                entry_price = df['close'].iloc[i]
                entry_date = df['date'].iloc[i]
        else:
            # 跌破下轨卖出
            if df['close'].iloc[i] < df['lower'].iloc[i-1]:
                exit_price = df['close'].iloc[i]
                exit_date = df['date'].iloc[i]
                ret = (exit_price / entry_price - 1) * 100
                trades.append({
                    'entry_date': entry_date, 'exit_date': exit_date,
                    'entry': entry_price, 'exit': exit_price,
                    'return_pct': ret
                })
                position = None
    
    if trades:
        df_trades = pd.DataFrame(trades)
        return {
            'total_trades': len(trades),
            'win_rate': len(df_trades[df_trades['return_pct'] > 0]) / len(trades) * 100,
            'avg_return': df_trades['return_pct'].mean(),
            'trades': trades
        }
    return {'total_trades': 0}

def strategy_rsi(df, period=14, oversold=30, overbought=70):
    """RSI超买超卖策略"""
    df = df.copy()
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    trades = []
    position = None
    entry_price = 0
    
    for i in range(period, len(df)):
        rsi = df['rsi'].iloc[i]
        rsi_prev = df['rsi'].iloc[i-1]
        
        if position is None:
            if rsi_prev < oversold and rsi >= oversold:
                position = 1
                entry_price = df['close'].iloc[i]
                entry_date = df['date'].iloc[i]
        else:
            if rsi_prev > overbought and rsi <= overbought:
                exit_price = df['close'].iloc[i]
                exit_date = df['date'].iloc[i]
                ret = (exit_price / entry_price - 1) * 100
                trades.append({
                    'entry_date': entry_date, 'exit_date': exit_date,
                    'entry': entry_price, 'exit': exit_price,
                    'return_pct': ret
                })
                position = None
    
    if trades:
        df_trades = pd.DataFrame(trades)
        return {
            'total_trades': len(trades),
            'win_rate': len(df_trades[df_trades['return_pct'] > 0]) / len(trades) * 100,
            'avg_return': df_trades['return_pct'].mean(),
            'trades': trades
        }
    return {'total_trades': 0}

def strategy_breakout(df, lookback=20, atr_mult=2):
    """价格突破策略"""
    df = df.copy()
    df['high_20'] = df['high'].rolling(lookback).max()
    df['low_20'] = df['low'].rolling(lookback).min()
    
    # ATR for stop loss
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['atr'] = df['tr'].rolling(14).mean()
    
    trades = []
    position = None
    entry_price = 0
    stop_loss = 0
    
    for i in range(lookback, len(df)):
        if position is None:
            if df['close'].iloc[i] > df['high_20'].iloc[i-1]:
                position = 1
                entry_price = df['close'].iloc[i]
                entry_date = df['date'].iloc[i]
                stop_loss = entry_price - atr_mult * df['atr'].iloc[i]
        else:
            # 止损
            if df['close'].iloc[i] < stop_loss:
                exit_price = stop_loss
                exit_date = df['date'].iloc[i]
                ret = (exit_price / entry_price - 1) * 100
                trades.append({
                    'entry_date': entry_date, 'exit_date': exit_date,
                    'entry': entry_price, 'exit': exit_price,
                    'return_pct': ret
                })
                position = None
            # 跌破20日最低卖出
            elif df['close'].iloc[i] < df['low_20'].iloc[i-1]:
                exit_price = df['close'].iloc[i]
                exit_date = df['date'].iloc[i]
                ret = (exit_price / entry_price - 1) * 100
                trades.append({
                    'entry_date': entry_date, 'exit_date': exit_date,
                    'entry': entry_price, 'exit': exit_price,
                    'return_pct': ret
                })
                position = None
    
    if trades:
        df_trades = pd.DataFrame(trades)
        return {
            'total_trades': len(trades),
            'win_rate': len(df_trades[df_trades['return_pct'] > 0]) / len(trades) * 100,
            'avg_return': df_trades['return_pct'].mean(),
            'trades': trades
        }
    return {'total_trades': 0}

def run_backtest(code, strategies=['ma_cross', 'bollinger', 'rsi', 'breakout']):
    """对单个ETF运行回测"""
    df = get_etf_hist_ak(code, days=500)
    if df is None or len(df) < 120:
        return None
    
    results = {}
    for strat in strategies:
        if strat == 'ma_cross':
            results[strat] = strategy_ma_cross(df)
        elif strat == 'bollinger':
            results[strat] = strategy_bollinger(df)
        elif strat == 'rsi':
            results[strat] = strategy_rsi(df)
        elif strat == 'breakout':
            results[strat] = strategy_breakout(df)
    
    return results

if __name__ == "__main__":
    # 加载ETF列表
    with open(r"D:\QClaw_Trading\data\etf_pool_V1_full.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    etf_list = data['data']
    
    print(f"共{len(etf_list)}只ETF，开始获取数据...")
    
    # 获取波动性数据
    vol_df = fetch_all_etf_volatility(etf_list)
    
    if len(vol_df) > 0:
        # 按年化波动率排序，筛选高波动ETF
        vol_df = vol_df.sort_values('annual_vol', ascending=False)
        
        print("\n=== 高波动ETF Top 30 ===")
        print(vol_df[['code','name','annual_vol','atr_pct','price_range_250d','max_drawdown']].head(30).to_string())
        
        # 保存结果
        vol_df.to_csv(r"D:\QClaw_Trading\data\etf_volatility.csv", index=False, encoding="utf-8-sig")
        print("\n波动性数据已保存到 etf_volatility.csv")
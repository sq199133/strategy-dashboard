# -*- coding: utf-8 -*-
"""
基于市场整体PE的择时策略
使用A股市场整体PE数据进行择时
"""

import json
import pandas as pd
import numpy as np
import os
from datetime import datetime

# 配置
PE_DATA_FILE = 'D:/QClaw_Trading/data/pe_data/a_market_pe.json'
ETF_DATA_DIR = 'D:/QClaw_Trading/data/history_long'
OUTPUT_DIR = 'D:/QClaw_Trading/backtest_results'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 策略参数
PERCENTILE_WINDOW = 252  # 1年窗口
TRANSACTION_COST = 0.0003  # 万三

def load_pe_data():
    """加载市场整体PE数据"""
    with open(PE_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df['pe'] = pd.to_numeric(df['pe'], errors='coerce')
    df = df.sort_values('date').reset_index(drop=True)
    return df

def calculate_percentile(series, window):
    """计算滚动分位数"""
    def rank_percentile(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        rank = (x[:-1] <= current).sum()
        return rank / (len(x) - 1) * 100
    
    return series.rolling(window=window, min_periods=window//2).apply(rank_percentile)

def generate_position_signal(percentile_series):
    """生成仓位信号（Sigmoid平滑）"""
    def sigmoid(x):
        return 1 / (1 + np.exp(x))
    
    # 将分位数转换为平滑仓位
    # 分位50%时仓位50%，分位低仓位高
    positions = percentile_series.apply(lambda x: sigmoid((x - 50) / 15) if pd.notna(x) else np.nan)
    return positions

def load_etf_data(etf_code):
    """加载ETF历史数据"""
    # 构建文件名
    if etf_code.startswith('5'):
        filename = f"sh{etf_code}.json"
    elif etf_code.startswith('1'):
        filename = f"sz{etf_code}.json"
    else:
        filename = f"sh{etf_code}.json"
    
    filepath = os.path.join(ETF_DATA_DIR, filename)
    
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if 'records' in data:
        df = pd.DataFrame(data['records'])
    else:
        df = pd.DataFrame(data)
    
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    return df

def run_backtest(pe_df, etf_df, strategy_name):
    """运行回测"""
    # 合并数据（按月对齐，因为PE是月度数据）
    pe_monthly = pe_df.copy()
    pe_monthly['year_month'] = pe_monthly['date'].dt.to_period('M')
    pe_monthly = pe_monthly.groupby('year_month').last().reset_index()
    
    # 计算PE分位
    pe_monthly['pe_percentile'] = calculate_percentile(pe_monthly['pe'], PERCENTILE_WINDOW)
    
    # 生成仓位信号
    pe_monthly['target_position'] = generate_position_signal(pe_monthly['pe_percentile'])
    
    # ETF数据按月聚合
    etf_df['year_month'] = etf_df['date'].dt.to_period('M')
    etf_monthly = etf_df.groupby('year_month').agg({
        'open': 'first',
        'close': 'last',
        'high': 'max',
        'low': 'min',
        'vol': 'sum'
    }).reset_index()
    
    # 合并
    merged = pd.merge(pe_monthly[['year_month', 'date', 'pe', 'pe_percentile', 'target_position']], 
                      etf_monthly, 
                      on='year_month', 
                      how='inner')
    
    if len(merged) < 10:
        return None
    
    # 计算收益
    merged['returns'] = merged['close'].pct_change()
    
    # 策略仓位（使用上一期信号）
    merged['position'] = merged['target_position'].shift(1)
    merged['position_change'] = merged['position'].diff().abs()
    
    # 策略收益
    merged['strategy_returns'] = merged['returns'] * merged['position']
    merged['strategy_returns'] -= merged['position_change'] * TRANSACTION_COST
    
    # 累计收益
    merged['cum_returns'] = (1 + merged['returns'].fillna(0)).cumprod()
    merged['strategy_cum_returns'] = (1 + merged['strategy_returns'].fillna(0)).cumprod()
    
    # 计算指标
    benchmark_return = merged['cum_returns'].iloc[-1] - 1
    strategy_return = merged['strategy_cum_returns'].iloc[-1] - 1
    
    n_years = len(merged) / 12
    benchmark_annual = (merged['cum_returns'].iloc[-1]) ** (1/n_years) - 1
    strategy_annual = (merged['strategy_cum_returns'].iloc[-1]) ** (1/n_years) - 1
    
    benchmark_vol = merged['returns'].std() * np.sqrt(12)
    strategy_vol = merged['strategy_returns'].std() * np.sqrt(12)
    
    rf = 0.02
    benchmark_sharpe = (benchmark_annual - rf) / benchmark_vol if benchmark_vol > 0 else 0
    strategy_sharpe = (strategy_annual - rf) / strategy_vol if strategy_vol > 0 else 0
    
    # 最大回撤
    def max_dd(cum):
        peak = cum.expanding(min_periods=1).max()
        dd = (cum - peak) / peak
        return dd.min()
    
    benchmark_dd = max_dd(merged['cum_returns'])
    strategy_dd = max_dd(merged['strategy_cum_returns'])
    
    trades = (merged['position_change'] > 0.05).sum()
    
    results = {
        'strategy': strategy_name,
        'period': f"{merged['date'].iloc[0].strftime('%Y-%m')} to {merged['date'].iloc[-1].strftime('%Y-%m')}",
        'months': len(merged),
        'benchmark': {
            'total_return': f"{benchmark_return:.2%}",
            'annual_return': f"{benchmark_annual:.2%}",
            'volatility': f"{benchmark_vol:.2%}",
            'sharpe': f"{benchmark_sharpe:.2f}",
            'max_drawdown': f"{benchmark_dd:.2%}"
        },
        'strategy': {
            'total_return': f"{strategy_return:.2%}",
            'annual_return': f"{strategy_annual:.2%}",
            'volatility': f"{strategy_vol:.2%}",
            'sharpe': f"{strategy_sharpe:.2f}",
            'max_drawdown': f"{strategy_dd:.2%}",
            'trades': int(trades)
        },
        'excess_return': f"{strategy_annual - benchmark_annual:.2%}",
        'current_pe': float(merged['pe'].iloc[-1]),
        'current_percentile': f"{merged['pe_percentile'].iloc[-1]:.1f}%",
        'current_position': f"{merged['target_position'].iloc[-1]:.0%}"
    }
    
    return results

def main():
    print("=" * 60)
    print("市场整体PE择时策略回测")
    print("=" * 60)
    
    # 加载PE数据
    print("\nLoading market PE data...")
    pe_df = load_pe_data()
    print(f"PE data range: {pe_df['date'].min().strftime('%Y-%m-%d')} to {pe_df['date'].max().strftime('%Y-%m-%d')}")
    print(f"Records: {len(pe_df)}")
    
    # 测试几个代表性ETF
    test_etfs = [
        ('510300', 'HS300 ETF'),
        ('510500', 'ZZ500 ETF'),
        ('512100', 'ZZ1000 ETF'),
    ]
    
    results_list = []
    
    for etf_code, etf_name in test_etfs:
        print(f"\nBacktesting {etf_name} ({etf_code})...")
        
        etf_df = load_etf_data(etf_code)
        
        if etf_df is None:
            print(f"  [FAIL] ETF data not found")
            continue
        
        result = run_backtest(pe_df, etf_df, etf_name)
        
        if result:
            results_list.append(result)
            print(f"  [OK] Period: {result['period']}")
            print(f"       Strategy Return: {result['strategy']['total_return']}")
            print(f"       Sharpe: {result['strategy']['sharpe']}")
            print(f"       Max DD: {result['strategy']['max_drawdown']}")
        else:
            print(f"  [FAIL] Insufficient data")
    
    # 保存结果
    output_file = os.path.join(OUTPUT_DIR, 'pe_strategy_backtest.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results_list, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print("Backtest Summary")
    print("=" * 60)
    
    for r in results_list:
        print(f"\n{r['strategy']}:")
        print(f"  Period: {r['period']}")
        print(f"  Benchmark Return: {r['benchmark']['total_return']} (Sharpe: {r['benchmark']['sharpe']})")
        print(f"  Strategy Return:  {r['strategy']['total_return']} (Sharpe: {r['strategy']['sharpe']})")
        print(f"  Excess Return: {r['excess_return']}")
        print(f"  Max Drawdown: {r['strategy']['max_drawdown']}")
        print(f"  Trades: {r['strategy']['trades']}")
    
    print(f"\n\nCurrent Market Status:")
    print(f"  PE: {results_list[0]['current_pe']:.2f}")
    print(f"  Percentile: {results_list[0]['current_percentile']}")
    print(f"  Suggested Position: {results_list[0]['current_position']}")
    
    print(f"\n\nResults saved to: {output_file}")

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
PE择时策略优化版
优化方向：
1. 参数优化 - 测试不同分位阈值
2. 趋势过滤 - 加入均线判断
3. 多周期分位 - 短期+长期分位结合
4. 动态仓位 - 根据信号强度调整
"""

import json
import pandas as pd
import numpy as np
import os
from datetime import datetime
from itertools import product

# 配置
PE_DATA_FILE = 'D:/QClaw_Trading/data/pe_data/a_market_pe.json'
ETF_DATA_DIR = 'D:/QClaw_Trading/data/history_long'
OUTPUT_DIR = 'D:/QClaw_Trading/backtest_results'
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRANSACTION_COST = 0.0003

# ==================== 数据加载 ====================

def load_pe_data():
    """加载市场PE数据"""
    with open(PE_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df['pe'] = pd.to_numeric(df['pe'], errors='coerce')
    df = df.sort_values('date').reset_index(drop=True)
    return df

def load_etf_data(etf_code):
    """加载ETF数据"""
    if etf_code.startswith('5'):
        filename = f"sh{etf_code}.json"
    else:
        filename = f"sz{etf_code}.json"
    
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

# ==================== 指标计算 ====================

def calc_percentile(series, window):
    """计算滚动分位数"""
    def rank_pct(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        rank = (x[:-1] <= current).sum()
        return rank / (len(x) - 1) * 100
    
    return series.rolling(window=window, min_periods=window//2).apply(rank_pct)

def calc_ma(prices, window):
    """计算移动平均"""
    return prices.rolling(window=window).mean()

def calc_volatility(returns, window):
    """计算波动率"""
    return returns.rolling(window=window).std() * np.sqrt(252)

# ==================== 策略信号生成 ====================

def signal_threshold(pe_pct, low=20, high=80):
    """阈值策略"""
    if pe_pct <= low:
        return 1.0
    elif pe_pct >= high:
        return 0.0
    elif pe_pct <= 30:
        return 0.8
    elif pe_pct <= 50:
        return 0.5
    elif pe_pct <= 70:
        return 0.3
    else:
        return 0.1

def signal_sigmoid(pe_pct, center=50, steepness=10):
    """Sigmoid策略"""
    x = (pe_pct - center) / steepness
    return 1 / (1 + np.exp(x))

def signal_linear(pe_pct):
    """线性策略"""
    return max(0, min(1, (100 - pe_pct) / 100))

def signal_with_trend(pe_pct, price, ma_short, ma_long):
    """趋势过滤策略"""
    base_position = signal_sigmoid(pe_pct)
    
    # 趋势过滤
    if pd.notna(ma_short) and pd.notna(ma_long):
        if ma_short > ma_long:
            # 上升趋势，增强仓位
            trend_factor = 1.2
        else:
            # 下降趋势，降低仓位
            trend_factor = 0.8
        base_position *= trend_factor
    
    return max(0, min(1, base_position))

def signal_multi_pe(pe_pct_short, pe_pct_long, weight_short=0.6):
    """多周期分位策略"""
    signal_short = signal_sigmoid(pe_pct_short)
    signal_long = signal_sigmoid(pe_pct_long)
    return weight_short * signal_short + (1 - weight_short) * signal_long

def signal_conservative(pe_pct, volatility):
    """波动率调整策略"""
    base = signal_sigmoid(pe_pct)
    
    # 波动率高时降低仓位
    if pd.notna(volatility):
        if volatility > 0.25:
            vol_factor = 0.7
        elif volatility > 0.20:
            vol_factor = 0.85
        else:
            vol_factor = 1.0
        base *= vol_factor
    
    return max(0, min(1, base))

# ==================== 回测框架 ====================

def prepare_monthly_data(pe_df, etf_df):
    """准备月度数据"""
    # PE按月聚合
    pe_df = pe_df.copy()
    pe_df['year_month'] = pe_df['date'].dt.to_period('M')
    pe_monthly = pe_df.groupby('year_month').agg({
        'date': 'last',
        'pe': 'last'
    }).reset_index()
    
    # ETF按月聚合
    etf_df = etf_df.copy()
    etf_df['year_month'] = etf_df['date'].dt.to_period('M')
    etf_monthly = etf_df.groupby('year_month').agg({
        'open': 'first',
        'close': 'last',
        'high': 'max',
        'low': 'min'
    }).reset_index()
    
    # 合并
    merged = pd.merge(pe_monthly, etf_monthly, on='year_month', how='inner')
    merged = merged.rename(columns={'date_x': 'date'})
    
    return merged

def backtest_strategy(merged, signal_func, **kwargs):
    """运行回测"""
    merged = merged.copy()
    
    # 计算分位数
    merged['pe_pct_1y'] = calc_percentile(merged['pe'], 12)
    merged['pe_pct_3y'] = calc_percentile(merged['pe'], 36)
    
    # 计算均线（用月度close）
    merged['ma_3m'] = calc_ma(merged['close'], 3)
    merged['ma_6m'] = calc_ma(merged['close'], 6)
    
    # 计算波动率
    merged['returns'] = merged['close'].pct_change()
    merged['volatility'] = calc_volatility(merged['returns'], 6)
    
    # 生成信号
    signals = []
    for i, row in merged.iterrows():
        pe_pct = row['pe_pct_1y']
        if pd.isna(pe_pct):
            signals.append(np.nan)
            continue
        
        try:
            signal = signal_func(row, **kwargs)
            signals.append(signal)
        except:
            signals.append(np.nan)
    
    merged['target_position'] = signals
    
    # 仓位滞后一期
    merged['position'] = merged['target_position'].shift(1)
    merged['position_change'] = merged['position'].diff().abs()
    
    # 计算收益
    merged['returns'] = merged['close'].pct_change()
    merged['strategy_returns'] = merged['returns'] * merged['position']
    merged['strategy_returns'] -= merged['position_change'] * TRANSACTION_COST
    
    # 累计收益
    merged['cum_returns'] = (1 + merged['returns'].fillna(0)).cumprod()
    merged['strategy_cum_returns'] = (1 + merged['strategy_returns'].fillna(0)).cumprod()
    
    return merged

def calc_metrics(merged):
    """计算回测指标"""
    valid = merged.dropna(subset=['position', 'returns'])
    
    if len(valid) < 10:
        return None
    
    # 基本指标
    benchmark_return = merged['cum_returns'].iloc[-1] - 1
    strategy_return = merged['strategy_cum_returns'].iloc[-1] - 1
    
    n_months = len(valid)
    n_years = n_months / 12
    
    benchmark_annual = (merged['cum_returns'].iloc[-1]) ** (1/n_years) - 1
    strategy_annual = (merged['strategy_cum_returns'].iloc[-1]) ** (1/n_years) - 1
    
    # 波动率（月度转年化）
    benchmark_vol = valid['returns'].std() * np.sqrt(12)
    strategy_vol = valid['strategy_returns'].std() * np.sqrt(12)
    
    # 夏普比率
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
    
    # 交易次数
    trades = (merged['position_change'] > 0.05).sum()
    
    return {
        'total_return': strategy_return,
        'annual_return': strategy_annual,
        'volatility': strategy_vol,
        'sharpe': strategy_sharpe,
        'max_drawdown': strategy_dd,
        'trades': trades,
        'benchmark_return': benchmark_return,
        'benchmark_sharpe': benchmark_sharpe,
        'excess_return': strategy_annual - benchmark_annual
    }

# ==================== 策略测试 ====================

def test_strategies(pe_df, etf_code, etf_name):
    """测试多种策略"""
    etf_df = load_etf_data(etf_code)
    if etf_df is None:
        return None
    
    merged = prepare_monthly_data(pe_df, etf_df)
    
    results = []
    
    # 策略1: 基准Sigmoid
    r = backtest_strategy(merged, lambda row: signal_sigmoid(row['pe_pct_1y']))
    m = calc_metrics(r)
    if m:
        m['strategy'] = 'Baseline_Sigmoid'
        results.append(m)
    
    # 策略2: 阈值策略 - 不同参数
    for low, high in [(15, 85), (20, 80), (25, 75)]:
        r = backtest_strategy(merged, lambda row: signal_threshold(row['pe_pct_1y'], low, high))
        m = calc_metrics(r)
        if m:
            m['strategy'] = f'Threshold_{low}_{high}'
            results.append(m)
    
    # 策略3: 多周期分位
    r = backtest_strategy(merged, lambda row: signal_multi_pe(
        row['pe_pct_1y'], row['pe_pct_3y'] if pd.notna(row.get('pe_pct_3y')) else row['pe_pct_1y']
    ))
    m = calc_metrics(r)
    if m:
        m['strategy'] = 'Multi_Period'
        results.append(m)
    
    # 策略4: 趋势过滤
    r = backtest_strategy(merged, lambda row: signal_with_trend(
        row['pe_pct_1y'], row['close'], row['ma_3m'], row['ma_6m']
    ))
    m = calc_metrics(r)
    if m:
        m['strategy'] = 'Trend_Filter'
        results.append(m)
    
    # 策略5: 波动率调整
    r = backtest_strategy(merged, lambda row: signal_conservative(row['pe_pct_1y'], row['volatility']))
    m = calc_metrics(r)
    if m:
        m['strategy'] = 'Vol_Adjusted'
        results.append(m)
    
    # 策略6: Sigmoid不同参数
    for center, steepness in [(40, 8), (50, 10), (60, 12)]:
        r = backtest_strategy(merged, lambda row: signal_sigmoid(row['pe_pct_1y'], center, steepness))
        m = calc_metrics(r)
        if m:
            m['strategy'] = f'Sigmoid_{center}_{steepness}'
            results.append(m)
    
    # 添加ETF信息
    for m in results:
        m['etf'] = etf_name
    
    return results

def main():
    print("=" * 70)
    print("PE择时策略优化测试")
    print("=" * 70)
    
    # 加载数据
    print("\nLoading data...")
    pe_df = load_pe_data()
    print(f"PE data: {len(pe_df)} records, {pe_df['date'].min().strftime('%Y-%m')} to {pe_df['date'].max().strftime('%Y-%m')}")
    
    # 测试ETF
    test_etfs = [
        ('510300', 'HS300'),
        ('510500', 'ZZ500'),
        ('512100', 'ZZ1000'),
    ]
    
    all_results = []
    
    for etf_code, etf_name in test_etfs:
        print(f"\nTesting {etf_name} ({etf_code})...")
        results = test_strategies(pe_df, etf_code, etf_name)
        if results:
            all_results.extend(results)
    
    # 汇总结果
    df_results = pd.DataFrame(all_results)
    
    # 按超额收益排序
    df_results = df_results.sort_values('excess_return', ascending=False)
    
    # 保存结果
    output_file = os.path.join(OUTPUT_DIR, 'pe_strategy_optimization.json')
    df_results.to_json(output_file, orient='records', indent=2, force_ascii=False)
    
    print("\n" + "=" * 70)
    print("优化结果汇总")
    print("=" * 70)
    
    # 显示Top 10
    print("\nTop 10策略（按超额收益）:\n")
    
    top10 = df_results.head(10)
    
    for i, row in top10.iterrows():
        print(f"{row['etf']:8} | {row['strategy']:20} | "
              f"收益: {row['annual_return']:6.2%} | "
              f"夏普: {row['sharpe']:5.2f} | "
              f"超额: {row['excess_return']:+5.2%} | "
              f"回撤: {row['max_drawdown']:6.2%}")
    
    # 按ETF分组最佳策略
    print("\n\n各ETF最佳策略:\n")
    
    for etf in df_results['etf'].unique():
        etf_best = df_results[df_results['etf'] == etf].iloc[0]
        print(f"{etf:8} | {etf_best['strategy']:20} | "
              f"收益: {etf_best['annual_return']:6.2%} | "
              f"夏普: {etf_best['sharpe']:5.2f} | "
              f"超额: {etf_best['excess_return']:+5.2%}")
    
    print(f"\n\n详细结果已保存到: {output_file}")

if __name__ == "__main__":
    main()

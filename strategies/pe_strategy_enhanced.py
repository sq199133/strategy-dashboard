# -*- coding: utf-8 -*-
"""
PE择时策略增强版
核心改进：极端估值择时 + 趋势跟随
"""

import json
import pandas as pd
import numpy as np
import os

# 配置
PE_DATA_FILE = 'D:/QClaw_Trading/data/pe_data/a_market_pe.json'
ETF_DATA_DIR = 'D:/QClaw_Trading/data/history_long'
OUTPUT_DIR = 'D:/QClaw_Trading/backtest_results'
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRANSACTION_COST = 0.0003

def load_pe_data():
    with open(PE_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df['pe'] = pd.to_numeric(df['pe'], errors='coerce')
    df = df.sort_values('date').reset_index(drop=True)
    return df

def load_etf_data(etf_code):
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

def calc_percentile(series, window):
    def rank_pct(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        rank = (x[:-1] <= current).sum()
        return rank / (len(x) - 1) * 100
    return series.rolling(window=window, min_periods=window//2).apply(rank_pct)

def prepare_data(pe_df, etf_df):
    """准备对齐的数据（日度）"""
    pe_df = pe_df.copy()
    
    # PE数据扩展到日度（向前填充）
    pe_daily = pe_df.set_index('date')['pe'].resample('D').ffill().reset_index()
    pe_daily = pe_daily.rename(columns={'pe': 'market_pe'})
    
    # 合并
    merged = pd.merge(etf_df[['date', 'open', 'close', 'high', 'low']], 
                      pe_daily, on='date', how='inner')
    merged = merged.sort_values('date').reset_index(drop=True)
    
    # 计算指标
    merged['pe_pct'] = calc_percentile(merged['market_pe'], 252)
    merged['returns'] = merged['close'].pct_change()
    merged['ma_20'] = merged['close'].rolling(20).mean()
    merged['ma_60'] = merged['close'].rolling(60).mean()
    merged['ma_120'] = merged['close'].rolling(120).mean()
    merged['vol_20'] = merged['returns'].rolling(20).std() * np.sqrt(252)
    
    return merged

# ==================== 增强策略 ====================

def strategy_extreme_only(row):
    """
    策略1: 极端估值择时
    只在极端估值时操作，其他时间满仓
    """
    pe_pct = row['pe_pct']
    
    if pd.isna(pe_pct):
        return 1.0
    
    # 只在极端情况减仓
    if pe_pct >= 90:
        return 0.0  # 极高估，清仓
    elif pe_pct >= 80:
        return 0.3  # 高估，轻仓
    elif pe_pct <= 10:
        return 1.5  # 极低估，杠杆（如果允许）
    elif pe_pct <= 20:
        return 1.2  # 低估，加仓
    else:
        return 1.0  # 正常，满仓

def strategy_trend_follow(row):
    """
    策略2: 趋势跟随为主，估值保护
    正常时间跟随趋势，极端估值时强制减仓
    """
    pe_pct = row['pe_pct']
    close = row['close']
    ma_20 = row['ma_20']
    ma_60 = row['ma_60']
    
    if pd.isna(pe_pct) or pd.isna(ma_20) or pd.isna(ma_60):
        return 1.0
    
    # 趋势判断
    trend_up = (ma_20 > ma_60)
    
    # 基础仓位
    if trend_up:
        base = 1.0
    else:
        base = 0.5
    
    # 极端估值调整
    if pe_pct >= 85:
        base *= 0.3  # 强制大幅减仓
    elif pe_pct >= 70:
        base *= 0.6  # 适度减仓
    elif pe_pct <= 15:
        base = min(1.5, base * 1.3)  # 低估加仓
    
    return base

def strategy_contrarian(row):
    """
    策略3: 逆向投资
    低估值加仓，高估值减仓，但配合波动率
    """
    pe_pct = row['pe_pct']
    vol = row['vol_20']
    
    if pd.isna(pe_pct):
        return 1.0
    
    # 波动率调整
    if pd.notna(vol):
        vol_adj = min(1.0, 0.20 / vol) if vol > 0.15 else 1.0
    else:
        vol_adj = 1.0
    
    # 分段仓位
    if pe_pct <= 15:
        position = 1.3
    elif pe_pct <= 30:
        position = 1.1
    elif pe_pct <= 50:
        position = 1.0
    elif pe_pct <= 70:
        position = 0.8
    elif pe_pct <= 85:
        position = 0.5
    else:
        position = 0.2
    
    return position * vol_adj

def strategy_momentum_pe(row):
    """
    策略4: PE动量策略
    PE下降时加仓（估值修复），PE上升时减仓（估值扩张）
    """
    pe_pct = row['pe_pct']
    close = row['close']
    ma_20 = row['ma_20']
    
    if pd.isna(pe_pct):
        return 1.0
    
    # 趋势基础
    if pd.notna(ma_20):
        trend = 1.0 if close > ma_20 else 0.5
    else:
        trend = 1.0
    
    # 估值分位
    if pe_pct <= 20:
        base = 1.2
    elif pe_pct <= 50:
        base = 1.0
    elif pe_pct <= 75:
        base = 0.7
    else:
        base = 0.4
    
    return base * trend

def strategy_hybrid(row):
    """
    策略5: 混合策略
    趋势 + 估值 + 波动率 三因子
    """
    pe_pct = row['pe_pct']
    close = row['close']
    ma_20 = row['ma_20']
    ma_60 = row['ma_60']
    vol = row['vol_20']
    
    if pd.isna(pe_pct):
        return 1.0
    
    # 因子1: 估值分数 (0-100)
    if pe_pct <= 20:
        val_score = 100
    elif pe_pct <= 40:
        val_score = 80
    elif pe_pct <= 60:
        val_score = 50
    elif pe_pct <= 80:
        val_score = 30
    else:
        val_score = 10
    
    # 因子2: 趋势分数 (0-100)
    if pd.notna(ma_20) and pd.notna(ma_60):
        if close > ma_20 > ma_60:
            trend_score = 100
        elif close > ma_20:
            trend_score = 70
        elif ma_20 > ma_60:
            trend_score = 50
        else:
            trend_score = 30
    else:
        trend_score = 50
    
    # 因子3: 波动率分数 (0-100)
    if pd.notna(vol):
        if vol <= 0.15:
            vol_score = 100
        elif vol <= 0.20:
            vol_score = 80
        elif vol <= 0.25:
            vol_score = 60
        else:
            vol_score = 40
    else:
        vol_score = 70
    
    # 综合评分 (加权平均)
    total_score = val_score * 0.4 + trend_score * 0.35 + vol_score * 0.25
    
    # 转换为仓位 (0-1.2)
    position = total_score / 100 * 1.2
    
    return max(0.1, min(1.2, position))

# ==================== 回测框架 ====================

def run_backtest(merged, signal_func, strategy_name):
    """执行回测"""
    merged = merged.copy()
    
    # 生成信号
    signals = []
    for i, row in merged.iterrows():
        try:
            sig = signal_func(row)
            signals.append(sig)
        except:
            signals.append(np.nan)
    
    merged['target_pos'] = signals
    
    # 仓位执行（T+1）
    merged['position'] = merged['target_pos'].shift(1)
    
    # 限制仓位范围
    merged['position'] = merged['position'].clip(0, 1.5)
    
    # 仓位变化
    merged['pos_change'] = merged['position'].diff().abs()
    
    # 计算收益
    merged['strategy_ret'] = merged['returns'] * merged['position']
    merged['strategy_ret'] -= merged['pos_change'] * TRANSACTION_COST
    
    # 累计收益
    merged['cum_ret'] = (1 + merged['returns'].fillna(0)).cumprod()
    merged['strategy_cum'] = (1 + merged['strategy_ret'].fillna(0)).cumprod()
    
    # 计算指标
    valid = merged.dropna(subset=['position', 'returns'])
    
    if len(valid) < 50:
        return None
    
    n_days = len(valid)
    n_years = n_days / 252
    
    bench_ret = merged['cum_ret'].iloc[-1] - 1
    strat_ret = merged['strategy_cum'].iloc[-1] - 1
    
    bench_ann = (merged['cum_ret'].iloc[-1]) ** (1/n_years) - 1
    strat_ann = (merged['strategy_cum'].iloc[-1]) ** (1/n_years) - 1
    
    bench_vol = valid['returns'].std() * np.sqrt(252)
    strat_vol = valid['strategy_ret'].std() * np.sqrt(252)
    
    rf = 0.02
    bench_sharpe = (bench_ann - rf) / bench_vol if bench_vol > 0 else 0
    strat_sharpe = (strat_ann - rf) / strat_vol if strat_vol > 0 else 0
    
    # 最大回撤
    def max_dd(cum):
        peak = cum.expanding(min_periods=1).max()
        dd = (cum - peak) / peak
        return dd.min()
    
    bench_dd = max_dd(merged['cum_ret'])
    strat_dd = max_dd(merged['strategy_cum'])
    
    trades = (merged['pos_change'] > 0.05).sum()
    
    return {
        'strategy': strategy_name,
        'period': f"{merged['date'].iloc[0].strftime('%Y-%m')} to {merged['date'].iloc[-1].strftime('%Y-%m')}",
        'days': n_days,
        'bench_return': f"{bench_ret:.2%}",
        'bench_sharpe': f"{bench_sharpe:.2f}",
        'bench_dd': f"{bench_dd:.2%}",
        'strat_return': f"{strat_ret:.2%}",
        'strat_ann': f"{strat_ann:.2%}",
        'strat_sharpe': f"{strat_sharpe:.2f}",
        'strat_dd': f"{strat_dd:.2%}",
        'excess': f"{strat_ann - bench_ann:+.2%}",
        'trades': int(trades)
    }

def main():
    print("=" * 70)
    print("PE择时策略增强版 - 极端估值 + 趋势跟随")
    print("=" * 70)
    
    # 加载数据
    print("\nLoading data...")
    pe_df = load_pe_data()
    print(f"PE data: {len(pe_df)} records")
    
    # 测试ETF
    test_etfs = [
        ('510300', 'HS300'),
        ('510500', 'ZZ500'),
        ('512100', 'ZZ1000'),
    ]
    
    strategies = [
        (strategy_extreme_only, 'Extreme_Valuation'),
        (strategy_trend_follow, 'Trend_with_PE'),
        (strategy_contrarian, 'Contrarian'),
        (strategy_momentum_pe, 'PE_Momentum'),
        (strategy_hybrid, 'Hybrid_3Factor'),
    ]
    
    all_results = []
    
    for etf_code, etf_name in test_etfs:
        print(f"\nTesting {etf_name} ({etf_code})...")
        
        etf_df = load_etf_data(etf_code)
        if etf_df is None:
            print(f"  [FAIL] ETF data not found")
            continue
        
        merged = prepare_data(pe_df, etf_df)
        print(f"  Data range: {merged['date'].min().strftime('%Y-%m-%d')} to {merged['date'].max().strftime('%Y-%m-%d')}")
        print(f"  Records: {len(merged)}")
        
        for signal_func, strategy_name in strategies:
            result = run_backtest(merged, signal_func, strategy_name)
            if result:
                result['etf'] = etf_name
                all_results.append(result)
                print(f"  {strategy_name:20} | Excess: {result['excess']}")
    
    # 汇总结果
    df_results = pd.DataFrame(all_results)
    df_results = df_results.sort_values('excess', ascending=False)
    
    # 保存
    output_file = os.path.join(OUTPUT_DIR, 'pe_strategy_enhanced.json')
    df_results.to_json(output_file, orient='records', indent=2, force_ascii=False)
    
    print("\n" + "=" * 70)
    print("增强策略结果汇总")
    print("=" * 70)
    
    print("\nTop 15策略:\n")
    
    for i, row in df_results.head(15).iterrows():
        print(f"{row['etf']:8} | {row['strategy']:20} | "
              f"收益: {row['strat_ann']:7} | "
              f"夏普: {row['strat_sharpe']:5} | "
              f"超额: {row['excess']:+6} | "
              f"回撤: {row['strat_dd']:7}")
    
    print(f"\n\n详细结果: {output_file}")

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
股债性价比 + 趋势综合策略回测
==================================
策略思路：
  1. 估值极端时，忽略趋势（避免踏空或深套）
  2. 估值中性时，参考趋势（顺势而为）
  3. 加入波动率过滤（高波动时谨慎）

综合方案：
  A. 层级优先级（Layered Priority）
  B. 加权综合评分（Weighted Score）
  C. 动态权重（Dynamic Weight）
  D. 信号确认（Signal Confirmation）
"""

import akshare as ak
import pandas as pd
import numpy as np
import json
import os
import time
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ETF_DATA_DIR = 'D:/QClaw_Trading/data/history_long'
OUTPUT_DIR = 'D:/QClaw_Trading/backtest_results'
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRANSACTION_COST = 0.0003


# ==================== 数据获取 ====================

def fetch_index_pe(symbol_name):
    """获取指数PE数据"""
    print(f"  Fetching PE: {symbol_name}...")
    df = ak.stock_index_pe_lg(symbol=symbol_name)
    col_map = {
        df.columns[0]: 'date',
        df.columns[1]: 'index_value',
        df.columns[6]: 'ttm_pe',
    }
    df = df.rename(columns=col_map)
    df['date'] = pd.to_datetime(df['date'])
    df['ttm_pe'] = pd.to_numeric(df['ttm_pe'], errors='coerce')
    df['index_value'] = pd.to_numeric(df['index_value'], errors='coerce')
    df = df.dropna(subset=['date', 'ttm_pe', 'index_value'])
    df = df.sort_values('date').reset_index(drop=True)
    return df[['date', 'index_value', 'ttm_pe']]


def fetch_bond_yield():
    """获取10年期国债收益率"""
    print("  Fetching 10Y bond yield...")
    df = ak.bond_zh_us_rate()
    col_map = {df.columns[0]: 'date', df.columns[3]: 'yield_10y'}
    df = df.rename(columns=col_map)[['date', 'yield_10y']]
    df['date'] = pd.to_datetime(df['date'])
    df['yield_10y'] = pd.to_numeric(df['yield_10y'], errors='coerce')
    df = df.dropna(subset=['date', 'yield_10y'])
    df = df.sort_values('date').reset_index(drop=True)
    return df


def build_data(pe_df, bond_df):
    """构建综合数据"""
    merged = pd.merge(pe_df, bond_df, on='date', how='inner')
    merged['earnings_yield'] = 1.0 / merged['ttm_pe']
    merged['bond_yield'] = merged['yield_10y'] / 100
    merged['eb_spread'] = merged['earnings_yield'] - merged['bond_yield']

    # 估值分位（3年滚动）
    merged['val_pct'] = calc_rolling_pct(merged['eb_spread'], 756)

    # 趋势指标
    merged['ma_20'] = merged['index_value'].rolling(20).mean()
    merged['ma_60'] = merged['index_value'].rolling(60).mean()
    merged['ma_120'] = merged['index_value'].rolling(120).mean()
    merged['ma_250'] = merged['index_value'].rolling(250).mean()

    # 趋势方向
    merged['trend_short'] = (merged['ma_20'] > merged['ma_60']).astype(float)
    merged['trend_mid'] = (merged['ma_60'] > merged['ma_120']).astype(float)
    merged['trend_long'] = (merged['ma_120'] > merged['ma_250']).astype(float)

    # 综合趋势评分 (0-100)
    merged['trend_score'] = (merged['trend_short'] * 40 +
                              merged['trend_mid'] * 35 +
                              merged['trend_long'] * 25) * 100

    # 动量（20日收益率）
    merged['momentum'] = merged['index_value'].pct_change(20)
    merged['momentum_score'] = pd.cut(merged['momentum'],
                                        bins=[-np.inf, -0.05, -0.02, 0, 0.02, 0.05, np.inf],
                                        labels=[0, 20, 40, 60, 80, 100]).astype(float)

    # 波动率（20日波动率）
    merged['returns'] = merged['index_value'].pct_change()
    merged['vol_20'] = merged['returns'].rolling(20).std() * np.sqrt(252)
    merged['vol_score'] = pd.cut(merged['vol_20'],
                                  bins=[0, 0.15, 0.20, 0.25, 0.30, np.inf],
                                  labels=[100, 75, 50, 25, 0]).astype(float)

    return merged.dropna(subset=['val_pct', 'returns'])


def calc_rolling_pct(series, window=756):
    """计算滚动分位数"""
    def rank_pct(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        rank = (x.iloc[:-1] <= current).sum()
        return rank / (len(x) - 1) * 100
    return series.rolling(window=window, min_periods=window//2).apply(rank_pct)


# ==================== 综合策略 ====================

def strategy_lp(row):
    """
    方案A：层级优先级（Layered Priority）
    - 估值极端（分位>90%或<10%）→ 忽略趋势
    - 估值中性（30-70%）→ 参考趋势
    """
    val_pct = row['val_pct']
    trend_score = row['trend_score']

    if pd.isna(val_pct):
        return 0.5

    # 第一优先级：估值
    if val_pct >= 90:
        return 1.0  # 极度便宜，满仓
    elif val_pct <= 10:
        return 0.0  # 极度昂贵，空仓

    # 第二优先级：趋势（只在估值中性时）
    if pd.isna(trend_score):
        return 0.5

    if val_pct >= 70:
        # 偏便宜，趋势向上加仓，向下保守
        return 0.8 if trend_score >= 50 else 0.6
    elif val_pct >= 30:
        # 中性，完全参考趋势
        return trend_score / 100
    elif val_pct >= 20:
        # 偏贵，趋势向上谨慎参与，向下减仓
        return 0.4 if trend_score >= 50 else 0.2
    else:
        # 较贵，轻仓
        return 0.2 if trend_score >= 50 else 0.0


def strategy_ws(row):
    """
    方案B：加权综合评分（Weighted Score）
    - 估值评分（50%）+ 趋势评分（30%）+ 波动率评分（20%）
    """
    val_pct = row['val_pct']
    trend_score = row['trend_score']
    vol_score = row['vol_score']

    if pd.isna(val_pct):
        return 0.5

    # 估值评分（分位越高=越便宜=评分越高）
    val_score = val_pct  # 直接使用分位作为评分

    # 综合评分
    scores = []
    weights = []

    if pd.notna(val_score):
        scores.append(val_score)
        weights.append(0.50)

    if pd.notna(trend_score):
        scores.append(trend_score)
        weights.append(0.30)

    if pd.notna(vol_score):
        scores.append(vol_score)
        weights.append(0.20)

    if len(scores) == 0:
        return 0.5

    # 加权平均
    total_score = np.average(scores, weights=weights)

    # 转换为仓位（0-1）
    position = total_score / 100
    return max(0.0, min(1.0, position))


def strategy_dw(row):
    """
    方案C：动态权重（Dynamic Weight）
    - 高波动时，估值权重提高
    - 强趋势时，趋势权重提高
    """
    val_pct = row['val_pct']
    trend_score = row['trend_score']
    vol_20 = row['vol_20']

    if pd.isna(val_pct):
        return 0.5

    # 动态权重
    if pd.notna(vol_20):
        if vol_20 >= 0.25:
            w_val, w_trend, w_vol = 0.60, 0.20, 0.20
        elif vol_20 >= 0.20:
            w_val, w_trend, w_vol = 0.50, 0.30, 0.20
        else:
            w_val, w_trend, w_vol = 0.40, 0.40, 0.20
    else:
        w_val, w_trend, w_vol = 0.50, 0.30, 0.20

    # 评分
    val_score = val_pct
    t_score = trend_score if pd.notna(trend_score) else 50
    v_score = 100 - min(100, vol_20 * 200) if pd.notna(vol_20) else 50

    total = val_score * w_val + t_score * w_trend + v_score * w_vol
    position = total / 100
    return max(0.0, min(1.0, position))


def strategy_sc(row):
    """
    方案D：信号确认（Signal Confirmation）
    - 只有估值和趋势同时发出信号才操作
    """
    val_pct = row['val_pct']
    trend_score = row['trend_score']

    if pd.isna(val_pct):
        return 0.5

    # 估值信号
    val_signal = 'buy' if val_pct >= 60 else ('sell' if val_pct <= 40 else 'neutral')

    # 趋势信号
    if pd.notna(trend_score):
        trend_signal = 'buy' if trend_score >= 60 else ('sell' if trend_score <= 40 else 'neutral')
    else:
        trend_signal = 'neutral'

    # 信号确认
    if val_signal == 'buy' and trend_signal == 'buy':
        return 1.0
    elif val_signal == 'sell' and trend_signal == 'sell':
        return 0.0
    elif val_signal == 'buy' and trend_signal == 'neutral':
        return 0.7
    elif val_signal == 'neutral' and trend_signal == 'buy':
        return 0.7
    elif val_signal == 'sell' and trend_signal == 'neutral':
        return 0.3
    elif val_signal == 'neutral' and trend_signal == 'sell':
        return 0.3
    else:
        return 0.5


def strategy_lp_v2(row):
    """
    方案A改进版：加入动量和更细分的档次
    """
    val_pct = row['val_pct']
    trend_score = row['trend_score']
    momentum = row['momentum_score']

    if pd.isna(val_pct):
        return 0.5

    # 极致估值：忽略一切
    if val_pct >= 95:
        return 1.0
    elif val_pct <= 5:
        return 0.0

    # 很端估值：估值为主，趋势微调
    if val_pct >= 80:
        base = 0.9
        adjustment = (trend_score - 50) / 100 * 0.2 if pd.notna(trend_score) else 0
        return max(0.7, min(1.0, base + adjustment))
    elif val_pct <= 20:
        base = 0.1
        adjustment = (trend_score - 50) / 100 * 0.2 if pd.notna(trend_score) else 0
        return max(0.0, min(0.3, base + adjustment))

    # 中性估值：趋势为主
    if pd.notna(trend_score):
        return trend_score / 100
    else:
        return 0.5


def strategy_momentum_value(row):
    """
    方案E：估值+动量（Value-Momentum）
    - 低估值+正动量 → 强买入
    - 高估值+负动量 → 强卖出
    """
    val_pct = row['val_pct']
    momentum = row['momentum_score']

    if pd.isna(val_pct):
        return 0.5

    val_score = val_pct / 100
    mom_score = momentum / 100 if pd.notna(momentum) else 0.5

    # 综合（估值和动量同等重要）
    score = val_score * 0.5 + mom_score * 0.5
    return max(0.0, min(1.0, score))


# ==================== 回测框架 ====================

def backtest(df, signal_func, strategy_name, start_year=2015):
    """执行回测"""
    df = df.copy()
    df = df.set_index('date')

    if start_year:
        df = df[df.index.year >= start_year]

    if len(df) < 100:
        return None

    # 生成信号
    df['target_pos'] = df.apply(signal_func, axis=1)

    # T+1执行
    df['position'] = df['target_pos'].shift(1)
    df['pos_change'] = df['position'].diff().abs()

    # 收益计算
    df['strategy_ret'] = df['returns'] * df['position']
    df['strategy_ret'] -= df['pos_change'] * TRANSACTION_COST

    # 累计收益
    df['cum_bench'] = (1 + df['returns'].fillna(0)).cumprod()
    df['cum_strat'] = (1 + df['strategy_ret'].fillna(0)).cumprod()

    # 指标计算
    valid = df.dropna(subset=['position', 'returns'])
    n_days = len(valid)
    n_years = n_days / 252

    bench_total = df['cum_bench'].iloc[-1] - 1
    strat_total = df['cum_strat'].iloc[-1] - 1

    bench_ann = (df['cum_bench'].iloc[-1]) ** (1/n_years) - 1 if n_years > 0 else 0
    strat_ann = (df['cum_strat'].iloc[-1]) ** (1/n_years) - 1 if n_years > 0 else 0

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

    bench_dd = max_dd(df['cum_bench'])
    strat_dd = max_dd(df['cum_strat'])

    # Calmar
    calmar = strat_ann / abs(strat_dd) if abs(strat_dd) > 0.001 else 0

    # 交易次数
    trades = int((df['pos_change'] > 0.05).sum())

    # 胜率
    monthly = df['strategy_ret'].resample('ME').sum()
    win_rate = (monthly > 0).sum() / len(monthly) if len(monthly) > 0 else 0

    # 超额收益
    excess = strat_ann - bench_ann

    return {
        'strategy': strategy_name,
        'start_year': start_year,
        'period': f"{df.index[0].strftime('%Y-%m')} to {df.index[-1].strftime('%Y-%m')}",
        'n_years': round(n_years, 1),
        'bench_ann': bench_ann,
        'strat_ann': strat_ann,
        'bench_sharpe': bench_sharpe,
        'strat_sharpe': strat_sharpe,
        'bench_dd': bench_dd,
        'strat_dd': strat_dd,
        'excess': excess,
        'calmar': calmar,
        'trades': trades,
        'win_rate': win_rate,
    }


def main():
    print("=" * 80)
    print("  股债性价比 + 趋势 综合策略回测")
    print("  Equity-Bond Spread + Trend Combined Strategy")
    print("=" * 80)

    # 1. Fetch data
    print("\n[1] Fetching data...")
    time.sleep(1)
    pe_hs300 = fetch_index_pe('沪深300')
    time.sleep(1)
    pe_zz500 = fetch_index_pe('中证500')
    time.sleep(1)
    bond_df = fetch_bond_yield()

    # 2. Build data
    print("\n[2] Building combined data...")
    indices = [
        ('HS300', '沪深300', pe_hs300),
        ('ZZ500', '中证500', pe_zz500),
    ]

    all_results = []

    for code, name, pe_df in indices:
        print(f"\n  Processing {name} ({code})...")
        df = build_data(pe_df, bond_df)
        print(f"    Data: {len(df)} rows, {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")

        # 3. Backtest strategies
        strategies = [
            (strategy_lp, 'LP_Original'),
            (strategy_lp_v2, 'LP_Improved'),
            (strategy_ws, 'WS_Weighted'),
            (strategy_dw, 'DW_Dynamic'),
            (strategy_sc, 'SC_Confirmation'),
            (strategy_momentum_value, 'MV_ValueMom'),
        ]

        for func, sname in strategies:
            for start_y in [2015, 2018]:
                result = backtest(df, func, sname, start_y)
                if result:
                    result['index'] = code
                    all_results.append(result)
                    print(f"    {sname:20} (start {start_y}): Excess {result['excess']:+.2%}")

    # 4. Results
    df_results = pd.DataFrame(all_results)
    df_results = df_results.sort_values('excess', ascending=False)

    print("\n" + "=" * 80)
    print("  回测结果 (按超额收益排序)")
    print("=" * 80)

    for start_y in [2015, 2018]:
        print(f"\n--- Start Year: {start_y} ---\n")
        sub = df_results[df_results['start_year'] == start_y]
        print(f"{'Index':8} {'Strategy':20} {'Strat':>8} {'Bench':>8} {'Sharpe':>7} {'Excess':>8} {'MaxDD':>8} {'Trades':>6}")
        print("-" * 95)

        for _, r in sub.iterrows():
            marker = " *" if r['excess'] > 0 else ""
            print(f"{r['index']:8} {r['strategy']:20} "
                  f"{r['strat_ann']:7.2%} "
                  f"{r['bench_ann']:7.2%} "
                  f"{r['strat_sharpe']:7.2f} "
                  f"{r['excess']:+7.2%} "
                  f"{r['strat_dd']:7.2%} "
                  f"{r['trades']:6d}"
                  f"{marker}")

    # 5. Comparison with single-factor
    print("\n\n" + "=" * 80)
    print("  对比：综合策略 vs 单一策略")
    print("=" * 80)

    # 读取之前的单一策略结果
    single_file = os.path.join(OUTPUT_DIR, 'equity_bond_strategy_v2.json')
    if os.path.exists(single_file):
        with open(single_file, 'r', encoding='utf-8') as f:
            single_results = json.load(f)
        df_single = pd.DataFrame(single_results)

        # 筛选2018年以后的结果
        df_single = df_single[df_single['start_year'] == 2018]

        print("\n  单一策略最佳 (start 2018):")
        for idx in ['HS300', 'ZZ500']:
            sub = df_single[df_single['index'] == idx]
            if len(sub) > 0:
                best = sub.iloc[0]
                print(f"    {idx}: {best['strategy']:20} Excess={best['excess']:+.2%}")

    print("\n  综合策略最佳 (start 2018):")
    df_2018 = df_results[df_results['start_year'] == 2018]
    for idx in ['HS300', 'ZZ500']:
        sub = df_2018[df_2018['index'] == idx]
        if len(sub) > 0:
            best = sub.iloc[0]
            print(f"    {idx}: {best['strategy']:20} Excess={best['excess']:+.2%}")

    # 6. Save
    output_file = os.path.join(OUTPUT_DIR, 'combined_strategy.json')
    save_data = []
    for _, r in df_results.iterrows():
        row = r.to_dict()
        for k, v in row.items():
            if isinstance(v, (np.floating, np.integer)):
                row[k] = float(v)
            elif isinstance(v, np.bool_):
                row[k] = bool(v)
        save_data.append(row)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()

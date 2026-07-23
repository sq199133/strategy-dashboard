# -*- coding: utf-8 -*-
"""
股债性价比择时策略回测 V2
======================
核心逻辑：
  股债性价比 = 1/PE(TTM) - 10年期国债收益率
  性价比高分位(>80%) = 股票便宜 = 买入
  性价比低分位(<20%) = 股票贵 = 卖出

数据源：akshare (乐咕乐股PE + 东方财富国债收益率)
回测标的：沪深300、中证500、创业板50 (指数价格，非ETF)
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

OUTPUT_DIR = 'D:/QClaw_Trading/backtest_results'
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRANSACTION_COST = 0.0003


def fetch_index_pe(symbol_name):
    """获取指数PE数据 (乐咕乐股)"""
    print(f"  Fetching PE: {symbol_name}...")
    df = ak.stock_index_pe_lg(symbol=symbol_name)
    col_map = {
        df.columns[0]: 'date',
        df.columns[1]: 'index_value',
        df.columns[2]: 'eq_static_pe',
        df.columns[3]: 'static_pe',
        df.columns[4]: 'static_pe_pct',
        df.columns[5]: 'eq_ttm_pe',
        df.columns[6]: 'ttm_pe',
        df.columns[7]: 'ttm_pe_pct',
    }
    df = df.rename(columns=col_map)
    df['date'] = pd.to_datetime(df['date'])
    df['ttm_pe'] = pd.to_numeric(df['ttm_pe'], errors='coerce')
    df['index_value'] = pd.to_numeric(df['index_value'], errors='coerce')
    df = df.dropna(subset=['date', 'ttm_pe', 'index_value'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"    OK: {len(df)} records, {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
    return df[['date', 'index_value', 'ttm_pe', 'ttm_pe_pct']]


def fetch_bond_yield():
    """获取10年期国债收益率"""
    print("  Fetching 10Y bond yield...")
    df = ak.bond_zh_us_rate()
    col_map = {
        df.columns[0]: 'date',
        df.columns[3]: 'yield_10y',
    }
    df = df.rename(columns=col_map)[['date', 'yield_10y']]
    df['date'] = pd.to_datetime(df['date'])
    df['yield_10y'] = pd.to_numeric(df['yield_10y'], errors='coerce')
    df = df.dropna(subset=['date', 'yield_10y'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"    OK: {len(df)} records, {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
    return df


def calc_rolling_percentile(series, window=252):
    """计算滚动分位数"""
    def rank_pct(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        rank = (x.iloc[:-1] <= current).sum()
        return rank / (len(x) - 1) * 100
    return series.rolling(window=window, min_periods=window // 2).apply(rank_pct)


def build_data(pe_df, bond_df):
    """构建股债性价比数据"""
    merged = pd.merge(pe_df, bond_df, on='date', how='inner')
    merged['earnings_yield'] = 1.0 / merged['ttm_pe']
    merged['bond_yield'] = merged['yield_10y'] / 100
    merged['eb_spread'] = merged['earnings_yield'] - merged['bond_yield']
    merged['eb_spread_pct_1y'] = calc_rolling_percentile(merged['eb_spread'], 252)
    merged['eb_spread_pct_3y'] = calc_rolling_percentile(merged['eb_spread'], 756)
    merged['eb_spread_pct_5y'] = calc_rolling_percentile(merged['eb_spread'], 1260)
    merged['returns'] = merged['index_value'].pct_change()
    # 移动均线
    merged['ma_20'] = merged['index_value'].rolling(20).mean()
    merged['ma_60'] = merged['index_value'].rolling(60).mean()
    merged['ma_120'] = merged['index_value'].rolling(120).mean()
    return merged


# ==================== 策略定义 ====================

def signal_pct_5tier(row, pct_col='eb_spread_pct_3y'):
    """
    五档分位策略
    分位高(性价比高)=股票便宜=买入
    分位低(性价比低)=股票贵=卖出
    """
    pct = row[pct_col]
    if pd.isna(pct):
        return 0.5
    if pct >= 80:
        return 1.0
    elif pct >= 60:
        return 0.8
    elif pct >= 40:
        return 0.5
    elif pct >= 20:
        return 0.3
    else:
        return 0.0


def signal_pct_3tier(row, pct_col='eb_spread_pct_3y'):
    """三档分位策略"""
    pct = row[pct_col]
    if pd.isna(pct):
        return 0.5
    if pct >= 70:
        return 1.0
    elif pct >= 30:
        return 0.5
    else:
        return 0.0


def signal_spread_absolute(row):
    """
    绝对利差策略
    股债性价比 > 3% → 重仓
    股债性价比 1-3% → 适中
    股债性价比 0-1% → 轻仓
    股债性价比 < 0 → 空仓
    """
    spread = row['eb_spread']
    if pd.isna(spread):
        return 0.5
    if spread >= 0.03:
        return 1.0
    elif spread >= 0.02:
        return 0.8
    elif spread >= 0.01:
        return 0.6
    elif spread >= 0:
        return 0.3
    else:
        return 0.0


def signal_pct_trend(row):
    """
    分位 + 趋势过滤
    性价比高 且 趋势向上 = 重仓
    性价比高 但 趋势向下 = 半仓
    """
    pct = row['eb_spread_pct_3y']
    price = row['index_value']
    ma_60 = row['ma_60']

    if pd.isna(pct) or pd.isna(ma_60):
        return 0.5

    # 趋势判断
    trend_up = price > ma_60

    if pct >= 70:
        return 1.0 if trend_up else 0.6
    elif pct >= 40:
        return 0.7 if trend_up else 0.4
    elif pct >= 20:
        return 0.4 if trend_up else 0.2
    else:
        return 0.0


def signal_pct_volatility(row):
    """
    分位 + 波动率调整
    高波动时降低仓位
    """
    pct = row['eb_spread_pct_3y']
    returns = row['returns']

    if pd.isna(pct):
        return 0.5

    # 基础仓位
    if pct >= 80:
        base = 1.0
    elif pct >= 60:
        base = 0.8
    elif pct >= 40:
        base = 0.5
    elif pct >= 20:
        base = 0.3
    else:
        base = 0.0

    return base


def signal_hybrid_v2(row):
    """
    综合策略：分位 + 趋势 + 波动率
    """
    pct = row['eb_spread_pct_3y']
    price = row['index_value']
    ma_60 = row['ma_60']
    ma_120 = row['ma_120']

    if pd.isna(pct) or pd.isna(ma_60):
        return 0.5

    # 趋势分数 (0-1)
    if pd.notna(ma_120):
        if price > ma_60 > ma_120:
            trend = 1.0
        elif price > ma_60:
            trend = 0.7
        elif ma_60 > ma_120:
            trend = 0.5
        else:
            trend = 0.3
    else:
        trend = 0.5

    # 估值分数 (0-1)
    val = pct / 100

    # 综合
    score = val * 0.6 + trend * 0.4
    return max(0, min(1.0, score))


def signal_1y_rolling(row):
    """1年滚动分位策略"""
    return signal_pct_5tier(row, 'eb_spread_pct_1y')


def signal_5y_rolling(row):
    """5年滚动分位策略"""
    return signal_pct_5tier(row, 'eb_spread_pct_5y')


# ==================== 回测 ====================

def backtest(df, signal_func, name, start_year=2010):
    """执行回测"""
    df = df.copy()
    df = df.set_index('date')

    # 过滤起始年份
    if start_year:
        df = df[df.index.year >= start_year]

    if len(df) < 100:
        return None

    # 生成信号
    df['target_pos'] = df.apply(signal_func, axis=1)

    # T+1执行
    df['position'] = df['target_pos'].shift(1)
    df['pos_change'] = df['position'].diff().abs()

    # 收益
    df['strategy_ret'] = df['returns'] * df['position']
    df['strategy_ret'] -= df['pos_change'] * TRANSACTION_COST

    # 累计
    df['cum_bench'] = (1 + df['returns'].fillna(0)).cumprod()
    df['cum_strat'] = (1 + df['strategy_ret'].fillna(0)).cumprod()

    # 指标
    valid = df.dropna(subset=['position', 'returns'])
    n_days = len(valid)
    n_years = n_days / 252

    bench_total = df['cum_bench'].iloc[-1] - 1
    strat_total = df['cum_strat'].iloc[-1] - 1
    bench_ann = df['cum_bench'].iloc[-1] ** (1/n_years) - 1
    strat_ann = df['cum_strat'].iloc[-1] ** (1/n_years) - 1

    bench_vol = valid['returns'].std() * np.sqrt(252)
    strat_vol = valid['strategy_ret'].std() * np.sqrt(252)

    rf = 0.02
    bench_sharpe = (bench_ann - rf) / bench_vol if bench_vol > 0 else 0
    strat_sharpe = (strat_ann - rf) / strat_vol if strat_vol > 0 else 0

    def max_dd(cum):
        peak = cum.expanding(min_periods=1).max()
        dd = (cum - peak) / peak
        return dd.min()

    bench_dd = max_dd(df['cum_bench'])
    strat_dd = max_dd(df['cum_strat'])

    calmar = strat_ann / abs(strat_dd) if abs(strat_dd) > 0.001 else 0

    trades = int((df['pos_change'] > 0.05).sum())

    # 月度胜率
    monthly = df['strategy_ret'].resample('ME').sum()
    win_rate = (monthly > 0).sum() / len(monthly) if len(monthly) > 0 else 0

    # 年化超额
    excess = strat_ann - bench_ann

    return {
        'strategy': name,
        'start_year': start_year,
        'period': f"{df.index[0].strftime('%Y-%m')} to {df.index[-1].strftime('%Y-%m')}",
        'n_years': round(n_years, 1),
        'bench_total': bench_total,
        'strat_total': strat_total,
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
    print("  股债性价比择时策略回测 V2")
    print("  Equity-Bond Spread Timing Strategy")
    print("=" * 80)

    # 1. Fetch data
    print("\n[1] Fetching data...")
    time.sleep(1)
    pe_hs300 = fetch_index_pe('沪深300')
    time.sleep(1)
    pe_zz500 = fetch_index_pe('中证500')
    time.sleep(1)
    pe_gem50 = fetch_index_pe('创业板50')
    bond_df = fetch_bond_yield()

    # 2. Build data
    print("\n[2] Building equity-bond spread data...")
    indices_config = [
        ('HS300', '沪深300', pe_hs300),
        ('ZZ500', '中证500', pe_zz500),
        ('GEM50', '创业板50', pe_gem50),
    ]

    all_results = []
    current_status = {}

    for code, name, pe_df in indices_config:
        print(f"\n  Building {name} ({code})...")
        merged = build_data(pe_df, bond_df)
        print(f"    Data: {len(merged)} rows, "
              f"{merged['date'].min().strftime('%Y-%m-%d')} to "
              f"{merged['date'].max().strftime('%Y-%m-%d')}")

        # Current status
        last = merged.iloc[-1]
        current_status[code] = {
            'name': name,
            'date': last['date'].strftime('%Y-%m-%d'),
            'pe': float(last['ttm_pe']),
            'index_value': float(last['index_value']),
            'earnings_yield_pct': float(last['earnings_yield']) * 100,
            'bond_yield_pct': float(last['bond_yield']) * 100,
            'spread_pct': float(last['eb_spread']) * 100,
            'spread_pct_1y': float(last['eb_spread_pct_1y']) if pd.notna(last['eb_spread_pct_1y']) else None,
            'spread_pct_3y': float(last['eb_spread_pct_3y']) if pd.notna(last['eb_spread_pct_3y']) else None,
            'spread_pct_5y': float(last['eb_spread_pct_5y']) if pd.notna(last['eb_spread_pct_5y']) else None,
        }

        # 3. Backtest
        strategies = [
            (signal_pct_5tier, 'PCT_5TIER_3Y'),
            (signal_pct_3tier, 'PCT_3TIER_3Y'),
            (signal_pct_trend, 'PCT_TREND_3Y'),
            (signal_hybrid_v2, 'HYBRID_3Y'),
            (signal_spread_absolute, 'SPREAD_ABS'),
            (signal_1y_rolling, 'PCT_5TIER_1Y'),
            (signal_5y_rolling, 'PCT_5TIER_5Y'),
        ]

        # Test multiple start years
        for start_year in [2010, 2015, 2018]:
            for func, sname in strategies:
                result = backtest(merged, func, sname, start_year)
                if result:
                    result['index'] = code
                    all_results.append(result)

    # 4. Display results
    df_results = pd.DataFrame(all_results)
    df_results = df_results.sort_values('excess', ascending=False)

    print("\n" + "=" * 80)
    print("  回测结果 (按超额收益排序)")
    print("=" * 80)

    # Group by start year
    for start_y in [2010, 2015, 2018]:
        print(f"\n--- Start Year: {start_y} ---\n")
        sub = df_results[df_results['start_year'] == start_y]
        print(f"{'Index':8} {'Strategy':20} {'Strat':>8} {'Bench':>8} {'Sharpe':>7} {'Excess':>8} {'MaxDD':>8} {'Trades':>6} {'WinR':>6}")
        print("-" * 95)

        for _, r in sub.iterrows():
            marker = " *" if r['excess'] > 0 else ""
            print(f"{r['index']:8} {r['strategy']:20} "
                  f"{r['strat_ann']:7.2%} "
                  f"{r['bench_ann']:7.2%} "
                  f"{r['strat_sharpe']:7.2f} "
                  f"{r['excess']:+7.2%} "
                  f"{r['strat_dd']:7.2%} "
                  f"{r['trades']:6d} "
                  f"{r['win_rate']:6.0%}"
                  f"{marker}")

        # Best per index
        print(f"\n  Best per index (start {start_y}):")
        for idx in ['HS300', 'ZZ500', 'GEM50']:
            idx_sub = sub[sub['index'] == idx]
            if len(idx_sub) > 0:
                best = idx_sub.iloc[0]
                print(f"    {idx:8} {best['strategy']:20} "
                      f"Strat={best['strat_ann']:6.2%} "
                      f"Excess={best['excess']:+6.2%} "
                      f"Sharpe={best['strat_sharpe']:5.2f} "
                      f"DD={best['strat_dd']:6.2%}")

    # 5. Current status
    print("\n\n" + "=" * 80)
    print("  当前市场状态 (股债性价比)")
    print("=" * 80)

    for code, st in current_status.items():
        print(f"\n  {st['name']} ({code}):")
        print(f"    指数点位:       {st['index_value']:.2f}")
        print(f"    PE(TTM):        {st['pe']:.2f}")
        print(f"    盈利收益率:     {st['earnings_yield_pct']:.2f}%")
        print(f"    10年国债:       {st['bond_yield_pct']:.2f}%")
        print(f"    股债性价比:     {st['spread_pct']:.2f}%")
        if st['spread_pct_1y'] is not None:
            print(f"    历史分位(1Y):   {st['spread_pct_1y']:.1f}%")
        if st['spread_pct_3y'] is not None:
            print(f"    历史分位(3Y):   {st['spread_pct_3y']:.1f}%")
        if st['spread_pct_5y'] is not None:
            print(f"    历史分位(5Y):   {st['spread_pct_5y']:.1f}%")

        pct = st['spread_pct_3y'] or st['spread_pct_1y'] or 50
        if pct >= 80:
            sig = "买入 (股票极具性价比)"
        elif pct >= 60:
            sig = "加仓 (股票偏便宜)"
        elif pct >= 40:
            sig = "中性 (正常配置)"
        elif pct >= 20:
            sig = "减仓 (股票偏贵)"
        else:
            sig = "卖出 (股票昂贵)"
        print(f"    信号(3Y分位):   {sig}")

    # 6. Save
    output_file = os.path.join(OUTPUT_DIR, 'equity_bond_strategy_v2.json')
    # Convert to serializable
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

    # 7. Summary
    print("\n\n" + "=" * 80)
    print("  总结")
    print("=" * 80)

    # Count positive excess
    total = len(df_results)
    positive = len(df_results[df_results['excess'] > 0])
    print(f"\n  Total strategy runs: {total}")
    print(f"  Positive excess: {positive} ({positive/total:.0%})")
    print(f"  Negative excess: {total - positive} ({(total-positive)/total:.0%})")

    # Best overall
    best = df_results.iloc[0]
    print(f"\n  Best overall: {best['index']} {best['strategy']} (start {int(best['start_year'])})")
    print(f"    Excess: {best['excess']:+.2%}, Sharpe: {best['strat_sharpe']:.2f}, MaxDD: {best['strat_dd']:.2%}")


if __name__ == "__main__":
    main()

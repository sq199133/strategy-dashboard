# -*- coding: utf-8 -*-
"""
股债性价比择时策略回测
======================
策略逻辑：
  股债性价比 = 股票盈利收益率(1/PE) - 10年期国债收益率
  当性价比 > 阈值 → 股票便宜，加仓
  当性价比 < 阈值 → 股票贵，减仓

数据源：
  - 指数PE：akshare stock_index_pe_lg (乐咕乐股)
  - 10年国债：akshare bond_zh_us_rate
  - ETF价格：本地历史数据
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


def fetch_index_pe(symbol_name):
    """获取指数PE数据 (乐咕乐股)"""
    print(f"  Fetching PE: {symbol_name}...")
    df = ak.stock_index_pe_lg(symbol=symbol_name)
    # Standardize columns
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
    df = df.dropna(subset=['date', 'ttm_pe'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"    OK: {len(df)} records, {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
    return df[['date', 'index_value', 'ttm_pe', 'ttm_pe_pct']]


def fetch_bond_yield():
    """获取10年期国债收益率"""
    print("  Fetching 10Y bond yield...")
    df = ak.bond_zh_us_rate()
    col_map = {
        df.columns[0]: 'date',
        df.columns[3]: 'yield_10y',  # 中国国债到期收益率10年
    }
    df = df.rename(columns=col_map)[['date', 'yield_10y']]
    df['date'] = pd.to_datetime(df['date'])
    df['yield_10y'] = pd.to_numeric(df['yield_10y'], errors='coerce')
    df = df.dropna(subset=['date', 'yield_10y'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"    OK: {len(df)} records, {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
    return df


def load_etf_price(etf_code):
    """加载ETF历史价格数据"""
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
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df = df.sort_values('date').reset_index(drop=True)
    return df[['date', 'close']]


def build_equity_bond_data(pe_df, bond_df, etf_df=None):
    """
    构建股债性价比数据
    股债性价比 = 1/PE(TTM) - 10年期国债收益率
    """
    # Merge PE and bond yield
    merged = pd.merge(pe_df, bond_df, on='date', how='inner')

    # Calculate equity-bond spread
    merged['earnings_yield'] = 1.0 / merged['ttm_pe']  # 盈利收益率
    merged['bond_yield'] = merged['yield_10y'] / 100     # 国债收益率 (转为小数)
    merged['eb_spread'] = merged['earnings_yield'] - merged['bond_yield']  # 股债性价比

    # Calculate rolling percentile of eb_spread
    merged['eb_spread_pct'] = calc_rolling_percentile(merged['eb_spread'], window=252)

    # If ETF data provided, merge price
    if etf_df is not None:
        merged = pd.merge(merged, etf_df, on='date', how='inner')
        merged = merged.rename(columns={'close': 'price'})

    return merged


def calc_rolling_percentile(series, window=252):
    """计算滚动分位数"""
    def rank_pct(x):
        if len(x) < 2:
            return np.nan
        current = x.iloc[-1]
        rank = (x.iloc[:-1] <= current).sum()
        return rank / (len(x) - 1) * 100

    return series.rolling(window=window, min_periods=window // 2).apply(rank_pct)


def calc_percentile(series, current_value):
    """计算当前值在历史序列中的分位"""
    valid = series.dropna()
    if len(valid) < 2:
        return 50.0
    rank = (valid <= current_value).sum()
    return rank / len(valid) * 100


def generate_signal(eb_spread, method='threshold', **params):
    """
    生成交易信号
    method:
      - 'threshold': 分位阈值
      - 'spread': 绝对利差阈值
      - 'hybrid': 混合策略
    """
    if pd.isna(eb_spread):
        return np.nan

    if method == 'threshold':
        # 分位阈值策略
        low_pct = params.get('low_pct', 20)
        high_pct = params.get('high_pct', 80)

        if eb_spread <= low_pct:
            return 1.0   # 高估，减仓
        elif eb_spread >= high_pct:
            return 1.0   # 低估，加仓  -- wait, this is percentile, low = cheap
        else:
            return 0.5

    elif method == 'spread':
        # 绝对利差策略
        low_threshold = params.get('low_threshold', 0.0)   # 盈利收益率=国债收益率
        high_threshold = params.get('high_threshold', 0.03) # 盈利收益率比国债高3%

        if eb_spread >= high_threshold:
            return 1.0   # 股票很便宜
        elif eb_spread >= low_threshold:
            return 0.6
        elif eb_spread >= 0:
            return 0.3
        else:
            return 0.0   # 股票比国债还贵

    elif method == 'sigmoid':
        # Sigmoid策略（分位版）
        center = params.get('center', 50)
        steepness = params.get('steepness', 15)
        x = (eb_spread - center) / steepness
        return 1.0 / (1.0 + np.exp(x))

    elif method == 'linear':
        return max(0, min(1, eb_spread / 100))

    return 0.5


def backtest(merged, signal_func, method_name, use_index_price=True):
    """
    执行回测
    """
    df = merged.copy()
    df = df.dropna(subset=['eb_spread', 'eb_spread_pct'])

    if len(df) < 100:
        return None

    # Generate signals
    df['target_pos'] = df['eb_spread_pct'].apply(
        lambda x: generate_signal(x, method=method_name) if pd.notna(x) else np.nan
    )

    # Shift signal (T+1 execution)
    df['position'] = df['target_pos'].shift(1)
    df['pos_change'] = df['position'].diff().abs()

    # Use index value or ETF price for returns
    if use_index_price:
        df['returns'] = df['index_value'].pct_change()
    elif 'price' in df.columns:
        df['returns'] = df['price'].pct_change()
    else:
        return None

    # Strategy returns
    df['strategy_ret'] = df['returns'] * df['position']
    df['strategy_ret'] -= df['pos_change'] * TRANSACTION_COST

    # Cumulative returns
    df['cum_bench'] = (1 + df['returns'].fillna(0)).cumprod()
    df['cum_strat'] = (1 + df['strategy_ret'].fillna(0)).cumprod()

    # Calculate metrics
    valid = df.dropna(subset=['position', 'returns'])
    n_days = len(valid)
    n_years = n_days / 252

    bench_ret = df['cum_bench'].iloc[-1] - 1
    strat_ret = df['cum_strat'].iloc[-1] - 1

    bench_ann = (df['cum_bench'].iloc[-1]) ** (1 / n_years) - 1
    strat_ann = (df['cum_strat'].iloc[-1]) ** (1 / n_years) - 1

    bench_vol = valid['returns'].std() * np.sqrt(252)
    strat_vol = valid['strategy_ret'].std() * np.sqrt(252)

    rf = 0.02
    bench_sharpe = (bench_ann - rf) / bench_vol if bench_vol > 0 else 0
    strat_sharpe = (strat_ann - rf) / strat_vol if strat_vol > 0 else 0

    # Max drawdown
    def max_dd(cum):
        peak = cum.expanding(min_periods=1).max()
        dd = (cum - peak) / peak
        return dd.min()

    bench_dd = max_dd(df['cum_bench'])
    strat_dd = max_dd(df['cum_strat'])

    # Calmar ratio
    calmar = (strat_ann / abs(strat_dd)) if abs(strat_dd) > 0.001 else 0

    trades = (df['pos_change'] > 0.05).sum()

    # Win rate
    df_with_date = df.set_index('date')
    monthly_ret = df_with_date['strategy_ret'].resample('ME').sum()
    win_rate = (monthly_ret > 0).sum() / len(monthly_ret) if len(monthly_ret) > 0 else 0

    return {
        'strategy': method_name,
        'period': f"{df['date'].iloc[0].strftime('%Y-%m-%d')} to {df['date'].iloc[-1].strftime('%Y-%m-%d')}",
        'days': n_days,
        'years': round(n_years, 1),
        'bench_return': bench_ret,
        'bench_annual': bench_ann,
        'bench_sharpe': bench_sharpe,
        'bench_maxdd': bench_dd,
        'strat_return': strat_ret,
        'strat_annual': strat_ann,
        'strat_sharpe': strat_sharpe,
        'strat_maxdd': strat_dd,
        'excess_return': strat_ann - bench_ann,
        'calmar': calmar,
        'trades': int(trades),
        'win_rate': win_rate,
        'final_spread': float(df['eb_spread'].iloc[-1]),
        'final_spread_pct': float(df['eb_spread_pct'].iloc[-1]),
        'current_position': float(df['target_pos'].iloc[-1]) if pd.notna(df['target_pos'].iloc[-1]) else None,
    }


def main():
    print("=" * 70)
    print("股债性价比择时策略回测")
    print("=" * 70)

    # ========== 1. Fetch Data ==========
    print("\n[1] Fetching PE data...")
    time.sleep(1)
    pe_hs300 = fetch_index_pe('沪深300')
    time.sleep(1)
    pe_zz500 = fetch_index_pe('中证500')
    time.sleep(1)
    pe_gem50 = fetch_index_pe('创业板50')

    print("\n[2] Fetching bond yield data...")
    bond_df = fetch_bond_yield()

    # ========== 2. Build Data ==========
    print("\n[3] Building equity-bond spread data...")

    indices = [
        ('HS300', pe_hs300, '510300'),
        ('ZZ500', pe_zz500, '510500'),
        ('GEM50', pe_gem50, '159949'),
    ]

    all_results = []
    current_status = {}

    for index_name, pe_df, etf_code in indices:
        print(f"\n  Processing {index_name} ({etf_code})...")

        # Load ETF price
        etf_df = load_etf_price(etf_code)
        if etf_df is not None:
            print(f"    ETF data: {len(etf_df)} records")
        else:
            print(f"    ETF data not found, using index value")

        # Build combined data
        merged = build_equity_bond_data(pe_df, bond_df, etf_df if etf_df is not None else None)

        if len(merged) < 100:
            print(f"    SKIP: insufficient data ({len(merged)} rows)")
            continue

        print(f"    Combined: {len(merged)} rows, {merged['date'].min().strftime('%Y-%m-%d')} to {merged['date'].max().strftime('%Y-%m-%d')}")

        # Use index value if no ETF data
        use_index = (etf_df is None)
        if use_index and 'index_value' in merged.columns:
            # Use index_value as price
            merged['price'] = merged['index_value']
            use_index = True

        # Current status
        last_row = merged.iloc[-1]
        current_status[index_name] = {
            'date': last_row['date'].strftime('%Y-%m-%d'),
            'ttm_pe': float(last_row['ttm_pe']),
            'bond_yield': float(last_row['bond_yield']) * 100,
            'earnings_yield': float(last_row['earnings_yield']) * 100,
            'eb_spread': float(last_row['eb_spread']) * 100,
            'eb_spread_pct': float(last_row['eb_spread_pct']),
        }

        # ========== 3. Backtest ==========
        print(f"  Backtesting {index_name}...")

        strategies = [
            ('threshold', {'low_pct': 20, 'high_pct': 80}),
            ('threshold_strict', {'low_pct': 30, 'high_pct': 70}),
            ('spread', {'low_threshold': 0.0, 'high_threshold': 0.03}),
            ('spread_strict', {'low_threshold': 0.01, 'high_threshold': 0.04}),
            ('sigmoid', {'center': 50, 'steepness': 15}),
            ('sigmoid_flat', {'center': 50, 'steepness': 20}),
        ]

        for method_name, params in strategies:
            result = backtest(merged, lambda x: generate_signal(x, method=method_name, **params),
                            method_name, use_index_price=use_index)
            if result:
                result['index'] = index_name
                all_results.append(result)

    # ========== 4. Results ==========
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    df_results = pd.DataFrame(all_results)
    df_results = df_results.sort_values('excess_return', ascending=False)

    # Display all results
    print("\nAll strategies (sorted by excess return):\n")
    print(f"{'Index':8} {'Strategy':20} {'AnnRet':>8} {'Sharpe':>7} {'Excess':>8} {'MaxDD':>8} {'Trades':>6} {'WinRate':>7}")
    print("-" * 80)

    for _, r in df_results.iterrows():
        print(f"{r['index']:8} {r['strategy']:20} "
              f"{r['strat_annual']:7.2%} "
              f"{r['strat_sharpe']:7.2f} "
              f"{r['excess_return']:+7.2%} "
              f"{r['strat_maxdd']:7.2%} "
              f"{r['trades']:6d} "
              f"{r['win_rate']:6.0%}")

    # Best per index
    print("\n\nBest strategy per index:\n")
    print(f"{'Index':8} {'Strategy':20} {'Bench':>8} {'Strat':>8} {'Sharpe':>7} {'Excess':>8} {'MaxDD':>8}")
    print("-" * 80)

    for idx_name in ['HS300', 'ZZ500', 'GEM50']:
        idx_results = df_results[df_results['index'] == idx_name]
        if len(idx_results) == 0:
            continue
        best = idx_results.iloc[0]
        print(f"{idx_name:8} {best['strategy']:20} "
              f"{best['bench_annual']:7.2%} "
              f"{best['strat_annual']:7.2%} "
              f"{best['strat_sharpe']:7.2f} "
              f"{best['excess_return']:+7.2%} "
              f"{best['strat_maxdd']:7.2%}")

    # Current market status
    print("\n\n" + "=" * 70)
    print("CURRENT MARKET STATUS (股债性价比)")
    print("=" * 70)

    for idx_name, status in current_status.items():
        print(f"\n{idx_name}:")
        print(f"  PE(TTM):        {status['ttm_pe']:.2f}")
        print(f"  盈利收益率(1/PE): {status['earnings_yield']:.2f}%")
        print(f"  10年国债收益率:   {status['bond_yield']:.2f}%")
        print(f"  股债性价比:       {status['eb_spread']:.2f}%")
        print(f"  历史分位:         {status['eb_spread_pct']:.1f}%")

        # Simple signal
        pct = status['eb_spread_pct']
        if pct >= 80:
            signal = "BUY (股票极具吸引力)"
        elif pct >= 60:
            signal = "ACCUMULATE (适度配置)"
        elif pct >= 40:
            signal = "HOLD (中性)"
        elif pct >= 20:
            signal = "REDUCE (适度减仓)"
        else:
            signal = "SELL (股票昂贵)"
        print(f"  信号: {signal}")

    # Save results
    output_file = os.path.join(OUTPUT_DIR, 'equity_bond_strategy.json')
    df_results.to_json(output_file, orient='records', indent=2, force_ascii=False)
    print(f"\n\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()

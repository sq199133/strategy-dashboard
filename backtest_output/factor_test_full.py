"""
A股 ETF 因子回测 - 单因子测试 + 多因子组合
============================================
数据: D:\QClaw_Trading\data\history\ 下所有ETF JSON文件
回测方式: 月末截面排序, 买入Top K, 等权持有, 下月再平衡
执行时点: 信号确认后次日开盘
"""

import json, os, sys, math
from datetime import datetime, timedelta
from collections import defaultdict

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Noto Sans CJK SC', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
# CONFIG
# ============================================================
DATA_DIR = 'D:/QClaw_Trading/data/history/'
OUTPUT_DIR = 'D:/QClaw_Trading/backtest_output/factor_test_' + datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs(OUTPUT_DIR, exist_ok=True)

INITIAL_CASH = 1_000_000
COMMISSION = 0.0003  # 买入佣金
SELL_COMMISSION = 0.0003  # 卖出佣金
SELL_TAX = 0.0  # ETF 免印花税
MIN_RECORDS = 120  # 最少 120 条记录才纳入回测
LOOKBACK_MIN = 12  # 因子计算最少需要 12 个月数据

# 回测时间范围
BT_START = '2019-01-01'
BT_END = '2026-07-10'

# Top K 测试
TOP_KS = [5, 10, 20]

# ============================================================
# 1. LOAD DATA
# ============================================================
def load_all_etfs(data_dir):
    """Load all ETF JSON files, return dict of {code: DataFrame}"""
    etf_data = {}
    for fname in os.listdir(data_dir):
        if not fname.endswith('.json'):
            continue
        code = fname[:-5]
        # filter for ETF codes: 159xxx, 51xxxx, 56xxxx, 588xxx
        if not ((code[:3] in ('159','510','511','512','513','515','516','517','518','560','561','562','563','588')) or
                code[:2] in ('51','56','58')):
            continue
        path = os.path.join(data_dir, fname)
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
        records = raw.get('records', [])
        if len(records) < MIN_RECORDS:
            continue
        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        # numeric columns
        for col in ['open','close','high','low','vol']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        etf_data[code] = df
    return etf_data

# ============================================================
# 2. FACTOR COMPUTATION
# ============================================================
def compute_momentum(df, months):
    """过去N个月收益率(排除最近1个月, 即12-1 / 6-1 / 3-1)"""
    # months=12: 用 t-12 到 t-1 的收益率
    trading_days = months * 21
    if len(df) < trading_days + 5:
        return pd.Series(index=df.index, dtype=float)
    mom = df['close'].shift(5) / df['close'].shift(trading_days + 5) - 1
    return mom

def compute_momentum_simple(df, months):
    """简单过去N个月收益率 (包含最近)"""
    trading_days = months * 21
    if len(df) < trading_days + 2:
        return pd.Series(index=df.index, dtype=float)
    mom = df['close'] / df['close'].shift(trading_days) - 1
    return mom

def compute_low_vol(df, months):
    """过去N个月日收益率波动率(标准差)"""
    trading_days = months * 21
    if len(df) < trading_days + 5:
        return pd.Series(index=df.index, dtype=float)
    ret = df['close'].pct_change()
    vol = ret.rolling(trading_days).std()
    return vol

def compute_beta(df, market_ret, months):
    """过去N个月 beta 相对市场"""
    trading_days = months * 21
    if len(df) < trading_days + 5:
        return pd.Series(index=df.index, dtype=float)
    ret = df['close'].pct_change()
    # use market return aligned to same dates
    dates = df['date']
    mkt = market_ret.reindex(dates, method=None)
    # rolling covariance / variance
    cov = ret.rolling(trading_days).cov(mkt)
    var = mkt.rolling(trading_days).var()
    beta = cov / var
    return beta

def compute_vol_momentum(df, months_slow, months_fast):
    """量能趋势: 短期均量 / 长期均量"""
    fast_days = months_fast * 21
    slow_days = months_slow * 21
    if len(df) < slow_days + 2:
        return pd.Series(index=df.index, dtype=float)
    vol_fast = df['vol'].rolling(fast_days).mean()
    vol_slow = df['vol'].rolling(slow_days).mean()
    ratio = vol_fast / vol_slow
    return ratio

def compute_price_ma(df, days):
    """价格 / 移动平均线"""
    if len(df) < days + 2:
        return pd.Series(index=df.index, dtype=float)
    ma = df['close'].rolling(days).mean()
    ratio = df['close'] / ma
    return ratio

def compute_short_reversal(df, months):
    """短期反转: 过去1个月收益率 (反转因子用负值, 过去涨的预期跌)"""
    trading_days = max(months * 21, 20)
    if len(df) < trading_days + 2:
        return pd.Series(index=df.index, dtype=float)
    ret = df['close'] / df['close'].shift(trading_days) - 1
    return -ret  # 负值: 过去跌得多=高排名

# ============================================================
# 3. BACKTEST ENGINE
# ============================================================
def monthly_factor_backtest(df_dict, factor_name, param_label, factor_func, 
                             top_k=10, ascending=False, bt_start=BT_START, bt_end=BT_END,
                             warmup_years=2):
    """
    月末再平衡因子回测
    factor_func: function(df) -> pd.Series of factor values aligned to df index
    ascending: True = 选最小的, False = 选最大的
    """
    print(f"  Running [{factor_name}] param={param_label} top={top_k} ...", end=' ', flush=True)
    
    # Collect all ETF daily data for price reference
    # Build monthly rebalance dates from any ETF that has enough history
    all_dates = set()
    for code, df in df_dict.items():
        for d in df['date'].dt.strftime('%Y-%m-%d'):
            all_dates.add(d)
    all_dates = sorted(all_dates)
    
    bt_start_dt = pd.Timestamp(bt_start)
    bt_end_dt = pd.Timestamp(bt_end)
    
    # Get month-end dates
    # For each calendar month, find the last trading day
    df_all = pd.DataFrame({'date': pd.to_datetime(all_dates)})
    df_all['year_month'] = df_all['date'].dt.to_period('M')
    month_end_dates = df_all.groupby('year_month')['date'].last().reset_index(drop=True)
    month_end_dates = month_end_dates[(month_end_dates >= bt_start_dt + pd.Timedelta(days=365*warmup_years)) & 
                                       (month_end_dates <= bt_end_dt)]
    
    if len(month_end_dates) < 6:
        print("SKIP - not enough monthly data")
        return None
    
    # Pre-compute factor values for all ETFs
    # Store as {code: {date_str: factor_value}}
    factor_values = {}
    for code, df in df_dict.items():
        fv = factor_func(df)
        # align to daily dates
        fv.index = df['date']
        factor_values[code] = fv
    
    # Backtest loop
    cash = INITIAL_CASH
    holdings = {}  # {code: {size, entry_price}}
    
    equity_curve = []
    trade_history = []
    
    # Process month by month
    for idx in range(len(month_end_dates)):
        rebal_date = month_end_dates.iloc[idx]
        rebal_date_str = rebal_date.strftime('%Y-%m-%d')
        
        # Find next trading day after rebal_date for execution
        i_next = all_dates.index(rebal_date_str) + 1 if rebal_date_str in all_dates else -1
        if i_next >= len(all_dates):
            continue
        exec_date_str = all_dates[i_next]
        exec_date = pd.Timestamp(exec_date_str)
        
        # Get factor values at rebal_date for all ETFs
        candidates = []
        for code, fv_series in factor_values.items():
            if rebal_date in fv_series.index:
                val = fv_series.loc[rebal_date]
                if pd.notna(val) and not np.isinf(val):
                    # check that ETF has data on exec_date for price
                    etf_df = df_dict[code]
                    if exec_date in etf_df['date'].values:
                        candidates.append((code, val))
        
        if len(candidates) < 3:
            # Too few candidates, skip this month
            # Liquidate any existing positions
            for code, pos in list(holdings.items()):
                etf_df = df_dict[code]
                exec_mask = etf_df['date'] == exec_date
                if exec_mask.any():
                    price = etf_df.loc[exec_mask, 'open'].iloc[0]
                    if pd.notna(price) and price > 0:
                        proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                        pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                        trade_history.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_date_str,
                            'symbol': code,
                            'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                            'pnl_pct': round(pnl / (pos['size'] * pos['entry_price']) * 100, 2),
                        })
                        cash += proceeds
            holdings.clear()
            # Record equity
            equity_curve.append({'date': exec_date_str, 'value': round(cash, 2)})
            continue
        
        # Rank candidates by factor value
        candidates.sort(key=lambda x: x[1], reverse=not ascending)
        selected = [code for code, val in candidates[:top_k]]
        n_selected = len(selected)
        
        # --- Liquidate ETFs no longer in selected set ---
        for code, pos in list(holdings.items()):
            if code not in selected:
                etf_df = df_dict[code]
                exec_mask = etf_df['date'] == exec_date
                if exec_mask.any():
                    price = etf_df.loc[exec_mask, 'open'].iloc[0]
                    if pd.notna(price) and price > 0:
                        proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                        pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                        trade_history.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_date_str,
                            'symbol': code,
                            'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                            'pnl_pct': round(pnl / (pos['size'] * pos['entry_price']) * 100, 2),
                        })
                        cash += proceeds
                        del holdings[code]
        
        # --- Buy new selected ETFs ---
        if n_selected == 0:
            equity_curve.append({'date': exec_date_str, 'value': round(cash, 2)})
            continue
        
        cash_per_position = cash / n_selected
        
        for code in selected:
            if code in holdings:
                continue  # already holding
            etf_df = df_dict[code]
            exec_mask = etf_df['date'] == exec_date
            if not exec_mask.any():
                continue
            price = etf_df.loc[exec_mask, 'open'].iloc[0]
            if pd.isna(price) or price <= 0:
                continue
            
            # Size: cash_per_position / price, no lot size (ETF 可以小数份额交易)
            size = int(cash_per_position / (price * (1 + COMMISSION)))
            if size <= 0:
                continue
            
            cost = size * price * (1 + COMMISSION)
            if cost > cash:
                size = int(cash / (price * (1 + COMMISSION)))
                cost = size * price * (1 + COMMISSION)
                if size <= 0:
                    continue
            
            cash -= cost
            holdings[code] = {
                'size': size,
                'entry_price': price,
                'entry_date': exec_date_str,
            }
        
        # Record daily equity
        total_value = cash
        for code, pos in holdings.items():
            etf_df = df_dict[code]
            mask = etf_df['date'] == exec_date
            if mask.any():
                close_price = etf_df.loc[mask, 'close'].iloc[0]
                if pd.notna(close_price):
                    total_value += pos['size'] * close_price
                else:
                    total_value += pos['size'] * pos['entry_price']
            else:
                total_value += pos['size'] * pos['entry_price']
        
        equity_curve.append({'date': exec_date_str, 'value': round(total_value, 2)})
        
        # Record equity on non-rebalance days (mark-to-market)
        # Only sample monthly for brevity
    
    # --- Force liquidate at end ---
    final_date_str = all_dates[-1]
    final_date = pd.Timestamp(final_date_str)
    for code, pos in list(holdings.items()):
        etf_df = df_dict[code]
        mask = etf_df['date'] == final_date
        if mask.any():
            price = etf_df.loc[mask, 'close'].iloc[0]
            if pd.notna(price) and price > 0:
                proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                trade_history.append({
                    'entry_date': pos['entry_date'],
                    'exit_date': final_date_str,
                    'symbol': code,
                    'side': 'long',
                    'size': pos['size'],
                    'entry_price': pos['entry_price'],
                    'exit_price': price,
                    'pnl': round(pnl, 2),
                    'pnl_pct': round(pnl / (pos['size'] * pos['entry_price']) * 100, 2),
                })
                cash += proceeds
                del holdings[code]
    
    # Final equity
    total_value = cash
    for code, pos in holdings.items():
        etf_df = df_dict[code]
        mask = etf_df['date'] == final_date
        if mask.any():
            cp = etf_df.loc[mask, 'close'].iloc[0]
            total_value += pos['size'] * (cp if pd.notna(cp) else pos['entry_price'])
    equity_curve.append({'date': final_date_str, 'value': round(total_value, 2)})
    
    # --- Compute metrics ---
    if len(equity_curve) < 6:
        print("SKIP - too few equity points")
        return None
    
    eq_df = pd.DataFrame(equity_curve)
    eq_df['date'] = pd.to_datetime(eq_df['date'])
    eq_df = eq_df.sort_values('date').reset_index(drop=True)
    
    initial_val = eq_df['value'].iloc[0]
    final_val = eq_df['value'].iloc[-1]
    total_return = (final_val / initial_val - 1) * 100
    
    # Annualized return
    total_days = (eq_df['date'].iloc[-1] - eq_df['date'].iloc[0]).days
    years = total_days / 365.25
    ann_return = ((final_val / initial_val) ** (1 / years) - 1) * 100 if years > 0 else 0
    
    # Sharpe (using daily returns, annualized)
    eq_df['daily_ret'] = eq_df['value'].pct_change()
    daily_ret = eq_df['daily_ret'].dropna()
    sharpe = np.nan
    if len(daily_ret) > 10:
        mean_ret = daily_ret.mean()
        std_ret = daily_ret.std()
        if std_ret > 0:
            sharpe = (mean_ret / std_ret) * np.sqrt(252)
    
    # Max drawdown
    eq_df['cummax'] = eq_df['value'].cummax()
    eq_df['dd'] = (eq_df['value'] / eq_df['cummax'] - 1) * 100
    max_dd = eq_df['dd'].min()
    
    # Win rate from trades
    if trade_history:
        winning = sum(1 for t in trade_history if t['pnl'] > 0)
        win_rate = winning / len(trade_history) * 100
    else:
        win_rate = 0
    
    # Calmar
    calmar = ann_return / abs(max_dd) if max_dd < 0 else np.nan
    
    # Average holding period
    if trade_history:
        hold_days = []
        for t in trade_history:
            ed = pd.Timestamp(t['entry_date'])
            exd = pd.Timestamp(t['exit_date'])
            hold_days.append((exd - ed).days)
        avg_hold = np.mean(hold_days) if hold_days else 0
    else:
        avg_hold = 0
    
    result = {
        'factor_name': factor_name,
        'param_label': param_label,
        'top_k': top_k,
        'total_return_pct': round(total_return, 2),
        'annual_return_pct': round(ann_return, 2),
        'sharpe': round(sharpe, 3) if not np.isnan(sharpe) else None,
        'max_drawdown_pct': round(max_dd, 2),
        'calmar': round(calmar, 3) if not np.isnan(calmar) else None,
        'win_rate_pct': round(win_rate, 1),
        'total_trades': len(trade_history),
        'avg_holding_days': round(avg_hold, 1),
        'n_months': len(month_end_dates),
        'n_candidates_avg': round(np.mean([len(candidates)])),
        'start_date': str(eq_df['date'].iloc[0].date()),
        'end_date': str(eq_df['date'].iloc[-1].date()),
    }
    
    # Save detailed files
    prefix = f"{factor_name}_{param_label}_top{top_k}".replace('.','_').replace('-','_').replace(' ','')
    eq_df.to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_equity.csv"), index=False, encoding='utf-8-sig')
    
    if trade_history:
        tr_df = pd.DataFrame(trade_history)
        tr_df.to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_trades.csv"), index=False, encoding='utf-8-sig')
    
    with open(os.path.join(OUTPUT_DIR, f"{prefix}_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Done: R={total_return:.1f}% A={ann_return:.1f}% S={sharpe:.2f} DD={max_dd:.1f}% W={win_rate:.0f}%")
    return result, eq_df, trade_history


# ============================================================
# 4. MULTI-FACTOR COMBINATION
# ============================================================
def multi_factor_backtest(df_dict, factor_funcs, weights, label, top_k=10, 
                           bt_start=BT_START, bt_end=BT_END, warmup_years=2):
    """
    多因子组合回测
    factor_funcs: list of (func, kwargs, ascending, weight)
    对每个ETF, 计算所有因子值, 标准化后加权求和, 排序选top_k
    """
    print(f"  Running [Multi: {label}] top={top_k} ...", end=' ', flush=True)
    
    all_dates = set()
    for code, df in df_dict.items():
        for d in df['date'].dt.strftime('%Y-%m-%d'):
            all_dates.add(d)
    all_dates = sorted(all_dates)
    
    bt_start_dt = pd.Timestamp(bt_start)
    bt_end_dt = pd.Timestamp(bt_end)
    
    df_all = pd.DataFrame({'date': pd.to_datetime(all_dates)})
    df_all['year_month'] = df_all['date'].dt.to_period('M')
    month_end_dates = df_all.groupby('year_month')['date'].last().reset_index(drop=True)
    month_end_dates = month_end_dates[(month_end_dates >= bt_start_dt + pd.Timedelta(days=365*warmup_years)) & 
                                       (month_end_dates <= bt_end_dt)]
    
    if len(month_end_dates) < 6:
        print("SKIP - not enough monthly data")
        return None
    
    # Pre-compute all factor values
    all_factors = {}
    for fi, (func, kwargs, asc, w) in enumerate(factor_funcs):
        fname = f"f{fi}"
        all_factors[fname] = {'asc': asc, 'weight': w}
        fv_dict = {}
        for code, df in df_dict.items():
            fv = func(df, **kwargs)
            fv.index = df['date']
            fv_dict[code] = fv
        all_factors[fname]['values'] = fv_dict
    
    # Backtest loop (same as single factor)
    cash = INITIAL_CASH
    holdings = {}
    equity_curve = []
    trade_history = []
    
    for idx in range(len(month_end_dates)):
        rebal_date = month_end_dates.iloc[idx]
        rebal_date_str = rebal_date.strftime('%Y-%m-%d')
        
        i_next = all_dates.index(rebal_date_str) + 1 if rebal_date_str in all_dates else -1
        if i_next >= len(all_dates):
            continue
        exec_date_str = all_dates[i_next]
        exec_date = pd.Timestamp(exec_date_str)
        
        # Compute composite score for each ETF
        candidates = []
        for code in df_dict:
            scores = []
            valid = True
            for fi, fcfg in all_factors.items():
                fv_series = fcfg['values'][code]
                if rebal_date in fv_series.index:
                    val = fv_series.loc[rebal_date]
                    if pd.notna(val) and not np.isinf(val):
                        scores.append((val, fcfg['asc']))
                    else:
                        valid = False
                        break
                else:
                    valid = False
                    break
            
            if not valid or len(scores) != len(factor_funcs):
                continue
            
            # Check exec_date price availability
            etf_df = df_dict[code]
            if exec_date not in etf_df['date'].values:
                continue
            
            # Rank-standardize + weighted sum
            # For each factor, get cross-sectional rank (0-1)
            # We need all scores for this at once, so we'll do it per factor
            candidates.append((code, scores))
        
        if len(candidates) < 3:
            # liquidate
            for code, pos in list(holdings.items()):
                etf_df = df_dict[code]
                exec_mask = etf_df['date'] == exec_date
                if exec_mask.any():
                    price = etf_df.loc[exec_mask, 'open'].iloc[0]
                    if pd.notna(price) and price > 0:
                        proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                        pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                        trade_history.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_date_str,
                            'symbol': code,
                            'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                            'pnl_pct': round(pnl / (pos['size'] * pos['entry_price']) * 100, 2),
                        })
                        cash += proceeds
            holdings.clear()
            equity_curve.append({'date': exec_date_str, 'value': round(cash, 2)})
            continue
        
        # Rank standardization for each factor
        # For each factor index fi, extract all values, rank, normalize
        n_factors = len(factor_funcs)
        for fi in range(n_factors):
            vals = [(code, c[1][fi][0]) for code, c in candidates]
            sorted_vals = sorted(vals, key=lambda x: x[1])
            ranks = {code: rank for rank, (code, val) in enumerate(sorted_vals)}
            max_rank = len(sorted_vals) - 1
            for ci, (code, scores) in enumerate(candidates):
                rank = ranks[code]
                normalized = rank / max_rank if max_rank > 0 else 0.5
                if factor_funcs[fi][2]:  # ascending=True -> smaller is better
                    normalized = 1 - normalized
                candidates[ci][1][fi] = normalized
        
        # Weighted sum
        scored = []
        for code, scores in candidates:
            composite = sum(s * factor_funcs[fi][3] for fi, s in enumerate(scores))
            scored.append((code, composite))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = [code for code, val in scored[:top_k]]
        n_selected = len(selected)
        
        # Liquidate exits
        for code, pos in list(holdings.items()):
            if code not in selected:
                etf_df = df_dict[code]
                exec_mask = etf_df['date'] == exec_date
                if exec_mask.any():
                    price = etf_df.loc[exec_mask, 'open'].iloc[0]
                    if pd.notna(price) and price > 0:
                        proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                        pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                        trade_history.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_date_str,
                            'symbol': code,
                            'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                            'pnl_pct': round(pnl / (pos['size'] * pos['entry_price']) * 100, 2),
                        })
                        cash += proceeds
                        del holdings[code]
        
        # Buy new
        if n_selected == 0:
            equity_curve.append({'date': exec_date_str, 'value': round(cash, 2)})
            continue
        
        cash_per_position = cash / n_selected
        for code in selected:
            if code in holdings:
                continue
            etf_df = df_dict[code]
            exec_mask = etf_df['date'] == exec_date
            if not exec_mask.any():
                continue
            price = etf_df.loc[exec_mask, 'open'].iloc[0]
            if pd.isna(price) or price <= 0:
                continue
            size = int(cash_per_position / (price * (1 + COMMISSION)))
            if size <= 0:
                continue
            cost = size * price * (1 + COMMISSION)
            if cost > cash:
                size = int(cash / (price * (1 + COMMISSION)))
                cost = size * price * (1 + COMMISSION)
                if size <= 0:
                    continue
            cash -= cost
            holdings[code] = {'size': size, 'entry_price': price, 'entry_date': exec_date_str}
        
        # Equity
        total_value = cash
        for code, pos in holdings.items():
            etf_df = df_dict[code]
            mask = etf_df['date'] == exec_date
            if mask.any():
                cp = etf_df.loc[mask, 'close'].iloc[0]
                total_value += pos['size'] * (cp if pd.notna(cp) else pos['entry_price'])
            else:
                total_value += pos['size'] * pos['entry_price']
        equity_curve.append({'date': exec_date_str, 'value': round(total_value, 2)})
    
    # Force liquidate
    final_date_str = all_dates[-1]
    final_date = pd.Timestamp(final_date_str)
    for code, pos in list(holdings.items()):
        etf_df = df_dict[code]
        mask = etf_df['date'] == final_date
        if mask.any():
            price = etf_df.loc[mask, 'close'].iloc[0]
            if pd.notna(price) and price > 0:
                proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                trade_history.append({
                    'entry_date': pos['entry_date'],
                    'exit_date': final_date_str,
                    'symbol': code,
                    'side': 'long',
                    'size': pos['size'],
                    'entry_price': pos['entry_price'],
                    'exit_price': price,
                    'pnl': round(pnl, 2),
                    'pnl_pct': round(pnl / (pos['size'] * pos['entry_price']) * 100, 2),
                })
                cash += proceeds
                del holdings[code]
    
    total_value = cash
    for code, pos in holdings.items():
        etf_df = df_dict[code]
        mask = etf_df['date'] == final_date
        if mask.any():
            cp = etf_df.loc[mask, 'close'].iloc[0]
            total_value += pos['size'] * (cp if pd.notna(cp) else pos['entry_price'])
    equity_curve.append({'date': final_date_str, 'value': round(total_value, 2)})
    
    if len(equity_curve) < 6:
        print("SKIP - too few equity points")
        return None
    
    eq_df = pd.DataFrame(equity_curve)
    eq_df['date'] = pd.to_datetime(eq_df['date'])
    eq_df = eq_df.sort_values('date').reset_index(drop=True)
    
    initial_val = eq_df['value'].iloc[0]
    final_val = eq_df['value'].iloc[-1]
    total_return = (final_val / initial_val - 1) * 100
    total_days = (eq_df['date'].iloc[-1] - eq_df['date'].iloc[0]).days
    years = total_days / 365.25
    ann_return = ((final_val / initial_val) ** (1 / years) - 1) * 100 if years > 0 else 0
    
    eq_df['daily_ret'] = eq_df['value'].pct_change()
    daily_ret = eq_df['daily_ret'].dropna()
    sharpe = np.nan
    if len(daily_ret) > 10:
        mean_ret = daily_ret.mean()
        std_ret = daily_ret.std()
        if std_ret > 0:
            sharpe = (mean_ret / std_ret) * np.sqrt(252)
    
    eq_df['cummax'] = eq_df['value'].cummax()
    eq_df['dd'] = (eq_df['value'] / eq_df['cummax'] - 1) * 100
    max_dd = eq_df['dd'].min()
    
    winning = sum(1 for t in trade_history if t['pnl'] > 0)
    win_rate = winning / len(trade_history) * 100 if trade_history else 0
    calmar = ann_return / abs(max_dd) if max_dd < 0 else np.nan
    
    hold_days = []
    for t in trade_history:
        ed = pd.Timestamp(t['entry_date'])
        exd = pd.Timestamp(t['exit_date'])
        hold_days.append((exd - ed).days)
    avg_hold = np.mean(hold_days) if hold_days else 0
    
    result = {
        'factor_name': f'Multi_{label}',
        'param_label': label,
        'top_k': top_k,
        'total_return_pct': round(total_return, 2),
        'annual_return_pct': round(ann_return, 2),
        'sharpe': round(sharpe, 3) if not np.isnan(sharpe) else None,
        'max_drawdown_pct': round(max_dd, 2),
        'calmar': round(calmar, 3) if not np.isnan(calmar) else None,
        'win_rate_pct': round(win_rate, 1),
        'total_trades': len(trade_history),
        'avg_holding_days': round(avg_hold, 1),
        'n_months': len(month_end_dates),
        'start_date': str(eq_df['date'].iloc[0].date()),
        'end_date': str(eq_df['date'].iloc[-1].date()),
    }
    
    prefix = f"multi_{label.replace(' ','').replace('+','_')}_top{top_k}"
    eq_df.to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_equity.csv"), index=False, encoding='utf-8-sig')
    if trade_history:
        tr_df = pd.DataFrame(trade_history)
        tr_df.to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_trades.csv"), index=False, encoding='utf-8-sig')
    with open(os.path.join(OUTPUT_DIR, f"{prefix}_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Done: R={total_return:.1f}% A={ann_return:.1f}% S={sharpe:.2f} DD={max_dd:.1f}% W={win_rate:.0f}%")
    return result, eq_df, trade_history


# ============================================================
# 5. VISUALIZATION
# ============================================================
def plot_comparison(results_list, title):
    """Plot equity curves for multiple strategies"""
    fig, axes = plt.subplots(3, 1, figsize=(16, 14), gridspec_kw={'height_ratios': [3, 1.2, 1.2]})
    
    colors = plt.cm.tab20(np.linspace(0, 1, len(results_list)))
    
    # Sort by total return for legend
    sorted_results = sorted(results_list, key=lambda r: r[0]['total_return_pct'], reverse=True)
    
    # Equity curve
    ax1 = axes[0]
    for i, (res, eq_df, _) in enumerate(sorted_results):
        eq_df = eq_df.sort_values('date')
        norm = eq_df['value'].values / eq_df['value'].iloc[0] * 100
        label = f"{res['factor_name']}_{res['param_label']}_top{res['top_k']} ({res['annual_return_pct']:.0f}%)"
        ax1.plot(eq_df['date'], norm, color=colors[i], linewidth=1.2, alpha=0.85, label=label)
    
    ax1.set_ylabel('净值 (初始=100)', fontsize=12)
    ax1.set_title(title, fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=7, ncol=2)
    ax1.grid(True, alpha=0.3)
    ax1.axhline(100, color='black', linewidth=0.5, linestyle='--')
    
    # Sharpe bar chart
    ax2 = axes[1]
    labels_short = [f"{r[0]['factor_name']}_{r[0]['param_label']}_T{r[0]['top_k']}"[:35] for r in sorted_results]
    shs = [r[0].get('sharpe', 0) or 0 for r in sorted_results]
    bars = ax2.bar(range(len(shs)), shs, color=colors[:len(shs)])
    ax2.set_ylabel('Sharpe', fontsize=12)
    ax2.set_xticks(range(len(shs)))
    ax2.set_xticklabels(labels_short, rotation=90, fontsize=6)
    ax2.axhline(1.0, color='red', linestyle='--', alpha=0.5, label='Sharpe=1')
    ax2.axhline(0, color='black', linewidth=0.5)
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Max DD bar chart
    ax3 = axes[2]
    dds = [abs(r[0]['max_drawdown_pct']) for r in sorted_results]
    ax3.bar(range(len(dds)), dds, color='coral', alpha=0.7)
    ax3.set_ylabel('最大回撤(%)', fontsize=12)
    ax3.set_xlabel('策略', fontsize=12)
    ax3.set_xticks(range(len(dds)))
    ax3.set_xticklabels(labels_short, rotation=90, fontsize=6)
    ax3.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'comparison_all.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved chart: {path}")
    return path


def plot_top_n(results_list, n=8, title="前N名业绩曲线"):
    """Plot top N by Sharpe"""
    valid = [(r[0], r[1], r[2]) for r in results_list if r[0].get('sharpe') is not None]
    valid.sort(key=lambda r: r[0]['sharpe'], reverse=True)
    top = valid[:n]
    
    fig, ax = plt.subplots(figsize=(14, 8))
    colors = plt.cm.Set1(np.linspace(0, 1, len(top)))
    
    for i, (res, eq_df, _) in enumerate(top):
        eq_df = eq_df.sort_values('date')
        norm = eq_df['value'].values / eq_df['value'].iloc[0] * 100
        label = f"{res['factor_name']}_{res['param_label']}_T{res['top_k']} (Sh={res['sharpe']:.2f}, R={res['annual_return_pct']:.1f}%, DD={res['max_drawdown_pct']:.1f}%)"
        ax.plot(eq_df['date'], norm, color=colors[i], linewidth=1.5, label=label)
    
    ax.set_ylabel('净值 (初始=100)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.axhline(100, color='black', linewidth=0.5, linestyle='--')
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'comparison_top.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved chart: {path}")
    return path


# ============================================================
# 6. MAIN
# ============================================================
def main():
    print("=" * 60)
    print("A股 ETF 多因子回测系统")
    print("=" * 60)
    print(f"数据目录: {DATA_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"回测范围: {BT_START} ~ {BT_END}")
    print()
    
    # Load data
    print("加载ETF数据...")
    etf_data = load_all_etfs(DATA_DIR)
    print(f"共加载 {len(etf_data)} 只ETF")
    
    # Compute market return (CSI 300 000300) for beta
    if '000300' in etf_data:
        mkt_df = etf_data['000300']
        mkt_ret = mkt_df.set_index('date')['close'].pct_change()
        print("市场基准: 000300 (沪深300)")
    else:
        # load separately
        idx_path = os.path.join(DATA_DIR, '000300.json')
        if os.path.exists(idx_path):
            with open(idx_path, encoding='utf-8') as f:
                raw = json.load(f)
            mkt_df = pd.DataFrame(raw['records'])
            mkt_df['date'] = pd.to_datetime(mkt_df['date'])
            mkt_df = mkt_df.sort_values('date').reset_index(drop=True)
            mkt_ret = mkt_df.set_index('date')['close'].pct_change()
            print("市场基准: 000300 (沪深300) - 单独加载")
        else:
            mkt_ret = None
            print("警告: 000300 (沪深300) 数据不可用, 无法计算Beta")
    
    all_results = []
    
    # ============================================================
    # Single Factor Tests
    # ============================================================
    print("\n" + "=" * 60)
    print("单因子测试")
    print("=" * 60)
    
    test_configs = [
        # (name, param_label, func, kwargs, ascending, top_k_list)
        # ascending=True -> 选最小的, ascending=False -> 选最大的
        
        # 1. Momentum 12-1 月
        ("动量12-1", "12m", compute_momentum, {'months': 12}, False, TOP_KS),
        ("动量6-1", "6m", compute_momentum, {'months': 6}, False, TOP_KS),
        ("动量3-1", "3m", compute_momentum, {'months': 3}, False, TOP_KS),
        
        # 2. Simple momentum
        ("动量简单12m", "12m", compute_momentum_simple, {'months': 12}, False, TOP_KS),
        ("动量简单6m", "6m", compute_momentum_simple, {'months': 6}, False, TOP_KS),
        ("动量简单3m", "3m", compute_momentum_simple, {'months': 3}, False, TOP_KS),
        
        # 3. Low Vol
        ("低波动12m", "12m", compute_low_vol, {'months': 12}, True, TOP_KS),
        ("低波动6m", "6m", compute_low_vol, {'months': 6}, True, TOP_KS),
        ("低波动3m", "3m", compute_low_vol, {'months': 3}, True, TOP_KS),
        
        # 4. Beta (low beta)
        ("低Beta12m", "12m", compute_beta, {'months': 12, 'market_ret': mkt_ret}, True, TOP_KS),
        ("低Beta6m", "6m", compute_beta, {'months': 6, 'market_ret': mkt_ret}, True, TOP_KS),
        
        # 5. Volume momentum
        ("量能趋势", "12-3m", compute_vol_momentum, {'months_slow': 12, 'months_fast': 3}, False, TOP_KS),
        ("量能趋势", "6-1m", compute_vol_momentum, {'months_slow': 6, 'months_fast': 1}, False, TOP_KS),
        
        # 6. Price / MA
        ("价格均线比", "MA60", compute_price_ma, {'days': 60}, False, TOP_KS),
        ("价格均线比", "MA120", compute_price_ma, {'days': 120}, False, TOP_KS),
        
        # 7. Short-term reversal (buy recent losers)
        ("短期反转", "1m", compute_short_reversal, {'months': 1}, False, TOP_KS),
    ]
    
    for name, param, func, kwargs, asc, topk_list in test_configs:
        for top_k in topk_list:
            try:
                res = monthly_factor_backtest(
                    etf_data, name, param, lambda df, kw=kwargs, f=func: f(df, **kw),
                    top_k=top_k, ascending=asc
                )
                if res is not None:
                    all_results.append(res)
            except Exception as e:
                print(f"  ERROR on {name} {param} top{top_k}: {e}")
    
    # ============================================================
    # Multi-Factor Combinations
    # ============================================================
    print("\n" + "=" * 60)
    print("多因子组合测试")
    print("=" * 60)
    
    multi_configs = [
        # (label, [(func, kwargs, ascending, weight), ...])
        # Weighted rank-based composite
        ("动量+低波", [
            (compute_momentum, {'months': 12}, False, 0.5),
            (compute_low_vol, {'months': 12}, True, 0.5),
        ]),
        ("动量+低Beta", [
            (compute_momentum, {'months': 12}, False, 0.5),
            (compute_beta, {'months': 12, 'market_ret': mkt_ret}, True, 0.5),
        ]),
        ("低波+低Beta", [
            (compute_low_vol, {'months': 12}, True, 0.5),
            (compute_beta, {'months': 12, 'market_ret': mkt_ret}, True, 0.5),
        ]),
        ("动量+低波+低Beta", [
            (compute_momentum, {'months': 12}, False, 0.34),
            (compute_low_vol, {'months': 12}, True, 0.33),
            (compute_beta, {'months': 12, 'market_ret': mkt_ret}, True, 0.33),
        ]),
        ("动量+量能+低波", [
            (compute_momentum, {'months': 12}, False, 0.4),
            (compute_vol_momentum, {'months_slow': 12, 'months_fast': 3}, False, 0.3),
            (compute_low_vol, {'months': 12}, True, 0.3),
        ]),
        ("动量+价格均线+低波", [
            (compute_momentum, {'months': 12}, False, 0.4),
            (compute_price_ma, {'days': 60}, False, 0.3),
            (compute_low_vol, {'months': 12}, True, 0.3),
        ]),
        ("全因子等权", [
            (compute_momentum, {'months': 12}, False, 0.2),
            (compute_low_vol, {'months': 12}, True, 0.2),
            (compute_beta, {'months': 12, 'market_ret': mkt_ret}, True, 0.2),
            (compute_vol_momentum, {'months_slow': 12, 'months_fast': 3}, False, 0.2),
            (compute_price_ma, {'days': 60}, False, 0.2),
        ]),
    ]
    
    for label, factor_configs in multi_configs:
        for top_k in [5, 10, 20]:
            try:
                res = multi_factor_backtest(
                    etf_data, factor_configs, None, label, top_k=top_k
                )
                if res is not None:
                    all_results.append(res)
            except Exception as e:
                print(f"  ERROR on Multi {label} top{top_k}: {e}")
    
    # ============================================================
    # Results Summary
    # ============================================================
    print("\n" + "=" * 60)
    print("结果汇总")
    print("=" * 60)
    
    # Filter valid results (those that returned good data)
    valid_results = [(r[0], r[1], r[2]) for r in all_results if r[0].get('sharpe') is not None]
    valid_results.sort(key=lambda r: r[0]['sharpe'], reverse=True)
    
    # Save summary CSV
    rows = []
    for res, _, _ in valid_results:
        rows.append({
            '因子': res['factor_name'],
            '参数': res['param_label'],
            'TopK': res['top_k'],
            '年化收益%': res['annual_return_pct'],
            'Sharpe': res['sharpe'],
            '最大回撤%': res['max_drawdown_pct'],
            'Calmar': res['calmar'],
            '胜率%': res['win_rate_pct'],
            '交易次数': res['total_trades'],
            '平均持仓天数': res['avg_holding_days'],
        })
    
    df_summary = pd.DataFrame(rows)
    summary_path = os.path.join(OUTPUT_DIR, 'factor_results_summary.csv')
    df_summary.to_csv(summary_path, index=False, encoding='utf-8-sig')
    print(f"\n保存汇总: {summary_path}")
    
    # Print top 20
    print("\n---------- Top 20 by Sharpe ----------")
    print(f"{'排名':>4} {'因子':<18} {'参数':<10} {'TopK':>5} {'年化%':>7} {'Sharpe':>8} {'回撤%':>7} {'Calmar':>7} {'胜率%':>6} {'交易':>5}")
    print("-" * 85)
    for i, (res, _, _) in enumerate(valid_results[:20]):
        c = res.get('calmar')
        if c is None or isinstance(c, str):
            calmar_str = 'N/A'
        else:
            calmar_str = f'{c:.2f}'
        print(f"{i+1:>4} {res['factor_name']:<18} {res['param_label']:<10} {res['top_k']:>5} {res['annual_return_pct']:>6.1f}% {res['sharpe']:>8.3f} {res['max_drawdown_pct']:>6.1f}% {calmar_str:>7} {res['win_rate_pct']:>5.1f}% {res['total_trades']:>5}")
    
    # Plot charts
    print("\n生成图表...")
    plot_comparison(valid_results, "A股ETF因子回测 - 整体对比")
    plot_top_n(valid_results, n=8, title="Top 8 策略 (按 Sharpe 排序)")
    
    # Save best individual factors equity curves
    print(f"\n输出目录: {OUTPUT_DIR}")
    print("完成!")
    
    return valid_results


if __name__ == '__main__':
    main()

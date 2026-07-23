"""
A股 ETF 多因子回测
单因子测试 + 多因子组合
数据: D:\\QClaw_Trading\\data\\history\\ 下所有ETF JSON文件
回测方式: 月末截面排序 -> 买入Top K -> 等权持有 -> 下月再平衡
执行时点: 信号确认后次日开盘
"""

import json, os, sys
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
# CONFIG
# ============================================================
DATA_DIR = 'D:/QClaw_Trading/data/history/'
OUTPUT_DIR = 'D:/QClaw_Trading/backtest_output/factor_run_' + datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs(OUTPUT_DIR, exist_ok=True)

INITIAL_CASH = 1_000_000
COMMISSION = 0.0003
SELL_COMMISSION = 0.0003
SELL_TAX = 0.0  # ETF 免印花税
MIN_RECORDS = 180
TOP_KS = [5, 10, 20]
BT_START = '2019-01-01'
BT_END = '2026-07-10'


# ============================================================
# 1. LOAD DATA
# ============================================================
def load_all_etfs(data_dir):
    """return dict of {code: DataFrame}"""
    etf_data = {}
    for fname in os.listdir(data_dir):
        if not fname.endswith('.json'):
            continue
        code = fname[:-5]
        # ETF code prefixes
        if code[:3] not in ('159','510','511','512','513','515','516','517','518',
                            '560','561','562','563','588'):
            if code[:2] not in ('51','56','58'):
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
        for col in ['open','close','high','low','vol']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        etf_data[code] = df
    return etf_data


# ============================================================
# 2. FACTOR FUNCTIONS (return Series aligned to df index)
# ============================================================
def factor_momentum_12_1(df):
    """12-1月动量: skip last month"""
    if len(df) < 260:
        return pd.Series(index=df.index, dtype=float)
    return df['close'].shift(21) / df['close'].shift(21+252) - 1

def factor_momentum_6_1(df):
    """6-1月动量: skip last month"""
    if len(df) < 140:
        return pd.Series(index=df.index, dtype=float)
    return df['close'].shift(21) / df['close'].shift(21+126) - 1

def factor_momentum_3_1(df):
    """3-1月动量: skip last month"""
    if len(df) < 80:
        return pd.Series(index=df.index, dtype=float)
    return df['close'].shift(21) / df['close'].shift(21+63) - 1

def factor_momentum_simple_12(df):
    """简单12月动量"""
    if len(df) < 260:
        return pd.Series(index=df.index, dtype=float)
    return df['close'] / df['close'].shift(252) - 1

def factor_momentum_simple_6(df):
    if len(df) < 140:
        return pd.Series(index=df.index, dtype=float)
    return df['close'] / df['close'].shift(126) - 1

def factor_momentum_simple_3(df):
    if len(df) < 80:
        return pd.Series(index=df.index, dtype=float)
    return df['close'] / df['close'].shift(63) - 1

def factor_low_vol_12(df):
    """过去12个月日收益率标准差"""
    if len(df) < 260:
        return pd.Series(index=df.index, dtype=float)
    ret = df['close'].pct_change()
    return ret.rolling(252).std()

def factor_low_vol_6(df):
    if len(df) < 140:
        return pd.Series(index=df.index, dtype=float)
    ret = df['close'].pct_change()
    return ret.rolling(126).std()

def factor_low_vol_3(df):
    if len(df) < 80:
        return pd.Series(index=df.index, dtype=float)
    ret = df['close'].pct_change()
    return ret.rolling(63).std()

def factor_vol_momentum_12_3(df):
    """量能趋势: 3月均量 / 12月均量"""
    if len(df) < 260:
        return pd.Series(index=df.index, dtype=float)
    return df['vol'].rolling(63).mean() / df['vol'].rolling(252).mean()

def factor_vol_momentum_6_1(df):
    """量能趋势: 1月均量 / 6月均量"""
    if len(df) < 140:
        return pd.Series(index=df.index, dtype=float)
    return df['vol'].rolling(21).mean() / df['vol'].rolling(126).mean()

def factor_price_ma60(df):
    """价格/MA60"""
    if len(df) < 70:
        return pd.Series(index=df.index, dtype=float)
    return df['close'] / df['close'].rolling(60).mean()

def factor_price_ma120(df):
    """价格/MA120"""
    if len(df) < 130:
        return pd.Series(index=df.index, dtype=float)
    return df['close'] / df['close'].rolling(120).mean()

def factor_short_rev_1m(df):
    """短期反转: 过去1个月收益率 (取负值, 涨多的预期跌)"""
    if len(df) < 25:
        return pd.Series(index=df.index, dtype=float)
    return -(df['close'] / df['close'].shift(21) - 1)

# ============================================================
# 3. CORE BACKTEST
# ============================================================
def run_factor_backtest(name, param_label, factor_fn, etf_data, top_k=10,
                         ascending=False, warmup_months=24):
    """
    Monthly cross-section factor backtest.
    ascending: True = select smallest factor values
    """
    print(f"  [{name} {param_label} top{top_k}] ", end='', flush=True)
    
    # Build monthly rebalance dates from all ETF data
    all_date_set = set()
    for code, df in etf_data.items():
        for d in df['date'].dt.strftime('%Y-%m-%d'):
            all_date_set.add(d)
    all_dates = sorted(all_date_set)
    all_df = pd.DataFrame({'date': pd.to_datetime(all_dates)})
    all_df['ym'] = all_df['date'].dt.to_period('M')
    month_ends = all_df.groupby('ym')['date'].last().reset_index(drop=True)
    
    # Filter to bt range with warmup
    bt_start = pd.Timestamp(BT_START)
    bt_end = pd.Timestamp(BT_END)
    warmup_start = bt_start - pd.Timedelta(days=365*warmup_months//12 + 30)
    month_ends = month_ends[(month_ends >= warmup_start) & (month_ends <= bt_end)]
    
    if len(month_ends) < 12:
        print("SKIP - too few months")
        return None
    
    # Pre-compute factor values for all ETFs
    fact_vals = {}  # {code: {date_str: value}}
    for code, df in etf_data.items():
        fv = factor_fn(df)
        fv.index = df['date'].dt.strftime('%Y-%m-%d')
        fd = {d: v for d, v in zip(fv.index, fv.values) if pd.notna(v) and not np.isinf(v)}
        if len(fd) > 100:  # need enough factor data
            fact_vals[code] = fd
    
    print(f"n_etf={len(fact_vals)} ", end='', flush=True)
    
    # Backtest
    cash = INITIAL_CASH
    holdings = {}
    equity_curve = []
    trade_history = []
    
    for idx in range(len(month_ends)):
        rebal_date = month_ends.iloc[idx]
        rebal_str = rebal_date.strftime('%Y-%m-%d')
        
        # Get next trading day for execution
        if rebal_str in all_date_set:
            ri = all_dates.index(rebal_str)
            if ri + 1 >= len(all_dates):
                continue
            exec_str = all_dates[ri + 1]
        else:
            continue
        
        # Skip warmup
        if rebal_date < bt_start + pd.Timedelta(days=365*warmup_months//12 - 30):
            # Still update pure state
            continue
        
        # Collect candidates
        candidates = []
        for code, fdict in fact_vals.items():
            if rebal_str in fdict:
                candidates.append((code, fdict[rebal_str]))
        
        if len(candidates) < 5:
            # Liquidate all
            for code, pos in list(holdings.items()):
                etf_df = etf_data[code]
                mask = etf_df['date'].dt.strftime('%Y-%m-%d') == exec_str
                if mask.any():
                    price = etf_df.loc[mask, 'open'].iloc[0]
                    if pd.notna(price) and price > 0:
                        proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                        pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                        trade_history.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_str,
                            'symbol': code,
                            'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
            holdings.clear()
            equity_curve.append({'date': exec_str, 'value': round(cash, 2)})
            continue
        
        # Rank by factor
        candidates.sort(key=lambda x: x[1], reverse=not ascending)
        selected = [c for c, v in candidates[:top_k]]
        
        # Sell exits
        for code, pos in list(holdings.items()):
            if code not in selected:
                etf_df = etf_data[code]
                mask = etf_df['date'].dt.strftime('%Y-%m-%d') == exec_str
                if mask.any():
                    price = etf_df.loc[mask, 'open'].iloc[0]
                    if pd.notna(price) and price > 0:
                        proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                        pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                        trade_history.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_str,
                            'symbol': code,
                            'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
                        del holdings[code]
        
        # Buy new
        if len(selected) == 0:
            equity_curve.append({'date': exec_str, 'value': round(cash, 2)})
            continue
        
        cash_per = cash / len(selected)
        for code in selected:
            if code in holdings:
                continue
            etf_df = etf_data[code]
            mask = etf_df['date'].dt.strftime('%Y-%m-%d') == exec_str
            if not mask.any():
                continue
            price = etf_df.loc[mask, 'open'].iloc[0]
            if pd.isna(price) or price <= 0:
                continue
            size = int(cash_per / (price * (1 + COMMISSION)))
            if size <= 0:
                continue
            cost = size * price * (1 + COMMISSION)
            if cost > cash:
                size = int(cash / (price * (1 + COMMISSION)))
                cost = size * price * (1 + COMMISSION)
                if size <= 0:
                    continue
            cash -= cost
            holdings[code] = {'size': size, 'entry_price': price, 'entry_date': exec_str}
        
        # Record equity
        tv = cash
        for code, pos in holdings.items():
            etf_df = etf_data[code]
            mask = etf_df['date'].dt.strftime('%Y-%m-%d') == exec_str
            if mask.any():
                cp = etf_df.loc[mask, 'close'].iloc[0]
                tv += pos['size'] * (cp if pd.notna(cp) else pos['entry_price'])
            else:
                tv += pos['size'] * pos['entry_price']
        equity_curve.append({'date': exec_str, 'value': round(tv, 2)})
    
    # Force liquidate at end
    final_str = all_dates[-1]
    for code, pos in list(holdings.items()):
        etf_df = etf_data[code]
        mask = etf_df['date'].dt.strftime('%Y-%m-%d') == final_str
        if mask.any():
            price = etf_df.loc[mask, 'close'].iloc[0]
        else:
            # use last available
            price = etf_data[code]['close'].iloc[-1]
        if pd.notna(price) and price > 0:
            proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
            pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
            trade_history.append({
                'entry_date': pos['entry_date'],
                'exit_date': final_str,
                'symbol': code,
                'side': 'long',
                'size': pos['size'],
                'entry_price': pos['entry_price'],
                'exit_price': price,
                'pnl': round(pnl, 2),
            })
            cash += proceeds
            del holdings[code]
    
    tv = cash
    for code, pos in holdings.items():
        tv += pos['size'] * pos['entry_price']
    equity_curve.append({'date': final_str, 'value': round(tv, 2)})
    
    # ===== METRICS =====
    if len(equity_curve) < 6:
        print("SKIP - short")
        return None
    
    eq = pd.DataFrame(equity_curve)
    eq['date'] = pd.to_datetime(eq['date'])
    eq = eq.sort_values('date').reset_index(drop=True)
    
    iv = eq['value'].iloc[0]
    fv = eq['value'].iloc[-1]
    tr = (fv / iv - 1) * 100
    days_run = (eq['date'].iloc[-1] - eq['date'].iloc[0]).days
    years = max(days_run / 365.25, 0.1)
    ar = ((fv / iv) ** (1 / years) - 1) * 100
    
    eq['dr'] = eq['value'].pct_change()
    dr = eq['dr'].dropna()
    sharpe = np.nan
    if len(dr) > 10 and dr.std() > 0:
        sharpe = (dr.mean() / dr.std()) * np.sqrt(252)
    
    eq['cmax'] = eq['value'].cummax()
    eq['dd'] = (eq['value'] / eq['cmax'] - 1) * 100
    mdd = eq['dd'].min()
    
    wins = sum(1 for t in trade_history if t['pnl'] > 0)
    wr = wins / max(len(trade_history), 1) * 100
    calmar = ar / abs(mdd) if mdd < 0 else np.nan
    
    hold_days = []
    for t in trade_history:
        ed = pd.Timestamp(t['entry_date'])
        exd = pd.Timestamp(t['exit_date'])
        hold_days.append((exd - ed).days)
    avg_hold = np.mean(hold_days) if hold_days else 0
    
    res = {
        'factor_name': name,
        'param_label': param_label,
        'top_k': top_k,
        'total_return_pct': round(tr, 1),
        'annual_return_pct': round(ar, 1),
        'sharpe': round(sharpe, 3) if not np.isnan(sharpe) else None,
        'max_drawdown_pct': round(mdd, 1),
        'calmar': round(calmar, 2) if not np.isnan(calmar) else None,
        'win_rate_pct': round(wr, 1),
        'total_trades': len(trade_history),
        'avg_holding_days': round(avg_hold, 1),
        'n_months': len([d for d in month_ends if d >= bt_start + pd.Timedelta(days=365*warmup_months//12-30)]),
        'start_date': str(eq['date'].iloc[0].date()),
        'end_date': str(eq['date'].iloc[-1].date()),
    }
    
    prefix = f"{name}_{param_label}_top{top_k}".replace('.','').replace('-','_').replace(' ','')
    eq.to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_equity.csv"), index=False, encoding='utf-8-sig')
    if trade_history:
        pd.DataFrame(trade_history).to_csv(
            os.path.join(OUTPUT_DIR, f"{prefix}_trades.csv"), index=False, encoding='utf-8-sig')
    with open(os.path.join(OUTPUT_DIR, f"{prefix}_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    
    print(f"R={tr:.1f}% A={ar:.1f}% S={sharpe:.2f} DD={mdd:.1f}%")
    return (res, eq, trade_history)


# ============================================================
# 4. MULTI-FACTOR BACKTEST
# ============================================================
def run_multi_factor(label, factor_configs, etf_data, top_k=10, warmup_months=24):
    """
    factor_configs: list of (factor_fn, ascending, weight)
    Rank-standardize each factor, then weighted sum, select top_k
    """
    print(f"  [Multi: {label} top{top_k}] ", end='', flush=True)
    
    # Month ends
    all_date_set = set()
    for code, df in etf_data.items():
        for d in df['date'].dt.strftime('%Y-%m-%d'):
            all_date_set.add(d)
    all_dates = sorted(all_date_set)
    all_df = pd.DataFrame({'date': pd.to_datetime(all_dates)})
    all_df['ym'] = all_df['date'].dt.to_period('M')
    month_ends = all_df.groupby('ym')['date'].last().reset_index(drop=True)
    
    bt_start = pd.Timestamp(BT_START)
    bt_end = pd.Timestamp(BT_END)
    warmup_start = bt_start - pd.Timedelta(days=365*warmup_months//12 + 30)
    month_ends = month_ends[(month_ends >= warmup_start) & (month_ends <= bt_end)]
    
    if len(month_ends) < 12:
        print("SKIP")
        return None
    
    # Pre-compute all factor values
    all_fact = []  # list of {code: {date: value}}
    for fn, asc, w in factor_configs:
        fdict = {}
        for code, df in etf_data.items():
            fv = fn(df)
            fv.index = df['date'].dt.strftime('%Y-%m-%d')
            fd = {d: v for d, v in zip(fv.index, fv.values) if pd.notna(v) and not np.isinf(v)}
            if len(fd) > 100:
                fdict[code] = fd
        all_fact.append({'asc': asc, 'weight': w, 'values': fdict})
    
    # Only keep ETFs that have ALL factor values
    common_codes = None
    for fi in all_fact:
        codes = set(fi['values'].keys())
        if common_codes is None:
            common_codes = codes
        else:
            common_codes = common_codes & codes
    
    if common_codes is None or len(common_codes) < 10:
        print(f"SKIP - only {len(common_codes or [])} common codes")
        return None
    
    # Filter to only common codes
    fi_list = []
    for fi in all_fact:
        fd = {c: fi['values'][c] for c in common_codes if c in fi['values']}
        fi_list.append({'asc': fi['asc'], 'weight': fi['weight'], 'values': fd})
    
    print(f"n_etf={len(common_codes)} ", end='', flush=True)
    
    # Backtest
    cash = INITIAL_CASH
    holdings = {}
    equity_curve = []
    trade_history = []
    
    for idx in range(len(month_ends)):
        rebal_date = month_ends.iloc[idx]
        rebal_str = rebal_date.strftime('%Y-%m-%d')
        
        if rebal_str in all_date_set:
            ri = all_dates.index(rebal_str)
            if ri + 1 >= len(all_dates):
                continue
            exec_str = all_dates[ri + 1]
        else:
            continue
        
        if rebal_date < bt_start + pd.Timedelta(days=365*warmup_months//12 - 30):
            continue
        
        # Get raw factor values at rebal_str for each factor
        factor_rank_sum = {}  # {code: weighted_score}
        for fi_i, fi in enumerate(fi_list):
            # Collect values for all common codes at this date
            codes_with_val = []
            for code in common_codes:
                fd = fi['values'].get(code, {})
                if rebal_str in fd:
                    codes_with_val.append((code, fd[rebal_str]))
            
            if len(codes_with_val) < 5:
                factor_rank_sum = {}
                break
            
            # Rank normalize
            sorted_codes = sorted(codes_with_val, key=lambda x: x[1])
            max_r = len(sorted_codes) - 1
            for rank_i, (c, v) in enumerate(sorted_codes):
                norm = rank_i / max_r if max_r > 0 else 0.5
                if fi['asc']:  # small is better
                    norm = 1 - norm
                factor_rank_sum[c] = factor_rank_sum.get(c, 0) + norm * fi['weight']
        
        if not factor_rank_sum:
            # Liquidate
            for code, pos in list(holdings.items()):
                etf_df = etf_data[code]
                mask = etf_df['date'].dt.strftime('%Y-%m-%d') == exec_str
                if mask.any():
                    price = etf_df.loc[mask, 'open'].iloc[0]
                    if pd.notna(price) and price > 0:
                        proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                        pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                        trade_history.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_str,
                            'symbol': code,
                            'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
            holdings.clear()
            equity_curve.append({'date': exec_str, 'value': round(cash, 2)})
            continue
        
        # Select top_k by composite score
        ranked = sorted(factor_rank_sum.items(), key=lambda x: x[1], reverse=True)
        selected = [c for c, s in ranked[:top_k]]
        
        # Check exec price availability
        valid_selected = []
        for code in selected:
            etf_df = etf_data[code]
            if (etf_df['date'].dt.strftime('%Y-%m-%d') == exec_str).any():
                valid_selected.append(code)
        selected = valid_selected
        
        # Sell exits
        for code, pos in list(holdings.items()):
            if code not in selected:
                etf_df = etf_data[code]
                mask = etf_df['date'].dt.strftime('%Y-%m-%d') == exec_str
                if mask.any():
                    price = etf_df.loc[mask, 'open'].iloc[0]
                    if pd.notna(price) and price > 0:
                        proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                        pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                        trade_history.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_str,
                            'symbol': code,
                            'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
                        del holdings[code]
        
        # Buy new
        if len(selected) == 0:
            equity_curve.append({'date': exec_str, 'value': round(cash, 2)})
            continue
        
        cash_per = cash / len(selected)
        for code in selected:
            if code in holdings:
                continue
            etf_df = etf_data[code]
            mask = etf_df['date'].dt.strftime('%Y-%m-%d') == exec_str
            if not mask.any():
                continue
            price = etf_df.loc[mask, 'open'].iloc[0]
            if pd.isna(price) or price <= 0:
                continue
            size = int(cash_per / (price * (1 + COMMISSION)))
            if size <= 0:
                continue
            cost = size * price * (1 + COMMISSION)
            if cost > cash:
                size = int(cash / (price * (1 + COMMISSION)))
                cost = size * price * (1 + COMMISSION)
                if size <= 0:
                    continue
            cash -= cost
            holdings[code] = {'size': size, 'entry_price': price, 'entry_date': exec_str}
        
        tv = cash
        for code, pos in holdings.items():
            etf_df = etf_data[code]
            mask = etf_df['date'].dt.strftime('%Y-%m-%d') == exec_str
            if mask.any():
                cp = etf_df.loc[mask, 'close'].iloc[0]
                tv += pos['size'] * (cp if pd.notna(cp) else pos['entry_price'])
            else:
                tv += pos['size'] * pos['entry_price']
        equity_curve.append({'date': exec_str, 'value': round(tv, 2)})
    
    # Force liquidate
    final_str = all_dates[-1]
    for code, pos in list(holdings.items()):
        price = None
        etf_df = etf_data[code]
        mask = etf_df['date'].dt.strftime('%Y-%m-%d') == final_str
        if mask.any():
            price = etf_df.loc[mask, 'close'].iloc[0]
        if price is None or pd.isna(price) or price <= 0:
            price = etf_data[code]['close'].iloc[-1]
        if pd.notna(price) and price > 0:
            proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
            pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
            trade_history.append({
                'entry_date': pos['entry_date'],
                'exit_date': final_str,
                'symbol': code,
                'side': 'long',
                'size': pos['size'],
                'entry_price': pos['entry_price'],
                'exit_price': price,
                'pnl': round(pnl, 2),
            })
            cash += proceeds
            del holdings[code]
    
    tv = cash
    for code, pos in holdings.items():
        tv += pos['size'] * pos['entry_price']
    equity_curve.append({'date': final_str, 'value': round(tv, 2)})
    
    if len(equity_curve) < 6:
        print("SKIP")
        return None
    
    eq = pd.DataFrame(equity_curve)
    eq['date'] = pd.to_datetime(eq['date'])
    eq = eq.sort_values('date').reset_index(drop=True)
    
    iv = eq['value'].iloc[0]
    fv = eq['value'].iloc[-1]
    tr = (fv / iv - 1) * 100
    days_run = (eq['date'].iloc[-1] - eq['date'].iloc[0]).days
    years = max(days_run / 365.25, 0.1)
    ar = ((fv / iv) ** (1 / years) - 1) * 100
    
    eq['dr'] = eq['value'].pct_change()
    dr = eq['dr'].dropna()
    sharpe = np.nan
    if len(dr) > 10 and dr.std() > 0:
        sharpe = (dr.mean() / dr.std()) * np.sqrt(252)
    
    eq['cmax'] = eq['value'].cummax()
    eq['dd'] = (eq['value'] / eq['cmax'] - 1) * 100
    mdd = eq['dd'].min()
    
    wins = sum(1 for t in trade_history if t['pnl'] > 0)
    wr = wins / max(len(trade_history), 1) * 100
    calmar = ar / abs(mdd) if mdd < 0 else np.nan
    
    hold_days = []
    for t in trade_history:
        ed = pd.Timestamp(t['entry_date'])
        exd = pd.Timestamp(t['exit_date'])
        hold_days.append((exd - ed).days)
    avg_hold = np.mean(hold_days) if hold_days else 0
    
    res = {
        'factor_name': f'Multi_{label}',
        'param_label': label,
        'top_k': top_k,
        'total_return_pct': round(tr, 1),
        'annual_return_pct': round(ar, 1),
        'sharpe': round(sharpe, 3) if not np.isnan(sharpe) else None,
        'max_drawdown_pct': round(mdd, 1),
        'calmar': round(calmar, 2) if not np.isnan(calmar) else None,
        'win_rate_pct': round(wr, 1),
        'total_trades': len(trade_history),
        'avg_holding_days': round(avg_hold, 1),
        'start_date': str(eq['date'].iloc[0].date()),
        'end_date': str(eq['date'].iloc[-1].date()),
    }
    
    prefix = f"multi_{label.replace(' ','').replace('+','+')}_top{top_k}"
    eq.to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_equity.csv"), index=False, encoding='utf-8-sig')
    if trade_history:
        pd.DataFrame(trade_history).to_csv(
            os.path.join(OUTPUT_DIR, f"{prefix}_trades.csv"), index=False, encoding='utf-8-sig')
    with open(os.path.join(OUTPUT_DIR, f"{prefix}_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    
    print(f"R={tr:.1f}% A={ar:.1f}% S={sharpe:.2f} DD={mdd:.1f}%")
    return (res, eq, trade_history)


# ============================================================
# 5. CHARTS
# ============================================================
def plot_all(results, title, filename):
    if not results:
        return
    fig, axes = plt.subplots(3, 1, figsize=(16, 14),
                             gridspec_kw={'height_ratios': [3, 1.2, 1.2]})
    sorted_r = sorted(results, key=lambda r: r[0].get('sharpe', 0) or 0, reverse=True)
    colors = plt.cm.tab20(np.linspace(0, 1, len(sorted_r)))
    
    ax1 = axes[0]
    for i, (res, eq_df, _) in enumerate(sorted_r):
        eq_df = eq_df.sort_values('date')
        norm = eq_df['value'].values / eq_df['value'].iloc[0] * 100
        label = f"{res['factor_name']}_{res['param_label']}_T{res['top_k']} ({res['annual_return_pct']:.0f}%, Sh={res.get('sharpe',0):.2f})"
        ax1.plot(eq_df['date'], norm, color=colors[i], lw=1.2, alpha=0.85, label=label)
    ax1.set_ylabel('净值(初始=100)', fontsize=12)
    ax1.set_title(title, fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=6, ncol=2)
    ax1.grid(True, alpha=0.3)
    ax1.axhline(100, color='k', lw=0.5, ls='--')
    
    ax2 = axes[1]
    shorts = [r[0].get('sharpe', 0) or 0 for r in sorted_r]
    labs = [f"{r[0]['factor_name'][:12]}_{r[0]['param_label'][:6]}_T{r[0]['top_k']}" for r in sorted_r]
    ax2.bar(range(len(shorts)), shorts, color=colors[:len(shorts)])
    ax2.set_ylabel('Sharpe', fontsize=12)
    ax2.set_xticks(range(len(shorts)))
    ax2.set_xticklabels(labs, rotation=90, fontsize=5)
    ax2.axhline(1, color='r', ls='--', alpha=0.5)
    ax2.axhline(0, color='k', lw=0.5)
    ax2.grid(True, alpha=0.3, axis='y')
    
    ax3 = axes[2]
    dds = [abs(r[0]['max_drawdown_pct']) for r in sorted_r]
    ax3.bar(range(len(dds)), dds, color='coral', alpha=0.7)
    ax3.set_ylabel('最大回撤(%)', fontsize=12)
    ax3.set_xticks(range(len(dds)))
    ax3.set_xticklabels(labs, rotation=90, fontsize=5)
    ax3.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  图表: {path}")
    return path


# ============================================================
# 6. MAIN
# ============================================================
def main():
    print("=" * 60)
    print("A股 ETF 多因子回测")
    print("=" * 60)
    print(f"输出: {OUTPUT_DIR}")
    print(f"回测: {BT_START} ~ {BT_END}")
    print()
    
    print("加载数据...")
    etf_data = load_all_etfs(DATA_DIR)
    print(f"加载 {len(etf_data)} 只 ETF")
    print()
    
    all_results = []
    
    # ==============================
    # SINGLE FACTOR TESTS
    # ==============================
    print("=" * 60)
    print("单因子测试")
    print("=" * 60)
    
    # Define all single-factor tests: (name, param_label, fn, ascending)
    single_tests = [
        ("动量12-1m", "12m", factor_momentum_12_1, False),
        ("动量6-1m", "6m", factor_momentum_6_1, False),
        ("动量3-1m", "3m", factor_momentum_3_1, False),
        ("动量简单12m", "12m", factor_momentum_simple_12, False),
        ("动量简单6m", "6m", factor_momentum_simple_6, False),
        ("动量简单3m", "3m", factor_momentum_simple_3, False),
        ("低波动12m", "12m", factor_low_vol_12, True),
        ("低波动6m", "6m", factor_low_vol_6, True),
        ("低波动3m", "3m", factor_low_vol_3, True),
        ("量能趋势12-3m", "12-3m", factor_vol_momentum_12_3, False),
        ("量能趋势6-1m", "6-1m", factor_vol_momentum_6_1, False),
        ("价格均线比MA60", "MA60", factor_price_ma60, False),
        ("价格均线比MA120", "MA120", factor_price_ma120, False),
        ("短期反转1m", "1m", factor_short_rev_1m, False),
    ]
    
    for name, param, fn, asc in single_tests:
        for top_k in TOP_KS:
            try:
                res = run_factor_backtest(name, param, fn, etf_data,
                                          top_k=top_k, ascending=asc)
                if res is not None:
                    all_results.append(res)
            except Exception as e:
                print(f"  ERROR: {name} {param} top{top_k}: {e}")
    
    # ==============================
    # MULTI-FACTOR TESTS
    # ==============================
    print()
    print("=" * 60)
    print("多因子组合测试")
    print("=" * 60)
    
    multi_configs = [
        ("动量+低波", [
            (factor_momentum_12_1, False, 0.5),
            (factor_low_vol_12, True, 0.5),
        ]),
        ("动量+量能趋势", [
            (factor_momentum_12_1, False, 0.5),
            (factor_vol_momentum_12_3, False, 0.5),
        ]),
        ("动量+价格均线", [
            (factor_momentum_12_1, False, 0.5),
            (factor_price_ma120, False, 0.5),
        ]),
        ("低波+量能趋势", [
            (factor_low_vol_12, True, 0.5),
            (factor_vol_momentum_12_3, False, 0.5),
        ]),
        ("动量+低波+量能", [
            (factor_momentum_12_1, False, 0.4),
            (factor_low_vol_12, True, 0.3),
            (factor_vol_momentum_12_3, False, 0.3),
        ]),
        ("动量+低波+均线", [
            (factor_momentum_12_1, False, 0.4),
            (factor_low_vol_12, True, 0.3),
            (factor_price_ma120, False, 0.3),
        ]),
        ("全因子等权", [
            (factor_momentum_12_1, False, 0.25),
            (factor_low_vol_12, True, 0.25),
            (factor_vol_momentum_12_3, False, 0.25),
            (factor_price_ma120, False, 0.25),
        ]),
    ]
    
    for label, config in multi_configs:
        for top_k in TOP_KS:
            try:
                res = run_multi_factor(label, config, etf_data, top_k=top_k)
                if res is not None:
                    all_results.append(res)
            except Exception as e:
                print(f"  ERROR: Multi {label} top{top_k}: {e}")
    
    # ==============================
    # SUMMARY
    # ==============================
    print()
    print("=" * 60)
    print("结果汇总")
    print("=" * 60)
    
    valid = [r for r in all_results if r is not None]
    valid.sort(key=lambda r: r[0].get('sharpe', 0) or 0, reverse=True)
    
    rows = []
    for res, _, _ in valid:
        rows.append({
            '因子': res['factor_name'],
            '参数': res['param_label'],
            'TopK': res['top_k'],
            '年化收益%': res['annual_return_pct'],
            'Sharpe': res['sharpe'],
            '最大回撤%': res['max_drawdown_pct'],
            'Calmar': res.get('calmar'),
            '胜率%': res['win_rate_pct'],
            '交易次数': res['total_trades'],
            '平均持仓天数': res['avg_holding_days'],
        })
    
    pd.DataFrame(rows).to_csv(
        os.path.join(OUTPUT_DIR, 'factor_results_summary.csv'),
        index=False, encoding='utf-8-sig')
    
    # Top 30
    print()
    print(f"{'Rank':>4} {'因子':<22} {'参':<6} {'TopK':>5} {'年化%':>6} {'Sharpe':>7} {'回撤%':>6} {'Calmar':>7} {'胜率%':>6} {'交易':>5}")
    print("-" * 80)
    for i, (res, _, _) in enumerate(valid[:30]):
        cs = res.get('calmar')
        cs_str = f'{cs:5.2f}' if cs is not None and isinstance(cs, (int, float)) else '  N/A'
        print(f"{i+1:>4} {res['factor_name']:<22} {res['param_label']:<6} {res['top_k']:>5} {res['annual_return_pct']:>5.1f}% {res['sharpe']:>7.3f} {res['max_drawdown_pct']:>5.1f}% {cs_str:>7} {res['win_rate_pct']:>5.1f}% {res['total_trades']:>5}")
    
    # Charts
    print()
    print("生成图表...")
    
    # Separate single-factor and multi-factor for clarity
    single_res = [r for r in valid if not r[0]['factor_name'].startswith('Multi_')]
    multi_res = [r for r in valid if r[0]['factor_name'].startswith('Multi_')]
    
    if single_res:
        plot_all(single_res, "A股ETF 单因子回测 - 整体对比", "single_factor_all.png")
        # Top 10 single factors
        top10 = single_res[:10]
        plot_all(top10, "A股ETF 单因子 Top10 (按Sharpe)", "single_factor_top10.png")
    
    if multi_res:
        plot_all(multi_res, "A股ETF 多因子组合 - 对比", "multi_factor_all.png")
    
    # All together
    plot_all(valid, "A股ETF 全策略对比", "all_strategies.png")
    
    print()
    print(f"输出目录: {OUTPUT_DIR}")
    print("完成!")


if __name__ == '__main__':
    main()

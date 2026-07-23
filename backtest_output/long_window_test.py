"""
A股ETF因子回测 - 长窗口版 (2015~2026)
单因子 + 多因子组合
数据: D:\QClaw_Trading\data\history\ 下所有ETF JSON文件
回测方式: 月末截面排序 -> 买入Top K -> 等权持有 -> 下月再平衡
早期(2015~2017)ETF数量有限，会标明
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

DATA_DIR = 'D:/QClaw_Trading/data/history/'
OUTPUT_DIR = 'D:/QClaw_Trading/backtest_output/long_run_' + datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs(OUTPUT_DIR, exist_ok=True)

INITIAL_CASH = 1_000_000
COMMISSION = 0.0003
SELL_COMMISSION = 0.0003
SELL_TAX = 0.0
MIN_RECORDS = 300  # need at least 300 records for 12-month vol calc
TOP_KS = [5, 10]
BT_START = '2014-01-01'
BT_END = '2026-07-14'

# ============================================================
# 1. LOAD DATA
# ============================================================
def load_all_etfs(data_dir):
    etf_data = {}
    for fname in os.listdir(data_dir):
        if not fname.endswith('.json'):
            continue
        code = fname[:-5]
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
# 2. FACTOR FUNCTIONS
# ============================================================
def factor_momentum_12_1(df):
    if len(df) < 260: return pd.Series(index=df.index, dtype=float)
    return df['close'].shift(21) / df['close'].shift(21+252) - 1

def factor_momentum_6_1(df):
    if len(df) < 140: return pd.Series(index=df.index, dtype=float)
    return df['close'].shift(21) / df['close'].shift(21+126) - 1

def factor_momentum_simple_12(df):
    if len(df) < 260: return pd.Series(index=df.index, dtype=float)
    return df['close'] / df['close'].shift(252) - 1

def factor_low_vol_12(df):
    if len(df) < 260: return pd.Series(index=df.index, dtype=float)
    ret = df['close'].pct_change()
    return ret.rolling(252).std()

def factor_low_vol_6(df):
    if len(df) < 140: return pd.Series(index=df.index, dtype=float)
    ret = df['close'].pct_change()
    return ret.rolling(126).std()

def factor_low_vol_3(df):
    if len(df) < 80: return pd.Series(index=df.index, dtype=float)
    ret = df['close'].pct_change()
    return ret.rolling(63).std()

def factor_price_ma60(df):
    if len(df) < 70: return pd.Series(index=df.index, dtype=float)
    return df['close'] / df['close'].rolling(60).mean()

def factor_price_ma120(df):
    if len(df) < 130: return pd.Series(index=df.index, dtype=float)
    return df['close'] / df['close'].rolling(120).mean()

def factor_vol_momentum_12_3(df):
    if len(df) < 260: return pd.Series(index=df.index, dtype=float)
    return df['vol'].rolling(63).mean() / df['vol'].rolling(252).mean()

def factor_short_rev_1m(df):
    if len(df) < 25: return pd.Series(index=df.index, dtype=float)
    return -(df['close'] / df['close'].shift(21) - 1)

# ============================================================
# 3. BACKTEST
# ============================================================
def run_backtest(name, param_label, factor_fn, etf_data, top_k=10,
                 ascending=False, warmup_months=12):
    print(f"  [{name} {param_label} top{top_k}] ", end='', flush=True)
    
    # Build dates
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
    warmup_start = bt_start - pd.Timedelta(days=400)
    month_ends = month_ends[(month_ends >= warmup_start) & (month_ends <= bt_end)]
    if len(month_ends) < 12:
        print("SKIP"); return None
    
    # Pre-compute factor
    fact_vals = {}
    for code, df in etf_data.items():
        # Only compute factor where we have enough history relative to each date
        # Store raw series
        fact_vals[code] = factor_fn(df)
    
    # Track universe size per month
    universe_log = []
    
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
        
        if rebal_date < bt_start:
            continue
        
        # Collect candidates at this date
        candidates = []
        for code, fv_series in fact_vals.items():
            if rebal_date in fv_series.index:
                val = fv_series.loc[rebal_date]
                if pd.notna(val) and not np.isinf(val):
                    etf_df = etf_data[code]
                    if exec_str in etf_df['date'].dt.strftime('%Y-%m-%d').values:
                        candidates.append((code, val))
        
        universe_log.append({'date': rebal_str, 'n_candidates': len(candidates)})
        
        if len(candidates) < top_k + 2:
            # Too few - liquidate if holding
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
                            'symbol': code, 'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
            holdings.clear()
            tv = cash
            for code, pos in holdings.items():
                tv += pos['size'] * pos['entry_price']
            equity_curve.append({'date': exec_str, 'value': round(tv, 2)})
            continue
        
        candidates.sort(key=lambda x: x[1], reverse=not ascending)
        selected = [c for c, v in candidates[:top_k]]
        
        # Sell
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
                            'symbol': code, 'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
                        del holdings[code]
        
        # Buy
        if len(selected) == 0:
            tv = cash
            for code, pos in holdings.items():
                tv += pos['size'] * pos['entry_price']
            equity_curve.append({'date': exec_str, 'value': round(tv, 2)})
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
                if size <= 0: continue
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
        etf_df = etf_data[code]
        mask = etf_df['date'].dt.strftime('%Y-%m-%d') == final_str
        if mask.any():
            price = etf_df.loc[mask, 'close'].iloc[0]
        else:
            price = etf_data[code]['close'].iloc[-1]
        if pd.notna(price) and price > 0:
            proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
            pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
            trade_history.append({
                'entry_date': pos['entry_date'],
                'exit_date': final_str,
                'symbol': code, 'side': 'long',
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
    if len(equity_curve) < 12:
        print("SKIP"); return None
    
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
    calmar = ar / abs(mdd) if mdd < 0 and mdd != 0 else np.nan
    
    hold_days = []
    for t in trade_history:
        ed = pd.Timestamp(t['entry_date'])
        exd = pd.Timestamp(t['exit_date'])
        hold_days.append((exd - ed).days)
    avg_hold = np.mean(hold_days) if hold_days else 0
    
    # Universe stats
    univ_df = pd.DataFrame(universe_log)
    univ_df['date_dt'] = pd.to_datetime(univ_df['date'])
    universe_early = univ_df[univ_df['date_dt'] < '2018-01-01']['n_candidates'].mean() if len(univ_df[univ_df['date_dt'] < '2018-01-01']) > 0 else 0
    universe_late = univ_df[univ_df['date_dt'] >= '2018-01-01']['n_candidates'].mean() if len(univ_df[univ_df['date_dt'] >= '2018-01-01']) > 0 else 0
    
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
        'n_months': len(month_ends),
        'start_date': str(eq['date'].iloc[0].date()),
        'end_date': str(eq['date'].iloc[-1].date()),
        'avg_candidates_2014_2017': round(universe_early, 1),
        'avg_candidates_2018_2026': round(universe_late, 1),
    }
    
    prefix = f"{name}_{param_label}_top{top_k}".replace('.','').replace('-','_').replace(' ','')
    eq.to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_equity.csv"), index=False, encoding='utf-8-sig')
    if trade_history:
        pd.DataFrame(trade_history).to_csv(
            os.path.join(OUTPUT_DIR, f"{prefix}_trades.csv"), index=False, encoding='utf-8-sig')
    with open(os.path.join(OUTPUT_DIR, f"{prefix}_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    
    print(f"R={tr:.1f}% A={ar:.1f}% S={sharpe:.2f} DD={mdd:.1f}% U={universe_early:.0f}->{universe_late:.0f}")
    return (res, eq, trade_history)


# ============================================================
# 4. MULTI-FACTOR
# ============================================================
def run_multi(label, configs, etf_data, top_k=10):
    print(f"  [Multi: {label} top{top_k}] ", end='', flush=True)
    
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
    month_ends = month_ends[(month_ends >= bt_start - pd.Timedelta(days=400)) & (month_ends <= bt_end)]
    
    if len(month_ends) < 12:
        print("SKIP"); return None
    
    # Pre-compute all factors
    all_fact = []
    for fn, asc, w in configs:
        fdict = {}
        for code, df in etf_data.items():
            fdict[code] = fn(df)
        all_fact.append({'asc': asc, 'weight': w, 'values': fdict})
    
    universe_log = []
    
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
        
        if rebal_date < bt_start:
            continue
        
        # Collect all codes with all factors at this date
        factor_raw_by_code = {}
        n_factors = len(configs)
        for fi_i, fi in enumerate(all_fact):
            for code, fv_series in fi['values'].items():
                if rebal_date in fv_series.index:
                    val = fv_series.loc[rebal_date]
                    if pd.notna(val) and not np.isinf(val):
                        if code not in factor_raw_by_code:
                            factor_raw_by_code[code] = [None] * n_factors
                        factor_raw_by_code[code][fi_i] = val
        
        # Filter complete records
        complete = {code: vals for code, vals in factor_raw_by_code.items()
                    if all(v is not None for v in vals)}
        
        # Check exec price
        valid_codes = []
        for code in complete:
            etf_df = etf_data[code]
            if exec_str in etf_df['date'].dt.strftime('%Y-%m-%d').values:
                valid_codes.append(code)
        
        universe_log.append({'date': rebal_str, 'n_candidates': len(valid_codes)})
        
        if len(valid_codes) < top_k + 2:
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
                            'symbol': code, 'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
            holdings.clear()
            tv = cash
            for code, pos in holdings.items():
                tv += pos['size'] * pos['entry_price']
            equity_curve.append({'date': exec_str, 'value': round(tv, 2)})
            continue
        
        # Rank-standardize each factor
        scored = {code: 0.0 for code in valid_codes}
        for fi_i in range(n_factors):
            vals_this = [(code, complete[code][fi_i]) for code in valid_codes]
            sorted_codes = sorted(vals_this, key=lambda x: x[1])
            max_r = len(sorted_codes) - 1
            for rank_i, (code, v) in enumerate(sorted_codes):
                norm = rank_i / max_r if max_r > 0 else 0.5
                if configs[fi_i][1]:
                    norm = 1 - norm
                scored[code] += norm * configs[fi_i][2]
        
        ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)
        selected = [c for c, s in ranked[:top_k]]
        
        # Sell
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
                            'symbol': code, 'side': 'long',
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
                        del holdings[code]
        
        # Buy
        if len(selected) == 0:
            tv = cash
            for code, pos in holdings.items():
                tv += pos['size'] * pos['entry_price']
            equity_curve.append({'date': exec_str, 'value': round(tv, 2)})
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
                if size <= 0: continue
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
    
    final_str = all_dates[-1]
    for code, pos in list(holdings.items()):
        etf_df = etf_data[code]
        mask = etf_df['date'].dt.strftime('%Y-%m-%d') == final_str
        if mask.any():
            price = etf_df.loc[mask, 'close'].iloc[0]
        else:
            price = etf_data[code]['close'].iloc[-1]
        if pd.notna(price) and price > 0:
            proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
            pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
            trade_history.append({
                'entry_date': pos['entry_date'],
                'exit_date': final_str,
                'symbol': code, 'side': 'long',
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
    
    if len(equity_curve) < 12:
        print("SKIP"); return None
    
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
    
    univ_df = pd.DataFrame(universe_log)
    univ_df['date_dt'] = pd.to_datetime(univ_df['date'])
    u_early = univ_df[univ_df['date_dt'] < '2018-01-01']['n_candidates'].mean() if len(univ_df[univ_df['date_dt'] < '2018-01-01']) > 0 else 0
    u_late = univ_df[univ_df['date_dt'] >= '2018-01-01']['n_candidates'].mean() if len(univ_df[univ_df['date_dt'] >= '2018-01-01']) > 0 else 0
    
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
        'avg_candidates_2014_2017': round(u_early, 1),
        'avg_candidates_2018_2026': round(u_late, 1),
    }
    
    prefix = f"multi_{label.replace(' ','').replace('+','+')}_top{top_k}"
    eq.to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_equity.csv"), index=False, encoding='utf-8-sig')
    if trade_history:
        pd.DataFrame(trade_history).to_csv(
            os.path.join(OUTPUT_DIR, f"{prefix}_trades.csv"), index=False, encoding='utf-8-sig')
    with open(os.path.join(OUTPUT_DIR, f"{prefix}_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    
    print(f"R={tr:.1f}% A={ar:.1f}% S={sharpe:.2f} DD={mdd:.1f}% U={u_early:.0f}->{u_late:.0f}")
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
    shvals = [r[0].get('sharpe', 0) or 0 for r in sorted_r]
    labs = [f"{r[0]['factor_name'][:12]}_{r[0]['param_label'][:6]}_T{r[0]['top_k']}" for r in sorted_r]
    ax2.bar(range(len(shvals)), shvals, color=colors[:len(shvals)])
    ax2.set_ylabel('Sharpe', fontsize=12)
    ax2.set_xticks(range(len(shvals)))
    ax2.set_xticklabels(labs, rotation=90, fontsize=5)
    ax2.axhline(1, color='r', ls='--', alpha=0.5)
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
    return path


# ============================================================
# 6. MAIN
# ============================================================
def main():
    print("=" * 60)
    print("A股 ETF 多因子回测 - 长窗口版 (2015~2026)")
    print("=" * 60)
    print(f"输出: {OUTPUT_DIR}")
    print(f"回测: {BT_START} ~ {BT_END}")
    print()
    
    print("加载数据...")
    etf_data = load_all_etfs(DATA_DIR)
    print(f"加载 {len(etf_data)} 只 ETF")
    print()
    
    # Also load CSI 300 for benchmark
    idx_path = os.path.join(DATA_DIR, '000300.json')
    with open(idx_path, encoding='utf-8') as f:
        ix = json.load(f)
    ix_df = pd.DataFrame(ix['records'])
    ix_df['date'] = pd.to_datetime(ix_df['date'])
    ix_df = ix_df.sort_values('reset_index') if 'sort' in dir(ix_df) else ix_df.sort_values('date').reset_index(drop=True)
    # Actually just do it simply
    ix_df = pd.DataFrame(ix['records'])
    ix_df['date'] = pd.to_datetime(ix_df['date'])
    ix_df = ix_df.sort_values('date').reset_index(drop=True)
    
    all_results = []
    
    # ==============================
    # SINGLE FACTORS
    # ==============================
    print("=" * 60)
    print("单因子测试")
    print("=" * 60)
    
    single_tests = [
        ("低波动12m", "12m", factor_low_vol_12, True),
        ("低波动6m", "6m", factor_low_vol_6, True),
        ("低波动3m", "3m", factor_low_vol_3, True),
        ("动量12-1m", "12m", factor_momentum_12_1, False),
        ("动量6-1m", "6m", factor_momentum_6_1, False),
        ("动量简单12m", "12m", factor_momentum_simple_12, False),
        ("价格均线比MA60", "MA60", factor_price_ma60, False),
        ("价格均线比MA120", "MA120", factor_price_ma120, False),
        ("量能趋势12-3m", "12-3m", factor_vol_momentum_12_3, False),
        ("短期反转1m", "1m", factor_short_rev_1m, False),
    ]
    
    for name, param, fn, asc in single_tests:
        for top_k in TOP_KS:
            try:
                res = run_backtest(name, param, fn, etf_data,
                                   top_k=top_k, ascending=asc)
                if res is not None:
                    all_results.append(res)
            except Exception as e:
                print(f"  ERROR: {name} {param} top{top_k}: {e}")
    
    # ==============================
    # MULTI-FACTOR
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
        ("低波+趋势", [
            (factor_low_vol_12, True, 0.5),
            (factor_vol_momentum_12_3, False, 0.5),
        ]),
        ("动量+低波+趋势", [
            (factor_momentum_12_1, False, 0.34),
            (factor_low_vol_12, True, 0.33),
            (factor_vol_momentum_12_3, False, 0.33),
        ]),
    ]
    
    for label, config in multi_configs:
        for top_k in TOP_KS:
            try:
                res = run_multi(label, config, etf_data, top_k=top_k)
                if res is not None:
                    all_results.append(res)
            except Exception as e:
                print(f"  ERROR: Multi {label} top{top_k}: {e}")
    
    # ==============================
    # BENCHMARK: CSI 300 buy-hold
    # ==============================
    # Buy CSI 300 on first available date after warmup and hold
    print()
    print("=" * 60)
    print("基准对比")
    print("=" * 60)
    
    # Compute CSI 300 buy-hold in the same period
    csi = ix_df[ix_df['date'] >= '2015-01-01'].copy()
    csi = csi[csi['date'] <= '2026-07-14'].copy()
    if len(csi) > 0:
        bh_ret = (csi.iloc[-1]['close'] / csi.iloc[0]['close'] - 1) * 100
        csi['dr'] = csi['close'].pct_change()
        bh_sharpe = (csi['dr'].mean() / csi['dr'].std()) * np.sqrt(252) if csi['dr'].std() > 0 else 0
        bh_years = (csi.iloc[-1]['date'] - csi.iloc[0]['date']).days / 365.25
        bh_ann = ((csi.iloc[-1]['close'] / csi.iloc[0]['close']) ** (1/bh_years) - 1) * 100 if bh_years > 0 else 0
        csi['cmax'] = csi['close'].cummax()
        csi['dd'] = (csi['close'] / csi['cmax'] - 1) * 100
        bh_mdd = csi['dd'].min()
        print(f"  沪深300 买持: {csi.iloc[0]['date'].date()} ~ {csi.iloc[-1]['date'].date()}")
        print(f"  总收益: {bh_ret:.1f}%  年化: {bh_ann:.1f}%  Sharpe: {bh_sharpe:.3f}  最大回撤: {bh_mdd:.1f}%")
    
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
            'Start': res['start_date'],
            '候选规模14-17': res.get('avg_candidates_2014_2017', '?'),
            '候选规模18-26': res.get('avg_candidates_2018_2026', '?'),
        })
    
    pd.DataFrame(rows).to_csv(
        os.path.join(OUTPUT_DIR, 'long_results_summary.csv'),
        index=False, encoding='utf-8-sig')
    
    print()
    hdr = f"{'Rank':>4} {'因子':<22} {'参':<6} {'TopK':>5} {'年化%':>6} {'Sharpe':>7} {'回撤%':>6} {'Calmar':>7} {'候选':>6}"
    print(hdr)
    print("-" * 75)
    
    for i, (res, _, _) in enumerate(valid[:30]):
        cs = res.get('calmar')
        cs_str = f'{cs:5.2f}' if cs is not None else '  N/A'
        u_str = f"{res.get('avg_candidates_2014_2017', 0):.0f}|{res.get('avg_candidates_2018_2026', 0):.0f}"
        print(f"{i+1:>4} {res['factor_name']:<22} {res['param_label']:<6} {res['top_k']:>5} {res['annual_return_pct']:>5.1f}% {res['sharpe']:>7.3f} {res['max_drawdown_pct']:>5.1f}% {cs_str:>7} {u_str:>6}")
    
    # Charts
    print()
    print("生成图表...")
    plot_all(valid, "A股ETF 长窗口因子回测 (2015~2026)", "long_window_all.png")
    
    # Filter for 2018-present
    valid_late = [(r,eq,t) for r,eq,t in valid if pd.Timestamp(r['start_date']) >= pd.Timestamp('2018-06-01')]
    if valid_late:
        plot_all(valid_late, "A股ETF 因子回测 (2018~2026)", "long_window_2018_present.png")
    
    print()
    print(f"输出目录: {OUTPUT_DIR}")
    print("完成!")


if __name__ == '__main__':
    main()

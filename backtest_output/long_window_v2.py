"""
A股ETF因子回测 - 长窗口版 (2015~2026)
单因子 + 多因子组合
数据: D:\QClaw_Trading\data\history\ 下所有ETF JSON文件
回测: 月末截面排序 -> 买入Top K -> 等权持有 -> 次月再平衡 -> 次日开盘执行
"""

import json, os
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# CONFIG
DATA_DIR = 'D:/QClaw_Trading/data/history/'
OUTPUT_DIR = 'D:/QClaw_Trading/backtest_output/long_run_' + datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs(OUTPUT_DIR, exist_ok=True)

INITIAL_CASH = 1_000_000
COMMISSION = 0.0003
SELL_COMMISSION = 0.0003
SELL_TAX = 0.0
MIN_RECORDS = 300
TOP_KS = [5, 10]
BT_START = '2015-01-01'
BT_END = '2026-07-14'

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

# FACTORS
def factor_low_vol_12(df):
    ret = df['close'].pct_change()
    return ret.rolling(252).std()

def factor_low_vol_6(df):
    ret = df['close'].pct_change()
    return ret.rolling(126).std()

def factor_low_vol_3(df):
    ret = df['close'].pct_change()
    return ret.rolling(63).std()

def factor_momentum_12_1(df):
    return df['close'].shift(21) / df['close'].shift(21+252) - 1

def factor_momentum_6_1(df):
    return df['close'].shift(21) / df['close'].shift(21+126) - 1

def factor_momentum_simple_12(df):
    return df['close'] / df['close'].shift(252) - 1

def factor_price_ma60(df):
    return df['close'] / df['close'].rolling(60).mean()

def factor_price_ma120(df):
    return df['close'] / df['close'].rolling(120).mean()

def factor_vol_momentum_12_3(df):
    return df['vol'].rolling(63).mean() / df['vol'].rolling(252).mean()

def factor_short_rev_1m(df):
    return -(df['close'] / df['close'].shift(21) - 1)

def run(name, param, factor_fn, etf_data, top_k=10, ascending=False):
    print(f"  [{name} {param} top{top_k}] ", end='', flush=True)

    # Build month-end rebalance dates
    all_date_set = set()
    for code, df in etf_data.items():
        for d in df['date'].dt.strftime('%Y-%m-%d'):
            all_date_set.add(d)
    all_dates = sorted(all_date_set)
    all_dt = pd.DataFrame({'date': pd.to_datetime(all_dates)})
    all_dt['ym'] = all_dt['date'].dt.to_period('M')
    month_ends = all_dt.groupby('ym')['date'].last().reset_index(drop=True)

    bt_start = pd.Timestamp(BT_START)
    bt_end = pd.Timestamp(BT_END)
    # Filter month_ends
    month_ends = month_ends[(month_ends >= bt_start - pd.Timedelta(days=30)) & (month_ends <= bt_end)]

    if len(month_ends) < 12:
        print("SKIP"); return None

    # Pre-compute factor for each ETF as Series (date string index)
    fact_vals = {}
    for code, df in etf_data.items():
        fv = factor_fn(df)
        fv.index = df['date']
        fact_vals[code] = fv  # Timestamp index

    # Track universe size
    earliest_rebal = month_ends[month_ends >= bt_start].iloc[0] if any(month_ends >= bt_start) else month_ends.iloc[-1]
    earliest_idx = month_ends.searchsorted(earliest_rebal)

    cash = INITIAL_CASH
    holdings = {}
    equity = []
    trades = []

    year_candidate_count = {}  # year -> avg candidates

    for idx in range(earliest_idx, len(month_ends)):
        rebal_date = month_ends.iloc[idx]
        rebal_str = rebal_date.strftime('%Y-%m-%d')

        if rebal_str not in all_date_set:
            continue
        ri = all_dates.index(rebal_str)
        if ri + 1 >= len(all_dates):
            continue
        exec_str = all_dates[ri + 1]

        # Collect candidates
        candidates = []
        for code, fv in fact_vals.items():
            if rebal_date in fv.index:
                val = fv.loc[rebal_date]
                if pd.notna(val) and not np.isinf(val):
                    # Check exec price
                    etf_df = etf_data[code]
                    if exec_str in etf_df['date'].dt.strftime('%Y-%m-%d').values:
                        candidates.append((code, val))

        # Track universe per year
        yr = rebal_date.year
        if yr not in year_candidate_count:
            year_candidate_count[yr] = []
        year_candidate_count[yr].append(len(candidates))

        if len(candidates) < top_k + 1:
            # Liquidate
            for code, pos in list(holdings.items()):
                etf_df = etf_data[code]
                mask = etf_df['date'].dt.strftime('%Y-%m-%d') == exec_str
                if mask.any():
                    price = etf_df.loc[mask, 'open'].iloc[0]
                    if pd.notna(price) and price > 0:
                        proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                        pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                        trades.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_str,
                            'symbol': code,
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
            holdings.clear()
            equity.append({'date': exec_str, 'value': round(cash, 2)})
            continue

        candidates.sort(key=lambda x: x[1], reverse=not ascending)
        selected = [c for c, _ in candidates[:top_k]]

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
                        trades.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_str,
                            'symbol': code,
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
                        del holdings[code]

        # Buy new
        cash_per = cash / max(len(selected), 1)
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
        equity.append({'date': exec_str, 'value': round(tv, 2)})

    # Force liquidate end
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
            trades.append({
                'entry_date': pos['entry_date'],
                'exit_date': final_str,
                'symbol': code,
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
    equity.append({'date': final_str, 'value': round(tv, 2)})

    if len(equity) < 12:
        print("SKIP"); return None

    eq = pd.DataFrame(equity)
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
    sharpe = None
    if len(dr) > 10 and dr.std() > 0:
        sharpe = round((dr.mean() / dr.std()) * np.sqrt(252), 3)

    eq['cmax'] = eq['value'].cummax()
    eq['dd'] = (eq['value'] / eq['cmax'] - 1) * 100
    mdd = round(eq['dd'].min(), 1)

    wins = sum(1 for t in trades if t['pnl'] > 0)
    wr = round(wins / max(len(trades), 1) * 100, 1)
    calmar = round(ar / abs(mdd), 2) if mdd and mdd < 0 else None

    hold_days = []
    for t in trades:
        ed = pd.Timestamp(t['entry_date'])
        exd = pd.Timestamp(t['exit_date'])
        hold_days.append((exd - ed).days)
    avg_hold = round(np.mean(hold_days), 1) if hold_days else 0

    # Universe stats by period
    early_years = [str(y) for y in range(2015, 2018)]
    late_years = [str(y) for y in range(2018, 2027)]
    u_early_arr = []
    for y in early_years:
        if y in year_candidate_count:
            u_early_arr.extend(year_candidate_count[y])
    u_late_arr = []
    for y in late_years:
        if y in year_candidate_count:
            u_late_arr.extend(year_candidate_count[y])

    res = {
        'factor_name': name,
        'param_label': param,
        'top_k': top_k,
        'total_return_pct': round(tr, 1),
        'annual_return_pct': round(ar, 1),
        'sharpe': sharpe,
        'max_drawdown_pct': mdd,
        'calmar': calmar,
        'win_rate_pct': wr,
        'total_trades': len(trades),
        'avg_holding_days': avg_hold,
        'n_months': len(equity),
        'start_date': str(eq['date'].iloc[0].date()),
        'end_date': str(eq['date'].iloc[-1].date()),
        'avg_candidates_2015_2017': round(np.mean(u_early_arr), 1) if u_early_arr else 0,
        'avg_candidates_2018_2026': round(np.mean(u_late_arr), 1) if u_late_arr else 0,
    }

    prefix = f"{name}_{param}_top{top_k}".replace('.','').replace('-','_').replace(' ','')
    eq.to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_equity.csv"), index=False, encoding='utf-8-sig')
    if trades:
        pd.DataFrame(trades).to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_trades.csv"), index=False, encoding='utf-8-sig')
    with open(os.path.join(OUTPUT_DIR, f"{prefix}_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    u_str = f"{res['avg_candidates_2015_2017']:.0f}|{res['avg_candidates_2018_2026']:.0f}"
    print(f"R={tr:.1f}% A={ar:.1f}% S={sharpe} DD={mdd}% U={u_str}")
    return (res, eq, trades)


def run_multi(label, configs, etf_data, top_k=10):
    print(f"  [Multi: {label} top{top_k}] ", end='', flush=True)

    all_date_set = set()
    for code, df in etf_data.items():
        for d in df['date'].dt.strftime('%Y-%m-%d'):
            all_date_set.add(d)
    all_dates = sorted(all_date_set)
    all_dt = pd.DataFrame({'date': pd.to_datetime(all_dates)})
    all_dt['ym'] = all_dt['date'].dt.to_period('M')
    month_ends = all_dt.groupby('ym')['date'].last().reset_index(drop=True)

    bt_start = pd.Timestamp(BT_START)
    bt_end = pd.Timestamp(BT_END)
    month_ends = month_ends[(month_ends >= bt_start - pd.Timedelta(days=30)) & (month_ends <= bt_end)]
    if len(month_ends) < 12:
        print("SKIP"); return None

    # Pre-compute all factors
    all_fact = []
    for fn, asc, w in configs:
        fd = {}
        for code, df in etf_data.items():
            fv = fn(df)
            fv.index = df['date']
            fd[code] = fv
        all_fact.append({'asc': asc, 'weight': w, 'values': fd})

    n_factors = len(configs)
    earliest_rebal = month_ends[month_ends >= bt_start].iloc[0]
    earliest_idx = month_ends.searchsorted(earliest_rebal)

    cash = INITIAL_CASH
    holdings = {}
    equity = []
    trades = []
    year_candidate_count = {}

    for idx in range(earliest_idx, len(month_ends)):
        rebal_date = month_ends.iloc[idx]
        rebal_str = rebal_date.strftime('%Y-%m-%d')

        if rebal_str not in all_date_set:
            continue
        ri = all_dates.index(rebal_str)
        if ri + 1 >= len(all_dates):
            continue
        exec_str = all_dates[ri + 1]

        # Collect codes with all factors
        raw_by_code = {}
        for fi_i in range(n_factors):
            fdict = all_fact[fi_i]['values']
            for code, fv in fdict.items():
                if rebal_date in fv.index:
                    val = fv.loc[rebal_date]
                    if pd.notna(val) and not np.isinf(val):
                        if code not in raw_by_code:
                            raw_by_code[code] = [None]*n_factors
                        raw_by_code[code][fi_i] = val

        # Filter complete + have exec price
        valid = []
        for code, vals in raw_by_code.items():
            if all(v is not None for v in vals):
                etf_df = etf_data[code]
                if exec_str in etf_df['date'].dt.strftime('%Y-%m-%d').values:
                    valid.append(code)

        yr = rebal_date.year
        if yr not in year_candidate_count:
            year_candidate_count[yr] = []
        year_candidate_count[yr].append(len(valid))

        if len(valid) < top_k + 1:
            for code, pos in list(holdings.items()):
                etf_df = etf_data[code]
                mask = etf_df['date'].dt.strftime('%Y-%m-%d') == exec_str
                if mask.any():
                    price = etf_df.loc[mask, 'open'].iloc[0]
                    if pd.notna(price) and price > 0:
                        proceeds = pos['size'] * price * (1 - SELL_COMMISSION - SELL_TAX)
                        pnl = proceeds - pos['size'] * pos['entry_price'] * (1 + COMMISSION)
                        trades.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_str,
                            'symbol': code,
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
            holdings.clear()
            equity.append({'date': exec_str, 'value': round(cash, 2)})
            continue

        # Rank standardize
        scored = {c: 0.0 for c in valid}
        for fi_i in range(n_factors):
            items = [(c, raw_by_code[c][fi_i]) for c in valid]
            items.sort(key=lambda x: x[1])
            max_r = len(items) - 1
            for ri, (c, _) in enumerate(items):
                norm = ri / max_r if max_r > 0 else 0.5
                if configs[fi_i][1]:
                    norm = 1 - norm
                scored[c] += norm * configs[fi_i][2]

        ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)
        selected = [c for c, _ in ranked[:top_k]]

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
                        trades.append({
                            'entry_date': pos['entry_date'],
                            'exit_date': exec_str,
                            'symbol': code,
                            'size': pos['size'],
                            'entry_price': pos['entry_price'],
                            'exit_price': price,
                            'pnl': round(pnl, 2),
                        })
                        cash += proceeds
                        del holdings[code]

        # Buy
        cash_per = cash / max(len(selected), 1)
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
        equity.append({'date': exec_str, 'value': round(tv, 2)})

    # Liquidate
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
            trades.append({
                'entry_date': pos['entry_date'],
                'exit_date': final_str,
                'symbol': code,
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
    equity.append({'date': final_str, 'value': round(tv, 2)})

    if len(equity) < 12:
        print("SKIP"); return None

    eq = pd.DataFrame(equity)
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
    sharpe = None
    if len(dr) > 10 and dr.std() > 0:
        sharpe = round((dr.mean() / dr.std()) * np.sqrt(252), 3)

    eq['cmax'] = eq['value'].cummax()
    eq['dd'] = (eq['value'] / eq['cmax'] - 1) * 100
    mdd = round(eq['dd'].min(), 1)
    wins = sum(1 for t in trades if t['pnl'] > 0)
    wr = round(wins / max(len(trades), 1) * 100, 1)
    calmar = round(ar / abs(mdd), 2) if mdd and mdd < 0 else None

    hold_days = []
    for t in trades:
        hd = (pd.Timestamp(t['exit_date']) - pd.Timestamp(t['entry_date'])).days
        hold_days.append(hd)
    avg_hold = round(np.mean(hold_days), 1) if hold_days else 0

    early_arr = []
    for y in [str(y) for y in range(2015, 2018)]:
        if y in year_candidate_count:
            early_arr.extend(year_candidate_count[y])
    late_arr = []
    for y in [str(y) for y in range(2018, 2027)]:
        if y in year_candidate_count:
            late_arr.extend(year_candidate_count[y])

    res = {
        'factor_name': f'Multi_{label}',
        'param_label': label,
        'top_k': top_k,
        'total_return_pct': round(tr, 1),
        'annual_return_pct': round(ar, 1),
        'sharpe': sharpe,
        'max_drawdown_pct': mdd,
        'calmar': calmar,
        'win_rate_pct': wr,
        'total_trades': len(trades),
        'avg_holding_days': avg_hold,
        'start_date': str(eq['date'].iloc[0].date()),
        'end_date': str(eq['date'].iloc[-1].date()),
        'avg_candidates_2015_2017': round(np.mean(early_arr), 1) if early_arr else 0,
        'avg_candidates_2018_2026': round(np.mean(late_arr), 1) if late_arr else 0,
    }

    prefix = f"multi_{label.replace(' ','').replace('+','+')}_top{top_k}"
    eq.to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_equity.csv"), index=False, encoding='utf-8-sig')
    if trades:
        pd.DataFrame(trades).to_csv(os.path.join(OUTPUT_DIR, f"{prefix}_trades.csv"), index=False, encoding='utf-8-sig')
    with open(os.path.join(OUTPUT_DIR, f"{prefix}_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    u_str = f"{res['avg_candidates_2015_2017']:.0f}|{res['avg_candidates_2018_2026']:.0f}"
    print(f"R={tr:.1f}% A={ar:.1f}% S={sharpe} DD={mdd}% U={u_str}")
    return (res, eq, trades)


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
        s_str = res.get('sharpe', 0) or 0
        lbl = f"{res['factor_name']}_{res['param_label']}_T{res['top_k']} ({res['annual_return_pct']:.0f}%, Sh={s_str:.2f})"
        ax1.plot(eq_df['date'], norm, color=colors[i], lw=1.2, alpha=0.85, label=lbl)
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


def main():
    print("=" * 60)
    print("A股 ETF 因子回测 - 长窗口版 (2015~2026)")
    print("=" * 60)
    print(f"输出: {OUTPUT_DIR}")
    print(f"回测: {BT_START} ~ {BT_END}")
    print()

    print("加载数据...")
    etf_data = load_all_etfs(DATA_DIR)
    print(f"加载 {len(etf_data)} 只 ETF")
    print()

    # CSI 300 benchmark
    with open(os.path.join(DATA_DIR, '000300.json'), encoding='utf-8') as f:
        ix = json.load(f)
    ix_df = pd.DataFrame(ix['records'])
    ix_df['date'] = pd.to_datetime(ix_df['date'])
    ix_df = ix_df.sort_values('date').reset_index(drop=True)
    csi = ix_df[ix_df['date'] >= '2015-01-01'].copy()
    csi = csi[csi['date'] <= '2026-07-14']
    if len(csi) > 1:
        yrs = (csi.iloc[-1]['date'] - csi.iloc[0]['date']).days / 365.25
        bh_ret = (csi.iloc[-1]['close'] / csi.iloc[0]['close'] - 1) * 100
        bh_ann = ((csi.iloc[-1]['close'] / csi.iloc[0]['close']) ** (1/max(yrs,0.1)) - 1) * 100
        csi['dr'] = csi['close'].pct_change()
        bh_sharpe = round((csi['dr'].mean() / csi['dr'].std()) * np.sqrt(252), 3) if csi['dr'].std() > 0 else 0
        csi['cmax'] = csi['close'].cummax()
        csi['dd'] = (csi['close'] / csi['cmax'] - 1) * 100
        bh_mdd = round(csi['dd'].min(), 1)
    print(f"沪深300基准 (2015~2026): 总{bh_ret:.1f}% 年化{bh_ann:.1f}% Sharpe{bh_sharpe} 回撤{bh_mdd}%")

    all_results = []

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
        for tk in TOP_KS:
            try:
                r = run(name, param, fn, etf_data, top_k=tk, ascending=asc)
                if r: all_results.append(r)
            except Exception as e:
                print(f"  ERROR: {name} {param} top{tk}: {e}")

    print()
    print("=" * 60)
    print("多因子组合测试")
    print("=" * 60)

    multi_cfgs = [
        ("动量+低波", [(factor_momentum_12_1, False, 0.5), (factor_low_vol_12, True, 0.5)]),
        ("低波+趋势", [(factor_low_vol_12, True, 0.5), (factor_vol_momentum_12_3, False, 0.5)]),
        ("低波+量能+动量", [(factor_low_vol_12, True, 0.34), (factor_vol_momentum_12_3, False, 0.33), (factor_momentum_12_1, False, 0.33)]),
    ]

    for lbl, cfg in multi_cfgs:
        for tk in TOP_KS:
            try:
                r = run_multi(lbl, cfg, etf_data, top_k=tk)
                if r: all_results.append(r)
            except Exception as e:
                print(f"  ERROR: Multi {lbl} top{tk}: {e}")

    # Summary
    print()
    print("=" * 60)
    print("结果汇总")
    print("=" * 60)

    valid = [r for r in all_results if r]
    valid.sort(key=lambda r: r[0].get('sharpe', 0) or 0, reverse=True)

    rows_data = []
    for res, _, _ in valid:
        rows_data.append({
            '因子': res['factor_name'], '参数': res['param_label'],
            'TopK': res['top_k'], '年化收益%': res['annual_return_pct'],
            'Sharpe': res['sharpe'], '最大回撤%': res['max_drawdown_pct'],
            'Calmar': res.get('calmar'), '胜率%': res['win_rate_pct'],
            '交易次数': res['total_trades'], 'Start': res['start_date'],
            'Univ15-17': res.get('avg_candidates_2015_2017', 0),
            'Univ18-26': res.get('avg_candidates_2018_2026', 0),
        })

    pd.DataFrame(rows_data).to_csv(
        os.path.join(OUTPUT_DIR, 'long_results_summary.csv'), index=False, encoding='utf-8-sig')

    hdr = f"{'Rank':>4} {'因子':<22} {'参':<6} {'TopK':>5} {'年化%':>6} {'Sharpe':>7} {'回撤%':>6} {'Univ':>8}"
    print(hdr)
    print("-" * 70)
    for i, (res, _, _) in enumerate(valid):
        s_str = res['sharpe'] if res['sharpe'] is not None else 0
        u_str = f"{res['avg_candidates_2015_2017']:.0f}|{res['avg_candidates_2018_2026']:.0f}"
        print(f"{i+1:>4} {res['factor_name']:<22} {res['param_label']:<6} {res['top_k']:>5} {res['annual_return_pct']:>5.1f}% {s_str:>7} {res['max_drawdown_pct']:>5.1f}% {u_str:>8}")

    print()
    print("生成图表...")
    plot_all(valid, "A股ETF 长窗口因子回测 (2015~2026)", "long_window_all.png")
    print(f"输出目录: {OUTPUT_DIR}")
    print("完成!")


if __name__ == '__main__':
    main()

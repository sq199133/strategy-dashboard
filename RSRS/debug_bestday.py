"""
排查最大单日收益的来源
"""
import sys, os, warnings
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling, run_strategy, DEFAULT_POOL)

N, M, BUY, SELL = 18, 900, 0.7, -1.0
TOP, RB, VW, TV = 1, 42, 70, 0.16

data, panel = build_panel(DEFAULT_POOL, min_rows=200)
df510 = load_etf("510300")
sig, _, _ = compute_rsrs(df510, N, M, BUY, SELL)
sig_dates = df510["date"].values
mom_data = compute_momentum(data, panel)
scale = compute_vol_scaling(df510, panel.index, VW, TV)
positions = run_strategy(data, panel, sig, sig_dates, mom_data, RB, TOP, scale)

daily_ret = panel.pct_change().fillna(0)
strat_ret = (daily_ret * positions.shift(1).fillna(0)).sum(axis=1)

# 找最好和最差的3天
best_days = strat_ret.sort_values(ascending=False).head(3)
worst_days = strat_ret.sort_values().head(3)

print("=== 最佳单日 TOP 3 ===")
for dt, ret in best_days.items():
    pos = positions.shift(1).loc[dt] if dt in positions.index else None
    held_code = None
    held_wt = 0
    if pos is not None:
        for c in pos.index:
            if pos[c] > 0:
                held_code = c
                held_wt = pos[c]
                break
    etf_ret = daily_ret.loc[dt, held_code] if held_code else None
    # 检查数据
    if dt in panel.index:
        prev_dt = panel.index[panel.index.get_loc(dt) - 1] if panel.index.get_loc(dt) > 0 else None
        if prev_dt and held_code:
            p_close = panel.loc[prev_dt, held_code]
            c_close = panel.loc[dt, held_code]
            print(f"\n{dt.date()} 策略={ret*100:.2f}%")
            print(f"  -> 持仓: {held_code} ({DEFAULT_POOL.get(held_code,'?')})  权重={held_wt:.2f}")
            print(f"  -> ETF日涨幅: {etf_ret*100:.2f}%")
            print(f"  -> 前日收盘: {p_close}  今日收盘: {c_close}")
            # 直接从源文件查
            raw_df = load_etf(held_code)
            edf = raw_df.set_index('date')
            if dt in edf.index:
                rec = edf.loc[dt]
                prev = edf.loc[prev_dt] if prev_dt in edf.index else None
                print(f"  -> 源数据: close={rec['close']}")
                if prev is not None:
                    print(f"  -> 前日源数据: close={prev['close']}  real_ret={(rec['close']/prev['close']-1)*100:.2f}%")

print("\n=== 最差单日 TOP 3 ===")
for dt, ret in worst_days.items():
    pos = positions.shift(1).loc[dt] if dt in positions.index else None
    held_code = None
    held_wt = 0
    if pos is not None:
        for c in pos.index:
            if pos[c] > 0:
                held_code = c
                held_wt = pos[c]
                break
    etf_ret = daily_ret.loc[dt, held_code] if held_code else None
    if dt in panel.index:
        prev_dt = panel.index[panel.index.get_loc(dt) - 1] if panel.index.get_loc(dt) > 0 else None
        if prev_dt and held_code:
            p_close = panel.loc[prev_dt, held_code]
            c_close = panel.loc[dt, held_code]
            print(f"\n{dt.date()} 策略={ret*100:.2f}%")
            print(f"  -> 持仓: {held_code} ({DEFAULT_POOL.get(held_code,'?')})  权重={held_wt:.2f}")
            print(f"  -> ETF日涨幅: {etf_ret*100:.2f}%")
            print(f"  -> 前日收盘: {p_close}  今日收盘: {c_close}")
            # 从源数据查
            raw_df = load_etf(held_code)
            edf = raw_df.set_index('date')
            if dt in edf.index:
                rec = edf.loc[dt]
                prev = edf.loc[prev_dt] if prev_dt in edf.index else None
                real_ret = (rec['close'] / prev['close'] - 1) * 100 if prev is not None else 0
                print(f"  -> 源数据 close={rec['close']}  前日close={prev['close'] if prev is not None else 'N/A'}  real_ret={real_ret:.2f}%")

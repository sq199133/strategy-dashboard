"""
RSRS修正对比 - debug版 - 先看数据结构
"""
import sys, os, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, r"D:\QClaw_Trading\RSRS")
from rsrs_final_strategy import (
    load_etf, build_panel, compute_momentum, c63_score,
    compute_vol_scaling, run_strategy, analyze_performance, DEFAULT_POOL, DATA_DIR
)

data, panel = build_panel(DEFAULT_POOL)
print(f"Panel: {len(panel)} rows")

with open(f"{DATA_DIR}\\510300.json","r",encoding="utf-8") as f:
    hs300 = json.load(f)
hs300 = pd.DataFrame(hs300["records"])
hs300["date"] = pd.to_datetime(hs300["date"])
high, low, close = hs300["high"].values, hs300["low"].values, hs300["close"].values
hs300_dates = hs300["date"].values

N, M = 18, 900

# Quick original RSRS
beta = np.full(len(hs300), np.nan)
for i in range(N-1, len(hs300)):
    y = high[i-N+1:i+1]; x = low[i-N+1:i+1]
    if not np.isnan(x).any() and not np.isnan(y).any():
        try: beta[i] = np.linalg.lstsq(np.column_stack([np.ones(N),x]),y,rcond=None)[0][1]
        except: pass

zs = np.full(len(beta), np.nan)
for i in range(M-1, len(beta)):
    v = beta[i-M+1:i+1]; vv=v[~np.isnan(v)]
    if len(vv)>=100:
        mu,sg=np.mean(vv),np.std(vv,ddof=1)
        if sg>0: zs[i]=(beta[i]-mu)/sg

sig = np.zeros(len(zs))
pos=0
for i in range(len(zs)):
    if not np.isnan(zs[i]):
        if zs[i]>0.7: pos=1
        elif zs[i]<-1.0: pos=0
    sig[i]=pos

mom_data = compute_momentum(data, panel)
df510 = load_etf('510300')
vol_scaling = compute_vol_scaling(df510, panel.index)

pos = run_strategy(data, panel, sig, hs300_dates, mom_data, rebalance_days=42, top_n=1, vol_scaling=vol_scaling)
annual_df, total_row, ret, stats = analyze_performance(panel, pos)

print(f"\ntotal_row type: {type(total_row)}")
print(f"total_row keys: {total_row.keys() if isinstance(total_row, dict) else 'not dict'}")
print(f"total_row: {total_row}")
print(f"\nannual_df:")
print(annual_df)

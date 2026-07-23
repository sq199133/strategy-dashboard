"""
RSRS z-score近期走势（用策略真实计算）
"""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, r"D:\QClaw_Trading\RSRS")
from rsrs_final_strategy import load_etf, compute_rsrs

df = load_etf("510300")
sig, zs, _ = compute_rsrs(df, 18, 900, 0.7, -1.0)

# Print latest 30 raw signals
dates = pd.to_datetime(df["date"].values)
print("RSRS raw z-score & signal (2026-06 最近的):")
print("Date       | Z-score | RawSig")
for i in range(max(0, len(dates)-40), len(dates)):
    dt = dates[i]
    z = round(float(zs[i]), 2) if not np.isnan(float(zs[i])) else None
    s = int(sig[i])
    s_str = "LONG" if s==1 else "FLAT"
    if z is not None:
        print(f"{str(dt.date()):<12} {z:+7.2f}   {s_str}")

# z-score趋势从5月11日(买入日)开始
print("\n从5月11日持仓买入以来的走势:")
print("Date       | Z-score | RawSig")
for i in range(len(dates)):
    dt = dates[i]
    if dt >= pd.Timestamp("2026-05-11"):
        z = round(float(zs[i]), 2) if not np.isnan(float(zs[i])) else None
        s = int(sig[i])
        s_str = "LONG" if s==1 else "FLAT"
        if z is not None:
            print(f"{str(dt.date()):<12} {z:+7.2f}   {s_str}")

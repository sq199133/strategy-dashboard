import sys, os, json, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
os.environ["PYTHONIOENCODING"] = "utf-8"

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling, DEFAULT_POOL)

# 加载
data, panel = build_panel(DEFAULT_POOL, min_rows=200)
df510 = load_etf("510300")
scale = compute_vol_scaling(df510, panel.index, 70, 0.16)

# 查几个关键日期的缩放因子
dates = ["2026-05-11", "2026-05-15", "2026-05-25", "2026-06-01",
         "2026-06-08", "2026-06-15", "2026-06-16"]
print("关键日期  仓位缩放  仓位%  说明")
print("-" * 40)
for d in dates:
    dt = pd.Timestamp(d)
    if dt in scale.index:
        v = float(scale.loc[dt])
        print(f"{d}  {v:.2f}      {v*100:.0f}%")

# 波动率序列走势
print("\n=== 2026年波动率缩放走势（关键时点）===")
s2026 = scale[scale.index >= "2026-01-01"]
for i in range(0, len(s2026), 20):
    dt = s2026.index[i]
    v = s2026.iloc[i]
    print(f"  {dt.date()}  {v:.2f}  ({v*100:.0f}%)")

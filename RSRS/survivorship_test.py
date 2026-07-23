"""
验证幸存者偏差：去掉最关键的几只ETF，看策略是否仍然有效
"""
import sys, os, json, warnings
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling, run_strategy, DEFAULT_POOL)

N, M, BUY, SELL = 18, 900, 0.7, -1.0
TOP, RB, VW, TV = 1, 42, 70, 0.16

def run_backtest(pool_dict, label):
    data, panel = build_panel(pool_dict, min_rows=200)
    df510 = load_etf("510300")
    sig, _, _ = compute_rsrs(df510, N, M, BUY, SELL)
    sig_dates = df510["date"].values
    mom_data = compute_momentum(data, panel)
    scale = compute_vol_scaling(df510, panel.index, VW, TV)
    positions = run_strategy(data, panel, sig, sig_dates, mom_data, RB, TOP, scale)
    daily_ret = panel.pct_change().fillna(0)
    ret = (daily_ret * positions.shift(1).fillna(0)).sum(axis=1)
    eq = (1 + ret).cumprod()
    cagr = float(eq.iloc[-1] ** (252 / len(ret)) - 1)
    sharpe = float(np.sqrt(252) * ret.mean() / ret.std()) if ret.std() > 1e-10 else 0
    mdd = float(((eq - eq.cummax()) / eq.cummax()).min())
    wr = float((ret > 0).sum() / len(ret) * 100)
    return cagr, sharpe, mdd, wr, ret, eq

# 原池
base_cagr, base_sp, base_mdd, base_wr, base_ret, base_eq = run_backtest(DEFAULT_POOL, "原池13只")
print(f"{'试验':<20}  {'CAGR%':>8}  {'Sharpe':>7}  {'MDD%':>7}  {'胜率%':>6}")
print(f"{'-'*50}")

results = [("原池 13只", base_cagr, base_sp, base_mdd, base_wr)]

# 1. 去掉创业板50
pool_a = {k:v for k,v in DEFAULT_POOL.items() if k != "159949"}
c,s,m,w,_,_ = run_backtest(pool_a, "去CYB50")
results.append(("去 CYB50", c, s, m, w))

# 2. 去掉TOP3明星 (CYB50, REALEST, METAL)
pool_b = {k:v for k,v in DEFAULT_POOL.items() if k not in ("159949","512200","512400")}
c,s,m,w,_,_ = run_backtest(pool_b, "去TOP3")
results.append(("去 TOP3", c, s, m, w))

# 3. 只看宽基 (去掉行业ETF和商品)
broad = {k:v for k,v in DEFAULT_POOL.items() if k in ("510300","510050","159902","159949","512100")}
c,s,m,w,_,_ = run_backtest(broad, "仅宽基5只")
results.append(("仅宽基5只", c, s, m, w))

# 4. 去掉两个最老的 (510050, 159902) - 历史最长的
pool_c = {k:v for k,v in DEFAULT_POOL.items() if k not in ("510050","159902")}
c,s,m,w,_,_ = run_backtest(pool_c, "去上证50+中小100")
results.append(("去50+中小100", c, s, m, w))

# 5. 交差验证: 只用2010年前就有的品种
legacy = {k:v for k,v in DEFAULT_POOL.items() if k in ("510050","159902","510160","159905","510300")}
c,s,m,w,_,_ = run_backtest(legacy, "仅传统5只")
results.append(("仅传统5只", c, s, m, w))

for name, cagr, sp, mdd, wr in results:
    flag = " [基]" if name == "原池 13只" else ""
    print(f"{name:<20} {cagr*100:>8.1f}% {sp:>7.2f} {mdd*100:>7.1f}% {wr:>6.1f}%{flag}")

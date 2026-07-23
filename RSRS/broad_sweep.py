"""
宽基池参数扫描
"""
import sys, os, json, warnings
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling, run_strategy)

BROAD_POOL = {
    "510050": "SH50", "159902": "ZZSM100", "159915": "CYB",
    "510300": "HS300", "518880": "GOLD", "159949": "CYB50", "512100": "ZZ1000",
}

VW, TV = 70, 0.16

def evaluate(N, M, BUY, SELL, TOP, RB):
    try:
        data, panel = build_panel(BROAD_POOL, min_rows=200)
    except:
        return None
    df = load_etf("510300")
    sig, zs, bt = compute_rsrs(df, N, M, BUY, SELL)
    sig_dates = df["date"].values
    mom_data = compute_momentum(data, panel)
    scale = compute_vol_scaling(df, panel.index, VW, TV)
    positions = run_strategy(data, panel, sig, sig_dates, mom_data, RB, TOP, scale)
    dr = panel.pct_change().fillna(0)
    ret = (dr * positions.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df["date"].iloc[M])
    ret = ret[ret.index >= fs]
    if len(ret) < 20:
        return None
    eq = (1 + ret).cumprod()
    cagr = eq.iloc[-1] ** (252 / len(ret)) - 1
    sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    wr = (ret > 0).sum() / len(ret) * 100
    return {"CAGR": round(cagr*100,1), "Sharpe": round(sp,2), "MDD": round(mdd*100,1), "W%": round(wr,1),
            "N":N,"M":M,"Buy":BUY,"Sell":SELL,"Top":TOP,"RB":RB,"Days":len(ret)}

print("="*72)
print("  宽基池(7只) 参数扫描")
print("="*72)

# 基线
b = evaluate(18, 900, 0.7, -1.0, 1, 42)
print(f"\n  基线: CAGR={b['CAGR']}%  Sharpe={b['Sharpe']}  MDD={b['MDD']}%")

# 1. N 扫描
print(f"\n--- [1] RSRS N (回归窗口) ---")
ns = []
for N in [12,15,18,21,24]:
    r = evaluate(N, 900, 0.7, -1.0, 1, 42)
    if r: ns.append(r); print(f"  N={N:>2}  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")
best_n = max(ns, key=lambda x: x['CAGR'])
print(f"  >> 最佳: N={best_n['N']}")

# 2. 阈值扫描
print(f"\n--- [2] 买入/卖出阈值 (N={best_n['N']}) ---")
ts = []
for buy in [0.5, 0.7, 1.0]:
    for sell in [-0.5, -0.7, -1.0, -1.5]:
        r = evaluate(best_n['N'], 900, buy, sell, 1, 42)
        if r: ts.append(r)
for r in sorted(ts, key=lambda x: -x['CAGR'])[:10]:
    print(f"  buy={r['Buy']:>3.1f} sell={r['Sell']:>+4.1f}  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")
best_t = max(ts, key=lambda x: x['Sharpe'])
print(f"  >> 最佳夏普: buy={best_t['Buy']} sell={best_t['Sell']}")

# 3. TopN + RB
print(f"\n--- [3] TopN + 调仓周期 ---")
ps = []
for top in [1,2]:
    for rb in [21,42,63,84]:
        r = evaluate(best_n['N'], 900, best_t['Buy'], best_t['Sell'], top, rb)
        if r: ps.append(r); print(f"  Top{top} RB={rb:>2}  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")
best_p = max(ps, key=lambda x: x['Sharpe'])

# 4. M 扫描
print(f"\n--- [4] M (z-score窗口) ---")
ms = []
for M in [600, 900, 1200]:
    r = evaluate(best_n['N'], M, best_t['Buy'], best_t['Sell'], best_p['Top'], best_p['RB'])
    if r: ms.append(r); print(f"  M={M:>4}  CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# 5. 最终确认: 最好的组合再拿基线M跑一次
all_r = ns + ts + ps + ms
by_sharpe = sorted(all_r, key=lambda x: -x['Sharpe'])
by_cagr = sorted(all_r, key=lambda x: -x['CAGR'])

print(f"\n{'='*72}")
best_s = by_sharpe[0]
best_c = by_cagr[0]
print(f"  夏普最优: N={best_s['N']} M={best_s['M']} buy={best_s['Buy']} sell={best_s['Sell']} Top{best_s['Top']} RB={best_s['RB']}")
print(f"    CAGR={best_s['CAGR']}%  Sharpe={best_s['Sharpe']}  MDD={best_s['MDD']}%")
print(f"  收益最优: N={best_c['N']} M={best_c['M']} buy={best_c['Buy']} sell={best_c['Sell']} Top{best_c['Top']} RB={best_c['RB']}")
print(f"    CAGR={best_c['CAGR']}%  Sharpe={best_c['Sharpe']}  MDD={best_c['MDD']}%")
print(f"{'='*72}")

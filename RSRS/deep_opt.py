"""
宽基池深度优化：找更多杠杆
"""
import sys, os, json, warnings
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore')

from rsrs_final_strategy import (DATA_DIR, load_etf, build_panel,
                                 compute_rsrs, compute_momentum, c63_score,
                                 compute_vol_scaling, run_strategy)

VW, TV = 70, 0.16

def rsrs_strategy(pool, N=18, M=1200, buy=0.7, sell=-1.0, top=1, rb=42, vw=70, tv=0.16):
    try:
        data, panel = build_panel(pool, min_rows=200)
    except:
        return None
    df = load_etf("510300")
    sig, zs, bt = compute_rsrs(df, N, M, buy, sell)
    sd = df["date"].values
    mom = compute_momentum(data, panel)
    sc = compute_vol_scaling(df, panel.index, vw, tv)
    pos = run_strategy(data, panel, sig, sd, mom, rb, top, sc)
    dr = panel.pct_change().fillna(0)
    ret = (dr * pos.shift(1).fillna(0)).sum(axis=1)
    fs = pd.to_datetime(df["date"].iloc[M])
    ret = ret[ret.index >= fs]
    if len(ret) < 20: return None
    eq = (1 + ret).cumprod()
    cagr = eq.iloc[-1] ** (252 / len(ret)) - 1
    sp = np.sqrt(252) * ret.mean() / ret.std() if ret.std() > 1e-10 else 0
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    wr = (ret > 0).sum() / len(ret) * 100
    return {"CAGR": round(cagr*100,1), "Sharpe": round(sp,2), "MDD": round(mdd*100,1), "W%": round(wr,1),
            "N":N,"M":M,"Buy":buy,"Sell":sell,"Top":top,"RB":rb,"VW":vw,"TV":tv,"Days":len(ret)}

CORE = {
    "510050": "SH50", "159902": "ZZSM100", "159915": "CYB",
    "510300": "HS300", "518880": "GOLD", "159949": "CYB50", "512100": "ZZ1000",
}

print("=" * 70)
print("  目标：宽基池 CAGR 20%+")  
print("=" * 70)

# 当前最优
b = rsrs_strategy(CORE, 18, 1200, 0.7, -1.0, 1, 42, 70, 0.16)
print(f"\n  当前最优: CAGR={b['CAGR']}%  Sharpe={b['Sharpe']}  MDD={b['MDD']}%")

# ── 杠杆1: 扩池子 ──
print(f"\n\n── [杠杆1] 扩充宽基池 ──")
extra = {
    "159901": "SZ100",    # 深证100 - 19年
    "510900": "HSHARE",   # H股ETF - 13年
    "513600": "HSI",      # 恒指ETF - 11年
    "513030": "DAX30",    # 德国30ETF - 11年
}
for code, name in extra.items():
    p = {**CORE, code: name}
    r = rsrs_strategy(p, 18, 1200, 0.7, -1.0, 1, 42, 70, 0.16)
    if r:
        ds = r['CAGR'] - 13.3
        print(f"  +{code} {name:<8}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%  增量={ds:+.1f}%")

# 最佳扩展池
BIG_POOL = {**CORE, "159901": "SZ100", "510900": "HSHARE"}
r_big = rsrs_strategy(BIG_POOL, 18, 1200, 0.7, -1.0, 1, 42, 70, 0.16)
print(f"\n  扩展池(9只)当前: CAGR={r_big['CAGR']}%  Sharpe={r_big['Sharpe']}  MDD={r_big['MDD']}%")

# ── 杠杆2: C63动量窗口 ──
print(f"\n\n── [杠杆2] 动量窗口调优 ──")
# 需替换compute_momentum里的C63窗口，先看现有的c63_score

# 看看不同M的效果（在9只池上）
for M in [600, 900, 1200, 1500]:
    r = rsrs_strategy(BIG_POOL, 18, M, 0.7, -1.0, 1, 42, 70, 0.16)
    if r:
        print(f"  M={M:>4}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 杠杆3: 波动率缩放参数 ──
print(f"\n\n── [杠杆3] 波动率参数 ──")
for tv in [0.12, 0.16, 0.20, 0.25]:
    r = rsrs_strategy(BIG_POOL, 18, 1200, 0.7, -1.0, 1, 42, 70, tv)
    if r:
        print(f"  TV={tv:.2f}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")
for vw in [42, 63, 70, 126]:
    r = rsrs_strategy(BIG_POOL, 18, 1200, 0.7, -1.0, 1, 42, vw, 0.16)
    if r:
        print(f"  VW={vw:>3}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 杠杆4: 买入/卖出阈值（扩展池）──
print(f"\n\n── [杠杆4] 阈值调优（扩展9只池） ──")
combos = [
    (0.7, -1.0), (0.7, -1.5), (1.0, -1.0), (0.5, -1.0), (0.7, -2.0), (0.5, -1.5), (1.0, -1.5)
]
for buy, sell in combos:
    r = rsrs_strategy(BIG_POOL, 18, 1200, buy, sell, 1, 42, 70, 0.16)
    if r:
        print(f"  buy={buy:>3.1f} sell={sell:>+4.1f}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# ── 杠杆5: 调仓频率 ──
print(f"\n\n── [杠杆5] 调仓频率 ──")
for rb in [21, 42, 63, 84]:
    r = rsrs_strategy(BIG_POOL, 18, 1200, 0.7, -1.0, 1, rb, 70, 0.16)
    if r:
        print(f"  RB={rb:>2}: CAGR={r['CAGR']:>5.1f}%  Sharpe={r['Sharpe']:.2f}  MDD={r['MDD']:>5.1f}%")

# 汇总
print(f"\n\n{'='*70}")
print(f"  优化汇总:")
print(f"  7只基础池:    {b['CAGR']}% / {b['Sharpe']} / {b['MDD']}%")
print(f"  9只扩展池:    {r_big['CAGR']}% / {r_big['Sharpe']} / {r_big['MDD']}%")
print(f"{'='*70}")
